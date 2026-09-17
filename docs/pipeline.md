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

Both files are licensed third-party content and are **not** part of the
repository; `scripts/README.md` says where to download them.

## Matching strategy

For each row of the HTML table the pipeline needs to assign a LOINC
code. `scripts/parse_lab_values.py` does this in stages:

0. **LOINC pre-filter.** Only *active*, *quantitative* (`SCALE_TYP = Qn`)
   result terms are loaded; order-entry terms (`CLASS = LABORDERS.*`),
   ordinal/nominal and deprecated terms are dropped once, up front.
1. **Eligibility per row.** A term is eligible only if its `SYSTEM`
   matches one of the row's specimens (`_SPECIMEN_SYSTEMS`) and its
   `PROPERTY` can carry the row's traditional unit (`_UNIT_PROPERTIES`,
   e.g. `mg/dL` → `MCnc`, `mEq/L` → `SCnc`, `U/L` → `CCnc`). This is what
   keeps serum magnesium from landing on a stool-magnesium term.
2. **Manual pin** from `scripts/manual_loinc_mapping.json` — wins
   unconditionally, but a pin that fails the eligibility filters is
   listed in the problem report. Keys are `Name`, `Name@specimen` or
   `Name@specimen@unit`; the most specific one wins.
3. **Exact match** of the normalized name against the LOINC `COMPONENT`
   column. Several eligible hits are ranked by LOINC's own
   `COMMON_TEST_RANK`, so the commonly used term wins over method-specific
   variants.
4. **Fuzzy match** via [`thefuzz`](https://github.com/seatgeek/thefuzz)
   with a threshold of `FUZZY_MATCH_RATIO = 80`, guarded by structural
   checks (roman numerals, digits, meaning-flipping qualifiers such as
   `free`, `total`, `Ag`).

Analytes without a match are not written to the output; they are listed
in the problem report as candidates for manual review.

## Source corrections

`scripts/source_corrections.json` overrides individual fields of rows
that are wrong in the AccessMedicine table itself (a factor off by 10×,
a unit typo). Every entry documents its evidence in `why`. Corrections
are applied before the consistency check below, so a correction must make
the row agree with its own reference intervals.

## Safety checks

- **Factor consistency.** The source prints every reference interval in
  both unit systems, so `traditional × factor` must reproduce the SI
  interval up to printed rounding. Violations are reported under
  *FACTOR INCONSISTENT* and must be resolved before shipping — this is
  how source errors (e.g. a factor off by 10×) surface.
- **No silent overwrite.** Two *different* rows resolving to the same
  LOINC abort the run. Verbatim repeats (the source lists the amino
  acids twice) are collapsed.

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
