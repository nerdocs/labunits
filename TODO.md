## Datenqualität

* [ ] **33 von 474 Quellzeilen werden nicht ausgeliefert** (Problem-Report, Abschnitt *no LOINC match*). Gründe und
      Liste in `docs/data.md`, Abschnitt *Rows left out on purpose*: kein passender LOINC-Term (mehrere Aminosäuren
      nur als Stoffmenge, Blei, Vitamin K, β-Carotin, pH), Faktor passt nicht zur genannten Substanz (Ammoniak,
      Bupropion, Niacin, Vitamin B1/B6, Methsuximid) oder zweite Umrechnung desselben LOINC (Hämoglobin g/L).

* [ ] **MCH, MCHC, MCV** stehen dauerhaft im Report unter *fail the eligibility filters*: ihre LOINC-Terme haben
      `SYSTEM = RBC`, die Quelle nennt Vollblut.

## Format

* [ ] **`analytes.json` mit `indent=2`.** Gut für Diffs; bei > 1000 Einträgen `indent=None` erwägen.

* [ ] **15 Einträge haben identische Einheiten auf beiden Seiten** (z. B. Gerinnungszeiten in `s`). Korrekt,
      aber reines Unit-Lookup ohne Umrechnungs-Mehrwert.

---

## Erledigt

* [x] **LOINC-Abdeckung 133 → 351 Einträge** — jede Quellzeile einzeln zugeordnet: kanonische Namen in
      `scripts/analyte_names.json`, Codes in `scripts/manual_loinc_mapping.json`.
* [x] **Präfix-Umrechnung** — `labunits.ucum`: `ucum_factor()`, `normalise()`, `display()`; `factor()` und
      `convert()` skalieren Präfix-Varianten automatisch. Damit geht auch Hämoglobin g/dL → g/L.
* [x] **Enzymfaktor 1/60** — alle 13 Enzyme rechnen U/L → µkat/L mit 0.01667 statt dem gerundeten 0.017 der Quelle.
* [x] **Molmassen-Abgleich** — `scripts/molar_masses.json`; die Pipeline rechnet jeden Masse↔Stoffmenge-Faktor nach.
* [x] **`TIME_ASPCT`-Filter und `urine_24_h`** für alle Raten pro 24 h.
* [x] **Fuzzy-Treffer gegengeprüft** — alle 19 verbliebenen sind korrekt (siehe `docs/data.md`).
* [x] **Faktor-Check ohne Rundungs-Fehlalarme** — die Rundung der traditionellen Grenze wird berücksichtigt.
* [x] **Abbreviation-Lookup entfernt**, **`loinc_num` nicht mehr im Eintrag**, ungenutzte Modellfelder entfernt.
* [x] **Einheiten als UCUM-Codes** — `scripts/ucum_units.json` übersetzt die Quell-Einheiten; `analytes.json` enthält
      nur noch UCUM (`umol/L`, `g/(24.h)`).
* [x] **Zweiter LOINC-Code je Analyt** — `si_loinc_num` (Term der SI-Einheit); die API löst beide Codes auf.
* [x] **Richtung über Einheiten** — `factor()` / `convert()` nehmen UCUM-Einheiten; Aufrufer müssen nicht wissen,
      welche Seite die traditionelle ist.
* [x] **Mehrdeutige Namen** — `ValueError` mit Kandidatenliste statt stillem „letzter gewinnt“.
* [x] **Öffentliche Iteration über alle Analyte** — `analytes()` in `converters.py`, liefert `Analyte`-Records
      (LOINC, Name, Specimen, Einheiten, Faktor); siehe `docs/api.md`.
* [x] **SI-Referenzintervall für Konsumenten** — Entscheidung: bleibt draußen (MDR); Konsumenten beziehen
      Referenzwerte aus ihrer eigenen, laborspezifischen Quelle. Begründung in `docs/design.md`.
* [x] **LOINC-Zuordnung ohne Specimen/Property/Scale** — Matcher filtert jetzt nach `SYSTEM`, `PROPERTY`,
      `SCALE_TYP`, `CLASS`, `STATUS`; Tie-Break über `COMMON_TEST_RANK`.
* [x] **Stille Kollisionen beim Schreiben von `analytes.json`** — Pipeline bricht bei zwei verschiedenen Zeilen
      auf einem LOINC ab.
* [x] **Kein Audit-Trail für Fuzzy-Matches** — Problem-Report listet Fuzzy-Treffer mit Score, Pins, Korrekturen
      und Faktor-Inkonsistenzen.
* [x] **Referenzintervalle in der Auslieferung** — entfernt; Zweckbestimmung in README/docs.
* [x] **`Loinc.csv` / AccessMedicine-HTML im Repo** — aus Tracking und History entfernt, gitignored.
