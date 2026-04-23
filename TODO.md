## Datenqualität

* [x] **Hemoglobin A2 (LOINC 27345-8) hat keinen Konversionsfaktor.**
      Gelöst: der Faktor ist jetzt `null` in der JSON, und `to_si_unit` /
      `to_traditional_unit` / `conversion_factor` werfen einen sprechenden
      `ValueError("No conversion factor available for 27345-8")`.
      `si_unit` / `traditional_unit` funktionieren weiterhin.
      Integrationstest `KNOWN_MISSING_FACTORS` dokumentiert den Upstream-Gap.

* [ ] **333 von 474 geparsten Analyten bekommen keine LOINC-Zuordnung**
      (Fuzzy-Match-Threshold = 80 in `scripts/parse_lab_values.py`).
      Sie werden bei der JSON-Erzeugung über `if a.loinc_num` herausgefiltert,
      darum landen am Ende nur 127 Einträge in `analytes.json`.
      Mögliche Verbesserungen: Threshold senken, alternative Matching-Strategien
      (Synonyme, Komponenten-Splits, manuelles Mapping-File für Edge Cases).

* [ ] **Kein Audit-Trail für Fuzzy-Matches.** Wenn der Parser bei 80 %
      einen LOINC zuweist, steht im JSON nicht mehr, ob das ein exakter
      oder ein Fuzzy-Treffer war. Fehl-Zuordnungen fallen dadurch
      niemandem auf. Vorschlag: `scripts/parse_lab_values.py` soll
      zusätzlich eine `analytes.audit.json` (oder CSV) schreiben — mit
      `loinc_num`, `analyte_name`, `loinc_component`, `match_type`
      (`exact`/`fuzzy`), `score`. Die ausgelieferte `analytes.json`
      bleibt damit schlank.

## Code-Qualität

* [ ] **`_resolve_analyte_identifier` in `converters.py`: Abbreviation-Lookup hat noch keine Daten.**
      Die Funktion nutzt jetzt einen Reverse-Index (`_abbrev_index`), der leer
      bleibt, solange `abbreviation`-Felder in `analytes.json` fehlen. Entweder
      die Abkürzungs-Spalte aus LOINC (`SHORTNAME` / `CONSUMER_NAME`) mit
      einspielen, oder den Zweig ganz entfernen.

* [ ] **`loinc_num` ist in jedem Entry **und** im Outer-Key.**
      Redundant — das eine ist aus dem anderen rekonstruierbar. Aktuell
      harmlos, aber beim nächsten Format-Bump könnte der innere Key raus.

## Performance / Format

* [ ] **`analytes.json` mit `indent=2` gespeichert.** Gut für Diffs und
      Code-Review, tragbare Parse-Kosten bei 127 Einträgen. Falls die Liste
      auf >1000 Analyte wächst, wäre `indent=None` oder ein Binärformat
      (msgpack, pickle, gzip) eine Option — aktuell nicht nötig.

* [ ] **30 / 127 Einträge haben `conversion_factor == 1.0`.**
      Korrekt (traditionelle Einheit == SI-Einheit), aber Beobachtung:
      für diese Analyte ist `labunits` eine reine Unit-Lookup-Tabelle und
      liefert keinen echten Umrechnungs-Mehrwert. Ggf. könnte eine
      separate API (`is_dimensionless(analyte)` o.ä.) sinnvoll werden.
