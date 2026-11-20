# Data pipeline inputs

`parse_lab_values.py` turns two upstream files into `src/labunits/data/analytes.json`. Both files are **not**
part of the repository — they are third-party content under their own licences. Download them into this
directory before running the pipeline:

| File                                        | Source                                                                                      |
|---------------------------------------------|---------------------------------------------------------------------------------------------|
| `Loinc.csv`                                 | LOINC table (`LoincTable/Loinc.csv` inside the LOINC release ZIP) from <https://loinc.org/downloads/>. Requires a free LOINC account; use is subject to the [LOINC licence](https://loinc.org/license/). Last used release: 2.81 (2025-08). |
| `Clinical Laboratory Reference Values.html` | AccessMedicine, *Clinical Laboratory Reference Values*, saved as HTML from <https://accessmedicine.mhmedical.com/content.aspx?bookid=1069&sectionid=60775149> (requires institutional access). Downloaded 2025-10-05. |

## Where the numbers come from

The table is the front-matter section *Clinical Laboratory Reference Values* of Michael Laposata (ed.), *Laboratory
Medicine: The Diagnosis of Disease in the Clinical Laboratory*, McGraw-Hill Education, as published on AccessMedicine
(the page's anchor ids, `lapo2_…`, point to the 2nd edition). The section states its own sources:

> This table is compiled from data in the following sources: 1) Tietz NW, ed. Clinical Guide to Laboratory Tests. 3rd
> ed. Philadelphia: WB Saunders Co; 1995; 2) Laposata M. SI Unit Conversion Guide. Boston: NEJM Books; 1992; 3)
> American Medical Association Manual of Style: A Guide for Authors and Editors. 9th ed. Chicago: AMA; 1998:486–503.
> Copyright 1998, American Medical Association; 4) Jacobs DS, DeMott WR, Oxley DK, eds. Jacobs & DeMott Laboratory
> Test Handbook With Key Word Index. 5th ed. Hudson, OH: Lexi-Comp Inc; 2001; 5) Henry JB, ed. Clinical Diagnosis and
> Management by Laboratory Methods. 20th ed. Philadelphia: WB Saunders Co; 2001; 6) Kratz A, et al. Laboratory
> reference values. N Engl J Med. 2006;351:1548–1563; 7) Burtis CA, ed. Tietz Textbook of Clinical Chemistry and
> Molecular Diagnostics. 5th ed. St. Louis: Elsevier; 2012. This version of the table of reference ranges was
> reviewed and updated by Jessica Franco-Colon, PhD, and Kay Brooks.

It is a compilation that was copied and revised several times, and it contains transcription errors (a factor off by
ten, units off by a thousand). A print of the page taken on 2026-11-20 is identical to the saved file in all 474
rows except one: the page prints no factor for hemoglobin A2, the saved file carries `1`. labunits therefore does
not take any factor on trust: every deviation from the table is listed with its evidence in
`source_corrections.json`, and the pipeline re-checks each factor against the table's own reference intervals and
against the molar mass (`docs/pipeline.md`).

As a second, independent source, the factors were compared on 2026-11-20 with the *International System of Units
(SI) Conversion* table of Mayo Clinic Laboratories
(<https://www.mayocliniclabs.com/order-tests/si-unit-conversion.html>). 41 of its 58 rows have a counterpart here;
40 agree within rounding. The comparison confirmed three of the corrections (norepinephrine in pmol/L, calcitriol
2.4, estradiol 3.671) and led to one more (total metanephrines 5.264 instead of 5.07).

One deviation is deliberate rather than a correction: the table keeps some enzymes in U/L (its footnote: the katal
"has not been universally accepted. It is suitable to maintain use of U/L in these circumstances (conversion factor
1.0)"), whereas labunits converts every enzyme to µkat/L with the exact 1/60.

Then run from the project root:

```bash
uv run python scripts/parse_lab_values.py
```

`manual_loinc_mapping.json`, `source_corrections.json`, `analyte_names.json`, `ucum_units.json` and
`molar_masses.json` are part of the repository and document every manual decision that goes into the output. See
`docs/pipeline.md` for how the matching works.
