# API reference

All public functions live in `labunits.converters`. Import them directly:

```python
from labunits.converters import (
    to_si_unit,
    to_traditional_unit,
    si_unit,
    traditional_unit,
    conversion_factor,
    factor,
    convert,
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
| `analyte` | `LoincNum \| str`    | LOINC code (preferred) or full name.                 |

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
| `analyte` | `LoincNum \| str`    | LOINC code (preferred) or full name.                 |

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

### Computing in `Decimal`

The factor is a `float` and prints exactly as it is stored, so the
loss-free way into `Decimal` is through `str`:

```python
>>> Decimal(str(conversion_factor("2160-0")))
Decimal('88.4')
>>> Decimal(conversion_factor("2160-0"))     # binary approximation — avoid
Decimal('88.400000000000005684341886080801486968994140625')
```

The conversion functions themselves compute in `float`; passing a
`Decimal` value raises `TypeError`. Fetch the factor as above (or via
[`factor()`](#factoranalyte-from_unit-to_unit-float)) and multiply in
`Decimal` yourself.

---

## `factor(analyte, from_unit, to_unit) -> float`

Return the factor for a pair of units, given as UCUM codes:
`value_in_to_unit = value_in_from_unit * factor`. The direction follows
from the units, so you never have to know which side is the traditional
one — useful when results arrive in whatever unit the laboratory used.

| Units                              | Result                         |
|------------------------------------|--------------------------------|
| traditional → SI                   | `conversion_factor(analyte)`   |
| SI → traditional                   | `1 / conversion_factor(analyte)` |
| the same unit of the analyte twice | `1.0`                          |
| anything else                      | `ValueError` naming the known units |

```python
>>> factor("2160-0", "mg/dL", "umol/L")     # Creatinine
88.4
>>> factor("14682-9", "umol/L", "mg/dL")    # same record, SI-side LOINC
0.011312217194570135
>>> factor("2160-0", "mg/dL", "mg/dL")
1.0
>>> factor("2160-0", "g/L", "umol/L")
ValueError: Cannot convert 2160-0 from g/L to umol/L; known units: mg/dL <-> umol/L
```

A unit may also be a prefix variant of one of the analyte's units; the
scaling is then included, on either side of the record's factor:

```python
>>> factor("2160-0", "mg/dL", "mg/L")       # same side: pure scaling
10.0
>>> factor("2160-0", "g/L", "umol/L")       # g/L -> mg/dL (x100) -> umol/L (x88.4)
8840.0
>>> convert(14.0, "718-7", "g/dL", "g/L")   # hemoglobin is stored as g/dL <-> mmol/L
140.0
```

Only prefixes, powers of ten and denominators are scaled (see
[`ucum_factor()`](#ucum_factorfrom_unit-to_unit-float)). A unit of
another kind — `meq/L` for an analyte kept in `mg/dL`, `U/L` for one
kept in `mg/dL` — raises `ValueError`.

Where one LOINC code belongs to two records, the units decide: magnesium
`2601-3` converts `meq/L` ↔ `mmol/L` as well as `mg/dL` ↔ `mmol/L`.

---

## `convert(value, analyte, from_unit, to_unit) -> float`

Convert a value between the analyte's two units; arguments and errors as
for `factor()`. `inf`, `-inf` and `nan` pass through unchanged.

```python
>>> convert(1.2, "2160-0", "mg/dL", "umol/L")
106.08
>>> convert(106.08, "14682-9", "umol/L", "mg/dL")
1.2
```

---

## Units: `labunits.ucum`

Three helpers that work on unit codes alone, without an analyte:

```python
from labunits.ucum import ucum_factor, normalise, display
```

### `ucum_factor(from_unit, to_unit) -> float`

Factor between two UCUM units of the same kind of quantity:
`value_in_to_unit = value_in_from_unit * factor`.

```python
>>> ucum_factor("mg/dL", "g/L")
0.01
>>> ucum_factor("umol/L", "mmol/L")
0.001
>>> ucum_factor("10*3/uL", "10*9/L")
1.0
>>> ucum_factor("mg/dL", "mmol/L")
ValueError: Cannot convert mg/dL to mmol/L: different kinds of quantity
```

| Converts                                                  | Refuses (`ValueError`)                         |
|-----------------------------------------------------------|------------------------------------------------|
| metric prefixes: `mg` ↔ `g`, `umol` ↔ `mmol`              | mass ↔ amount of substance: `mg/dL` ↔ `mmol/L` |
| volumes: `/dL` ↔ `/L` ↔ `/mL`, `um3` ↔ `fL`               | `meq` ↔ `mmol`, `mosm` ↔ `mmol`                |
| powers of ten: `10*3/uL` ↔ `10*9/L`, `%` ↔ `1`            | `U` ↔ `kat` ↔ `[IU]` ↔ `[arb'U]`               |
| time: `/min` ↔ `/s`, `/(24.h)` ↔ `/d`                     | annotated ↔ plain: `g{Hb}` ↔ `g`               |

The refused conversions need the analyte; use `factor()` for them. Only
the subset of UCUM that laboratory results use is understood; anything
else raises `ValueError("Not a UCUM unit labunits understands: ...")`.

### `normalise(unit_text) -> str | None`

Suggest the UCUM code for a unit as a laboratory writes it. Returns
`None` when the text is not recognised or is ambiguous.

```python
>>> normalise("mg/dl")
'mg/dL'
>>> normalise("µmol/l")
'umol/L'
>>> normalise("G/l")          # 10^9 per litre
'10*9/L'
>>> normalise("IE/l")
'[IU]/L'
>>> normalise("g/24h")
'g/(24.h)'
>>> normalise("u/l")          # units or micro?
None
```

It covers spelling variants and abbreviations of units — litre as `l`,
`µ`, `mcg`, powers of ten (`10^9`, `10³`), count shorthands (`G/l`,
`T/l`, `Tsd/µl`, `Mio/µl`), `IE`/`IU`, `mval`, `mmHg`, `sec`, `24h` —
not written-out words. A code that is already UCUM comes back unchanged.

**The result is a suggestion.** Show it to a person to confirm; never
store it unseen. Laboratory spellings are not a defined language.

### `display(unit) -> str`

Render a UCUM code for people to read. Cosmetic only — the result is
not a UCUM code and must not be stored or compared as one.

```python
>>> display("10*3/uL")
'10³/µL'
>>> display("umol/L")
'µmol/L'
>>> display("mg/(24.h)")
'mg/24 h'
>>> display("U/g{Hb}")
'U/g Hb'
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
| Units of another kind than the analyte's (`factor`, `convert`) | `ValueError("Cannot convert ...")`, naming the known units |
| Name matching several records      | `ValueError("Ambiguous analyte name: ...")`, listing the candidate LOINC codes |
| `value` is `nan` / `±inf`          | Returned unchanged                              |
| `value` is any other float         | Converted                                       |
| `value` is non-numeric             | `TypeError` (raised by the `*` / `/` operator)  |

`labunits` deliberately keeps its error model thin: it doesn't validate
physiological ranges, doesn't check units against a grammar, and doesn't
try to recover from bad inputs. It's a lookup table plus two
multiplications.
