# Getting started

## Requirements

- Python ≥ 3.10
- No runtime dependencies

## Install

```bash
pip install labunits
```

Or, inside a `uv` project:

```bash
uv add labunits
```

## Your first conversion

```python
from labunits.converters import to_si_unit, to_traditional_unit

# Serum glucose (LOINC 2345-7) reported as 90 mg/dL -> mmol/L
si_value = to_si_unit(90.0, "2345-7")

# And back
trad_value = to_traditional_unit(si_value, "2345-7")
```

## Identifying an analyte

Every public function accepts an analyte identifier (as the first
argument for lookup helpers, or as the second argument for the
conversion functions) and resolves it through the same lookup chain:

1. **LOINC code** — preferred, unambiguous. Example: `"5568-1"`. Both the
   code of the traditional-unit term and the code of the SI-unit term
   work: `"2160-0"` (creatinine, mg/dL) and `"14682-9"` (creatinine,
   µmol/L) resolve to the same record.
2. **Full analyte name** — case-insensitive. Example: `"Acetone"`,
   `"acetone"`, `"ACETONE"`. A name shared by several records is
   rejected rather than guessed (see below).
3. **Abbreviation** — reserved for future use; the current shipped data
   set does not contain abbreviations yet, but the API accepts them.

If the identifier can't be resolved, a `ValueError` is raised:

```python
>>> si_unit("definitely-not-a-real-analyte")
ValueError: Unknown analyte identifier: definitely-not-a-real-analyte
```

The same happens for a name that is not unique — the message lists the
LOINC codes to choose from:

```python
>>> conversion_factor("Creatinine")
ValueError: Ambiguous analyte name: Creatinine — use a LOINC code: 2160-0 (serum/plasma, mg/dL); 2162-6 (urine, g/(24.h))
```

Whichever identifier you pass, the direction of a conversion is set by
the function, never by the code: `to_si_unit()` always expects a value in
the traditional unit, `to_traditional_unit()` a value in the SI unit.

If you don't know which side a value is on, name the units instead:

```python
from labunits.converters import convert

convert(106.08, "14682-9", "umol/L", "mg/dL")   # 1.2
```

## Units

`si_unit()` and `traditional_unit()` return [UCUM](https://ucum.org)
codes (`"umol/L"`, `"g/(24.h)"`, `"meq/L"`), so they can be compared with
the units of your own data. See [Data model](data.md#units-are-ucum-codes).

**Recommendation:** use LOINC codes in production code. Names are
convenient for interactive use but are not stable identifiers —
spelling, capitalisation, or renaming in the upstream reference table
can break name-based lookups between releases.

## Special float values

`inf`, `-inf` and `nan` are propagated through the conversion functions
unchanged. This lets you feed sentinel values (e.g. for "above detection
limit") through a conversion pipeline without special-casing them.

```python
import math
from labunits.converters import to_si_unit

to_si_unit(float("inf"), "Acetone")       # inf
math.isnan(to_si_unit(float("nan"), "Acetone"))  # True
```
