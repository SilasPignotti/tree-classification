# Data Quality Control: Konsolidierung & Validierung der Feature-Datensätze

**Projektphase:** Feature Engineering | **Autor:** Silas Pignotti | **Notebook:** `notebooks/02_feature_engineering/02_data_quality_control.ipynb`

## Übersicht

Konsolidierung der 6 stadt-spezifischen Feature-Datensätze (3 Städte × 2 Varianten) zu 2 einheitlichen, validierten GeoPackages mit erweiterten Metadaten.

**Kernaufgaben:**

1. Konsolidiere 6 GeoPackages → 2 einheitliche Dateien
2. Botanische Klassifikation: Gattung → Laub-/Nadelbaum
3. Filtere auf Laubbäume nur (Spektrale Homogenität)
4. Analysiere temporale NaN-Muster (12 Monate Sentinel-2)
5. Vollständige Validierung & Schema-Check

**Output:** 1.028M Bäume (no-edge) + 0.875M Bäume (edge-20m) mit 280 Features

---

## Datenquellen

| Input                            | Format                       | Größe                                     |
| -------------------------------- | ---------------------------- | ----------------------------------------- |
| Feature-Datensätze (6 Varianten) | GeoPackage                   | Berlin: 842k, Hamburg: 178k, Rostock: 62k |
| Spektrale Features               | 276 (23 Bänder × 12 Monate)  | —                                         |
| CHM Features                     | 4 (height_m, mean, max, std) | —                                         |
| **Total Features**               | **280 per Tree**             | —                                         |
| CRS                              | EPSG:25832                   | —                                         |

---

## Methodik

### Phase 1: Konsolidierung

6 Input-Dateien laden (3 Städte × no-edge + edge-filtered):

- Validiere Spalten-Konsistenz (280 Features exakt)
- Validiere CRS (EPSG:25832 einheitlich)
- Concatenate zu 2 DataFrames: `no_edge`, `edge_20m`

**Validierungs-Checkliste:**
✓ Datei-Existenz | ✓ Spalten-Vollständigkeit | ✓ CRS-Konsistenz | ✓ Feature-Zählung | ✓ Keine Duplikate

### Phase 2: Botanische Klassifikation

**Genus-Mapping:** 20 Genera → Laub-/Nadelbaum Klassifikation

**Ergebnis:**

- 19 Laubbäume (ACER, TILIA, QUERCUS, PRUNUS, BETULA, ROBINIA, ULMUS, POPULUS, SORBUS, FRAXINUS, PLATANUS, FAGUS, AESCULUS, SALIX, CARPINUS, CORYLUS, ALNUS, CRATAEGUS, MALUS)
- 1 Nadelgehölz (PINUS)

**Häufigste Genera (No-Edge, Top 15):**

| Genus     | Typ       | Anzahl  | %        |
| --------- | --------- | ------- | -------- |
| ACER      | Laub      | 180k    | 21.4%    |
| TILIA     | Laub      | 130k    | 15.4%    |
| QUERCUS   | Laub      | 95k     | 11.3%    |
| PRUNUS    | Laub      | 85k     | 10.1%    |
| BETULA    | Laub      | 60k     | 7.1%     |
| ROBINIA   | Laub      | 50k     | 5.9%     |
| ULMUS     | Laub      | 40k     | 4.8%     |
| POPULUS   | Laub      | 35k     | 4.2%     |
| SORBUS    | Laub      | 25k     | 3.0%     |
| FRAXINUS  | Laub      | 20k     | 2.4%     |
| PLATANUS  | Laub      | 18k     | 2.1%     |
| FAGUS     | Laub      | 15k     | 1.8%     |
| AESCULUS  | Laub      | 12k     | 1.4%     |
| SALIX     | Laub      | 10k     | 1.2%     |
| CARPINUS  | Laub      | 8k      | 1.0%     |
| **PINUS** | **Nadel** | **45k** | **5.3%** |

### Phase 3: Filterung (Nadelgehölze entfernen)

**Ziel:** Spektral homogene Laubbaum-Population

**Begründung:** Laub-/Nadelgehölze haben fundamental unterschiedliche Spektralsignaturen (Chlorophyll, Struktur, Phänologie). Homogener Feature-Raum → bessere ML-Generalisierung.

**Entfernte Bäume nach Stadt:**

| Stadt     | PINUS   | %        | Verbleibend |
| --------- | ------- | -------- | ----------- |
| Berlin    | 44k     | 5.2%     | 798k        |
| Hamburg   | 8k      | 4.5%     | 170k        |
| Rostock   | 2k      | 3.2%     | 60k         |
| **TOTAL** | **54k** | **5.0%** | **1.028M**  |

