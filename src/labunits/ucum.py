"""Analyte-independent handling of UCUM unit codes.

Three helpers that need no analyte table:

- :func:`ucum_factor` converts between two units of the same kind of
  quantity that differ only in prefixes, powers of ten and denominators
  (``mg/dL`` -> ``g/L``).
- :func:`normalise` suggests the UCUM code for a unit as laboratories
  write it (``µmol/l`` -> ``umol/L``).
- :func:`display` renders a UCUM code for humans (``10*3/uL`` -> ``10³/µL``).

Only the subset of UCUM that laboratory results use is understood. A mass
never converts into an amount of substance here — that needs the analyte
(see :func:`labunits.converters.factor`).
"""

import re
from fractions import Fraction
from functools import lru_cache

# Powers of ten of the metric prefixes that occur in laboratory units.
_PREFIXES = {
    "G": 9,
    "M": 6,
    "k": 3,
    "d": -1,
    "c": -2,
    "m": -3,
    "u": -6,
    "n": -9,
    "p": -12,
    "f": -15,
}

# Atom -> (scale, base quantities). Atoms sharing base quantities convert
# into each other; everything else is deliberately kept apart: gram and
# mole, mole and equivalent, enzyme unit (U), katal and international unit.
_METRIC_ATOMS: dict[str, tuple[Fraction, dict[str, int]]] = {
    "g": (Fraction(1), {"g": 1}),
    "mol": (Fraction(1), {"mol": 1}),
    "eq": (Fraction(1), {"eq": 1}),
    "osm": (Fraction(1), {"osm": 1}),
    "kat": (Fraction(1), {"kat": 1}),
    "U": (Fraction(1), {"U": 1}),
    "[IU]": (Fraction(1), {"[IU]": 1}),
    "[arb'U]": (Fraction(1), {"[arb'U]": 1}),
    "L": (Fraction(1, 1000), {"m": 3}),
    "l": (Fraction(1, 1000), {"m": 3}),
    "m": (Fraction(1), {"m": 1}),
    "m[Hg]": (Fraction(1), {"m[Hg]": 1}),
    "s": (Fraction(1), {"s": 1}),
}
_OTHER_ATOMS: dict[str, tuple[Fraction, dict[str, int]]] = {
    "min": (Fraction(60), {"s": 1}),
    "h": (Fraction(3600), {"s": 1}),
    "d": (Fraction(86400), {"s": 1}),
    "%": (Fraction(1, 100), {}),
}

_Parsed = tuple[Fraction, tuple[tuple[str, int], ...]]

_NUMBER = re.compile(r"(\d+(?:\.\d+)?)(?:[*^](-?\d+))?")
_SYMBOL = re.compile(r"(?:\[[^\]]*\]|[^/.(){}\[\]\d-])+")
_EXPONENT = re.compile(r"-?\d+")
_ANNOTATION = re.compile(r"\{[^{}]*\}")


def _atom(symbol: str) -> tuple[Fraction, dict[str, int]] | None:
    """Resolve a unit symbol such as ``mg``, ``dL`` or ``min``."""
    if symbol in _METRIC_ATOMS:
        return _METRIC_ATOMS[symbol]
    if symbol in _OTHER_ATOMS:
        return _OTHER_ATOMS[symbol]
    if symbol[:1] in _PREFIXES and symbol[1:] in _METRIC_ATOMS:
        scale, dims = _METRIC_ATOMS[symbol[1:]]
        return scale * Fraction(10) ** _PREFIXES[symbol[0]], dims
    return None


