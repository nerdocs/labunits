import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

_analytes_data: dict[str, dict] = {}
_si_loinc_index: dict[str, list[str]] = {}
_name_index: dict[str, list[str]] = {}
_records: tuple["Analyte", ...] = ()
_indexed_for: dict | None = None

LoincNum: TypeAlias = str


@dataclass(frozen=True)
class Analyte:
    """One shipped analyte record, as returned by :func:`analytes`.

    ``loinc_num`` is the LOINC term for results in the traditional unit,
    ``si_loinc_num`` the one for results in the SI unit. They are equal
    when one term covers both units; ``si_loinc_num`` is ``None`` when LOINC
    has no term for the SI side. Units are UCUM codes.
    """

    loinc_num: LoincNum
    si_loinc_num: LoincNum | None
    name: str
    specimen: tuple[str, ...]
    traditional_unit: str
    si_unit: str
    conversion_factor: float


def _load_data() -> dict:
    """Load the shipped analyte table into the module-level cache.

    The JSON file (``data/analytes.json``) is keyed by LOINC number; each entry
    holds ``si_loinc_num``, ``name``, ``specimen``, ``traditional_units``,
    ``si_units`` (both UCUM codes) and ``conversion_factor``.

    Returns:
        dict: Mapping ``{loinc_num: {...}}``. Cached after the first call.
    """
    global _analytes_data
    if _analytes_data:
        return _analytes_data

    data_dir = Path(__file__).parent / "data"
    with Path.open(data_dir / "analytes.json", "r", encoding="utf-8") as file:
        _analytes_data = json.load(file)

    return _analytes_data


def _ensure_indexes() -> dict:
    """Return the analyte data, rebuilding the lookup indexes if stale.

    The indexes (and the :class:`Analyte` records served by
    :func:`analytes`) are derived caches; they are rebuilt whenever the underlying
    ``_analytes_data`` object changes (so tests can swap the cache and have
    the indexes follow automatically). The data object itself is remembered,
    not its ``id()``: an address can be reused once an object is freed.
    """
    global _indexed_for, _si_loinc_index, _name_index, _records
    data = _load_data()
    if _indexed_for is not data:
        # SI-side LOINC -> keys of the records it is the SI side of (other
        # than itself).
        _si_loinc_index = {}
        for loinc, entry in data.items():
            si_loinc = entry.get("si_loinc_num")
            if si_loinc and si_loinc != loinc:
                _si_loinc_index.setdefault(si_loinc, []).append(loinc)
        _name_index = {}
        for loinc, entry in data.items():
            if entry.get("name"):
                _name_index.setdefault(entry["name"].lower(), []).append(loinc)
        _records = tuple(
            Analyte(
                loinc_num=loinc,
                si_loinc_num=entry["si_loinc_num"],
                name=entry["name"],
                specimen=tuple(entry["specimen"]),
                traditional_unit=entry["traditional_units"],
                si_unit=entry["si_units"],
                conversion_factor=float(entry["conversion_factor"]),
            )
            for loinc, entry in data.items()
        )
        _indexed_for = data
    return data


def _resolve_analyte_identifier(identifier: str) -> LoincNum:
    """Resolve a LOINC code or full name to a LOINC code.

    The returned code is always the record's key, i.e. the LOINC of the
    traditional-unit side.

    Lookup order:
        1. Exact LOINC match (the record's key).
        2. LOINC of the SI-unit side (``si_loinc_num``), e.g. ``14682-9``
           for serum creatinine in µmol/L. A code that is itself a key
           always means that record (step 1).
        3. Case-insensitive match against ``name``.

    Raises:
        ValueError: if the identifier cannot be resolved, or if a name
            matches several records (e.g. "Creatinine" in serum and in
            urine); the message lists the candidate LOINC codes.
    """
    data = _ensure_indexes()
    if identifier in data:
        return identifier
    if identifier in _si_loinc_index:
        return _si_loinc_index[identifier][0]

    needle = identifier.lower()
    matches = _name_index.get(needle, [])
    if len(matches) == 1:
        return matches[0]
    if matches:
        candidates = "; ".join(
            f"{loinc} ({'/'.join(data[loinc]['specimen'])}, "
            f"{data[loinc]['traditional_units']})"
            for loinc in matches
        )
        raise ValueError(
            f"Ambiguous analyte name: {identifier} — use a LOINC code: {candidates}"
        )

    raise ValueError(f"Unknown analyte identifier: {identifier}")