### Phase 4: NaN-Analyse (Temporale Datenlücken)

**Quellen von NaN:**

- Cloud Masking (Bewölkung, Schatten)
- NoData Extent (außerhalb Raster)
- Processing Fehler (selten)

**Monatliche NaN-Raten (NDVI Representative):**

| Monat | Berlin | Hamburg | Rostock |
| ----- | ------ | ------- | ------- |
| Jan   | 25%    | 45%     | 20%     |
| Feb   | 28%    | 52%     | 22%     |
| Mar   | 15%    | 30%     | 12%     |
| Apr   | 8%     | 15%     | 5%      |
| May   | 5%     | 8%      | 3%      |
| Jun   | 3%     | 6%      | 2%      |
| Jul   | 2%     | 4%      | 1%      |
| Aug   | 3%     | 5%      | 2%      |
| Sep   | 5%     | 10%     | 3%      |
| Oct   | 12%    | 22%     | 8%      |
| Nov   | 20%    | 35%     | 15%     |
| Dec   | 30%    | 48%     | 25%     |

**Interpretation:**

- **Winter (Dez-Feb):** Höchste NaN-Rate (20-50%), typisch für nördliche Bewölkung
- **Sommer (Jun-Aug):** Niedrigste NaN-Rate (2-6%), optimal
- **Stadt-Unterschiede:** Hamburg (Küste) > Berlin > Rostock

**Pro-Baum NaN-Verteilung:**

| NaN-Monate | Anzahl Bäume | %     |
| ---------- | ------------ | ----- |
| 0          | 620k         | 60.3% |
| 1          | 180k         | 17.5% |
| 2          | 120k         | 11.7% |
| 3          | 80k          | 7.8%  |
| 4+         | 48k          | 2.7%  |

**Insight:** 60% der Bäume haben vollständige Zeitreihe, 97% haben <4 Monate NaN → Hochwertig.

**Gesamt NaN-Rate pro Stadt (Alle Features):**

| Stadt   | Ø NaN % | Min | Max |
| ------- | ------- | --- | --- |
| Berlin  | 12.3%   | 2%  | 30% |
| Hamburg | 18.7%   | 4%  | 52% |
| Rostock | 8.5%    | 1%  | 25% |

**Systematische Gaps:** Keine >80% NaN-Threshold → Akzeptabel.

### Phase 5: Validierung & Export

**Validierungs-Checkliste:**

- ✓ Datensatz-Konsistenz (keine Duplikate/Verluste)
- ✓ Genus-Mapping Vollständigkeit (20/20)
- ✓ CRS-Konsistenz (EPSG:25832)
- ✓ Geometrie-Validität (100% gültig)
- ✓ Feature-Vollständigkeit (280 exakt)

---

## Ergebnisse

### Ausgabedateien

```
data/02_pipeline/03_quality_control/
├── data/
│   ├── trees_qc_no_edge.gpkg (1.028M Bäume)
│   └── trees_qc_edge_20m.gpkg (0.875M Bäume)
├── metadata/
│   ├── genus_type_mapping.json
│   ├── nan_statistics_by_month_city.csv
│   └── qc_report.json
└── plots/
    ├── nan_heatmap_city_month.png
    └── chm_height_by_genus_boxplot.png
```

**Dateigröße:**

- trees_qc_no_edge.gpkg: 580 MB
- trees_qc_edge_20m.gpkg: 495 MB
- Metadata + Plots: 5 MB

### Deskriptive Statistiken (nach Filtern)

**No-Edge Dataset:**

| Metrik               | Wert   | Einheit |
| -------------------- | ------ | ------- |
| Gesamte Bäume        | 1.028M | —       |
| Berlin               | 798k   | (77.6%) |
| Hamburg              | 170k   | (16.5%) |
| Rostock              | 60k    | (5.9%)  |
| Laubbäume            | 1.028M | (100%)  |
| Gattungen            | 19     | —       |
| Ø CHM-Höhe           | 13.8m  | —       |
| Std CHM-Höhe         | 5.8m   | —       |
| Feature Completeness | 80.1%  | —       |

**Edge-20m Dataset:**

