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
   matches one of the row's specimens (`_SPECIMEN_SYSTEMS`), its
   `PROPERTY` can carry the row's traditional unit (`_UNIT_PROPERTIES`,
   e.g. `mg/dL` → `MCnc`, `mEq/L` → `SCnc`, `U/L` → `CCnc`) and its
   `TIME_ASPCT` is `24H` exactly when the row is a 24-hour urine (every
   unit per `24 h` makes the specimen `urine_24_h`), otherwise `Pt`. This
   is what keeps serum magnesium from landing on a stool-magnesium term.
2. **Manual pin** from `scripts/manual_loinc_mapping.json` — wins
   unconditionally, but a pin that fails the eligibility filters is
   listed in the problem report. Keys are `Name`, `Name@specimen` or
   `Name@specimen@unit`; the most specific one wins.
3. **Exact match** of the normalized name against the LOINC `COMPONENT`
   column. Several eligible hits are ranked by LOINC's own
   `COMMON_TEST_RANK`, so the commonly used term wins over method-specific
   variants.
4. **Fuzzy match** via [`thefuzz`](https://github.com/seatgeek/thefuzz)
   with a ratio above `FUZZY_MATCH_RATIO = 80`, guarded by structural
   checks (roman numerals, digits, meaning-flipping qualifiers such as
   `free`, `total`, `Ag`).

Analytes without a match, and rows without a numeric conversion factor,
are not written to the output; they are listed in the problem report as
candidates for manual review.

## Canonical names

`scripts/analyte_names.json` maps a source row name to the analyte name
that is matched and shipped, dropping reference-population qualifiers
(`Digoxin (therapeutic)` → `Digoxin`, `Testosterone, female` →
`Testosterone`). Keys are `Name`, `Name@specimen` or `Name@specimen@unit`
— needed where the source left a sub-row with a bare label such as
`Male`. It is applied after the source corrections and before the manual
pins, so pins are keyed by the canonical name. Rows that end up with the
same LOINC, name, units and factor are merged into one record whose
specimens are the union; any other two rows on one LOINC abort the run.

## SI-side LOINC

The matched term fits the row's *traditional* unit. For the SI unit the
pipeline derives `si_loinc_num`: if the matched term's `PROPERTY` also
fits the SI unit, it is the same term; otherwise the sibling term with
identical `COMPONENT`, `SYSTEM` and `TIME_ASPCT` and a fitting `PROPERTY`
(best `COMMON_TEST_RANK` first). A sibling of the same method wins; a
term of another method is taken only if there is none, and is listed in
the problem report. Rows without any such term get `null` and are listed
as well, as are SI units missing from `_UNIT_PROPERTIES`.

## UCUM units

`scripts/ucum_units.json` maps every unit string of the source to its
UCUM code; `Unit@PROPERTY` overrides the bare unit where the source is
ambiguous (`mU/mL` meaning international units for an `ACnc` term). A
shipped row whose unit is missing from the table aborts the run.

## Source corrections

`scripts/source_corrections.json` overrides individual fields of rows
that are wrong in the AccessMedicine table itself (a factor off by 10×,
a unit typo). Keys are `Name`, or `Name@specimen` when several rows share
a name. Every entry documents its evidence in `why`. Corrections
are applied before the consistency check below, so a correction must make
the row agree with its own reference intervals.

## Safety checks

- **Factor consistency.** The source prints every reference interval in
  both unit systems, so `traditional × factor` must reproduce the SI
  interval up to the rounding of both printed numbers. Violations are
  reported under *FACTOR INCONSISTENT* and must be resolved before
  shipping — this is how source errors (e.g. a factor off by 10×) surface.
- **Molar mass.** A factor that is wrong on both sides of a row passes
  the check above (the source printed calcitriol with 2.6 instead of 2.4
  and a matching interval). For every mass ↔ amount-of-substance pair the
  factor is therefore recomputed from `scripts/molar_masses.json`
  (`mg/dL` → `mmol/L` is `10 / M`); more than 2 % deviation is reported,
  and so is a pair without a molar mass.
- **No silent overwrite.** Two *different* rows resolving to the same
  LOINC abort the run. Verbatim repeats (the source lists the amino
  acids twice) are collapsed. Two rows claiming the same SI-side LOINC
  abort the run as well.

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
