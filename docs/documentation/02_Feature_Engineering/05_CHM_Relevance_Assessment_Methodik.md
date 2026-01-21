# 05. CHM Relevance Assessment & Feature Engineering

**Notebook:** `02_feature_engineering/03c_chm_relevance_assessment.ipynb`  
**Laufzeit:** ~15 min | **RAM:** 4-6 GB | **Input:** 924k Bäume, 4 CHM-Features

---

## Ziel & Methodik

Quantitative Evaluierung von 4 CHM-Features auf Basis von:

- **Diskriminative Kraft (η²):** Erklärte Varianz pro Gattung (Schwelle: ≥0.06)
- **Transfer-Risiko (Cohen's d):** City-Offsets (Schwelle: <0.8)
- **Datenqualität r:** Nachbarbaum-Kontamination (Schwelle: ≥0.7)
- **Feature Engineering:** Z-Score-Normalisierung, Percentile-Ranks, Ratios

## Workflow: 5-Phasen-Pipeline

1. **Phase 1:** ANOVA η² (diskriminative Kraft pro Feature)
2. **Phase 2:** Cohen's d (City-Transfer-Risiko)
3. **Phase 3:** Kontaminations-Diagnose (r(height_m, CHM_mean))
4. **Phase 4:** Feature-Engineering (Z-Score, Percentile, Ratios)
5. **Phase 5:** KEEP/EXCLUDE/KEEP_ABLATION Klassifikation → Export

**Feature-Entscheidungen:** height_m KEEP | CHM_mean/CHM_max/CHM_std EXCLUDE (Nachbarbaum-Kontamination) | 3 engineered Features KEEP

---

## Statistische Konzepte

**Eta-Squared (η²):** Erklärte Varianz durch Gattung

- Schwelle: η² ≥ 0.06 = Strong Discriminator
- Beispiel: height_m η²=0.174 (KEEP) | CHM_mean η²=0.082 (EXCLUDE wegen Kontamination)

**Cohen's d:** City-Höhen-Unterschiede (z.B. Berlin → Rostock)

- Schwelle: d < 0.8 = Low Transfer Risk
- Typisch: d≈0.18 für QUERCUS (0.9m Unterschied bei ~18m mean)

**Kontamination r:** Korrelation height_m ↔ CHM_mean

- Schwelle: r ≥ 0.7 = Akzeptabel, aber bei r=0.638 liegt **Nachbarbaum-Kontamination vor**
- Kritik: 10m-Resampling zu grob für urbane Bäume (zu hohe Pixel-Aggregation)

---

## 3. Datenstruktur & Input

### 3.1 Input-Daten aus Notebook 03b

**GeoPackages:**

- `trees_clean_no_edge.gpkg`: 924.220 Bäume
- `trees_clean_20m_edge.gpkg`: 849.454 Bäume

**Struktur:**

```
GeoDataFrame: trees_clean_no_edge
├─ Geometrie: Point (EPSG:25832, UTM 32N)
├─ Attribut-Spalten:
│  ├─ tree_id: int (eindeutige ID)
│  ├─ city: str ('Berlin', 'Hamburg', 'Rostock')
│  ├─ genus_latin: str (20 Laubbaumgattungen)
│  ├─ species_group: str ('deciduous')
│  ├─ CHM Features: 4 Spalten
│  │  ├─ height_m (gemessene/interpolierte Baumhöhe in Metern)
│  │  ├─ CHM_mean (Durchschnittshöhe im 10m-Pixel)
│  │  ├─ CHM_max (Maximale Höhe im 10m-Pixel)
│  │  └─ CHM_std (Standardabweichung Höhen im Pixel)
│  └─ S2 Temporal Features: 184 Spalten (23 Indizes × 8 Monate)
│
└─ Datenqualität:
   ├─ NaNs: 0 (100% complete)
   ├─ Plausible NDVI: 100% (max_NDVI ≥ 0.3)
   ├─ Gültige Geometrien: 100%
```

### 3.2 CHM Features im Detail

**height_m (Original-Feature aus Baumkataster):**

- Quelle: Stadtische Baumkataster (Berlin, Hamburg, Rostock)
- Ursprüngliche Erfassung: Manual oder automatisiert
- Qualität: Sehr variabel (teilweise manuell, teilweise aus LiDAR)
- Verwendung: Referenz-Höhe für Kontaminations-Diagnose

**CHM_mean, CHM_max, CHM_std (Resampled Rasterfeatures):**

- Quelle: 1m-Auflösung DHM/DOM → aggregiert auf 10m
- Erstellungs-Prozess (Notebook 01): Rasterio-Sampling bei Baum-Koordinaten
- Potentielles Problem: 10m-Raster kann mehrere Objekte mitteln
- Qualität: Stark abhängig von räumlicher Isolation (urbane Zentren problemtisch)

### 3.3 Geografische Charakterisierung

**No-Edge Datensatz:**

- Berlin: 352.856 Bäume (38%)
- Hamburg: 298.234 Bäume (32%)
- Rostock: 273.130 Bäume (30%)
- **Total: 924.220 Bäume**

**20m-Edge Datensatz:**

- Berlin: 327.234 Bäume (-7.3%)
- Hamburg: 276.456 Bäume (-7.3%)
- Rostock: 245.764 Bäume (-10.0%)
- **Total: 849.454 Bäume (-8.1%)**

**Interpretation:** Edge-Filterung entfernt **systematisch Rostock-Bäume** (Küstenlage, weniger Stadtfläche)

---

## Ergebnisse: Phase 1-5 Zusammenfassung

**Phase 1 - ANOVA η² (Diskriminative Kraft):**

**Kantenpixel-Vergleich (20m-Edge vs. No-Edge):**

| Feature  | 20m-Edge | No-Edge | Δη²    | Δη²(%) | Interpretation                  |
| -------- | -------- | ------- | ------ | ------ | ------------------------------- |
| height_m | 0.192    | 0.174   | +0.018 | +10.1% | ✓ Edge-Filter verbessert Signal |
| CHM_mean | 0.062    | 0.082   | -0.019 | -23.7% | ✗ Nachbarabhängigkeit erkannt   |
| CHM_max  | 0.073    | 0.075   | -0.002 | -2.7%  | ~ Stabil, aber kontaminiert     |
| CHM_std  | 0.046    | 0.037   | +0.008 | +22.5% | ✗ Noise-Feature (zu schwach)    |

**Phase 2 - Feature-Entscheidungslogik:**

| Feature      | η²    | Entscheidung | Begründung                                                                             |
| ------------ | ----- | ------------ | -------------------------------------------------------------------------------------- |
| **height_m** | 0.174 | **KEEP**     | Starker Diskriminator, nur 11% High-Risk-Gattungen                                     |
| **CHM_mean** | 0.082 | **EXCLUDE**  | Nachbarbaum-Kontamination (r=0.638 < 0.7). 10m-Resampling ungeeignet für urbane Bäume. |
| **CHM_max**  | 0.075 | **EXCLUDE**  | Nachbarbaum-Kontamination (r=0.638 < 0.7). 10m-Resampling ungeeignet für urbane Bäume. |
| **CHM_std**  | 0.046 | **EXCLUDE**  | Nachbarbaum-Kontamination (r=0.638 < 0.7). 10m-Resampling ungeeignet für urbane Bäume. |

**Phase 3 - Engineered Features für Ablationstudie:**

| Feature                 | Methode                             | Entscheidung |
| ----------------------- | ----------------------------------- | ------------ |
| **height_m_norm**       | Z-Score pro City/Genus              | **KEEP**     |
| **height_m_percentile** | Percentile-Rank (city-invariant)    | **KEEP**     |
| **crown_ratio**         | CHM_mean / height_m (r=0.638 ≥ 0.5) | **KEEP**     |

**Phase 4 - Export Final:**

```
✓ trees_clean_chm_final_no_edge.gpkg
  • 714.676 Bäume (volle Versorgung)
  • 193 Spalten (5 Metadaten + 184 Spektral + 4 CHM)
  • CHM Features: [height_m, height_m_norm, height_m_percentile, crown_ratio]

✓ trees_clean_chm_final_20m_edge.gpkg
  • 289.525 Bäume (20m-Puffer-Filterung)
  • 193 Spalten (5 Metadaten + 184 Spektral + 4 CHM)
  • CHM Features: [height_m, height_m_norm, height_m_percentile, crown_ratio]

⚠️  Ausgeschlossene CHM-Features: [CHM_mean, CHM_max, CHM_std]
     Grund: Nachbarbaum-Kontamination durch 10m-Resampling
```

**Status:** Ready für Notebook 03d (Correlation Analysis)
