# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`labunits` is a small Python library (>=3.10) for converting laboratory analyte values between traditional units (e.g. mg/dL) and SI units (e.g. mmol/L), keyed by LOINC code. There is no equivalent existing library — that is the reason this project exists.

## Commands

This project uses `uv` for environment/runtime management. The package itself has no runtime dependencies; `dev`/`test` dependency groups are declared in `pyproject.toml`.

- Run a script: `uv run python scripts/parse_lab_values.py`
- Lint: `uv run ruff check`
- Format: `uv run ruff format` (or `uv run black .`)
- Tests: `uv run pytest` — note: no test suite exists yet despite `pytest` being a declared dev dependency.
- Build sdist/wheel: `uv run python -m build`

## Architecture

The repo has two cleanly separated halves:

### 1. `src/labunits/` — the published library (runtime)

- `converters.py` exposes the public API: `to_si_unit()`, `to_traditional_unit()`, `si_unit()`, `traditional_unit()`, `conversion_factor()`.
- All functions accept a LOINC code (preferred), an abbreviation, or a full analyte name; `_resolve_analyte_identifier()` normalizes any of these to a LOINC code before lookup.
- The data source is `src/labunits/data/analytes.json`, lazily loaded once into a module-level `_analytes_data` cache via `_load_data()`. The JSON is shipped with the package; the library does no network or filesystem I/O beyond this single read.
- `analytes.json` is keyed by LOINC number; each entry stores `name`, `specimen`, `traditional_units`, `si_units`, `conversion_factor`, and reference intervals.

### 2. `scripts/` — the offline data-generation pipeline (NOT runtime)

This is a one-shot pipeline that produces `src/labunits/data/analytes.json` from two upstream sources:

- `scripts/Clinical Laboratory Reference Values.html` — scraped from AccessMedicine (see `scripts/README.md` for source/date).
- `scripts/Loinc.csv` (+ `loinc_part.csv`) — the LOINC reference table.

`scripts/parse_lab_values.py` parses the HTML table with BeautifulSoup, then matches each analyte name against the LOINC `COMPONENT` column — manual pin (`manual_loinc_mapping.json`), then exact match, then `thefuzz` fuzzy ratio (threshold `FUZZY_MATCH_RATIO = 80`). Only active quantitative result terms whose `SYSTEM` fits the specimen and whose `PROPERTY` fits the unit are eligible; ties are broken by `COMMON_TEST_RANK`. Two different rows on one LOINC abort the run; factors are cross-checked against the source's own reference intervals. Known source errors are overridden via `scripts/source_corrections.json`. Pydantic models live in `scripts/models.py` (`Analyte`, `AnalyteRange`, `Specimen`).

When run as `__main__`, it writes the output to `src/labunits/data/analytes.json`. Re-run this script whenever upstream data changes; do not hand-edit `analytes.json`.

The `scripts/` package depends on `beautifulsoup4`, `thefuzz`, and `pydantic` — these are intentionally in the `dev` group, not runtime, since the published library only needs the pre-generated JSON.

## Conventions

- Public API functions live directly in `converters.py` — re-exports from `__init__.py` are not currently set up; importers use `from labunits.converters import ...`.
- The type alias `LoincNum = str` (`typing.TypeAlias`) signals "this string is expected to be a LOINC code." Keep using it for clarity at boundaries.
- `inf`/`-inf`/`nan` values pass through `to_si_unit` / `to_traditional_unit` unchanged.
