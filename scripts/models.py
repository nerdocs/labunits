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
    name: str
    subtitle: Optional[str] = None
    gender: str = ""  # ("m","f")
    specimen: list[Specimen]
    traditional_reference_interval: AnalyteRange
    traditional_units: str
    conversion_factor: str
    si_reference_interval: AnalyteRange
    si_units: str
    reference_range_is_age_dependent: bool = False

    def to_json(self):
        return {
            "loinc_num": self.loinc_num,
            "name": self.name,
            "specimen": [specimen.id for specimen in self.specimen],
            "traditional_units": self.traditional_units,
            "traditional_reference_interval": self.traditional_reference_interval.model_dump(),
            "conversion_factor": self.conversion_factor,
            "si_units": self.si_units,
            "si_reference_interval": self.si_reference_interval.model_dump(),
            "reference_range_is_age_dependent": self.reference_range_is_age_dependent,
        }