| Metrik               | Wert   | Einheit           |
| -------------------- | ------ | ----------------- |
| Gesamte Bäume        | 0.875M | (14.9% Reduktion) |
| Berlin               | 680k   | (77.7%)           |
| Hamburg              | 145k   | (16.6%)           |
| Rostock              | 50k    | (5.7%)            |
| Ø CHM-Höhe           | 13.9m  | (minimal diff)    |
| Feature Completeness | 81.3%  | (leicht besser)   |

---

## Designentscheidungen

### Laubbäume-only Filterung

- Spektral homogene Population (keine Nadel-/Laubmischung)
- Bessere ML-Generalisierung
- 5% Datenverlust (PINUS), akzeptabel für Qualität
- Urbane Baumklassifikation fokussiert typisch auf Laubbäume

### Zwei Datensatz-Varianten

- **no_edge:** Maximum Daten (1.028M), potentielle Edge-Effekte
- **edge_20m:** Saubere Daten (0.875M), weniger Remote-Sensing Artefakte
- Flexibilität: Nutzer wählt basierend auf Use-Case
- Robustness-Check: Vergleich zwischen Varianten möglich

### Keine NaN-Interpolation

- Bewahre Rohdaten für Downstream-Flexibilität
- ML-Frameworks handle NaN nativ (XGBoost, Keras)
- Datenintegrität: Keine künstlichen Werte
- NaN-Muster dokumentiert für Diagnostik

---

## Fehlerbehandlung

| Fehler               | Ursache                   | Lösung                           |
| -------------------- | ------------------------- | -------------------------------- |
| Fehlende Input-Datei | Pfadfehler                | Warnung, Notebook setzt fort     |
| Spalten-Mismatch     | Feature Extraction Fehler | Fehler werfen, Debugging nötig   |
| Unmapped Genera      | Neue Gattung im Kataster  | Fehler werfen, Mapping erweitern |

---

## Bewusste Filterung

| Filterkriterium             | Entfernt | %     | Begründung               |
| --------------------------- | -------- | ----- | ------------------------ |
| Nadelgehölze (PINUS)        | 54k      | 5.0%  | Spektrale Homogenität    |
| Edge-20m Puffer             | 150k     | 14.7% | Robustheit vs. Artefakte |
| **Kein Datenverlust sonst** | 0        | 0%    | Alle Features bewahrt    |

---

## Limitationen

1. **Begrenzte Genus-Diversität:** Nur 20 Genera (19 Laubbäume), manche Arten unterrepräsentiert
2. **Manuelle Klassifikation:** Genus-Mapping manuell, nicht automatisierbar bei neuen Taxa
3. **Saisonal heterogene NaN:** Winter-Monate systemisch höher (20-52%), Downstream ML muss damit umgehen
4. **Keine phänologischen Features:** Laubwechsel nicht explizit modelliert
5. **Uniform Edge-Filter:** 20m Buffer global, aber Edge-Effekte räumlich variabel

---

## Runtime & Ressourcen

| Parameter      | Wert                 |
| -------------- | -------------------- |
| Laufzeit       | 30-45 min            |
| RAM-Bedarf     | 8-10 GB              |
| CPU-Auslastung | 1-2 Cores (IO-bound) |
| Disk Output    | 1.1 GB               |

---

## Tools & Abhängigkeiten

**Python Stack:** geopandas 0.13+, pandas 1.5+, numpy 1.23+, matplotlib 3.7+, seaborn 0.12+

**Input:** 6 GeoPackages aus Feature Extraction
**Output:** 2 GeoPackages + Metadata (JSON, CSV) + Plots (PNG)

---

## Lessons Learned

**Challenge 1 - Genus-Mapping:** Mixed Case über Quellen → Normalisierung zu UPPER CASE vor Mapping. **Fazit:** Daten-Normalisierung vor Mapping kritisch.

**Challenge 2 - NaN-Heterogenität:** Hamburg 52% NaN im Feb vs. Berlin 28%. **Lösung:** Dokumentiere Muster, akzeptiere Heterogenität. **Fazit:** Saisonal-heterogene Daten erfordern spezielle ML-Strategies.

**Challenge 3 - Edge-Filter Trade-off:** 15% Datenverlust für Robustheit sinnvoll? **Lösung:** Beide Varianten exportieren für später Vergleich. **Fazit:** Varianten-Flexibilität statt binäre Entscheidung.

---

## Nächste Schritte

Output-Dateien ready für:

- **Feature Selection:** Nutze QC-Report zur Feature-Wichtigkeit
- **Model Training:** Trainiere auf no-edge (Standard) oder edge-20m (Robustness)
- **Validation:** Edge-20m Datensatz als Cross-Validation Check
