from typing import Optional
from pydantic import BaseModel


class Specimen(BaseModel):
    id: str
    name: str

    def __str__(self):
        return self.name


class AnalyteRange(BaseModel):
    lower_limit: Optional[float] = None
    upper_limit: Optional[float] = None
    text: str = ""  # if limits can't be parsed to float, use this field

    def to_json(self):
        return self.model_dump()


class Analyte(BaseModel):
    loinc_num: str = ""
    # LOINC term for results reported in the SI unit: equal to ``loinc_num``
    # when one term covers both units, ``None`` when LOINC has no such term.
    si_loinc_num: Optional[str] = None
    name: str
    subtitle: Optional[str] = None
    gender: str = ""  # ("m","f")
    specimen: list[Specimen]
    traditional_reference_interval: AnalyteRange
    traditional_units: str  # as printed in the source
    traditional_ucum: str = ""
    conversion_factor: Optional[float] = None
    si_reference_interval: AnalyteRange
    si_units: str  # as printed in the source
    si_ucum: str = ""

    def to_json(self):
        """Serialise the shipped record.

        The reference intervals are deliberately NOT part of it: they are
        parsed only to cross-check the conversion factor. labunits converts
        units and must not carry anything that invites clinical
        interpretation. Units are shipped as UCUM codes, not as the source's
        free-text strings.
        """
        return {
            "loinc_num": self.loinc_num,
            "si_loinc_num": self.si_loinc_num,
            "name": self.name,
            "specimen": [specimen.id for specimen in self.specimen],
            "traditional_units": self.traditional_ucum,
            "conversion_factor": self.conversion_factor,
            "si_units": self.si_ucum,
        }
