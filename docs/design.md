# Design decisions

A short log of *why* `labunits` looks the way it does. Useful when you
need to change something and wonder whether the current design is
load-bearing or incidental.

## LOINC as the canonical key

Lab values are identified in practice by all of: full name, common
abbreviation, in-house code, and LOINC. Of those, **LOINC is the only
globally stable, internationally maintained identifier** — so every
record is keyed by LOINC number. Names and abbreviations are convenience
aliases at the API boundary; internally everything normalises to LOINC
first. A name that fits several records raises instead of picking one:
a silent pick once turned "Creatinine" into the urine record (×8.84
instead of ×88.4).

LOINC assigns separate terms to one analyte measured as mass and as
substance concentration, so every record knows both codes and resolves by
either (see [Data model](data.md#two-loinc-codes-per-analyte)).

## Units as UCUM codes

Units are shipped as [UCUM](https://ucum.org) codes rather than as the
source's display strings (`μmol/L`, `g/24 h`, `Fraction of 1.0`).
Consumers store and compare units as UCUM; free text would force each of
them to write the same normalisation. The library still does no unit
algebra — the codes are data, not parsed.

## A single conversion factor per analyte

The math is:

```
si_value = traditional_value * conversion_factor
```

This works because each analyte ships with matching pairs of units
(e.g. `mg/dL` ↔ `mmol/L`). There is **no generic unit algebra**; the
library is a lookup table, not a units library. If an analyte is
reported in a unit not covered by its pair, `labunits` cannot help —
that's by design.

## No reference intervals

The upstream table prints a reference interval next to every factor,
and consumers occasionally ask for it. `labunits` does **not** ship it,
on purpose:

- Reference intervals are method- and laboratory-specific; a textbook
  value is the wrong thing to compare a real result against.
- Shipping them would turn a unit converter into something that invites
  clinical interpretation ("is this value abnormal?") — exactly the
  feature set that makes software a medical device. See
  [Intended use](index.md#intended-use).

The pipeline still parses the intervals, but only to cross-check the
factors (`docs/pipeline.md`). Consumers that need reference intervals
should take them from their own laboratory's data.

## Lazy, cached data load

The JSON file is a few dozen kilobytes. We load it:

- **Lazily** — on first call to any public function. Importing the
  library does not touch the disk.
- **Once** — a module-level dict caches the parsed data. All subsequent
  calls are pure dict lookups.
- **Read-only** — nothing in the runtime writes the cache back.

Tests replace the cache via `monkeypatch.setattr(converters,
"_analytes_data", {...})`, giving deterministic, fast test runs without
touching the shipped data file.

## `nan` / `±inf` pass through unchanged

Laboratory results sometimes carry sentinel values: "above detection
limit", "not measurable". Those get encoded as `inf` or `nan` in some
pipelines. Converting them mathematically is nonsense, but raising is
annoying — callers would have to wrap every call. So:

```python
if math.isinf(value) or math.isnan(value):
    return value
return value * factor   # or / factor
```

The sentinel propagates; the caller decides what to do with it.

## No runtime dependencies

The library deliberately has **zero** runtime dependencies. This is a
strong constraint — it means:

- No `pydantic` at runtime, even though the build pipeline uses it.
- No `beautifulsoup4` or `thefuzz` in end-user installs.
- The entire runtime is one small module of standard-library Python.

This keeps `labunits` safe to depend on from very different projects
(EMR backends, bioinformatics scripts, Jupyter notebooks) without
pulling in a dependency forest.

## Public API lives in `converters.py`

`__init__.py` intentionally does **not** re-export anything today.
Importers use explicit paths:

```python
from labunits.converters import to_si_unit
```

This may change later — re-exports are cheap — but the current form
keeps the import surface unambiguous.
