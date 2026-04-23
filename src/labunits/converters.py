import json
import math
from pathlib import Path

_analytes_data = {}

type LoincNum = str


def _load_data() -> dict:
    """
    Load data from the 'data' directory.

    Returns:
        dict: Data in the format {'analyte': {'value': float, 'units': str}}
    """
    global _analytes_data
    # check if data is already loaded
    if _analytes_data:
        return _analytes_data

    # get data dir of labunits package using Pathlib
    data_dir = Path(__file__).parent / "data"

    with Path.open(data_dir / "analytes.json", "r") as file:
        _analytes_data = json.load(file)

    return _analytes_data


def _resolve_analyte_identifier(identifier: str) -> LoincNum:
    """Resolve various identifiers to LOINC code."""
    data = _load_data()

    # Direct LOINC lookup
    if identifier in data:
        return identifier

    # Search by abbreviation or name
    for loinc, info in data.items():
        if (  # FIXME
            info.get("abbreviation", "").lower() == identifier.lower()
            or info.get("name", "").lower() == identifier.lower()
        ):
            return loinc

    raise ValueError(f"Unknown analyte identifier: {identifier}")


def si_unit(analyte: LoincNum | str) -> str:
    """Returns the SI unit for the given analyte.

    Examples:
        "mmol/L"
        "µmol/L"
    """
    loinc = _resolve_analyte_identifier(analyte)
    return _analytes_data[loinc]["si_units"]


def traditional_unit(analyte: LoincNum | str) -> str:
    """Returns the traditional unit for the given analyte."""
    loinc = _resolve_analyte_identifier(analyte)
    return _analytes_data[loinc]["traditional_units"]


def conversion_factor(analyte: LoincNum | str) -> float:
    """Returns the conversion factor for the given analyte.

    Multiply with the factor to convert from traditional to SI, divide by it the
    other way round.

    Returns:
        float: Conversion factor
    """
    loinc = _resolve_analyte_identifier(analyte)
    return float(_analytes_data[loinc]["conversion_factor"])


def to_si_unit(analyte: LoincNum | str, value: float) -> float:
    """
    Convert value to SI unit.

    Args:
        analyte: LOINC code (preferred), abbreviation, or full name
        value (float): Concentration in traditional units
    Returns:
        float: value in SI units
    """
    # Normalize to LOINC internally
    loinc = _resolve_analyte_identifier(analyte)
    data = _load_data()
    factor = float(data[loinc]["conversion_factor"])

    if math.isinf(value) or math.isnan(value):
        return value
    return value * factor


def to_traditional_unit(analyte: str, value: float) -> float:
    """
    Convert SI to value unit.

    Args:
        analyte: LOINC code (preferred), abbreviation, or full name
        value (float): Concentration in SI units
    Returns:
        float: value in traditional units
    """
    loinc = _resolve_analyte_identifier(analyte)
    data = _load_data()
    factor = float(data[loinc]["conversion_factor"])

    if math.isinf(value) or math.isnan(value):
        return value
    return value / factor
