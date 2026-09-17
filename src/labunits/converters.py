import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

_analytes_data: dict[str, dict] = {}
_name_index: dict[str, str] = {}
_abbrev_index: dict[str, str] = {}
_indexed_for: int | None = None

LoincNum: TypeAlias = str


@dataclass(frozen=True)
class Analyte:
    """One shipped analyte record, as returned by :func:`analytes`."""

    loinc_num: LoincNum
    name: str
    specimen: tuple[str, ...]
    traditional_unit: str
    si_unit: str
    conversion_factor: float


def _load_data() -> dict:
    """Load the shipped analyte table into the module-level cache.

    The JSON file (``data/analytes.json``) is keyed by LOINC number; each entry
    holds ``name``, ``specimen``, ``traditional_units``, ``si_units`` and
    ``conversion_factor``.

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


def _ensure_indexes() -> dict:
    """Return the analyte data, rebuilding name/abbreviation indexes if stale.

    The indexes are derived caches; they are rebuilt whenever the underlying
    ``_analytes_data`` object changes (so tests can swap the cache and have
    the indexes follow automatically).
    """
    global _indexed_for, _name_index, _abbrev_index
    data = _load_data()
    if _indexed_for != id(data):
        _name_index = {
            entry["name"].lower(): loinc
            for loinc, entry in data.items()
            if entry.get("name")
        }
        _abbrev_index = {
            entry["abbreviation"].lower(): loinc
            for loinc, entry in data.items()
            if entry.get("abbreviation")
        }
        _indexed_for = id(data)
    return data


def _resolve_analyte_identifier(identifier: str) -> LoincNum:
    """Resolve a LOINC code, abbreviation or full name to a LOINC code.

    Lookup order:
        1. Exact LOINC match.
        2. Case-insensitive match against ``name``.
        3. Case-insensitive match against ``abbreviation`` (reserved — the
           shipped ``analytes.json`` does not carry abbreviations yet).

    Raises:
        ValueError: if the identifier cannot be resolved.
    """
    data = _ensure_indexes()
    if identifier in data:
        return identifier

    needle = identifier.lower()
    if needle in _name_index:
        return _name_index[needle]
    if needle in _abbrev_index:
        return _abbrev_index[needle]

    raise ValueError(f"Unknown analyte identifier: {identifier}")


def analytes() -> list[Analyte]:
    """Return every shipped analyte as an :class:`Analyte` record.

    This is the supported way to enumerate the data set (e.g. to build a
    picker or to check coverage) without touching ``analytes.json``
    directly. Order follows the data file.
    """
    return [
        Analyte(
            loinc_num=loinc,
            name=entry["name"],
            specimen=tuple(entry["specimen"]),
            traditional_unit=entry["traditional_units"],
            si_unit=entry["si_units"],
            conversion_factor=float(entry["conversion_factor"]),
        )
        for loinc, entry in _load_data().items()
    ]


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


def to_si_unit(value: float, analyte: LoincNum | str) -> float:
    """Convert a concentration from its traditional unit to its SI unit.

    Args:
        value: Concentration in the analyte's traditional unit.
        analyte: LOINC code (preferred), abbreviation, or full name.

    Returns:
        The value expressed in the analyte's SI unit. ``inf``/``-inf``/``nan``
        are propagated unchanged.
    """
    factor = conversion_factor(analyte)
    if math.isinf(value) or math.isnan(value):
        return value
    return value * factor


def to_traditional_unit(value: float, analyte: LoincNum | str) -> float:
    """Convert a concentration from its SI unit to its traditional unit.

    Args:
        value: Concentration in the analyte's SI unit.
        analyte: LOINC code (preferred), abbreviation, or full name.

    Returns:
        The value expressed in the analyte's traditional unit.
        ``inf``/``-inf``/``nan`` are propagated unchanged.
    """
    factor = conversion_factor(analyte)
    if math.isinf(value) or math.isnan(value):
        return value
    return value / factor
