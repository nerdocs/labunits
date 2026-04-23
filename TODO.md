## Datenqualität

* [ ] **Hemoglobin A2 (LOINC 27345-8) hat keinen Konversionsfaktor.**
      Im AccessMedicine-HTML ist die Faktor-Spalte leer, weil die Einheiten
      `% total Hb` ↔ `Fraction of 1.0` dimensionslos sind.
      Aktuell: `to_si_unit(x, "27345-8")` wirft einen unklaren `ValueError`
      aus `float("")`. Die Integration-Tests dokumentieren den Eintrag in
      `KNOWN_NON_NUMERIC_FACTORS`, damit ein evtl. Upstream-Fix auffällt.
      Optionen:
      - in `converters.py` einen sprechenden Fehler werfen
        (z.B. `ValueError("No conversion factor available for 27345-8")`),
      - oder solche Einträge im Parser ganz aussortieren,
      - oder den Faktor manuell ergänzen (z.B. `0.01` für % → fraction).

* [ ] **333 von 474 geparsten Analyten bekommen keine LOINC-Zuordnung**
      (Fuzzy-Match-Threshold = 80 in `scripts/parse_lab_values.py`).
      Sie werden bei der JSON-Erzeugung über `if a.loinc_num` herausgefiltert,
      darum landen am Ende nur 127 Einträge in `analytes.json`.
      Mögliche Verbesserungen: Threshold senken, alternative Matching-Strategien
      (Synonyme, Komponenten-Splits, manuelles Mapping-File für Edge Cases).

## Code-Qualität

* [ ] **`_resolve_analyte_identifier` in `converters.py`: Abbreviation-Lookup ist toter Code.**
      Die Funktion sucht nach `info.get("abbreviation", ...)`, aber im Datensatz
      existiert dieses Feld nirgends. Bereits mit `# FIXME` markiert.
      Entweder die Abkürzungs-Spalte aus LOINC mitziehen und in
      `analytes.json` schreiben, oder den toten Zweig entfernen.
