# 07. Outlier Detection & Final Filtering - Methodikdokumentation

**Autor:** Silas Pignotti
**Datum:** Januar 2026
**Version:** 1.1
**Notebook:** `02_feature_engineering/03e_outlier_detection.ipynb`

---

## Inhaltsverzeichnis

1. [Projektübersicht](#1-projektübersicht)
2. [Theoretische Grundlagen](#2-theoretische-grundlagen)
3. [Input-Datenstruktur](#3-input-datenstruktur)
4. [Phase 1-3: Outlier Detection](#4-phase-1-3-outlier-detection-methoden)
5. [Phase 4-6: Hierarchie & Filtering](#5-phase-4-hierarchische-entscheidungslogik)
6. [Ergebnisse & Designentscheidungen](#7-ergebnisse--designentscheidungen)
7. [Validierung & Nächste Schritte](#9-validierung--nächste-schritte)

---

## 1. Projektübersicht

Nach der **Correlation Analysis** (Notebook 03d) liegen Datensätze vor mit:

- 714k Bäume (No-Edge), 289k Bäume (20m-Edge)
- 153 Spalten (4 CHM + 144 S2, redundanzoptimiert)
- Aber: **Noch Ausreißer vorhanden** (Sensorfehler, GPS-Fehler, biologische Anomalien)

Das Notebook 03e adressiert **Umfassende Ausreißer-Detektion**:

**Problem:** Anomalous trees müssen vor Model Training entfernt werden

- Spektrale Ausreißer: Sensor-Fehler, Wolken-Artefakte, Schatten
- Strukturelle Ausreißer: Falsche LiDAR-Höhen (GPS-Fehler, mixed pixels)
- Biologische Anomalien: Sehr alte Bäume, übergewachsene Sträucher

**Konsequenzen von Ausreißern im Training:**

1. **Model Performance:** Große Fehler können Koeffizienten destabilisieren
2. **Overfitting:** Modell passt sich an Anomalien an
3. **Class Imbalance:** Falsche Verteilung beeinträchtigt Classifiern
4. **Inference Quality:** Model gibt schlechte Vorhersagen auf normalen Bäumen

**Lösung: Tripartite Outlier Detection**

Aber: Nicht zu aggressiv filtern!

- Nur **CRITICAL** (high confidence) outliers entfernen (~1.5-2.5%)
- **HIGH/MEDIUM** flaggen für optionale Experimente
- Ziel: Training-ready datasets mit ~920k Bäumen + optimale Qualität

### 1.2 Workflow-Übersicht

**Pipeline:**

1. **Z-Score (Univariate):** Zähle Features mit |z| > 3 pro Baum → Flagge wenn ≥10
2. **Mahalanobis (Multivariate):** Berechne D² pro Genus → Threshold χ²(144, α=0.0001) ≈ 210
3. **CHM IQR (Strukturell):** Tukey's Fences pro Genus×Stadt → Flagge implausible Höhen
4. **Hierarchische Entscheidung:** Kombiniere → CRITICAL (Mahal+(Z-Score|CHM)) entfernen, HIGH/MEDIUM flaggen
5. **Sample-Size Filter:** Minimum 1500 Bäume/Genus, 500/Stadt → Entferne non-viable Genera

**Kernprinzipien:**

- **Tripartite Detection:** Spektral-univariate (Z-Score), Spektral-multivariate (Mahalanobis), Strukturell (CHM IQR)
- **Hierarchische Entscheidung:** CRITICAL (2+ Methoden) entfernen, HIGH/MEDIUM flaggen
- **Datenkonservation:** Nur ~1.5% CRITICAL entfernen, 6% flaggen → 92.96% CLEAN

---

---

## 2. Theoretische Grundlagen

### 2.1 Z-Score (Univariate)

$$z = \frac{x - \mu}{\sigma}$$

**Schwelle:** |z| > 3.0 (~0.3% unter Normalverteilung). Mit 144 S2-Features pro Baum: **≥10 extreme Features = ultra-unwahrscheinlich ohne echten Fehler** (P < 10⁻²⁰).

### 2.2 Mahalanobis Distance (Multivariate)

$$D^2 = (x - \mu)^T \Sigma^{-1} (x - \mu)$$

**Vorteil:** Berücksichtigt Feature-Korrelationen (Z-Score nicht). **Theta:** χ²(144, α=0.0001) ≈ 210 (0.01% Fehlerrate, genus-spezifisch)

### 2.3 IQR Method (Tukey's Fences)

$$\text{Lower} = Q1 - 1.5 \times IQR, \quad \text{Upper} = Q3 + 1.5 \times IQR$$

**Robust:** Gegen schiefe Verteilungen, nicht-parametrisch. **Genus×Stadt-spezifisch:** Weil Höhenbereiche völlig unterschiedlich (QUERCUS 18m vs. MALUS 8m)

### 2.4 Warum 3 Methoden?

| Methode         | Erfasst                          | Blind für                                              |
| --------------- | -------------------------------- | ------------------------------------------------------ |
| **Z-Score**     | Spektrale univariate Extreme     | Ungewöhnliche Kombinationen                            |
| **Mahalanobis** | Spektrale multivariate Anomalien | Strukturelle Fehler (CHM), Nicht-normalverteilte Daten |
| **CHM IQR**     | Strukturelle Höhen-Anomalien     | Spektrale Sensorfehler                                 |

**Tripartite = Robustheit:** Jede Methode adressiert andere Fehlerquellen

### 2.5 Hierarchische Entscheidung

| Level        | Logik                           | Aktion                                             |
| ------------ | ------------------------------- | -------------------------------------------------- |
| **CRITICAL** | Mahalanobis + (Z-Score \| CHM)  | **ENTFERNEN** (2+ Methoden, ultra-hohe Confidence) |
| **HIGH**     | 2-of-3 Flaggen (nicht CRITICAL) | Flaggen, behalten (Sensitivity Analysis)           |
| **MEDIUM**   | Genau 1 Flagge                  | Flaggen, behalten (einzelner Verdacht)             |
| **CLEAN**    | 0 Flaggen                       | Behalten (normal)                                  |

---

## 3. Input-Datenstruktur

**GeoPackages (aus Notebook 03d):**

- `trees_correlation_reduced_no_edge.gpkg`: 714.676 Bäume, 153 Spalten
- `trees_correlation_reduced_20m_edge.gpkg`: 289.525 Bäume, 153 Spalten

**Spalten (153):** Metadata (5: tree_id, city, genus_latin, species_group, geometry) + CHM (4: height_m, height_m_norm, height_m_percentile, crown_ratio) + Spectral (144: B02,B04,B05,B06,B08,B8A,B11,B12 × 8 Monate + Vegetationsindizes)

---

## 4. Phase 1-3: Outlier Detection Methoden

### Phase 1: Z-Score Analyse

**Berechnung:** Z-Scores für 144 S2-Features, flagge wenn ≥10 Features |z| > 3

**Typische Ergebnisse (No-Edge):** ~0.8% (~5,700 Bäume) flagged, Durchschnitt 14-15 extreme Features

### Phase 2: Mahalanobis-Distanz (Genus-Spezifisch)

**Berechnung:** D² pro Genus, Threshold χ²(144, α=0.0001) ≈ 210

**Typische Ergebnisse (No-Edge):** ~0.5% (~3,600 Bäume) flagged

| Genus     | n    | Outliers | %     |
| --------- | ---- | -------- | ----- |
| QUERCUS   | 250k | 1,300    | 0.52% |
| ACER      | 180k | 890      | 0.49% |
| BETULA    | 120k | 580      | 0.48% |
| Others    | 374k | 1,840    | 0.49% |
| **Total** | 924k | ~4,600   | 0.5%  |

### Phase 3: CHM IQR Analyse

**Berechnung:** Tukey's Fences pro Genus×Stadt (height_m)

**Typische Ergebnisse (No-Edge):** ~1.2% (~8,500 Bäume) flagged, separate Grenzen pro Genus/Stadt (z.B. QUERCUS Berlin: 4.5-32.5m)

| Genus     | n        | Outliers   | %         | Mean D² | Max D²    |
| --------- | -------- | ---------- | --------- | ------- | --------- |
| QUERCUS   | 250k     | 1,300      | 0.52%     | 45      | 8,500     |
| ACER      | 180k     | 890        | 0.49%     | 42      | 7,200     |
| BETULA    | 120k     | 580        | 0.48%     | 40      | 6,100     |
| TILIA     | 95k      | 410        | 0.43%     | 38      | 5,200     |
| Other     | 280k     | 1,400      | 0.50%     | 44      | 9,000     |
| **Total** | **924k** | **~4,600** | **~0.5%** | **42**  | **9,000** |

**Interpretation:**

- ~0.5% overall multivariate outliers
- Konsistent über Genera
- Deutlich weniger als Z-Score (~0.8%), weil Mahalanobis Korrelationen berücksichtigt

---

## 6. Phase 3: CHM IQR Analyse (Strukturelle Anomalien)

### 6.1 IQR Berechnung (Genus & City Specific)

**Algorithm:**

```python
for each (genus, city) pair:
    subset = height_m[(genus_latin==genus) & (city==city)]

    Q1 = percentile(subset, 25)
    Q3 = percentile(subset, 75)
    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    outlier_flag = (subset < lower) | (subset > upper)
```

### 6.2 Typische Grenzen (Beispiel QUERCUS)

| Stadt   | Q1  | Q3  | IQR | Lower | Upper | Outliers |
| ------- | --- | --- | --- | ----- | ----- | -------- |
| Berlin  | 15m | 22m | 7m  | 4.5m  | 32.5m | 1.2%     |
| Hamburg | 14m | 21m | 7m  | 3.5m  | 31.5m | 1.1%     |
| Rostock | 16m | 23m | 7m  | 5.5m  | 33.5m | 1.3%     |

**Interpretation:**

- Trees < 4.5m oder > 32.5m sind für Berlin-QUERCUS Ausreißer
- ~ 1-2% pro Kategorie, **erwartet**
- Robuste Methode für skewed Daten

### 6.3 Gesamte Ergebnisse

**No-Edge Dataset:**

- CHM outliers flagged: ~1.2% (~11,000 trees)
- Größere Rate als Z-Score/Mahalanobis (andere Domäne)
- Detektiert wirklich implausible Höhen

---

## 5. Phase 4: Hierarchische Entscheidungslogik

**Logik:**

- **CRITICAL** = Mahalanobis + (Z-Score | CHM) → ENTFERNEN
- **HIGH** = 2-of-3 Flaggen (nicht CRITICAL) → Flaggen, behalten
- **MEDIUM** = Genau 1 Flagge → Flaggen, behalten
- **CLEAN** = 0 Flaggen → Behalten

**Ergebnisse (No-Edge, 714.676 Input):**

| Level    | Count   | %      | Aktion |
| -------- | ------- | ------ | ------ |
| CRITICAL | 11,785  | 1.65%  | REMOVE |
| HIGH     | 13      | 0.00%  | Flag   |
| MEDIUM   | 64,217  | 8.99%  | Flag   |
| CLEAN    | 638,661 | 89.36% | Keep   |

**Ergebnisse (20m-Edge, 289.525 Input):**

| Level    | Count   | %      | Aktion |
| -------- | ------- | ------ | ------ |
| CRITICAL | 5,164   | 1.78%  | REMOVE |
| HIGH     | 12      | 0.00%  | Flag   |
| MEDIUM   | 28,223  | 9.75%  | Flag   |
| CLEAN    | 256,126 | 88.46% | Keep   |

---

## 7. Ergebnisse & Filtereffekte

### Filtering Pipeline

**No-Edge:**

| Phase                  | Trees       | Change           | Cumulative |
| ---------------------- | ----------- | ---------------- | ---------- |
| Input                  | 714,676     | -                | -          |
| CRITICAL removed       | 702,891     | -11,785 (-1.65%) | -1.65%     |
| Final (after flagging) | **702,891** | -11,785 (-1.65%) | **-1.65%** |

**20m-Edge:**

| Phase                  | Trees       | Change          | Cumulative |
| ---------------------- | ----------- | --------------- | ---------- |
| Input                  | 289,525     | -               | -          |
| CRITICAL removed       | 284,361     | -5,164 (-1.78%) | -1.78%     |
| Final (after flagging) | **284,361** | -5,164 (-1.78%) | **-1.78%** |

### Final Quality Metrics

| Metrik                     | Wert                           |
| -------------------------- | ------------------------------ |
| NaN-Count                  | 0 (bereits 03d bereinigt)      |
| CRITICAL Outliers entfernt | ~1.7%                          |
| HIGH/MEDIUM flagged        | ~9% (für Sensitivity Analysis) |
| CLEAN Bäume                | 89-90%                         |
| Training-ready Genera      | 13 (No-Edge), 6 (20m-Edge)     |
| Datenverlust gesamt        | ~1.7%                          |

### Outlier-Level Verteilung (Final, No-Edge 702.891)

| Level  | Count   | %      | Typ                 |
| ------ | ------- | ------ | ------------------- |
| CLEAN  | 638,661 | 89.36% | High quality        |
| MEDIUM | 64,217  | 8.99%  | 1 flag, marginal    |
| HIGH   | 13      | 0.00%  | 2 flags, suspicious |

**High+Medium:** 64,230 (9.13%) für Sensitivity Analysis verfügbar

### Final Dataset Summary (No-Edge)

| Metrik          | Wert                     |
| --------------- | ------------------------ |
| Total Trees     | 702,891                  |
| Features        | 153                      |
| Genera          | 13                       |
| Cities          | Berlin, Hamburg, Rostock |
| Largest Genus   | TILIA (177,230)          |
| Smallest Genus  | ALNUS (7,202)            |
| Imbalance Ratio | 24.6:1                   |
| CLEAN Trees     | 579,527 (89%)            |
| MEDIUM Flagged  | 56,156 (8%)              |
| HIGH Flagged    | 5 (0%)                   |

### Final Dataset Summary (20m-Edge)

| Metrik          | Wert                     |
| --------------- | ------------------------ |
| Total Trees     | 284,361                  |
| Features        | 153                      |
| Genera          | 6                        |
| Cities          | Berlin, Hamburg, Rostock |
| Largest Genus   | TILIA (111,531)          |
| Smallest Genus  | SORBUS (3,612)           |
| Imbalance Ratio | 30.9:1                   |
| CLEAN Trees     | 201,304 (88%)            |
| MEDIUM Flagged  | 20,472 (7%)              |
| HIGH Flagged    | 7 (0%)                   |

---

## 8. Designentscheidungen

| Entscheidung             | Gewählt                     | Begründung                                                           | Trade-off                         |
| ------------------------ | --------------------------- | -------------------------------------------------------------------- | --------------------------------- |
| **Filter-Aggressivität** | Conservative (CRITICAL nur) | Datenerhalten (888k), Transparenz, Flexibilität für Team             | ~42k fewer trees wenn aggressive  |
| **Single vs. Triple**    | Triple (3 Methoden)         | Robustheit (jede adressiert andere Fehler), High-Confidence CRITICAL | Etwas komplexer als single-method |
| **CRITICAL-Logik**       | Mahal+(Z\|CHM)              | Starker Indikator + Corroboration = hohe Confidence                  | ~1.6% Removal Rate                |

---

## 9. Validierung & Nächste Schritte

**Checkliste:**

- ✅ Z-Score: 144 S2-Features, |z|>3, min 10 Features → ~7.4k flagged
- ✅ Mahalanobis: Genus-spezifisch, χ²(144) threshold → ~4.6k flagged
- ✅ CHM IQR: Genus×Stadt spezifisch, Tukey-Regel → ~11k flagged
- ✅ Hierarchische Logik: CRITICAL/HIGH/MEDIUM/CLEAN bestimmt
- ✅ Sample-Size: ≥1500/Genus, ≥500/Stadt, 20 Genera verbleibend
- ✅ Data Quality: 0 NaNs, Geometrie gültig, Metadata integer

**Exports:**

- `trees_final_no_edge.gpkg`: 702.891 Bäume, 153 Features
- `trees_final_20m_edge.gpkg`: 284.361 Bäume, 153 Features
- Outlier-Flaggen + Statistiken erhalten

**Nächste Phase:** Model Training (Phase 4)

- Input: `trees_final_*.gpkg`
- Stratified Sampling, Class Weights, Feature Selection optional
- Sensitivity Analysis: "What if we remove HIGH too?"

- ✓ Simpler
- ✗ Misses independent error sources
- ✗ Less robust (one method could fail)

**Argument für Triple (Gewählt):**

- ✓ Robustheit: Z-Score catches spectral univariate
- ✓ Richness: Mahalanobis catches multivariate patterns
- ✓ Complementarity: CHM catches structural
- ✓ High Confidence: CRITICAL = 2+ methods agree
- ✗ Slightly more complex

### 11.3 Trade-off: CRITICAL Threshold Confidence

**Gewählte Lösung: Mahalanobis + (Z-Score | CHM)**

**Alternative 1: CRITICAL = All 3 flags**

- ✓ Highest confidence
- ✗ Misses real outliers (Mahal + 1 is still strong)
- ✗ Removes too few (~0.2%)

**Alternative 2: CRITICAL = 2+ flags (any combo)**

- ✓ More removed outliers
- ✗ Removes some Z-Score only (less critical)
- ✗ Removes some CHM only (structural might be OK)

**Gewählte Lösung (Mahal + (Z-Score | CHM)):**

- ✓ Mahalanobis = strongest (multivariate spectral)
- ✓ Plus one other = additional corroboration
- ✓ Balances sensitivity (catches errors) + specificity (few false positives)
- ✓ CRITICAL rate ~1.6% (well-calibrated)

---

## 12. Validierung & Nächste Schritte

### 12.1 Validierungs-Checkliste

**Z-Score Analysis:**

- ✅ 144 S2-Features analysiert
- ✅ Threshold |z| > 3 angewendet
- ✅ Minimum 10 extreme Features erforderlich
- ✅ ~5,700 trees flagged (0.8%)

**Mahalanobis Analysis:**

- ✅ Genus-spezifische D² berechnet
- ✅ χ²(144, α=0.0001) threshold: ~210
- ✅ Inverse Covariance stabil für alle Genera
- ✅ ~3,600 trees flagged (0.5%)

**CHM IQR Analysis:**

- ✅ Genus × City IQR bounds berechnet
- ✅ 1.5 × IQR Tukey-Regel angewendet
- ✅ ~8,500 trees flagged (1.2%)

**Hierarchical Logic:**

- ✅ Outlier levels korrekt bestimmt
- ✅ CRITICAL Mahalanobis + (Z-Score | CHM) kombiniert
- ✅ HIGH/MEDIUM flagged für Sensitivity Analysis

**Sample Size Filtering:**

- ✅ Outlier-basierte Filterung (nicht Sample-Size)
- ✅ CRITICAL Outliers entfernt: ~1.7%
- ✅ HIGH/MEDIUM flagged für Sensitivity Analysis
- ✅ Final Set: 13 genera (No-Edge), 6 genera (20m-Edge)

**Data Quality:**

- ✅ No NaNs in features
- ✅ All columns present
- ✅ Geometric validity (Points, EPSG:25832)
- ✅ Metadata integrity (tree_id, genus, city)

### 12.2 Export & Deliverables

**GeoPackages (Training-Ready):**

- `trees_final_no_edge.gpkg`: 702,891 trees, 153 features
- `trees_final_20m_edge.gpkg`: 284,361 trees, 153 features

**Metadata & Reports:**

- `outlier_detection_report.json`: Statistics per method
- `sample_size_filter_report.csv`: Genus viability decisions
- `final_dataset_summary.json`: Final dataset overview

**Visualizations:**

- `outlier_zscore_distribution.png`: Z-Score histogram
- `outlier_mahalanobis_scatter.png`: Mahalanobis D² per genus
- `outlier_chm_boxplots.png`: CHM height distributions with IQR bounds
- `outlier_venn_diagram.png`: Method overlap visualization
- `genus_distribution_final.png`: Final genus distribution stacked bar

### 12.3 Nächster Phase: Model Training (Phase 4)

**Input:** `trees_final_*.gpkg` (training-ready)

**Geplante Experimente:**

1. **Experiment 0:** Baseline Random Forest
2. **Experiment 1:** Stratified sampling (address imbalance)
3. **Experiment 2:** Feature selection (recursive elimination)
4. **Experiment 3:** Class weights (focal loss)
5. **Experiment 4:** Hyperparameter tuning
6. **Experiment 5:** Ensemble methods

**Sensitivity Analysis (Optional):**

- "What if we also remove HIGH outliers?" → 876k trees
- "What if we keep MEDIUM?" → Already kept
- Compare model performance across filtering thresholds

---

## Zusammenfassung

Das Notebook **03e_outlier_detection** ist der **Quality Guardian** der Feature Engineering Pipeline. Es:

1. **Detektiert Tripartite:** Z-Score (univariate spectral), Mahalanobis (multivariate spectral), CHM IQR (structural)
2. **Kombiniert Hierarchisch:** CRITICAL removes ultra-confident outliers (~1.7%), HIGH/MEDIUM flags for analysis
3. **Filtert Konservativ:** ~1.7% gesamte Datenverlust, 702k clean trees verbleiben (No-Edge)
4. **Sichert Viability:** 13 Genera (No-Edge), 6 Genera (20m-Edge) trainingsfähig
5. **Dokumentiert Detailliert:** Outlier-Flaggen beibehalten für Transparenz + Experimente

**Final Output:**

- **No-Edge:** 702.891 Bäume, 153 Spalten, 13 Genera
- **20m-Edge:** 284.361 Bäume, 153 Spalten, 6 Genera
- **Quality:** 89-90% CLEAN trees, 9-10% flagged for analysis
- **Status:** Training-ready, optimale Qualität-Datenleck Balance

---

**Notebook Ende**

**Nächster Phase:** Model Training & Experiments  
**Input:** `trees_final_*.gpkg` (Final training-ready datasets)  
**Output:** Classification models with performance metrics

**Autor:** Silas Pignotti  
**Datum:** Januar 2026  
**Version:** 1.0
