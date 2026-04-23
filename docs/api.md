# API reference

All public functions live in `labunits.converters`. Import them directly:

```python
from labunits.converters import (
    to_si_unit,
    to_traditional_unit,
    si_unit,
    traditional_unit,
    conversion_factor,
)
```

The type alias `LoincNum` is a plain `str`; it signals at boundaries
that a string is expected to be a LOINC code.

---

## `to_si_unit(analyte, value) -> float`

Convert a concentration from its traditional unit to its SI unit.

| Parameter | Type                 | Meaning                                              |
|-----------|----------------------|------------------------------------------------------|
| `analyte` | `LoincNum \| str`    | LOINC code (preferred), abbreviation, or full name.  |
| `value`   | `float`              | Concentration in the analyte's traditional unit.     |

**Returns** `float` — value in the analyte's SI unit.
`inf`, `-inf` and `nan` pass through unchanged.

**Raises** `ValueError` — if the identifier cannot be resolved.

```python
>>> to_si_unit("109547-0", 1.0)   # Acetone, 1 mg/dL
0.172
>>> to_si_unit("Albumin", 4.0)    # 4 g/dL -> 40 g/L
40.0
```

---

## `to_traditional_unit(analyte, value) -> float`

Convert a concentration from its SI unit to its traditional unit.

| Parameter | Type                 | Meaning                                              |
|-----------|----------------------|------------------------------------------------------|
| `analyte` | `LoincNum \| str`    | LOINC code (preferred), abbreviation, or full name.  |
| `value`   | `float`              | Concentration in the analyte's SI unit.              |

**Returns** `float` — value in the analyte's traditional unit.
`inf`, `-inf` and `nan` pass through unchanged.

**Raises** `ValueError` — if the identifier cannot be resolved.

```python
>>> to_traditional_unit("109547-0", 0.172)   # mmol/L -> mg/dL
1.0
>>> to_traditional_unit("Albumin", 40.0)     # g/L -> g/dL
4.0
```

---

## `si_unit(analyte) -> str`

Return the SI unit string for the given analyte.

```python
>>> si_unit("Acetone")
'mmol/L'
>>> si_unit("100158-5")   # Albumin
'g/L'
```

---

## `traditional_unit(analyte) -> str`

Return the traditional unit string for the given analyte.

```python
>>> traditional_unit("Acetone")
'mg/dL'
>>> traditional_unit("100158-5")
'g/dL'
```

---

## `conversion_factor(analyte) -> float`

Return the traditional→SI conversion factor. Useful if you need the raw
number (e.g. for display, or to build your own vectorised conversion).

The relationship is:

```
si_value = traditional_value * factor
traditional_value = si_value / factor
```

```python
>>> conversion_factor("Acetone")
0.172
>>> conversion_factor("Albumin")
10.0
```

---

## Error model

| Situation                          | Behaviour                                       |
|------------------------------------|-------------------------------------------------|
| Unknown identifier                 | `ValueError("Unknown analyte identifier: ...")` |
| `value` is `nan` / `±inf`          | Returned unchanged                              |
| `value` is any other float         | Converted                                       |
| `value` is non-numeric             | `TypeError` (raised by the `*` / `/` operator)  |

`labunits` deliberately keeps its error model thin: it doesn't validate
physiological ranges, doesn't check units against a grammar, and doesn't
try to recover from bad inputs. It's a lookup table plus two
multiplications.