class _Parser:
    """Recursive-descent parser for the UCUM subset described above."""

    def __init__(self, unit: str) -> None:
        self.unit = unit
        self.pos = 0

    def fail(self) -> ValueError:
        return ValueError(f"Not a UCUM unit labunits understands: {self.unit}")

    def peek(self) -> str:
        return self.unit[self.pos : self.pos + 1]

    def expression(self) -> tuple[Fraction, dict[str, int]]:
        scale, dims = Fraction(1), {}
        operator = "."
        if self.peek() == "/":  # "/uL"
            operator = "/"
            self.pos += 1
        while True:
            term_scale, term_dims = self.term()
            sign = 1 if operator == "." else -1
            scale *= term_scale**sign
            for key, exponent in term_dims.items():
                dims[key] = dims.get(key, 0) + sign * exponent
            operator = self.peek()
            if operator not in ("/", "."):
                return scale, dims
            self.pos += 1

    def term(self) -> tuple[Fraction, dict[str, int]]:
        if self.peek() == "(":
            self.pos += 1
            result = self.expression()
            if self.peek() != ")":
                raise self.fail()
            self.pos += 1
            return result
        annotation = _ANNOTATION.match(self.unit, self.pos)
        if annotation:  # "{creat}" on its own counts as a quantity of its own
            self.pos = annotation.end()
            return Fraction(1), {annotation.group(): 1}
        number = _NUMBER.match(self.unit, self.pos)
        if number:
            self.pos = number.end()
            value = Fraction(number.group(1))
            return value ** int(number.group(2) or 1), {}
        symbol = _SYMBOL.match(self.unit, self.pos)
        if not symbol:
            raise self.fail()
        self.pos = symbol.end()
        atom = _atom(symbol.group())
        if atom is None:
            raise self.fail()
        scale, dims = atom
        exponent = 1
        match = _EXPONENT.match(self.unit, self.pos)
        if match:  # "um3"
            self.pos = match.end()
            exponent = int(match.group())
        annotation = _ANNOTATION.match(self.unit, self.pos)
        suffix = ""
        if annotation:  # "g{Hb}" is not plain "g"
            self.pos = annotation.end()
            suffix = annotation.group()
        return scale**exponent, {key + suffix: n * exponent for key, n in dims.items()}


@lru_cache(maxsize=1024)
def _parse(unit: str) -> _Parsed:
    """Reduce a unit to a scale and its base quantities."""
    parser = _Parser(unit)
    if not unit:
        raise parser.fail()
    scale, dims = parser.expression()
    if parser.pos != len(unit):
        raise parser.fail()
    return scale, tuple(sorted((key, n) for key, n in dims.items() if n))


def ucum_factor(from_unit: str, to_unit: str) -> float:
    """Return the factor between two UCUM units of the same kind of quantity.

    ``value_in_to_unit = value_in_from_unit * factor``. The units may differ
    in metric prefixes, powers of ten, denominators and time units::

        ucum_factor("mg/dL", "g/L")         # 0.01
        ucum_factor("umol/L", "mmol/L")     # 0.001
        ucum_factor("10*3/uL", "10*9/L")    # 1.0
        ucum_factor("mL/min", "mL/s")       # 0.016666...

    No analyte is involved, so nothing is converted that needs one: gram
    and mole, mole and equivalent, enzyme unit and katal, international
    units, and annotated units (``g{Hb}``) all stay apart.

    Raises:
        ValueError: if a unit is not understood, or the two units measure
            different kinds of quantity.
    """
    from_scale, from_dims = _parse(from_unit)
    to_scale, to_dims = _parse(to_unit)
    if from_dims != to_dims:
        raise ValueError(
            f"Cannot convert {from_unit} to {to_unit}: different kinds of quantity"
        )
    return float(from_scale / to_scale)


_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_FROM_SUPERSCRIPT = str.maketrans(_SUPERSCRIPTS + "⁻", "0123456789-")
_TO_SUPERSCRIPT = str.maketrans("0123456789-", _SUPERSCRIPTS + "⁻")

# Whole parts of a unit (between slashes) as laboratories abbreviate them,
# lower-cased -> UCUM. Abbreviations only, no written-out words.
_WORDS = {
    "%": "%",
    "tsd": "10*3",
    "mio": "10*6",
    "mrd": "10*9",
    "s": "s",
    "sec": "s",
    "sek": "s",
    "min": "min",
    "h": "h",
    "std": "h",
    "d": "d",
    "24h": "(24.h)",
    "24 h": "(24.h)",
    "mmhg": "mm[Hg]",
    "mm hg": "mm[Hg]",
}
_BASES = {
    "g": "g",
    "mol": "mol",
    "l": "L",
    "kat": "kat",
    "eq": "eq",
    "val": "eq",
    "osm": "osm",
    "osmol": "osm",
    "m": "m",
}
# Gram and metre only in lower case: "G" and "M" mean giga and mega.
_PREFIXED = re.compile(r"(mc|[kdcmunpf])?(g|m|[lL]|(?i:mol|kat|eq|val|osmol|osm))")
_ACTIVITY = re.compile(r"([kmun])?(U|IU|IE|I\.E\.)")
_ANNOTATED = re.compile(r"(\S+)\s+(?i:(hb|krea|crea))")
_BODY_SURFACE = re.compile(r"1[.,]73\s*m\s*\^?2?")
_POWER_OF_TEN = re.compile(r"(?:x\s*)?10\s*(?:\*\*|\^|\*|[eE])\s*(\d+)")


