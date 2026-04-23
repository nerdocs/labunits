import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from thefuzz import fuzz
from scripts.models import Specimen, AnalyteRange, Analyte

FUZZY_MATCH_RATIO = 80


# TODO: AnalyteGroups
# TODO: ranges as separate entities


specimens: dict[str, Specimen] = {}  # id, Specimen
no_loinc_count = 0
analyte_count = 0


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
        print(
            f"⚠️ Could not convert range '{range_str}' into proper values, saving as "
            f"text."
        )
        return AnalyteRange(text=range_str)
    return AnalyteRange(lower_limit=lower_limit, upper_limit=upper_limit)


def parse_lab_values(
    loinc_file_path: str | Path, html_file_path: str | Path
) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file."""
    analytes = []
    group_name = ""
    global specimens, no_loinc_count, analyte_count

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
                print(f"Skipping '{content}'")
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
            analyte = Analyte(
                name=full_name,
                specimen=analyte_specimens,
                traditional_reference_interval=parse_interval(
                    cells[2].get_text().strip()
                ),
                traditional_units=cells[3].get_text().strip(),
                conversion_factor=cells[4].get_text().strip(),
                si_reference_interval=parse_interval(cells[5].get_text().strip()),
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
                        print(
                            f" ✅ [Fuzzy match ({ratio}%)] {analyte.name} <> "
                            f"{data['COMPONENT']}"
                        )
                        if analyte.loinc_num:
                            raise ValueError(
                                f"Analyte {analyte.name} has already a LOINC number"
                            )
                        analyte.loinc_num = loinc_num
                        break

            if not analyte.loinc_num:
                no_loinc_count += 1

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

    # Print first few analytes
    for i, analyte in enumerate(analytes[:10]):
        print(f"{i+1}. {analyte.name}")
        print(f"   Specimen: {analyte.specimen}")
        print(
            f"   Traditional: {analyte.traditional_reference_interval} {analyte.traditional_units}"
        )
        print(f"   Reference interval: {analyte.si_reference_interval}")
        print(f"   Conversion factor: {analyte.conversion_factor}")
        print(f"   SI: {analyte.si_units}")
        print(f"   Loinc number: {analyte.loinc_num}")
        print()

    print(f"{analyte_count} analytes found.")
    print(f"{no_loinc_count} analytes have no loinc numbers.")
    print()

    print("Specimens:")
    for id, sp in specimens.items():
        print(f"{id:20}{sp.name}")
