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

Every `analyte` argument accepts the LOINC code of either unit side, or a
unique name — see
[Identifying an analyte](getting-started.md#identifying-an-analyte).

---

## `to_si_unit(value, analyte) -> float`

Convert a concentration from its traditional unit to its SI unit.

| Parameter | Type                 | Meaning                                              |
|-----------|----------------------|------------------------------------------------------|
| `value`   | `float`              | Concentration in the analyte's traditional unit.     |
| `analyte` | `LoincNum \| str`    | LOINC code (preferred), abbreviation, or full name.  |

**Returns** `float` — value in the analyte's SI unit.
`inf`, `-inf` and `nan` pass through unchanged.

**Raises** `ValueError` — if the identifier cannot be resolved or a name is ambiguous.

```python
>>> to_si_unit(1.0, "5568-1")   # Acetone, 1 mg/dL
0.172
>>> to_si_unit(4.0, "Albumin")    # 4 g/dL -> 40 g/L
40.0
>>> to_si_unit(1.0, "14582-1")  # same record via the SI-side LOINC
0.172
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

**Raises** `ValueError` — if the identifier cannot be resolved or a name is ambiguous.

```python
>>> to_traditional_unit(0.172, "5568-1")   # mmol/L -> mg/dL
1.0
>>> to_traditional_unit(40.0, "Albumin")     # g/L -> g/dL
4.0
```

---

## `si_unit(analyte) -> str`

Return the SI unit of the given analyte as a [UCUM](https://ucum.org) code.

```python
>>> si_unit("Acetone")
'mmol/L'
>>> si_unit("1751-7")   # Albumin
'g/L'
```

---

## `traditional_unit(analyte) -> str`

Return the traditional unit of the given analyte as a UCUM code.

```python
>>> traditional_unit("Acetone")
'mg/dL'
>>> traditional_unit("1751-7")
'g/dL'
>>> si_unit("2160-0")              # Creatinine: UCUM writes µ as "u"
'umol/L'
>>> traditional_unit("2162-6")     # Creatinine, 24 h urine
'g/(24.h)'
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
| `si_loinc_num`       | `LoincNum \| None` | `"14582-1"`            |
| `name`               | `str`             | `"Acetone"`            |
| `specimen`           | `tuple[str, ...]` | `("serum", "plasma")`  |
| `traditional_unit`   | `str` (UCUM)      | `"mg/dL"`              |
| `si_unit`            | `str` (UCUM)      | `"mmol/L"`             |
| `conversion_factor`  | `float`           | `0.172`                |

`loinc_num` is the LOINC term for results in the traditional unit,
`si_loinc_num` the term for results in the SI unit. Both are equal when
one term covers both units (`g/dL` and `g/L` are both mass
concentrations); `si_loinc_num` is `None` when LOINC has no term for the
SI side.

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
| Name matching several records      | `ValueError("Ambiguous analyte name: ...")`, listing the candidate LOINC codes |
| `value` is `nan` / `±inf`          | Returned unchanged                              |
| `value` is any other float         | Converted                                       |
| `value` is non-numeric             | `TypeError` (raised by the `*` / `/` operator)  |

`labunits` deliberately keeps its error model thin: it doesn't validate
physiological ranges, doesn't check units against a grammar, and doesn't
try to recover from bad inputs. It's a lookup table plus two
multiplications.