def _normalise_part(part: str, shorthand: bool) -> str | None:
    """Translate one slash-separated part of a laboratory unit to UCUM."""
    key = part.lower().rstrip(".")
    if shorthand and part in ("G", "T"):  # "G/l" = 10^9 per litre
        return "10*9" if part == "G" else "10*12"
    if key in _WORDS:
        return _WORDS[key]
    if _BODY_SURFACE.fullmatch(key):
        return "{1.73_m2}"
    annotated = _ANNOTATED.fullmatch(part)
    if annotated:
        base = _normalise_part(annotated.group(1), False)
        note = "{Hb}" if annotated.group(2).lower().startswith("h") else "{creat}"
        return base + note if base else None
    prefixed = _PREFIXED.fullmatch(part)
    if prefixed:
        prefix = "u" if prefixed.group(1) == "mc" else prefixed.group(1) or ""
        return prefix + _BASES[prefixed.group(2).lower()]
    activity = _ACTIVITY.fullmatch(part)
    if activity:
        unit = "U" if activity.group(2) == "U" else "[IU]"
        return (activity.group(1) or "") + unit
    try:  # already UCUM, e.g. "10*9", "(24.h)", "m[IU]"
        _parse(part)
    except ValueError:
        return None
    return part


def normalise(unit_text: str) -> str | None:
    """Suggest the UCUM code for a unit as a laboratory writes it.

    Handles spelling variants and abbreviations of units — litre as ``l``,
    ``µ`` for micro, powers of ten (``10^9``, ``10³``), count shorthands
    (``G/l``, ``T/l``, ``Tsd/µl``, ``Mio/µl``), ``IE``/``IU``, ``mval``,
    ``mmHg``, ``sec``, ``24h`` collections — but no written-out words::

        normalise("mg/dl")      # "mg/dL"
        normalise("µmol/l")     # "umol/L"
        normalise("G/l")        # "10*9/L"
        normalise("sec")        # "s"

    A code that is already UCUM is returned unchanged.

    The result is a *suggestion* for a human to confirm: laboratory
    spellings are ambiguous (``u/l`` may be units or micro) and such text
    yields ``None``, as does anything not recognised.
    """
    text = unit_text.strip().replace("µ", "u").replace("μ", "u")
    text = re.sub(
        f"10([{_SUPERSCRIPTS}]+)",
        lambda m: "10*" + m.group(1).translate(_FROM_SUPERSCRIPT),
        text,
    ).translate(_FROM_SUPERSCRIPT)
    text = _POWER_OF_TEN.sub(r"10*\1", text)
    text = re.sub(r"\s*/\s*", "/", text)
    if not text:
        return None
    parts = text.split("/")
    result = []
    for position, part in enumerate(parts):
        if part == "" and position == 0 and len(parts) > 1:  # "/µl"
            result.append("")
            continue
        translated = _normalise_part(part, position == 0 and len(parts) > 1)
        if translated is None:
            return None
        result.append(translated)
    unit = "/".join(result)
    try:
        _parse(unit)
    except ValueError:
        return None
    return unit


def display(unit: str) -> str:
    """Render a UCUM code in the form people read.

    ``10*3/uL`` -> ``10³/µL``, ``umol/L`` -> ``µmol/L``, ``m[IU]/mL`` ->
    ``mIU/mL``, ``mg/(24.h)`` -> ``mg/24 h``, ``U/g{Hb}`` -> ``U/g Hb``,
    ``um3`` -> ``µm³``. Purely cosmetic: the result is not a UCUM code and
    must not be stored or compared as one.
    """
    text = re.sub(
        r"10\*(-?\d+)", lambda m: "10" + m.group(1).translate(_TO_SUPERSCRIPT), unit
    )
    text = text.replace("[IU]", "IU").replace("[arb'U]", "U").replace("m[Hg]", "mHg")
    text = re.sub(r"\((\d+)\.([A-Za-z]+)\)", r"\1 \2", text)
    text = re.sub(r"\{([^{}]*)\}", lambda m: " " + m.group(1).replace("_", " "), text)
    text = text.replace("/ ", "/").strip()
    text = re.sub(r"(?<![A-Za-z])u(?=(?:mol|kat|IU|[gLlmUs])(?![a-z]))", "µ", text)
    text = re.sub(
        r"(?<=[A-Za-z])([23])(?![\d.,])",
        lambda m: m.group(1).translate(_TO_SUPERSCRIPT),
        text,
    )
    return re.sub(r"(?<=[A-Za-z)])\.(?=[A-Za-z(])", "·", text)
