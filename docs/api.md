# API reference

All public functions live in `labunits.converters`. Import them directly:

```python
from labunits.converters import (
    to_si_unit,
    to_traditional_unit,
    si_unit,
    traditional_unit,
    conversion_factor,
    analytes,
)
```

The type alias `LoincNum` is a plain `str`; it signals at boundaries
that a string is expected to be a LOINC code.

---

## `to_si_unit(value, analyte) -> float`

Convert a concentration from its traditional unit to its SI unit.

| Parameter | Type                 | Meaning                                              |
|-----------|----------------------|------------------------------------------------------|
| `value`   | `float`              | Concentration in the analyte's traditional unit.     |
| `analyte` | `LoincNum \| str`    | LOINC code (preferred), abbreviation, or full name.  |

**Returns** `float` — value in the analyte's SI unit.
`inf`, `-inf` and `nan` pass through unchanged.

**Raises** `ValueError` — if the identifier cannot be resolved.

```python
>>> to_si_unit(1.0, "5568-1")   # Acetone, 1 mg/dL
0.172
>>> to_si_unit(4.0, "Albumin")    # 4 g/dL -> 40 g/L
40.0
```

---

## `to_traditional_unit(value, analyte) -> float`

Convert a concentration from its SI unit to its traditional unit.

| Parameter | Type                 | Meaning                                              |
|-----------|----------------------|------------------------------------------------------|
| `value`   | `float`              | Concentration in the analyte's SI unit.              |
| `analyte` | `LoincNum \| str`    | LOINC code (preferred), abbreviation, or full name.  |

**Returns** `float` — value in the analyte's traditional unit.
`inf`, `-inf` and `nan` pass through unchanged.

**Raises** `ValueError` — if the identifier cannot be resolved.

```python
>>> to_traditional_unit(0.172, "5568-1")   # mmol/L -> mg/dL
1.0
>>> to_traditional_unit(40.0, "Albumin")     # g/L -> g/dL
4.0
```

---

## `si_unit(analyte) -> str`

Return the SI unit string for the given analyte.

```python
>>> si_unit("Acetone")
'mmol/L'
>>> si_unit("1751-7")   # Albumin
'g/L'
```

---

## `traditional_unit(analyte) -> str`

Return the traditional unit string for the given analyte.

```python
>>> traditional_unit("Acetone")
'mg/dL'
>>> traditional_unit("1751-7")
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

## `analytes() -> list[Analyte]`

Return every shipped analyte as an `Analyte` record. This is the
supported way to enumerate the data set — to build a picker, check
coverage, or export a mapping — without touching `analytes.json`.

`Analyte` is a frozen dataclass:

| Field                | Type              | Example                |
|----------------------|-------------------|------------------------|
| `loinc_num`          | `LoincNum`        | `"5568-1"`             |
| `name`               | `str`             | `"Acetone"`            |
| `specimen`           | `tuple[str, ...]` | `("serum", "plasma")`  |
| `traditional_unit`   | `str`             | `"mg/dL"`              |
| `si_unit`            | `str`             | `"mmol/L"`             |
| `conversion_factor`  | `float`           | `0.172`                |

There are deliberately **no reference intervals** on the record — see
[Design decisions](design.md#no-reference-intervals).

```python
>>> for a in analytes():
...     print(a.loinc_num, a.name, a.traditional_unit, "->", a.si_unit)
5568-1 Acetone mg/dL -> mmol/L
...
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
