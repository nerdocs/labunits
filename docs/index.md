# labunits

A small, dependency-free Python library that converts laboratory analyte
values between **traditional units** (e.g. `mg/dL`) and **SI units**
(e.g. `mmol/L`), keyed by [LOINC](https://loinc.org/) code.

> Why another library? Because there **is no** other Python library for this.
> `labunits` fills that gap.

## At a glance

```python
from labunits.converters import to_si_unit, to_traditional_unit, si_unit

# Acetone: 1 mg/dL -> mmol/L
to_si_unit(1.0, "109547-0")          # 0.172
to_si_unit(1.0, "Acetone")           # same — lookup by name also works
si_unit("Acetone")                   # "mmol/L"

# Round-trip
to_traditional_unit(0.172, "109547-0")   # 1.0
```

## What this library does — and doesn't do

| Does                                                   | Doesn't                                   |
| ------------------------------------------------------ | ----------------------------------------- |
| Convert a numeric value between traditional and SI    | Interpret free-text lab reports          |
| Look up units and conversion factor by LOINC/name     | Fetch LOINC data at runtime               |
| Ship with a curated analyte table (see [Data](data.md))| Validate physiological plausibility       |
| Return `inf`/`-inf`/`nan` unchanged                   | Handle age- or sex-specific reference ranges |

All data is shipped inside the package; `labunits` makes **no network and
no filesystem I/O** beyond a single one-time read of the bundled
`analytes.json`.

## Documentation

- **[Getting started](getting-started.md)** — install & first conversion.
- **[API reference](api.md)** — every public function, with examples.
- **[Data model](data.md)** — what's in `analytes.json` and how it's keyed.
- **[Data pipeline](pipeline.md)** — how `analytes.json` is generated from
  LOINC + AccessMedicine sources.
- **[Design decisions](design.md)** — why LOINC keys, why a factor,
  how `nan`/`inf` are handled.

## License

[MIT](https://github.com/nerdocs/labunits/blob/main/LICENSE.md). Attribution appreciated.
