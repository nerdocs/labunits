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

# Serum glucose reported as 90 mg/dL -> mmol/L
si_value = to_si_unit(90.0, "Glucose")

# And back
trad_value = to_traditional_unit(si_value, "Glucose")
```

## Identifying an analyte

Every public function accepts an analyte identifier (as the first
argument for lookup helpers, or as the second argument for the
conversion functions) and resolves it through the same lookup chain:

1. **LOINC code** — preferred, unambiguous. Example: `"5568-1"`.
2. **Full analyte name** — case-insensitive. Example: `"Acetone"`,
   `"acetone"`, `"ACETONE"`.
3. **Abbreviation** — reserved for future use; the current shipped data
   set does not contain abbreviations yet, but the API accepts them.

If the identifier can't be resolved, a `ValueError` is raised:

```python
>>> si_unit("definitely-not-a-real-analyte")
ValueError: Unknown analyte identifier: definitely-not-a-real-analyte
```

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
