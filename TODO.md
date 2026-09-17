## Datenqualität

* [ ] **346 von 474 geparsten Analyten bekommen keine LOINC-Zuordnung** und werden nicht ausgeliefert
      (Problem-Report von `scripts/parse_lab_values.py`, Abschnitt *no LOINC match*). Größte Gruppen:
      Medikamentenspiegel (`(therapeutic)`-Suffix), Hormone mit Zyklusphasen/Geschlecht als Unterzeilen,
      Zellzählungen (`μL−1`), Immunglobuline, Vitamine. Weg: Suffixe wie `(therapeutic)` vor dem Matching
      abstreifen, Unterzeilen-Namen normalisieren, dann gezielt in `manual_loinc_mapping.json` pinnen.

* [ ] **37 traditionelle Einheiten ohne PROPERTY-Mapping** (`μL−1`, `mm Hg`, `s`, `pg/cell`, `g Hb/dL`,
      `mL/min/1.73 m2`, …) — für sie greift kein Property-Filter. `_UNIT_PROPERTIES` erweitern, sobald
      Analyte mit diesen Einheiten ausgeliefert werden sollen.

* [ ] **Fuzzy-Matches im Problem-Report einmal komplett gegenprüfen** (aktuell 20, alle ≥ 82 %).
      Gegengeprüft und dokumentiert: Acetylcholinesterase, LDH, Hb-Fraktionen (siehe `docs/data.md`).

* [ ] **Faktor-Check meldet Methionin und Tyrosin** — Rundung in der Quelle (6.71 → 6, 22.08 → 20),
      kein Fehler. Ggf. Toleranz für einstellige SI-Werte lockern, damit der Report leer bleibt.

## Code-Qualität

* [ ] **`_resolve_analyte_identifier` in `converters.py`: Abbreviation-Lookup hat noch keine Daten.**
      Der Reverse-Index `_abbrev_index` bleibt leer, solange `abbreviation`-Felder in `analytes.json`
      fehlen. Entweder LOINC `SHORTNAME`/`CONSUMER_NAME` einspielen oder den Zweig entfernen.

* [ ] **`loinc_num` ist in jedem Entry und im Outer-Key.** Redundant; beim nächsten Format-Bump raus.

* [ ] **`scripts/models.py`: `subtitle` und `gender` sind ungenutzt.**

* [ ] **`docs/design.md`, Abschnitt „conversion_factor stored as string“ ist veraltet** — der Faktor ist
      seit `Remove support for null conversion_factor` ein `float`.

## Format

* [ ] **`analytes.json` mit `indent=2`.** Gut für Diffs; bei > 1000 Einträgen `indent=None` erwägen.

* [ ] **~30 Einträge haben `conversion_factor == 1.0`** (traditionelle Einheit == SI-Einheit). Korrekt,
      aber reines Unit-Lookup ohne Umrechnungs-Mehrwert.
