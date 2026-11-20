import csv
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
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "π": "pi",
    "σ": "sigma",
    "τ": "tau",
    "ω": "omega",
}

# Tokens that must match between two names if present on either side.
# Roman numerals disambiguate things like coagulation factors (V vs VI vs IX).
_ROMAN_TOKENS = {
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
    "xiii",
}

# Qualifiers that flip the meaning of an analyte; e.g. "testosterone, free"
# must never match "testosterone" alone or "testosterone, total", and an
# antigen ("Ag") or antibody ("Ab") term is not the analyte itself.
_QUALIFIER_TOKENS = {
    "male",
    "female",
    "free",
    "total",
    "ionized",
    "cardiac",
    "peak",
    "trough",
    "therapeutic",
    "toxic",
    "upright",
    "supine",
    "unconjugated",
    "conjugated",
    "fasting",
    "postprandial",
    "ag",
    "ab",
}

# Specimen id (as produced by this parser) -> LOINC SYSTEM values that
# describe the same material. A LOINC whose SYSTEM is not in the union of
# the analyte's specimens is never a valid match, no matter how well the
# COMPONENT name fits ("Magnesium" in stool is not serum magnesium).
_SPECIMEN_SYSTEMS = {
    "serum": {"Ser", "Ser/Plas", "Ser/Plas/Bld"},
    "plasma": {"Plas", "Ser/Plas", "Ser/Plas/Bld", "PPP"},
    "whole_blood": {"Bld", "Ser/Plas/Bld"},
    "venous_blood": {"BldV", "Bld"},
    "arterial_blood": {"BldA", "Bld"},
    "red_blood_cells": {"RBC"},
    "urine": {"Urine"},
    "urine_24_h": {"Urine"},
    "csf": {"CSF"},
    "stool": {"Stool"},
}

# Unit (as printed in the source) -> LOINC PROPERTY values that can carry
# such a unit. Mass per volume is MCnc, moles per volume SCnc, enzyme
# activity CCnc, … Used for the traditional unit (eligibility filter) and
# for the SI unit (finding the SI-side LOINC term).
# Unknown units yield ``None`` (= no property filter) and are reported.
_UNIT_PROPERTIES: list[tuple[re.Pattern, set[str]]] = [
    (re.compile(r"^(m|μ|n|p)?(mol|Eq)/(L|dL|mL)$"), {"SCnc"}),
    (re.compile(r"^(m|μ|n|p)?g/(L|dL|mL)$"), {"MCnc"}),
    (re.compile(r"^(m|μ)?g/24 h$"), {"MRat"}),
    (re.compile(r"^(m|μ|n)?(mol|Eq)/(24 h|day)$"), {"SRat"}),
    (re.compile(r"^U/L$"), {"CCnc"}),
    (re.compile(r"^(μ|n)?Kat/L$"), {"CCnc"}),
    # "U/mL" is an enzyme activity or the arbitrary unit of a tumour marker.
    (re.compile(r"^(m|μ|k)?I?U/(L|mL)$"), {"ACnc", "CCnc"}),
    (re.compile(r"^I?U/(24 h|day)$"), {"ARat"}),
    (
        re.compile(r"^(%|Fraction)"),
        {"MFr", "NFr", "VFr", "SFr", "CFr", "RelTime", "RelCCnc", "RelACnc", "RelMCnc"},
    ),
    (re.compile(r"^(10\d+ )?(μL|L)−1$"), {"NCnc"}),
    (re.compile(r"^(μm3|fL)$"), {"EntVol", "EntMeanVol"}),
    (re.compile(r"^s$"), {"Time"}),
    (re.compile(r"^mm Hg$"), {"PPres"}),
    (re.compile(r"^mm/h$"), {"Vel", "Sedimentation Rate"}),
    (re.compile(r"^nmol BCE/L$"), {"SCnc"}),
    (re.compile(r"^nmol/mmol creatinine$"), {"SRto"}),
    (re.compile(r"^ng/(mL/h|\(mL h\))$"), {"CCnc"}),
    (re.compile(r"^(mOsm|mmol)/kg"), {"Osmol"}),
    (re.compile(r"^U/g of Hb$"), {"CCnt"}),
]


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


