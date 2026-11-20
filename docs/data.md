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

The key is the LOINC number as a string (e.g. `"5568-1"`) — the term for
results in the **traditional** unit. LOINC codes are the canonical
identifier throughout the library — names are only resolution
conveniences.

## Analyte entry

Example (Acetone):

```json
"5568-1": {
  "si_loinc_num": "14582-1",
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
| `name`                               | `str`                      | Full analyte name as found in the AccessMedicine reference table.                |
| `specimen`                           | `list[str]`                | Specimen IDs — e.g. `serum`, `plasma`, `red_blood_cells`.                        |
| `si_loinc_num`                       | `str \| null`              | LOINC term for results in the SI unit — see below.                               |
| `traditional_units`                  | `str`                      | UCUM code, e.g. `mg/dL`, `ug/(24.h)`, `meq/L`.                                   |
| `si_units`                           | `str`                      | UCUM code, e.g. `mmol/L`, `umol/L`, `ukat/L`.                                    |
| `conversion_factor`                  | `float`                    | Numeric traditional↔SI factor. `1.0` when the units are identical.               |

## Two LOINC codes per analyte

LOINC has one term per *property*: serum creatinine as a mass
concentration (mg/dL) is `2160-0`, as a substance concentration (µmol/L)
it is `14682-9`. Each entry therefore carries both:

- The key — the term matching `traditional_units`.
- `si_loinc_num` — the term matching `si_units`: the sibling term with the
  same component, system, time aspect and method. It equals the key
  when one term covers both units (`g/dL` ↔ `g/L`, `U/L` ↔ `ukat/L`,
  `meq/L` ↔ `mmol/L`) and is `null` when LOINC has no such term.

The API resolves either code to the same record. A code that is itself a
key always means that record: magnesium ships as `19123-9` (mg/dL ↔
mmol/L) and as `2601-3` (meq/L ↔ mmol/L); `2601-3` is also the SI side of
the first, but resolves to the second. `factor()` and `convert()` take
the units into account and reach both.

## Units are UCUM codes

`traditional_units` and `si_units` are [UCUM](https://ucum.org) codes,
not the display strings of the source table — plain ASCII, machine
comparable. The translation lives in `scripts/ucum_units.json`.
Conventions:

- `µ` is written `u` (`umol/L`, `ug/dL`, `ukat/L`).
- Per-day rates are written `/(24.h)` on both sides (`g/(24.h)` ↔
  `mmol/(24.h)`), as LOINC does.
- Percentages are `%`, fractions of 1 are the UCUM unity `1`.
- International units are `[IU]` (`u[IU]/mL`, `k[IU]/L`).
- "of hemoglobin" on a content is an annotation: `U/g{Hb}`.

## Notes on individual codes

A few assignments deserve a word, because the obvious code is not the
one shipped:

- **Acetylcholinesterase → `2099-0`** (*Cholinesterase in Red Blood
  Cells*). LOINC has no separate "acetylcholinesterase" term for
  erythrocytes; the RBC cholinesterase term *is* the true (acetyl-)
  cholinesterase assay, as opposed to serum pseudocholinesterase.
- **Lactate dehydrogenase → `14805-6`** (method *pyruvate → lactate*).
  The methodless serum term `2532-0` is marked *DISCOURAGED* by LOINC;
  among the method-specific terms, LOINC's own usage ranking picks
  `14805-6`.
- **Hemoglobin fractions** (HbA1c `4548-4`, HbA2 `4551-8`, HbF `4576-5`,
  methemoglobin `2614-6`, sulfhemoglobin `4685-4`) are pinned manually:
  their LOINC components are named `X/Hemoglobin.total`, which the fuzzy
  matcher rejects. The source's factor `1` for `%` → `Fraction` is
  corrected to `0.01` (see `scripts/source_corrections.json`).

- **Fuzzy matches.** The 19 rows still matched by name similarity (see
  the problem report) were each checked against the LOINC long name; all
  are the intended term. Every other row added since is pinned explicitly
  in `scripts/manual_loinc_mapping.json`.
- **Enzymes** convert `U/L` → `ukat/L` with `0.01667` (1 U = 1 µmol/min,
  so the factor is exactly 1/60); the source prints the rounded `0.017`,
  which is 2 % too high. The source left ALT, alkaline phosphatase and LDH
  in `U/L`; they are converted like the others.
- **Hemoglobin, MCH, MCHC** are listed twice in the source, once converted
  to mass units (`g/L`) and once to amount of substance (`mmol/L`, per
  iron atom, 16114 g/mol). Both would sit on the same LOINC, and a record
  carries one unit pair, so only the `mmol/L` conversion is stored; `g/L`
  is reached by prefix scaling (`convert(14, "718-7", "g/dL", "g/L")`).
- **Hematology indices** (MCH `28539-5`, MCHC `28540-3`, MCV `30428-7`)
  are LOINC terms of the red cells (`SYSTEM = RBC`), although the source
  names whole blood as specimen.
- **Coagulation activities and protein fractions** only exist as
  method-specific terms (clotting or chromogenic assay, electrophoresis).

## Names

`name` is the analyte, not the source's row label. Everything that only
describes a reference population or situation is dropped — sex, cycle
phase, age group, smoker, therapeutic/toxic, time of day, risk category,
panel header — because labunits ships no reference intervals. Rows that
thereby describe the same record are merged (testosterone male/female,
the five LDL risk categories). The mapping is
`scripts/analyte_names.json`.

A name is not unique: creatinine, calcium, glucose and others ship once
per specimen. Such a name raises `ValueError` listing the LOINC codes.

## Specimens

`specimen` lists the materials the source names for the record: `serum`,
`plasma`, `whole_blood`, `arterial_blood`, `venous_blood`,
`red_blood_cells`, `urine`, `urine_24_h`, `csf`. Every rate per 24 hours
is a `urine_24_h` record.

## Rows left out on purpose

33 of the 474 source rows are not shipped:

- **No LOINC term for the traditional unit:** alanine, α-aminobutyric
  acid, arginine, asparagine, aspartic acid and citrulline exist in LOINC
  only as amount of substance, not as mass concentration; lead has no
  whole-blood mass term; no term for vitamin K, β-carotene, arterial pH or
  thyroxine-binding capacity.
- **The factor does not belong to the named substance:** ammonia (factor
  of ammonia nitrogen), bupropion and vitamin B1 (factor of the
  hydrochloride salt), vitamin B6 (factor of pyridoxal phosphate),
  methsuximide (factor of normethsuximide), niacin (10 % off nicotinic
  acid).
- **Not a conversion of one defined quantity:** creatinine clearance,
  D-dimer (FEU or DDU units), von Willebrand factor (antigen or
  activity), fecal fat, the evening cortisol row (a percentage of the
  morning value), the HbA1c "diagnosis" row.
- **Second conversion on the same LOINC:** hemoglobin, MCH and MCHC in
  mass units (see above; available through prefix scaling).

## What's *not* in the data

- **No reference intervals, no flags, no interpretation** — by design.
  The pipeline reads the source's reference intervals only to cross-check
  the conversion factors; they are never shipped. `labunits` converts
  units, nothing more (see [Intended use](index.md#intended-use)).
- **No full units grammar.** Units are UCUM codes; the library parses
  only the subset laboratory results use, to scale between prefixes (see
  [API](api.md#units-labunitsucum)).
- **No uncertainty or precision metadata.**

## Loading behaviour

- `_load_data()` reads the file exactly once and caches it in the
  module-level `_analytes_data` dict.
- On first lookup, `_ensure_indexes()` builds two derived dicts —
  `_si_loinc_index` (SI-side LOINC → keys) and `_name_index` (name → all
  LOINCs carrying it) — so
  that lookups are **O(1)** instead of O(n). The `Analyte` records
  returned by `analytes()` are built in the same step and reused.
  The indexes are rebuilt automatically when the data dict is
  replaced (detected by object identity), which keeps tests straightforward.
- Tests can replace the data cache via `monkeypatch.setattr` — see
  `tests/conftest.py` for the pattern.
- Consumers enumerate the data via `analytes()` (see [API](api.md));
  `_load_data()` and the JSON file are internal.

## Editing the data

**Do not hand-edit `analytes.json`.** It is a build artefact of the
[data pipeline](pipeline.md). Edits get overwritten the next time the
pipeline runs.
