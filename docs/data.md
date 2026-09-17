# Data model

The library ships a single data file: `src/labunits/data/analytes.json`.
It is loaded lazily on first use, cached in a module-level dict, and
never written to.

## Top-level shape

```json
{
  "<loinc-num>": { ...analyte entry... },
  "<loinc-num>": { ...analyte entry... }
}
```

The key is the LOINC number as a string (e.g. `"5568-1"`). LOINC codes
are the canonical identifier throughout the library — names and
abbreviations are only resolution conveniences.

## Analyte entry

Example (Acetone):

```json
"5568-1": {
  "loinc_num": "5568-1",
  "name": "Acetone",
  "specimen": ["serum", "plasma"],
  "traditional_units": "mg/dL",
  "conversion_factor": 0.172,
  "si_units": "mmol/L"
}
```

### Fields

| Field                                | Type                       | Notes                                                                            |
|--------------------------------------|----------------------------|----------------------------------------------------------------------------------|
| `loinc_num`                          | `str`                      | Duplicate of the outer key; kept for round-trippable records.                    |
| `name`                               | `str`                      | Full analyte name as found in the AccessMedicine reference table.                |
| `specimen`                           | `list[str]`                | Specimen IDs — e.g. `serum`, `plasma`, `red_blood_cells`.                        |
| `traditional_units`                  | `str`                      | e.g. `mg/dL`, `g/dL`, `U/L`.                                                     |
| `si_units`                           | `str`                      | e.g. `mmol/L`, `g/L`, `μKat/L`.                                                  |
| `conversion_factor`                  | `float`                    | Numeric traditional↔SI factor. `1.0` when the units are identical.               |

## What's *not* in the data

- **No abbreviations** (yet). The API accepts abbreviations as a lookup
  alias, but the current data set has none. The `_resolve_analyte_identifier`
  code path is ready for them.
- **No reference intervals, no flags, no interpretation** — by design.
  The pipeline reads the source's reference intervals only to cross-check
  the conversion factors; they are never shipped. `labunits` converts
  units, nothing more (see [Intended use](index.md#intended-use)).
- **No units grammar.** Units are opaque strings — the library never
  parses them.
- **No uncertainty or precision metadata.**

## Loading behaviour

- `_load_data()` reads the file exactly once and caches it in the
  module-level `_analytes_data` dict.
- On first lookup, `_ensure_indexes()` builds two derived dicts —
  `_name_index` (name → LOINC) and `_abbrev_index` (abbreviation →
  LOINC) — so that name-based lookups are **O(1)** instead of O(n).
  The indexes are rebuilt automatically when the data dict is
  replaced (detected via `id()`), which keeps tests straightforward.
- Tests can replace the data cache via `monkeypatch.setattr` — see
  `tests/conftest.py` for the pattern.

## Editing the data

**Do not hand-edit `analytes.json`.** It is a build artefact of the
[data pipeline](pipeline.md). Edits get overwritten the next time the
pipeline runs.
