import json
import re
import unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from thefuzz import fuzz
from models import Specimen, AnalyteRange, Analyte

FUZZY_MATCH_RATIO = 80

# Greek letters are normalized to their latin spellings BEFORE unicode NFKD,
# because NFKD keeps them as separate codepoints (α is not decomposable).
# Mapping only the letters that actually appear in clinical analyte names.
_GREEK_TO_LATIN = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "κ": "kappa", "λ": "lambda", "μ": "mu", "π": "pi", "σ": "sigma",
    "τ": "tau", "ω": "omega",
}

# Tokens that must match between two names if present on either side.
# Roman numerals disambiguate things like coagulation factors (V vs VI vs IX).
_ROMAN_TOKENS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
    "xiii",
}

# Qualifiers that flip the meaning of an analyte; e.g. "testosterone, free"
# must never match "testosterone" alone or "testosterone, total".
_QUALIFIER_TOKENS = {
    "male", "female", "free", "total", "ionized", "cardiac", "peak", "trough",
    "therapeutic", "toxic", "upright", "supine", "unconjugated", "conjugated",
    "fasting", "postprandial",
}


def _normalize_name(name: str) -> str:
    """Canonicalize an analyte/LOINC component name for comparison.

    Folds Greek letters to their latin spelling, strips diacritics via NFKD,
    lowercases, and collapses every non-alphanumeric run to a single space.
    Meant to make variants like ``"α2-Macroglobulin"`` and
    ``"Alpha-2-Macroglobulin"`` compare equal.
    """
    s = name
    for greek, latin in _GREEK_TO_LATIN.items():
        s = s.replace(greek, latin)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _number_set(tokens: set[str]) -> set[str]:
    """Return the set of numeric runs found inside the tokens.

    ``"b12"`` contributes ``"12"``; ``"17alpha"`` contributes ``"17"``.
    Used as a structural fingerprint — two names with different number sets
    are almost always different analytes (B1 vs B12, T3 vs T4, 25-OH vs 1,25-OH).
    """
    out: set[str] = set()
    for t in tokens:
        out.update(re.findall(r"\d+", t))
    return out


def _structural_match(a_norm: str, b_norm: str) -> bool:
    """Reject fuzzy matches whose *structure* disagrees.

    Even a 95%-similar name pair is rejected if one carries a roman numeral,
    arabic number or meaning-flipping qualifier that the other does not. This
    is what stops ``coagulation factor V`` from matching ``coagulation factor VI``
    and ``testosterone, female`` from matching ``testosterone.free``.
    """
    a_tokens = set(a_norm.split())
    b_tokens = set(b_norm.split())
    if (a_tokens & _ROMAN_TOKENS) != (b_tokens & _ROMAN_TOKENS):
        return False
    if _number_set(a_tokens) != _number_set(b_tokens):
        return False
    if (a_tokens & _QUALIFIER_TOKENS) != (b_tokens & _QUALIFIER_TOKENS):
        return False
    return True


# TODO: AnalyteGroups
# TODO: ranges as separate entities


specimens: dict[str, Specimen] = {}  # id, Specimen
no_loinc_count = 0
analyte_count = 0

# Collected parsing problems, rendered as a structured report at the end of
# the run. Each bucket holds items of a stable shape so the report loop can
# stay dumb.
issues: dict[str, list] = {
    "skipped_see_references": [],       # list[str]  (raw cell text)
    "missing_loinc": [],                # list[str]  (analyte name)
    "ambiguous_exact_matches": [],      # list[tuple[str, list[str]]]
    "fuzzy_matches": [],                # list[tuple[str, str, int, str]]
    "pinned_matches": [],               # list[tuple[str, str]]   (analyte, loinc)
    "pinned_no_match": [],              # list[str]               (analyte)
    "missing_factors": [],              # list[str]  (analyte name)
    "unparseable_factors": [],          # list[tuple[str, str]]
    "unparseable_ranges": [],           # list[tuple[str, str]]
}


