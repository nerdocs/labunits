# Data pipeline

The runtime library never touches the network. Instead, `analytes.json`
is generated **offline** by the scripts in `scripts/` and shipped inside
the package.

This page explains how the pipeline works, so that you can rebuild
`analytes.json` when the upstream sources change.

## Inputs

| File                                                    | Purpose                                                      |
|---------------------------------------------------------|--------------------------------------------------------------|
| `scripts/Clinical Laboratory Reference Values.html`     | Scraped HTML table from AccessMedicine (units, factors, reference ranges). |
| `scripts/Loinc.csv`                                     | Upstream LOINC reference table — source of LOINC numbers.    |
| `scripts/loinc_part.csv`                                | LOINC "part" file; supplements component lookups.            |

See `scripts/README.md` for the provenance of the AccessMedicine file
and its download date.

## Matching strategy

For each row of the HTML table the pipeline needs to assign a LOINC
code. `scripts/parse_lab_values.py` does this in two stages:

1. **Exact match** against the LOINC `COMPONENT` column.
2. If no exact hit: **fuzzy match** via
   [`thefuzz`](https://github.com/seatgeek/thefuzz) with a threshold of
   `FUZZY_MATCH_RATIO = 80`.

Analytes that match below the threshold are written into the output
with an empty `loinc_num` and a warning on stdout — they are candidates
for manual review.

## Output

Running the script as `__main__` writes the result to
`src/labunits/data/analytes.json`:

```bash
uv run python scripts/parse_lab_values.py
```

After regeneration, re-run the tests:

```bash
uv run --group test pytest
```

## Models

`scripts/models.py` defines the pydantic models used during parsing:

- `Analyte` — one row of the table; serialised by `Analyte.to_json()`.
- `AnalyteRange` — reference interval (`lower_limit`, `upper_limit`, `text`).
- `Specimen` — specimen id + human-readable name.

Serialisation is flat and deterministic: the JSON produced by
`to_json()` is the exact shape consumed by the runtime library.

## Why keep the pipeline as dev-only dependencies?

The upstream parsers need `beautifulsoup4`, `thefuzz` and `pydantic`.
The runtime library does not — it only reads the already-generated
JSON. Keeping these packages in the `dev` dependency group means that
downstream users who merely `pip install labunits` don't drag those
transitive dependencies along.
