import json
import math
from pathlib import Path

_analytes_data: dict[str, dict] = {}

type LoincNum = str


def _load_data() -> dict:
    """Load the shipped analyte table into the module-level cache.

    The JSON file (``data/analytes.json``) is keyed by LOINC number; each entry
    holds ``name``, ``specimen``, ``traditional_units``, ``si_units``,
    ``conversion_factor`` and reference intervals.

    Returns:
        dict: Mapping ``{loinc_num: {...}}``. Cached after the first call.
    """
    global _analytes_data
    if _analytes_data:
        return _analytes_data

    data_dir = Path(__file__).parent / "data"
    with Path.open(data_dir / "analytes.json", "r") as file:
        _analytes_data = json.load(file)

    return _analytes_data


def _resolve_analyte_identifier(identifier: str) -> LoincNum:
    """Resolve a LOINC code, abbreviation or full name to a LOINC code.

    Lookup order:
        1. Exact LOINC match.
        2. Case-insensitive match against ``abbreviation`` or ``name``.

    Note:
        The shipped ``analytes.json`` does not (yet) contain ``abbreviation``
        fields, so abbreviation lookup is effectively a no-op today. It is
        kept because it is part of the public API contract and will start
        working once abbreviations are added to the data pipeline.

    Raises:
        ValueError: if the identifier cannot be resolved.
    """
    data = _load_data()

    if identifier in data:
        return identifier

    needle = identifier.lower()
    for loinc, info in data.items():
        if (
            info.get("abbreviation", "").lower() == needle
            or info.get("name", "").lower() == needle
        ):
            return loinc

    raise ValueError(f"Unknown analyte identifier: {identifier}")


def si_unit(analyte: LoincNum | str) -> str:
    """Return the SI unit string for the given analyte (e.g. ``"mmol/L"``)."""
    loinc = _resolve_analyte_identifier(analyte)
    return _load_data()[loinc]["si_units"]


def traditional_unit(analyte: LoincNum | str) -> str:
    """Return the traditional unit string for the given analyte (e.g. ``"mg/dL"``)."""
    loinc = _resolve_analyte_identifier(analyte)
    return _load_data()[loinc]["traditional_units"]


def conversion_factor(analyte: LoincNum | str) -> float:
    """Return the traditional→SI conversion factor for the given analyte.

    ``si_value = traditional_value * factor`` — so multiply to go traditional→SI
    and divide to go SI→traditional.
    """
    loinc = _resolve_analyte_identifier(analyte)
    return float(_load_data()[loinc]["conversion_factor"])


def to_si_unit(analyte: LoincNum | str, value: float) -> float:
    """Convert a concentration from its traditional unit to its SI unit.

    Args:
        analyte: LOINC code (preferred), abbreviation, or full name.
        value: Concentration in the analyte's traditional unit.

    Returns:
        The value expressed in the analyte's SI unit. ``inf``/``-inf``/``nan``
        are propagated unchanged.
    """
    loinc = _resolve_analyte_identifier(analyte)
    factor = float(_load_data()[loinc]["conversion_factor"])

    if math.isinf(value) or math.isnan(value):
        return value
    return value * factor


def to_traditional_unit(analyte: LoincNum | str, value: float) -> float:
    """Convert a concentration from its SI unit to its traditional unit.

    Args:
        analyte: LOINC code (preferred), abbreviation, or full name.
        value: Concentration in the analyte's SI unit.

    Returns:
        The value expressed in the analyte's traditional unit.
        ``inf``/``-inf``/``nan`` are propagated unchanged.
    """
    loinc = _resolve_analyte_identifier(analyte)
    factor = float(_load_data()[loinc]["conversion_factor"])

    if math.isinf(value) or math.isnan(value):
        return value
    return value / factor