def _load_manual_mapping(path: Path) -> dict[str, str | None]:
    """Load analyte-name -> LOINC overrides from ``manual_loinc_mapping.json``.

    Keys starting with ``_`` are ignored, so the file can carry inline
    documentation (``_comment``) without polluting the mapping. Missing file
    returns an empty mapping rather than raising; the pipeline should still
    run before anyone has written the first override.
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def parse_conversion_factor(raw: str) -> float | None:
    """Parse the conversion-factor cell into a numeric factor.

    Returns ``None`` when the cell is blank or cannot be parsed as a number —
    some AccessMedicine rows (e.g. % <-> fraction) intentionally ship
    without a numeric factor.
    """
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        # Caller is responsible for surfacing this via the issue tracker,
        # because only the caller knows which analyte the raw value belongs to.
        return None


def parse_interval(range_str: str) -> AnalyteRange:
    """Parses a string representing an interval and returns an AnalyteRange.

    The given range string can contain a "from - to" interval, or a "less than" or
    "greater than" expression:
    - 40-90
    - <3.45
    - >200

    If it cant be determined, it returns an AnalyteRange with a string representation.
    """
    # parse lower and upper limits
    lower_limit = None
    upper_limit = None
    try:
        if "-" in range_str:
            lower_limit, upper_limit = range_str.split("-")
            lower_limit = float(lower_limit.strip())
            upper_limit = float(upper_limit.strip())
        elif "<" in range_str:
            upper_limit = float(range_str.strip("<"))
            lower_limit = None
        elif ">" in range_str:
            lower_limit = float(range_str.strip(">"))
            upper_limit = None
    except ValueError:
        # Caller is responsible for surfacing this via the issue tracker.
        return AnalyteRange(text=range_str)
    return AnalyteRange(lower_limit=lower_limit, upper_limit=upper_limit)


def parse_lab_values(
    loinc_file_path: str | Path,
    html_file_path: str | Path,
    manual_mapping: dict[str, str | None] | None = None,
) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file.

    ``manual_mapping`` lets callers pin specific analyte names to a LOINC
    (string) or to "no match, don't try" (None). Entries there always win
    over the exact and fuzzy matchers below.
    """
    analytes = []
    group_name = ""
    global specimens, no_loinc_count, analyte_count, issues
    manual_mapping = manual_mapping or {}

    # ------ CSV LOINC file ------
    # open loinc csv file and read it
    loinc_data: dict[str, dict[str, str]] = {}
    with Path.open(loinc_file_path, "r", encoding="utf-8") as file:
        # parse LOINC data
        for line_number, line in enumerate(file.readlines()):
            if line_number == 0:
                # parse header row
                header_row = line.strip().split(",")
                header_row = [header.strip('"') for header in header_row]
                if header_row[0] != "LOINC_NUM":
                    raise ValueError("Invalid LOINC CSV file")
                continue
            if line.strip():  # skip empty lines
                fields = line.strip().split(",")
                fields = [field.strip('"') for field in fields]
                # if there are more than 5 whitespaces in the text,
                # we can assume it is verbose text, not an analyte name.
                if len(fields[1].split(" ")) > 5:
                    continue

                if len(fields) >= len(header_row):
                    # Create a dictionary with all columns
                    row_data = {}
                    for i, header in enumerate(header_row):
                        if i < len(fields):
                            # only keep some rows to save memory
                            if header in ["LOINC_NUM", "COMPONENT"]:
                                row_data[header] = fields[i]
                    loinc_data[fields[0]] = row_data  # Use LOINC_NUM as key

    # Pre-compute the normalized form of every LOINC COMPONENT once, so the
    # per-analyte match below can do both an O(1) exact lookup and a single
    # fuzzy pass over already-normalized strings.
    loinc_by_norm: dict[str, list[str]] = {}       # norm -> [loinc_num, ...]
    loinc_norm_by_num: dict[str, str] = {}         # loinc_num -> norm
    for loinc_num, data in loinc_data.items():
        norm = _normalize_name(data["COMPONENT"])
        if not norm:
            continue
        loinc_by_norm.setdefault(norm, []).append(loinc_num)
        loinc_norm_by_num[loinc_num] = norm

    with open(html_file_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

        # Find the table (assuming it's the main table in the document)
        table = soup.find("table")
        if not table:
            raise ValueError("No table found in HTML file")

        rows = table.find_all("tr")

        # Skip header row
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])

            reference_range_is_age_dependent = False
            cell0 = cells[0]
            # Skip lines with (see...) references
            content = cell0.get_text()
            if re.match(r".*\(.*[sS]ee .*\)", str(content)):
                issues["skipped_see_references"].append(str(content).strip())
                continue

            # Find all sup elements and process them
            for sup in cell0.find_all("sup"):
                sup_content = sup.get_text().strip()
                if sup_content == "b":
                    reference_range_is_age_dependent = True
                if sup_content in ["a", "b", "a,b"]:
                    # next_sibling = sup.find_next_sibling()
                    # Remove the sup element and any immediately following comma
                    next_node = sup.next_sibling
                    if isinstance(
                        next_node, NavigableString
                    ) and next_node.lstrip().startswith(","):
                        # Komma entfernen
                        sup.next_sibling.replace_with(next_node.lstrip()[1:])
                    sup.decompose()
                else:
                    # find all <a> tags and  replace it with their get_text()
                    for a in sup.find_all("a"):
                        a.replace_with(a.get_text())
                    sup.replace_with(sup.get_text())
            for a in cell0.find_all("a"):
                a.replace_with(a.get_text())
                print(f"Replaced link with text: '{a.get_text()}'")

            # Clean up any remaining right whitespace
            name = cell0.get_text().rstrip()

            if len(cells) < 7 or cells[1].get_text() == "":
                group_name = name
                print(f"Found new group for next analytes: '{group_name}'")
                continue
            # Check if this is a subtype (starts with spaces)
            if name.startswith(" ") or name.startswith(" ") or name.startswith("\t"):
                # This is a subtype, prepend with current header
                subtype_name = name.strip()
                full_name = f"{group_name}, {subtype_name}"
            else:
                full_name = name

            print(" ✅ ", full_name)
            analyte_count += 1

            analyte_specimens: list[Specimen] = []
            specimen_string = cells[1].get_text().strip()
            specimen_string = specimen_string.replace(", 24 h", " (24 h)").strip()
            for specimen_name in re.split(r",| or ", specimen_string):
                # Ensure the specimen name is lowercase and replace spaces with underscores
                specimen_id = (
                    specimen_name.strip()
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                )
                if specimen_id:
                    if specimen_id not in specimens:
                        specimens[specimen_id] = Specimen(
                            id=specimen_id, name=specimen_name.strip().capitalize()
                        )
                    analyte_specimens.append(specimens[specimen_id])
            if not analyte_specimens:
                raise ValueError(f"No specimens found for analyte: '{full_name}'")
            traditional_range_raw = cells[2].get_text().strip()
            si_range_raw = cells[5].get_text().strip()
            raw_factor = cells[4].get_text()

            traditional_range = parse_interval(traditional_range_raw)
            si_range = parse_interval(si_range_raw)
            factor = parse_conversion_factor(raw_factor)

            if factor is None:
                if raw_factor.strip():
                    issues["unparseable_factors"].append((full_name, raw_factor.strip()))
                else:
                    issues["missing_factors"].append(full_name)
            if traditional_range.text:
                issues["unparseable_ranges"].append((full_name, traditional_range_raw))
            if si_range.text:
                issues["unparseable_ranges"].append((full_name, si_range_raw))

            analyte = Analyte(
                name=full_name,
                specimen=analyte_specimens,
                traditional_reference_interval=traditional_range,
                traditional_units=cells[3].get_text().strip(),
                conversion_factor=factor,
                si_reference_interval=si_range,
                si_units=cells[6].get_text().strip(),
                reference_range_is_age_dependent=reference_range_is_age_dependent,
            )
            # ---- LOINC matching ----
            # Step 0: manual override. If the operator has pinned this
            # analyte in manual_loinc_mapping.json, obey it unconditionally
            # (either a forced LOINC, or a deliberate "no match").
            # A specimen-qualified key ``name@specimen`` wins over the bare
            # ``name`` — needed when the same analyte name appears in the
            # source with different specimens (e.g. Osmolality in serum vs urine).
            # Step 1: normalized exact match (O(1)).
            # Step 2: fuzzy match over all LOINC components, but only among
            # candidates that pass the structural guards. We collect ALL
            # qualifying candidates and take the highest-scoring one, instead
            # of the old "first-over-threshold-wins" which lumped coagulation
            # factors V/VI/VII/IX/X/XI/XII all onto the same LOINC.
            specimen_id = analyte_specimens[0].id if analyte_specimens else ""
            mapping_key = None
            if f"{analyte.name}@{specimen_id}" in manual_mapping:
                mapping_key = f"{analyte.name}@{specimen_id}"
            elif analyte.name in manual_mapping:
                mapping_key = analyte.name
            if mapping_key is not None:
                pinned = manual_mapping[mapping_key]
                if pinned is None:
                    issues["pinned_no_match"].append(mapping_key)
                else:
                    analyte.loinc_num = pinned
                    issues["pinned_matches"].append((mapping_key, pinned))
                    if pinned not in loinc_data:
                        print(
                            f"⚠️  Manual mapping pins {analyte.name!r} to "
                            f"{pinned}, which is not in the LOINC CSV."
                        )
                analytes.append(analyte)
                if not analyte.loinc_num:
                    no_loinc_count += 1
                continue

            analyte_norm = _normalize_name(analyte.name)

            if analyte_norm in loinc_by_norm:
                exact_hits = loinc_by_norm[analyte_norm]
                # LOINC frequently has multiple components with the same name
                # but different specimen/method (e.g. 58 "Sodium" entries).
                # Keep the legacy behaviour — take the first in file order —
                # but log the ambiguity so a reviewer can pick the right one
                # by hand (ideally by also consulting SYSTEM/METHOD_TYP).
                analyte.loinc_num = exact_hits[0]
                if len(exact_hits) > 1:
                    issues["ambiguous_exact_matches"].append(
                        (analyte.name, exact_hits)
                    )
            else:
                best: tuple[int, str, str] | None = None  # (ratio, loinc, component)
                for loinc_num, data in loinc_data.items():
                    cand_norm = loinc_norm_by_num.get(loinc_num)
                    if not cand_norm:
                        continue
                    ratio = fuzz.ratio(cand_norm, analyte_norm)
                    if ratio <= FUZZY_MATCH_RATIO:
                        continue
                    if not _structural_match(analyte_norm, cand_norm):
                        continue
                    if best is None or ratio > best[0]:
                        best = (ratio, loinc_num, data["COMPONENT"])
                if best:
                    ratio, loinc_num, component = best
                    analyte.loinc_num = loinc_num
                    issues["fuzzy_matches"].append(
                        (analyte.name, component, ratio, loinc_num)
                    )

            if not analyte.loinc_num:
                no_loinc_count += 1
                issues["missing_loinc"].append(analyte.name)

            analytes.append(analyte)

    return analytes