# UCUM mass / amount-of-substance units the molar-mass check understands:
# prefix -> factor to the base unit, denominator -> factor to "per litre".
_PREFIX = {"": 1.0, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
_PER = {"L": 1.0, "dL": 10.0, "mL": 1000.0, "(24.h)": 1.0}
_MASS_UNIT = re.compile(r"^(m|u|n|p)?g/(L|dL|mL|\(24\.h\))$")
_MOLE_UNIT = re.compile(r"^(m|u|n|p|f)?mol/(L|dL|mL|\(24\.h\))$")


def _properties_for_unit(unit: str) -> set[str] | None:
    """Return the LOINC PROPERTY values compatible with a traditional unit."""
    for pattern, props in _UNIT_PROPERTIES:
        if pattern.match(unit):
            return props
    return None


def _rank_key(row: dict[str, str]) -> tuple:
    """Sort key preferring commonly used, method-agnostic LOINC terms.

    ``COMMON_TEST_RANK`` is LOINC's own usage ranking (1 = most common,
    0 = unranked). Among equally ranked terms a term without METHOD_TYP is
    the generic one and wins.
    """
    rank = int(row["COMMON_TEST_RANK"] or 0)
    return (rank == 0, rank, row["METHOD_TYP"] != "", row["LOINC_NUM"])


def _load_loinc(path: str | Path) -> dict[str, dict[str, str]]:
    """Load the LOINC table, keeping only quantitative, active result terms.

    Order-entry terms (``LABORDERS.*``), ordinal/nominal terms and
    deprecated terms can never be the right key for a numeric conversion,
    so they are dropped here once instead of being filtered per analyte.
    """
    keep = (
        "LOINC_NUM",
        "COMPONENT",
        "PROPERTY",
        "TIME_ASPCT",
        "SYSTEM",
        "METHOD_TYP",
        "COMMON_TEST_RANK",
    )
    loinc: dict[str, dict[str, str]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or reader.fieldnames[0] != "LOINC_NUM":
            raise ValueError("Invalid LOINC CSV file")
        for row in reader:
            if row["SCALE_TYP"] != "Qn" or row["STATUS"] != "ACTIVE":
                continue
            if row["CLASS"].startswith("LABORDERS"):
                continue
            loinc[row["LOINC_NUM"]] = {k: row[k] for k in keep}
    return loinc


def _sibling_key(row: dict[str, str]) -> tuple[str, str, str]:
    """What identifies a LOINC term apart from its PROPERTY and method."""
    return (row["COMPONENT"], row["SYSTEM"], row["TIME_ASPCT"])


def _find_si_loinc(
    loinc_num: str,
    si_props: set[str],
    loinc_data: dict[str, dict[str, str]],
    siblings: dict[tuple, list[str]],
) -> str | None:
    """Return the LOINC term that carries this analyte in its SI unit.

    LOINC has one term per PROPERTY: serum creatinine in mg/dL is
    ``2160-0`` (mass concentration), in µmol/L it is ``14682-9`` (substance
    concentration). If the matched term's own PROPERTY already fits the SI
    unit (g/dL -> g/L), that term covers both units and is returned.
    Otherwise the sibling term — same component, system and time aspect —
    with a fitting PROPERTY is looked up; ``None`` if LOINC has none. A
    sibling of the same method wins; only if there is none, a term of
    another method is taken (sirolimus in nmol/L exists only as an
    immunoassay term), which the caller reports.
    """
    row = loinc_data.get(loinc_num)
    if row is None:
        return None
    if row["PROPERTY"] in si_props:
        return loinc_num
    candidates = [
        n
        for n in siblings.get(_sibling_key(row), [])
        if loinc_data[n]["PROPERTY"] in si_props
    ]
    same_method = [
        n for n in candidates if loinc_data[n]["METHOD_TYP"] == row["METHOD_TYP"]
    ]
    return min(
        same_method or candidates,
        key=lambda n: _rank_key(loinc_data[n]),
        default=None,
    )


def _to_ucum(unit: str, loinc_property: str | None, ucum_units: dict[str, str]) -> str:
    """Translate a source unit string to UCUM, ``""`` if it is not mapped.

    ``unit@PROPERTY`` wins over the bare unit (see ``ucum_units.json``).
    """
    return ucum_units.get(f"{unit}@{loinc_property}") or ucum_units.get(unit, "")


# TODO: AnalyteGroups


specimens: dict[str, Specimen] = {}  # id, Specimen
no_loinc_count = 0
analyte_count = 0

# Collected parsing problems, rendered as a structured report at the end of
# the run. Each bucket holds items of a stable shape so the report loop can
# stay dumb.
issues: dict[str, list] = {
    "skipped_see_references": [],  # list[str]  (raw cell text)
    "missing_loinc": [],  # list[str]  (analyte name)
    "ambiguous_exact_matches": [],  # list[tuple[str, str, list[str]]]
    "fuzzy_matches": [],  # list[tuple[str, str, int, str]]
    "pinned_matches": [],  # list[tuple[str, str]]   (analyte, loinc)
    "pinned_no_match": [],  # list[str]               (analyte)
    "pinned_ineligible": [],  # list[tuple[str, str, str]] (analyte, loinc, why)
    "unknown_units": [],  # list[tuple[str, str]]   (analyte, unit)
    "unknown_si_units": [],  # list[tuple[str, str]]   (analyte, unit)
    "missing_si_loinc": [],  # list[tuple[str, str, str]] (analyte, loinc, unit)
    "other_method_si_loinc": [],  # list[tuple[str, str, str]] (analyte, si loinc, method)
    "molar_mass_mismatch": [],  # list[tuple[str, float, float, float]]
    "missing_molar_mass": [],  # list[str]  (analyte name)
    "missing_ucum": [],  # list[tuple[str, str]]   (analyte, unit)
    "missing_factors": [],  # list[str]  (analyte name)
    "unparseable_factors": [],  # list[tuple[str, str]]
    "unparseable_ranges": [],  # list[tuple[str, str]]
    "inconsistent_factors": [],  # list[tuple[str, str, float, str]]
    "corrected_rows": [],  # list[tuple[str, dict]]  (analyte, fields)
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


def _load_source_corrections(path: Path) -> dict[str, dict]:
    """Load per-analyte field overrides from ``source_corrections.json``.

    Same conventions as :func:`_load_manual_mapping`: ``_``-prefixed keys
    are documentation, a missing file means "no corrections".
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v["set"] for k, v in raw.items() if not k.startswith("_")}


def _load_analyte_names(path: Path) -> dict[str, str]:
    """Load the source-name -> canonical-name table from ``analyte_names.json``.

    ``_``-prefixed keys are documentation.
    """
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _load_molar_masses(path: Path) -> dict[str, float]:
    """Load analyte name -> molar mass (g/mol) from ``molar_masses.json``.

    ``_``-prefixed keys are documentation.
    """
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _load_ucum_units(path: Path) -> dict[str, str]:
    """Load the source-unit -> UCUM table from ``ucum_units.json``.

    ``_``-prefixed keys are documentation.
    """
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


_NUMBER = r"\d+(?:\.\d+)?"
_INTERVAL_PATTERNS: list[tuple[re.Pattern, tuple[int | None, int | None]]] = [
    # pattern, (group of the lower limit, group of the upper limit)
    (re.compile(rf"({_NUMBER})\s*-\s*({_NUMBER})"), (1, 2)),
    (re.compile(rf"[<≤]\s*({_NUMBER})"), (None, 1)),
    (re.compile(rf"[>≥]\s*({_NUMBER})"), (1, None)),
    (re.compile(rf"({_NUMBER})"), (1, 1)),
]


def parse_interval(range_str: str) -> AnalyteRange:
    """Parses a string representing an interval and returns an AnalyteRange.

    The given range string can contain a "from - to" interval, a "less than"
    or "greater than" expression, or a single value:
    - 40-90
    - <3.45, ≤3.45
    - >200, ≥200
    - 56 (lower and upper limit are both 56)

    Anything else comes back as an AnalyteRange carrying the raw string in
    ``text`` and no limits, so the caller can report it — a cell is never
    dropped silently.
    """
    cell = range_str.strip()
    for pattern, (lower, upper) in _INTERVAL_PATTERNS:
        match = pattern.fullmatch(cell)
        if match:
            return AnalyteRange(
                lower_limit=float(match.group(lower)) if lower else None,
                upper_limit=float(match.group(upper)) if upper else None,
            )
    # Caller is responsible for surfacing this via the issue tracker.
    return AnalyteRange(text=range_str)


def _rounding(raw: str) -> float:
    """Half a unit of the last printed decimal of the least precise number."""
    decimals = [
        len(n.split(".")[1]) if "." in n else 0
        for n in re.findall(r"\d+(?:\.\d+)?", raw)
    ]
    return 0.5 * 10 ** -min(decimals) if decimals else 0.0


def _format_interval(interval: AnalyteRange) -> str:
    """Render a corrected interval the way the source would print it."""
    return "-".join(
        f"{limit:g}"
        for limit in (interval.lower_limit, interval.upper_limit)
        if limit is not None
    )


def check_factor_consistency(
    name: str,
    traditional: AnalyteRange,
    si: AnalyteRange,
    traditional_raw: str,
    si_raw: str,
    factor: float,
) -> None:
    """Cross-check the factor against the two reference intervals of the row.

    The source prints the same interval in both unit systems, so
    ``traditional * factor`` must reproduce the SI interval up to rounding:
    the printed SI number may be off by half a unit of its last decimal (or
    5 %, whichever is larger), and so may the printed traditional number,
    which the factor scales (0.1 mg/dL of methionine is anything from 0.05
    to 0.15, i.e. 3.4-10 μmol/L). A violation almost always means the
    factor or a unit in the source row is wrong (e.g. BUN 0.0357 instead of
    0.357). Findings go to ``issues["inconsistent_factors"]``.
    """
    si_rounding = _rounding(si_raw)
    traditional_rounding = _rounding(traditional_raw) * factor
    for trad_limit, si_limit in (
        (traditional.lower_limit, si.lower_limit),
        (traditional.upper_limit, si.upper_limit),
    ):
        if trad_limit is None or si_limit is None:
            continue
        expected = trad_limit * factor
        tolerance = max(si_rounding, 0.05 * abs(si_limit)) + traditional_rounding
        if abs(expected - si_limit) > tolerance:
            issues["inconsistent_factors"].append(
                (
                    name,
                    f"{trad_limit:g} * {factor:g} = {expected:.4g}",
                    si_limit,
                    si_raw,
                )
            )


def check_molar_mass(
    name: str,
    traditional_ucum: str,
    si_ucum: str,
    factor: float,
    molar_masses: dict[str, float],
) -> None:
    """Cross-check a mass <-> amount-of-substance factor against the molar mass.

    The reference intervals cannot reveal a factor that is wrong on both
    sides of the row (calcitriol was printed with 2.6 instead of 2.4 and a
    matching SI interval). For a pair like mg/dL <-> mmol/L the factor
    follows from the molar mass alone: ``10 / M``. A deviation of more than
    2 % (the source rounds its factors to about three digits) goes to
    ``issues["molar_mass_mismatch"]``; a mass/mole pair without an entry
    in ``molar_masses.json`` to ``issues["missing_molar_mass"]``.
    """
    mass = _MASS_UNIT.match(traditional_ucum)
    mole = _MOLE_UNIT.match(si_ucum)
    if not mass or not mole:
        return
    if name not in molar_masses:
        issues["missing_molar_mass"].append(name)
        return
    mass_scale = _PREFIX[mass.group(1) or ""] * _PER[mass.group(2)]
    mole_scale = _PREFIX[mole.group(1) or ""] * _PER[mole.group(2)]
    expected = mass_scale / mole_scale / molar_masses[name]
    if abs(expected - factor) > 0.02 * expected:
        issues["molar_mass_mismatch"].append(
            (name, factor, expected, molar_masses[name])
        )


def parse_lab_values(
    loinc_file_path: str | Path,
    html_file_path: str | Path,
    manual_mapping: dict[str, str | None] | None = None,
    corrections: dict[str, dict] | None = None,
    ucum_units: dict[str, str] | None = None,
    analyte_names: dict[str, str] | None = None,
    molar_masses: dict[str, float] | None = None,
) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file.

    ``manual_mapping`` lets callers pin specific analyte names to a LOINC
    (string) or to "no match, don't try" (None). Entries there always win
    over the exact and fuzzy matchers below.

    ``corrections`` maps analyte names to ``Analyte`` field overrides for
    rows that are wrong in the source itself (see
    ``source_corrections.json``); a ``name@specimen`` key corrects only the
    row with that (first) specimen. They are applied before the factor
    consistency check.

    ``ucum_units`` translates the source's unit strings to UCUM codes (see
    ``ucum_units.json``); the result lands in ``traditional_ucum`` /
    ``si_ucum`` of every analyte that got a LOINC.

    ``analyte_names`` maps a source name to the canonical analyte name
    that is matched and shipped (see ``analyte_names.json``); it is applied
    after ``corrections``. ``molar_masses`` feeds :func:`check_molar_mass`.
    """
    analytes = []
    group_name = ""
    global specimens, no_loinc_count, analyte_count, issues
    manual_mapping = manual_mapping or {}
    corrections = corrections or {}
    ucum_units = ucum_units or {}
    analyte_names = analyte_names or {}
    molar_masses = molar_masses or {}

    loinc_data = _load_loinc(loinc_file_path)
    siblings: dict[tuple, list[str]] = {}
    for loinc_num, data in loinc_data.items():
        siblings.setdefault(_sibling_key(data), []).append(loinc_num)

    # Pre-compute the normalized form of every LOINC COMPONENT once, so the
    # per-analyte match below can do both an O(1) exact lookup and a single
    # fuzzy pass over already-normalized strings.
    loinc_by_norm: dict[str, list[str]] = {}  # norm -> [loinc_num, ...]
    loinc_norm_by_num: dict[str, str] = {}  # loinc_num -> norm
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

            cell0 = cells[0]
            # Skip lines with (see...) references
            content = cell0.get_text()
            if re.match(r".*\(.*[sS]ee .*\)", str(content)):
                issues["skipped_see_references"].append(str(content).strip())
                continue

            # Find all sup elements and process them
            for sup in cell0.find_all("sup"):
                sup_content = sup.get_text().strip()
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
            # Check if this is a subtype (indented with any kind of whitespace,
            # the source uses U+00A0 no-break spaces)
            if name[:1].isspace():
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
                    issues["unparseable_factors"].append(
                        (full_name, raw_factor.strip())
                    )
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
            )
            # ``name@specimen`` corrects one of several rows sharing a name
            # (Norepinephrine in plasma vs urine) and wins over the bare name.
            specimen_id = analyte_specimens[0].id
            correction_key = next(
                (
                    key
                    for key in (f"{full_name}@{specimen_id}", full_name)
                    if key in corrections
                ),
                None,
            )
            if correction_key is not None:
                for field, value in corrections[correction_key].items():
                    if field.endswith("_reference_interval"):
                        value = AnalyteRange(**value)
                        # The rounding of a corrected interval is the
                        # correction's own, not the source cell's.
                        if field.startswith("si_"):
                            si_range_raw = _format_interval(value)
                        else:
                            traditional_range_raw = _format_interval(value)
                    setattr(analyte, field, value)
                factor = analyte.conversion_factor
                traditional_range = analyte.traditional_reference_interval
                si_range = analyte.si_reference_interval
                issues["corrected_rows"].append(
                    (correction_key, corrections[correction_key])
                )
            # A rate per 24 h is measured in a 24-hour urine collection,
            # whether or not the source says so in its specimen column.
            if analyte.traditional_units.endswith("/24 h"):
                analyte.specimen = analyte_specimens = [
                    specimens.setdefault(
                        "urine_24_h", Specimen(id="urine_24_h", name="Urine 24 h")
                    )
                    if s.id == "urine"
                    else s
                    for s in analyte_specimens
                ]
                specimen_id = analyte_specimens[0].id
            # ---- canonical name ----
            # The most specific key wins, as for the manual LOINC mapping.
            for key in (
                f"{analyte.name}@{specimen_id}@{analyte.traditional_units}",
                f"{analyte.name}@{specimen_id}",
                analyte.name,
            ):
                if key in analyte_names:
                    analyte.name = analyte_names[key]
                    break
            # ---- LOINC matching ----
            # A LOINC term is *eligible* for this row only if its SYSTEM
            # matches one of the row's specimens, its PROPERTY can carry
            # the row's traditional unit and its TIME_ASPCT is a 24-hour
            # collection exactly when the specimen is. Scale/status/class
            # were already filtered in _load_loinc. Among eligible terms with the same
            # component name, LOINC's own COMMON_TEST_RANK decides.
            allowed_systems: set[str] = set()
            for s in analyte_specimens:
                allowed_systems |= _SPECIMEN_SYSTEMS.get(s.id, set())
            allowed_props = _properties_for_unit(analyte.traditional_units)
            time_aspect = (
                "24H" if any(s.id == "urine_24_h" for s in analyte_specimens) else "Pt"
            )
            if allowed_props is None:
                issues["unknown_units"].append((full_name, analyte.traditional_units))

            def eligible(loinc_num: str) -> str | None:
                """Return a reason string if the term is NOT eligible."""
                row = loinc_data.get(loinc_num)
                if row is None:
                    return "not a quantitative, active result term"
                if row["SYSTEM"] not in allowed_systems:
                    return f"SYSTEM {row['SYSTEM']!r} does not fit specimen"
                if allowed_props is not None and row["PROPERTY"] not in allowed_props:
                    return f"PROPERTY {row['PROPERTY']!r} does not fit unit"
                if row["TIME_ASPCT"] != time_aspect:
                    return f"TIME_ASPCT {row['TIME_ASPCT']!r} is not {time_aspect!r}"
                return None

            # Step 0: manual override. If the operator has pinned this
            # analyte in manual_loinc_mapping.json, obey it unconditionally
            # (either a forced LOINC, or a deliberate "no match").
            # The most specific key wins: ``name@specimen@unit`` (same name
            # and specimen, different unit — Methemoglobin in g/dL vs %),
            # then ``name@specimen`` (Osmolality in serum vs urine), then
            # the bare ``name``.
            mapping_key = None
            for key in (
                f"{analyte.name}@{specimen_id}@{analyte.traditional_units}",
                f"{analyte.name}@{specimen_id}",
                analyte.name,
            ):
                if key in manual_mapping:
                    mapping_key = key
                    break
            analyte_norm = _normalize_name(analyte.name)
            exact_hits = [
                n for n in loinc_by_norm.get(analyte_norm, []) if eligible(n) is None
            ]
            if mapping_key is not None:
                pinned = manual_mapping[mapping_key]
                if pinned is None:
                    issues["pinned_no_match"].append(mapping_key)
                else:
                    analyte.loinc_num = pinned
                    issues["pinned_matches"].append((mapping_key, pinned))
                    why = eligible(pinned)
                    if why:
                        issues["pinned_ineligible"].append((mapping_key, pinned, why))
            elif exact_hits:
                # Step 1: normalized exact match (O(1)).
                exact_hits.sort(key=lambda n: _rank_key(loinc_data[n]))
                analyte.loinc_num = exact_hits[0]
                if len(exact_hits) > 1:
                    issues["ambiguous_exact_matches"].append(
                        (analyte.name, exact_hits[0], exact_hits[1:])
                    )
            else:
                # Step 2: fuzzy match over all eligible LOINC components, but
                # only among candidates that pass the structural guards. We
                # collect ALL qualifying candidates and take the
                # highest-scoring one.
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
                    if eligible(loinc_num) is not None:
                        continue
                    if (
                        best is None
                        or ratio > best[0]
                        or (
                            ratio == best[0]
                            and _rank_key(data) < _rank_key(loinc_data[best[1]])
                        )
                    ):
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
            else:
                # Only rows that will ship are worth a human's attention.
                if factor is not None:
                    check_factor_consistency(
                        analyte.name,
                        traditional_range,
                        si_range,
                        traditional_range_raw,
                        si_range_raw,
                        factor,
                    )
                # ---- SI-side LOINC and UCUM units ----
                si_props = _properties_for_unit(analyte.si_units)
                if si_props is None:
                    issues["unknown_si_units"].append((analyte.name, analyte.si_units))
                else:
                    analyte.si_loinc_num = _find_si_loinc(
                        analyte.loinc_num, si_props, loinc_data, siblings
                    )
                    if analyte.si_loinc_num is None:
                        issues["missing_si_loinc"].append(
                            (analyte.name, analyte.loinc_num, analyte.si_units)
                        )
                    elif (
                        loinc_data[analyte.si_loinc_num]["METHOD_TYP"]
                        != loinc_data[analyte.loinc_num]["METHOD_TYP"]
                    ):
                        issues["other_method_si_loinc"].append(
                            (
                                analyte.name,
                                analyte.si_loinc_num,
                                loinc_data[analyte.si_loinc_num]["METHOD_TYP"],
                            )
                        )
                analyte.traditional_ucum = _to_ucum(
                    analyte.traditional_units,
                    loinc_data.get(analyte.loinc_num, {}).get("PROPERTY"),
                    ucum_units,
                )
                analyte.si_ucum = _to_ucum(
                    analyte.si_units,
                    loinc_data.get(analyte.si_loinc_num or "", {}).get("PROPERTY"),
                    ucum_units,
                )
                for unit, ucum in (
                    (analyte.traditional_units, analyte.traditional_ucum),
                    (analyte.si_units, analyte.si_ucum),
                ):
                    if not ucum:
                        issues["missing_ucum"].append((analyte.name, unit))
                if factor is not None:
                    check_molar_mass(
                        analyte.name,
                        analyte.traditional_ucum,
                        analyte.si_ucum,
                        factor,
                        molar_masses,
                    )

            analytes.append(analyte)

    return analytes


def build_output(analytes: list[Analyte]) -> dict[str, dict]:
    """Key the analytes by LOINC, refusing to let two rows share one key.

    A silent "last one wins" here once replaced serum creatinine (×88.4)
    with urine creatinine (×8.84). Two *different* rows on the same LOINC
    always mean a matching bug or a missing manual pin, so this is fatal on
    purpose; repeats of the same record (the source lists the amino acids
    twice, and many analytes once per reference population) are collapsed,
    merging their specimens.

    The same holds for the SI-side LOINC, which the runtime accepts as an
    alias: two rows must not claim the same alias. An alias that is itself
    the key of another row is fine — the runtime resolves the code to that
    row (magnesium ``2601-3`` is the mEq/L row, not the SI side of the
    mg/dL row). A shipped row without UCUM units is fatal as well.

    Rows without a LOINC or without a numeric conversion factor are not
    shipped; both are listed in the problem report.
    """
    out: dict[str, dict] = {}
    for a in analytes:
        if not a.loinc_num or a.conversion_factor is None:
            continue
        if not a.traditional_ucum or not a.si_ucum:
            raise ValueError(
                f"No UCUM unit for {a.name!r} ({a.traditional_units} -> {a.si_units}); "
                "add it to ucum_units.json"
            )
        entry = a.to_json()
        if a.loinc_num in out:
            # The source lists some rows twice (the amino acids), or once
            # per reference population (testosterone male/female); such
            # rows differ at most in the specimens they name.
            known = out[a.loinc_num]
            if {**known, "specimen": None} == {**entry, "specimen": None}:
                known["specimen"] += [
                    s for s in entry["specimen"] if s not in known["specimen"]
                ]
                continue
            raise ValueError(
                f"LOINC {a.loinc_num} assigned twice: "
                f"{out[a.loinc_num]['name']!r} ({out[a.loinc_num]['traditional_units']}) "
                f"and {a.name!r} ({a.traditional_units})"
            )
        out[a.loinc_num] = entry
    aliases: dict[str, str] = {}  # si_loinc_num -> loinc_num
    for loinc_num, entry in out.items():
        alias = entry["si_loinc_num"]
        if alias is None or alias in out:
            continue
        if alias in aliases:
            raise ValueError(
                f"SI LOINC {alias} claimed twice: by {aliases[alias]} and {loinc_num}"
            )
        aliases[alias] = loinc_num
    return out


if __name__ == "__main__":
    # Example usage
    # get current path
    current_path = Path(__file__).parent.resolve()
    manual_mapping = _load_manual_mapping(current_path / "manual_loinc_mapping.json")
    corrections = _load_source_corrections(current_path / "source_corrections.json")
    analytes = parse_lab_values(
        current_path / "Loinc.csv",
        current_path / "Clinical Laboratory Reference Values.html",
        manual_mapping=manual_mapping,
        corrections=corrections,
        ucum_units=_load_ucum_units(current_path / "ucum_units.json"),
        analyte_names=_load_analyte_names(current_path / "analyte_names.json"),
        molar_masses=_load_molar_masses(current_path / "molar_masses.json"),
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
        "Manually unpinned — no LOINC on purpose (from manual_loinc_mapping.json)",
        issues["pinned_no_match"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Pinned LOINCs that fail the eligibility filters — verify",
        issues["pinned_ineligible"],
        lambda t: f"- {t[0]}  ->  {t[1]}: {t[2]}",
    )
    _print_section(
        "Analytes with no LOINC match (dropped from analytes.json)",
        issues["missing_loinc"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Ambiguous exact matches — chosen by COMMON_TEST_RANK, alternatives listed",
        issues["ambiguous_exact_matches"],
        lambda t: f"- {t[0]}: {t[1]}  (also: {', '.join(t[2])})",
    )
    _print_section(
        "Fuzzy LOINC matches — verify manually",
        sorted(issues["fuzzy_matches"], key=lambda t: t[2]),  # lowest score first
        lambda t: f"[{t[2]}%] {t[0]!r}  ->  {t[3]} ({t[1]!r})",
    )
    _print_section(
        "Traditional units without a PROPERTY mapping (no property filter applied)",
        issues["unknown_units"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "SI units without a PROPERTY mapping (no SI LOINC determined)",
        issues["unknown_si_units"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "No LOINC term for the SI unit (si_loinc_num is null)",
        issues["missing_si_loinc"],
        lambda t: f"- {t[0]} ({t[1]}): {t[2]!r}",
    )
    _print_section(
        "SI LOINC of another method than the traditional term — verify",
        issues["other_method_si_loinc"],
        lambda t: f"- {t[0]}: {t[1]} ({t[2]!r})",
    )
    _print_section(
        "Mass/mole conversions without a molar mass (not cross-checked)",
        sorted(set(issues["missing_molar_mass"])),
        lambda s: f"- {s}",
    )
    _print_section(
        "FACTOR INCONSISTENT with the molar mass — fix before shipping",
        issues["molar_mass_mismatch"],
        lambda t: f"- {t[0]}: factor {t[1]:g}, but {t[3]:g} g/mol gives {t[2]:.4g}",
    )
    _print_section(
        "UNIT WITHOUT UCUM CODE — add to ucum_units.json",
        issues["missing_ucum"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "Analytes without numeric conversion factor (dropped from analytes.json)",
        issues["missing_factors"],
        lambda s: f"- {s}",
    )
    _print_section(
        "Unparseable conversion-factor cells (dropped from analytes.json)",
        issues["unparseable_factors"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "Unparseable reference-range cells",
        issues["unparseable_ranges"],
        lambda t: f"- {t[0]}: {t[1]!r}",
    )
    _print_section(
        "Rows corrected via source_corrections.json",
        issues["corrected_rows"],
        lambda t: f"- {t[0]}: {t[1]}",
    )
    _print_section(
        "FACTOR INCONSISTENT with the source's own reference intervals — fix before shipping",
        issues["inconsistent_factors"],
        lambda t: f"- {t[0]}: {t[1]}, but SI interval says {t[2]:g} ({t[3]!r})",
    )

    output = build_output(analytes)
    target_path = current_path.parent / "src" / "labunits" / "data"
    with Path.open(target_path / "analytes.json", "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print()
    print("=" * 72)
    print(
        f"Summary: {analyte_count} analytes parsed, "
        f"{analyte_count - no_loinc_count} with LOINC, "
        f"{no_loinc_count} without, {len(output)} written."
    )
    print(f"Specimens: {len(specimens)}")
    print("=" * 72)
