import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from thefuzz import fuzz
from models import Specimen, AnalyteRange, Analyte

FUZZY_MATCH_RATIO = 80


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
    "fuzzy_matches": [],                # list[tuple[str, str, int, str]]
    "missing_factors": [],              # list[str]  (analyte name)
    "unparseable_factors": [],          # list[tuple[str, str]]
    "unparseable_ranges": [],           # list[tuple[str, str]]
}


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
    loinc_file_path: str | Path, html_file_path: str | Path
) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file."""
    analytes = []
    group_name = ""
    global specimens, no_loinc_count, analyte_count, issues

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
            for loinc_num, data in loinc_data.items():
                if data["COMPONENT"] == analyte.name:
                    if analyte.loinc_num:
                        raise ValueError(
                            f"Analyte {analyte.name} has already a LOINC number"
                        )
                    analyte.loinc_num = loinc_num
                    break
            else:
                for loinc_num, data in loinc_data.items():
                    ratio = fuzz.ratio(data["COMPONENT"], analyte.name)
                    if ratio > FUZZY_MATCH_RATIO:
                        if analyte.loinc_num:
                            raise ValueError(
                                f"Analyte {analyte.name} has already a LOINC number"
                            )
                        analyte.loinc_num = loinc_num
                        issues["fuzzy_matches"].append(
                            (analyte.name, data["COMPONENT"], ratio, loinc_num)
                        )
                        break

            if not analyte.loinc_num:
                no_loinc_count += 1
                issues["missing_loinc"].append(analyte.name)

            analytes.append(analyte)

    return analytes


if __name__ == "__main__":
    # Example usage
    # get current path
    current_path = Path(__file__).parent.resolve()
    analytes = parse_lab_values(
        current_path / "Loinc.csv",
        current_path / "Clinical Laboratory Reference Values.html",
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
        "Analytes with no LOINC match (dropped from analytes.json)",
        issues["missing_loinc"],
        lambda s: f"- {s}",
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