if __name__ == "__main__":
    # Example usage
    # get current path
    current_path = Path(__file__).parent.resolve()
    manual_mapping = _load_manual_mapping(
        current_path / "manual_loinc_mapping.json"
    )
    analytes = parse_lab_values(
        current_path / "Loinc.csv",
        current_path / "Clinical Laboratory Reference Values.html",
        manual_mapping=manual_mapping,
    )

    target_path = current_path.parent / "src" / "labunits" / "data"
    with Path.open(target_path / "analytes.json", "w", encoding="utf-8") as file:
        json.dump(
            {a.loinc_num: a.to_json() for a in analytes if a.loinc_num},
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # Problem report — anything a human may want to investigate / fix
    # ------------------------------------------------------------------
    def _print_section(title: str, items: list, render) -> None:
        if not items:
            return
        print(f"\n{title} ({len(items)}):")
        for item in items:
            print(f"  {render(item)}")

    print()
    print("=" * 72)
    print("PROBLEM REPORT")
    print("=" * 72)

    _print_section(
        "Rows skipped via '(see …)' cross-reference",
        issues["skipped_see_references"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Manually pinned LOINCs (from manual_loinc_mapping.json)",
        issues["pinned_matches"],
        lambda t: f"- {t[0]}  ->  {t[1]}",
    )
    _print_section(
        "Manually unpinned — no LOINC on purpose "
        "(from manual_loinc_mapping.json)",
        issues["pinned_no_match"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Analytes with no LOINC match (dropped from analytes.json)",
        issues["missing_loinc"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Ambiguous exact matches — multiple LOINCs share the normalized name",
        issues["ambiguous_exact_matches"],
        lambda t: f"- {t[0]}: {', '.join(t[1])}",
    )
    _print_section(
        "Fuzzy LOINC matches — verify manually",
        sorted(issues["fuzzy_matches"], key=lambda t: t[2]),  # lowest score first
        lambda t: f"[{t[2]}%] {t[0]!r}  ->  {t[3]} ({t[1]!r})",
    )
    _print_section(
        "Analytes without numeric conversion factor "
        "(shipped as null — callers get a clear ValueError)",
        issues["missing_factors"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Unparseable conversion-factor cells",
        issues["unparseable_factors"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "Unparseable reference-range cells (stored as .text)",
        issues["unparseable_ranges"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )

    print()
    print("=" * 72)
    print(
        f"Summary: {analyte_count} analytes parsed, "
        f"{analyte_count - no_loinc_count} with LOINC, "
        f"{no_loinc_count} without."
    )
    print(f"Specimens: {len(specimens)}")
    print("=" * 72)
