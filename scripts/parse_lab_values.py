import re
from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup


@dataclass
class Specimen:
    name: str

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self)


@dataclass
class Analyte:
    name: str
    specimen: list[Specimen]
    traditional_reference_interval: str
    traditional_units: str
    conversion_factor: str
    si_reference_interval: str
    si_units: str
    reference_range_is_age_dependent: bool = False


specimens: dict[str, Specimen] = {}  # id, Specimen


def parse_lab_values(html_file_path: str | Path) -> list[Analyte]:
    """Parse Clinical Laboratory Reference Values HTML file."""
    analytes = []
    current_header = ""

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

            # Handle superscript elements and set age dependency flag
            reference_range_is_age_dependent = False
            name_html = cells[0].decode_contents()

            # Skip lines with (see...) references
            if "(see " in name_html and name_html.endswith(")"):
                continue

            if len(cells) < 7 or cells[1].get_text() == "":
                current_header = name_html
                continue

            # Find all sup elements and process them
            sups = cells[0].find_all("sup")
            for sup in sups:
                sup_content = sup.get_text().strip()
                if sup_content == "b":
                    reference_range_is_age_dependent = True

                # Remove the sup element and any immediately following comma
                sup_str = str(sup)
                if sup_str + "," in name_html:
                    name_html = name_html.replace(sup_str + ",", "")
                else:
                    name_html = name_html.replace(sup_str, "")

            # find all <a> tags and  replace it with their get_text()
            a_tags = [
                a for a in cells[0].find_all("a") if a.get_text() not in ["a", "b"]
            ]
            for a in a_tags:
                name_html = name_html.replace(str(a), a.get_text())

            # Clean up any remaining right whitespace
            name = name_html.rstrip()

            # Check if this is a subtype (starts with spaces)
            if name.startswith(" ") or name.startswith("\t"):
                # This is a subtype, prepend with current header
                subtype_name = name.strip()
                full_name = f"{current_header}, {subtype_name}"
            else:
                full_name = name

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
                            name=specimen_name.strip().capitalize()
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

            analytes.append(analyte)

    return analytes


if __name__ == "__main__":
    # Example usage
    # get current path
    current_path = Path(__file__).parent.resolve()
    html_path = current_path / "Clinical Laboratory Reference Values.html"
    analytes = parse_lab_values(html_path)

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
        print()

    print("Specimens:")
    for id, sp in specimens.items():
        print(f"{id:20}{sp.name}")
