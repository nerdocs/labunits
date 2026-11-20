# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-20

### Added

- 218 more analytes (351 instead of 133): blood count, lipids, bilirubin, thyroid, hormones, vitamins, drug levels.
- `py.typed` marker, SPDX licence field, classifiers and keywords in the package metadata.
- Data pipeline: molar-mass check of every mass/mole factor, `TIME_ASPCT` filter, canonical analyte names.

### Changed

- **Breaking:** the reserved abbreviation lookup is gone; identifiers are a LOINC code or a name.
- **Breaking:** entries of `analytes.json` no longer repeat their key in a `loinc_num` field.
- **Breaking:** ALT, alkaline phosphatase and LDH convert `U/L` to `ukat/L` like the other enzymes (was factor 1).
- All 13 enzymes convert `U/L` to `ukat/L` with the exact 1/60 = 0.01667 instead of the source's rounded 0.017.
- Every rate per 24 hours has the specimen `urine_24_h` (was `urine` for all but aldosterone).
- Sirolimus and tacrolimus resolve by their SI-side LOINC (method-specific term).

### Fixed

- Data pipeline: the factor check no longer reports the source's rounding (methionine, tyrosine).

## [0.3.1] - 2026-11-20

### Changed

- `analytes()` caches its records instead of rebuilding them on every call.

### Fixed

- Lookup indexes track the data cache by object identity instead of `id()`, which can be reused.
- Data pipeline: single values and `>=`/`<=` interval cells are parsed; unknown cells are reported, not dropped.

## [0.3.0] - 2026-11-20

### Added

- Every record carries `si_loinc_num`; all functions resolve an analyte by its traditional or SI-side LOINC code.
- `factor(analyte, from_unit, to_unit)` returns the factor for a unit pair; the direction follows from the units.
- `convert(value, analyte, from_unit, to_unit)` converts a value between the analyte's two units.
- LOINC copyright notice in the README.

### Changed

- **Breaking:** units are UCUM codes (e.g. `umol/L` instead of `μmol/L`).
- **Breaking:** a name matching several records raises `ValueError` listing the candidates.

### Fixed

- Cystine factor 83.3 -> 41.6 (dimer, not half-cystine).
- 1,25-dihydroxyvitamin D factor 2.6 -> 2.4 (416.64 g/mol).
- Norepinephrine (plasma) SI unit is pmol/L; acetylcholinesterase unit is kU/L.
- `analytes.json` is read as UTF-8.
- Rows without a numeric conversion factor are no longer shipped.

## [0.2.1] - 2026-10-04

### Fixed

- `analytes.json` is included in the built package.

## [0.2.0] - 2026-09-17

### Added

- `analytes()` enumerates all shipped records as frozen `Analyte` dataclasses.
- Hemoglobin fractions: HbA1c, HbA2, HbF, methemoglobin, sulfhemoglobin.
- Intended-use statement: labunits is a unit converter, not a medical device.
- Documentation site.

### Changed

- **Breaking:** `to_si_unit()` and `to_traditional_unit()` take `value` before `analyte`.
- LOINC matching respects specimen, property and scale; ties are broken by common test rank.
- Every shipped conversion factor is cross-checked against the source's own reference intervals.

### Removed

- Reference intervals are no longer shipped.

### Fixed

- Serum creatinine was silently replaced by urine creatinine (factor 8.84 instead of 88.4).
- Source errors: BUN factor 0.0357 -> 0.357, lamotrigine unit μg/mL, G6PD SI unit MU/mol Hb.
- Python 3.10 and 3.11 support (`TypeAlias` instead of the PEP 695 `type` statement).

## [0.1.0] - 2026-04-23

### Added

- Initial release: `to_si_unit()`, `to_traditional_unit()`, `si_unit()`, `traditional_unit()` and
  `conversion_factor()`, accepting a LOINC code, abbreviation or name.
- Analyte table generated from a clinical reference values table, matched to LOINC codes.

[Unreleased]: https://github.com/nerdocs/labunits/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/nerdocs/labunits/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/nerdocs/labunits/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/nerdocs/labunits/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/nerdocs/labunits/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/nerdocs/labunits/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nerdocs/labunits/releases/tag/v0.1.0