def analytes() -> list[Analyte]:
    """Return every shipped analyte as an :class:`Analyte` record.

    This is the supported way to enumerate the data set (e.g. to build a
    picker or to check coverage) without touching ``analytes.json``
    directly. Order follows the data file.

    The (immutable) records are built once and reused; every call returns
    a fresh list of them, so the caller may sort or filter it freely.
    """
    _ensure_indexes()
    return list(_records)


def si_unit(analyte: LoincNum | str) -> str:
    """Return the SI unit of the given analyte as a UCUM code (e.g. ``"umol/L"``)."""
    loinc = _resolve_analyte_identifier(analyte)
    return _load_data()[loinc]["si_units"]


def traditional_unit(analyte: LoincNum | str) -> str:
    """Return the traditional unit of the given analyte as a UCUM code (e.g. ``"mg/dL"``)."""
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
        analyte: LOINC code (preferred; of either unit side) or full name.

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
        analyte: LOINC code (preferred; of either unit side) or full name.

    Returns:
        The value expressed in the analyte's traditional unit.
        ``inf``/``-inf``/``nan`` are propagated unchanged.
    """
    factor = conversion_factor(analyte)
    if math.isinf(value) or math.isnan(value):
        return value
    return value / factor


def _unit_factor(
    analyte: LoincNum | str, from_unit: str, to_unit: str
) -> tuple[float, bool]:
    """Find the factor for a unit pair; return ``(factor, divide)``.

    ``divide`` tells whether the value has to be divided by the factor
    (SI -> traditional) instead of multiplied. A LOINC code may belong to
    two records — magnesium ``2601-3`` is the meq/L record and the SI side
    of the mg/dL record — so every record the code belongs to is tried and
    the units decide.
    """
    data = _ensure_indexes()
    loinc = _resolve_analyte_identifier(analyte)
    candidates = [loinc] + [
        other for other in _si_loinc_index.get(analyte, []) if other != loinc
    ]
    for candidate in candidates:
        entry = data[candidate]
        traditional, si = entry["traditional_units"], entry["si_units"]
        if from_unit == to_unit and from_unit in (traditional, si):
            return 1.0, False
        if (from_unit, to_unit) == (traditional, si):
            return float(entry["conversion_factor"]), False
        if (from_unit, to_unit) == (si, traditional):
            return float(entry["conversion_factor"]), True
    known = "; ".join(
        f"{data[c]['traditional_units']} <-> {data[c]['si_units']}" for c in candidates
    )
    raise ValueError(
        f"Cannot convert {analyte} from {from_unit} to {to_unit}; known units: {known}"
    )


def factor(analyte: LoincNum | str, from_unit: str, to_unit: str) -> float:
    """Return the factor that converts a value from one unit to another.

    ``value_in_to_unit = value_in_from_unit * factor``. Unlike
    :func:`conversion_factor`, the direction follows from the units, so
    the caller need not know which side is the traditional one.

    Args:
        analyte: LOINC code (of either unit side) or full name.
        from_unit: UCUM code of the unit the value is in.
        to_unit: UCUM code of the unit wanted.

    Returns:
        ``1.0`` if both units are the same unit of the analyte, the
        conversion factor for traditional -> SI, its reciprocal for
        SI -> traditional.

    Raises:
        ValueError: if the analyte is unknown, or if the units are not the
            analyte's unit pair; the message names the known units. Units
            are compared as exact UCUM strings.
    """
    value, divide = _unit_factor(analyte, from_unit, to_unit)
    return 1 / value if divide else value


def convert(
    value: float, analyte: LoincNum | str, from_unit: str, to_unit: str
) -> float:
    """Convert a value of an analyte from one of its units to the other.

    Same arguments and errors as :func:`factor`. ``inf``/``-inf``/``nan``
    are propagated unchanged.
    """
    unit_factor, divide = _unit_factor(analyte, from_unit, to_unit)
    if math.isinf(value) or math.isnan(value):
        return value
    return value / unit_factor if divide else value * unit_factor
