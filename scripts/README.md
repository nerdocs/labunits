# Data pipeline inputs

`parse_lab_values.py` turns two upstream files into `src/labunits/data/analytes.json`. Both files are **not**
part of the repository — they are third-party content under their own licences. Download them into this
directory before running the pipeline:

| File                                        | Source                                                                                      |
|---------------------------------------------|---------------------------------------------------------------------------------------------|
| `Loinc.csv`                                 | LOINC table (`LoincTable/Loinc.csv` inside the LOINC release ZIP) from <https://loinc.org/downloads/>. Requires a free LOINC account; use is subject to the [LOINC licence](https://loinc.org/license/). Last used release: 2.81 (2025-08). |
| `Clinical Laboratory Reference Values.html` | AccessMedicine, *Clinical Laboratory Reference Values*, saved as HTML from <https://accessmedicine.mhmedical.com/content.aspx?bookid=1069&sectionid=60775149> (requires institutional access). Downloaded 2025-10-05. |

Then run from the project root:

```bash
uv run python scripts/parse_lab_values.py
```

`manual_loinc_mapping.json` and `source_corrections.json` are part of the repository and document every manual
decision that goes into the output. See `docs/pipeline.md` for how the matching works.
