import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from pydantic import BaseModel


class Specimen(BaseModel):
    id: str
    name: str

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)



class Analyte(BaseModel):
    name: str
    specimen: list[Specimen]
    traditional_reference_interval: str
    traditional_units: str
    conversion_factor: str
    si_reference_interval: str
    si_units: str
    reference_range_is_age_dependent: bool = False
    loinc_num: str = ""

    def to_json(self):
        return {
            "name": self.name,
            "specimen": [specimen.id for specimen in self.specimen],
            "traditional_reference_interval": self.traditional_reference_interval,
            "traditional_units": self.traditional_units,
            "conversion_factor": self.conversion_factor,
            "si_reference_interval": self.si_reference_interval,
            "si_units": self.si_units,
            "reference_range_is_age_dependent": self.reference_range_is_age_dependent,
            "loinc_num": self.loinc_num,
        }


specimens: dict[str, Specimen] = {}  # id, Specimen
no_loinc_count = 0
analyte_count = 0


def parse_lab_values(
    loinc_file_path: str | Path, html_file_path: str | Path
) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file."""
    analytes = []
    current_header = ""
    global specimens, no_loinc_count, analyte_count

    # ------ CSV LOINC file ------
    # open loinc csv file and read it
    loinc_data: dict[str, dict[str, str]] = {}
    with Path.open(loinc_file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # parse header row
    header_row = lines[0].strip().split(",")
    header_row = [header.strip('"') for header in header_row]
    if header_row[0] != "LOINC_NUM":
        raise ValueError("Invalid LOINC CSV file")

    # parse LOINC data
    for line in lines[1:]:
        if line.strip():  # skip empty lines
            fields = line.strip().split(",")
            fields = [field.strip('"') for field in fields]
            if len(fields) >= len(header_row):
                # Create a dictionary with all columns
                row_data = {}
                for i, header in enumerate(header_row):
                    if i < len(fields):
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
                current_header = name
                print(f"Found new header for next analytes: '{current_header}'")
                continue
            # Check if this is a subtype (starts with spaces)
            if name.startswith(" ") or name.startswith("\t"):
                # This is a subtype, prepend with current header
                subtype_name = name.strip()
                full_name = f"{current_header}, {subtype_name}"
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
                traditional_reference_interval=cells[2].get_text().strip(),
                traditional_units=cells[3].get_text().strip(),
                conversion_factor=cells[4].get_text().strip(),
                si_reference_interval=cells[5].get_text().strip(),
                si_units=cells[6].get_text().strip(),
                reference_range_is_age_dependent=reference_range_is_age_dependent,
            )
            for loinc_num, data in loinc_data.items():
                if data["COMPONENT"] == analyte.name:
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
        # use pydantic to serialize the list of Analyte objects to JSON
        json.dump([analyte.to_json() for analyte in analytes], file, indent=2)

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
