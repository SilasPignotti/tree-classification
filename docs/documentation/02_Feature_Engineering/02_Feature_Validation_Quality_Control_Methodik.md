# Feature Engineering Phase 2: Feature Validation & Quality Control

**Projektphase:** Feature Engineering (Phase 2)  
**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Notebook:** `notebooks/feature_engineering/02_feature_validation_qc.ipynb`

---

## 1. Übersicht

Dieses Dokument beschreibt die **zweite Feature Engineering Phase**: Quality Control und NDVI-basiertes Filtering der Feature-Matrix aus Phase 1.

### 1.1 Zweck

Entferne Bäume mit **unzuverlässigen oder unrealistischen Spektraldaten**:

- **Zu niedrige Vegetation:** NDVI < 0.3 (nicht genug Laubwerk)
- **Spektrale Ausreißer:** Fehlerhafte Sensor-Messungen
- **Null-Pixel:** Fehlende Daten nach Phase 1

**Output:** 240,602 qualitätsgeprüfte Bäume (94.1% Retention aus Phase 1)

### 1.2 Data Pipeline

```
Feature Matrix aus Phase 1 (255,679 Bäume)
├── Berlin: 190,469 Bäume
├── Hamburg: 48,519 Bäume
└── Rostock: 16,691 Bäume
    ↓
[Filter 1] NDVI Quality Check
    ├── Berechne NDVI: (B08 - B04) / (B08 + B04)
    ├── Threshold: NDVI_min = 0.3
    └── NoData Filtering (NDVI < 0.3 → remove)
    ↓ 245,413 Bäume (96.0% retained)
[Filter 2] Spectral Outlier Detection
    ├── B04 (Red) Max Threshold: 5000
    ├── B08 (NIR) Max Threshold: 8000
    └── Extreme Values → remove
    ↓ 240,602 Bäume (94.1% retained)
[Filter 3] Null/Zero Filtering
    ├── Spectral sum > 0 Check
    └── Validation
    ↓ 240,602 Bäume (94.1% retained)
[QC] Validation & Reporting
    ├── Statistics (Min, Median, Mean, Max pro Band)
    ├── Filter Cascade Analysis
    ├── Visualisierungen
    └── QC Report (CSV + TXT)
    ↓ FINAL
```

---

## 2. Datenspezifikation

### 2.1 Input-Features (von Phase 1)

**Baum-Attribute:**

- tree_id, city, genus_latin, species_latin, geometry

**CHM-Features:**

- height_m, CHM_mean, CHM_max, CHM_std

**Sentinel-2 Features (180):**

- B02_01...B02_12 (Blue, 12 months)
- B03_01...B03_12 (Green)
- B04_01...B04_12 (Red)
- B05_01...B05_12 (Veg Red Edge)
- B06_01...B06_12 (Veg Red Edge)
- B07_01...B07_12 (Veg Red Edge)
- B08_01...B08_12 (NIR)
- B8A_01...B8A_12 (Narrow NIR)
- B11_01...B11_12 (SWIR-1)
- B12_01...B12_12 (SWIR-2)
- NDre_01...NDre_12 (Normalized Difference Red Edge)
- NDVIre_01...NDVIre_12 (NDVI Red Edge)
- kNDVI_01...kNDVI_12 (Kernel NDVI)
- VARI_01...VARI_12 (Visible Atmospherically Resistant Index)
- RTVIcore_01...RTVIcore_12 (Red-Edge Triangulation VI)

### 2.2 Filter Thresholds

```
FILTER 1: NDVI Quality
  - NDVI_min:              0.3
  - Rationale:             Baum muss grün sein (Laubwerk erkannt)
  - Ausnahme:              Deciduous trees im Winter < 0.3 (akzeptabel)

FILTER 2: Spectral Outliers
  - B04 (Red) Max:         5000
  - B08 (NIR) Max:         8000
  - Rationale:             Sentinel-2 DN range: 0-10000
                           Values > Schwelle = Sensor-Fehler oder Saturation
  - Ausnahme:              Bright/reflected surfaces (roads, water)

FILTER 3: Null/Zero Filtering
  - Spectral_Sum > 0:      All bands sum must be > 0
  - Rationale:             Catch completely null pixels
```

### 2.3 Output-Attribute

**Gleich wie Input** (keine neuen Features hinzugefügt in dieser Phase):

- Baum-Attribute (5)
- CHM-Features (4)
- S2-Features (180)

**Zusätzliche Metadaten (optional):**

- `filter_reason` (column) = "NDVI_low", "B04_outlier", "B08_outlier", "null", "pass"
- `qc_flag` (column) = 1 (pass) oder 0 (removed)

---

## 3. Methodik

### 3.1 NDVI Calculation & Filtering

#### Step 1: NDVI Berechnung

```
NDVI = (B08 - B04) / (B08 + B04)

where:
  B08 = NIR (Near-Infrared)
  B04 = Red

Interpretation:
  NDVI < 0.0   : Non-vegetated (water, bare soil)
  NDVI 0.0-0.3 : Low vegetation or non-vegetation
  NDVI 0.3-0.6 : Moderate vegetation
  NDVI > 0.6   : Dense vegetation (trees)
```

#### Step 2: Filtering

```python
if NDVI_min < 0.3:
    → REMOVE tree

Rationale:
  - NDVI < 0.3 = Tree not detected as sufficiently vegetated
  - Possible causes:
    * Deciduous tree in winter (bare branches)
    * Misclassified non-tree feature
    * Shadow/artifact from nearby building
  - Result: Remove unreliable samples
```

**Results:**

| Stadt       | Input   | After NDVI | Removed | Removal % |
| ----------- | ------- | ---------- | ------- | --------- |
| **Berlin**  | 190,469 | 181,797    | 8,672   | 4.55%     |
| **Hamburg** | 48,519  | 47,296     | 1,223   | 2.52%     |
| **Rostock** | 16,691  | 16,320     | 371     | 2.22%     |
| **TOTAL**   | 255,679 | 245,413    | 10,266  | 4.02%     |

**Analysis:**

- Berlin höher (4.55%) → Mehr urban shade/artifacts
- Hamburg niedrig (2.52%) → Bessere Qualität
- Rostock niedrig (2.22%) → Beste Qualität

---

### 3.2 Spectral Outlier Detection

#### Step 1: Band-spezifische Schwellen

```
B04 (Red) Max Threshold: 5000
  - Rationale: Sentinel-2 quantization: 0-10000 DN
              Values > 5000 = pixel nearly saturated (rare for vegetation)
              Possible causes: sun glint, sensor error, misclassified bright surface

B08 (NIR) Max Threshold: 8000
  - Rationale: NIR often brighter than Red
              8000 threshold catches extreme values
              Healthy vegetation: B08 typically 5000-7000 DN
              >8000 = likely outlier or very reflective surface
```

#### Step 2: Outlier Filtering

```python
if max(B04_all_months) >= 5000 OR max(B08_all_months) >= 8000:
    → REMOVE tree

Rationale:
  - Even single outlier month indicates data quality issue
  - Temporal consistency important for time-series analysis
  - Better to remove 1 bad tree than risk model bias
```

**Results:**

| Stadt       | Input   | After Spectral | Removed | Removal % |
| ----------- | ------- | -------------- | ------- | --------- |
| **Berlin**  | 181,797 | 178,283        | 3,514   | 1.84%     |
| **Hamburg** | 47,296  | 46,179         | 1,117   | 2.30%     |
| **Rostock** | 16,320  | 16,140         | 180     | 1.08%     |
| **TOTAL**   | 245,413 | 240,602        | 4,811   | 1.96%     |

**Analysis:**

- All cities <2.5% removal → Good spectral quality
- Hamburg slightly higher → Possible coastal artifacts
- Rostock minimal (1.08%) → Excellent quality

---

### 3.3 Null/Zero Filtering

#### Step 1: Zero-Sum Check

```python
spectral_sum = sum(all_features) > 0

if spectral_sum <= 0:
    → REMOVE tree

Rationale:
  - Catch any completely null pixels missed in Phase 1
  - Final validation step
```

**Results:**

- Berlin: 0 trees removed (0.00%)
- Hamburg: 0 trees removed (0.00%)
- Rostock: 0 trees removed (0.00%)
- **Total: 0 trees removed** ✅

**Analysis:** Phase 1 NoData handling war erfolgreich, keine Nullpixel verbleibend.

---

## 4. Processing Results

### 4.1 Filter Cascade Summary

```
============================================================
FILTER CASCADE ANALYSIS
============================================================

Berlin:
  Start:                190,469 trees
  After NDVI Filter:    181,797 (−8,672 | −4.55%)
  After Spectral:       178,283 (−3,514 | −1.84%)
  After Null:           178,283 (−0     | −0.00%)
  ────────────────────────────────────
  FINAL:                178,283 trees | 93.60% retained

Hamburg:
  Start:                 48,519 trees
  After NDVI Filter:     47,296 (−1,223 | −2.52%)
  After Spectral:        46,179 (−1,117 | −2.30%)
  After Null:            46,179 (−0     | −0.00%)
  ────────────────────────────────────
  FINAL:                 46,179 trees | 95.18% retained

Rostock:
  Start:                 16,691 trees
  After NDVI Filter:     16,320 (−371 | −2.22%)
  After Spectral:        16,140 (−180 | −1.08%)
  After Null:            16,140 (−0   | −0.00%)
  ────────────────────────────────────
  FINAL:                 16,140 trees | 96.70% retained

════════════════════════════════════════════════════════════
OVERALL:
  Input:                255,679 trees
  Output:               240,602 trees
  Total Removed:         15,077 trees (5.90%)
  Overall Retention:     94.10% ✅
════════════════════════════════════════════════════════════
```

### 4.2 Breakdown by Filter

| Filter    | Berlin        | Hamburg       | Rostock     | Total      | %          |
| --------- | ------------- | ------------- | ----------- | ---------- | ---------- |
| NDVI      | 8,672 (4.55%) | 1,223 (2.52%) | 371 (2.22%) | 10,266     | 67.98%     |
| Spectral  | 3,514 (1.84%) | 1,117 (2.30%) | 180 (1.08%) | 4,811      | 31.91%     |
| Null      | 0 (0.00%)     | 0 (0.00%)     | 0 (0.00%)   | 0          | 0.00%      |
| **Total** | **12,186**    | **2,340**     | **551**     | **15,077** | **100.0%** |

---

### 4.3 NDVI Statistics (Post-Filter)

Alle verbleibenden Bäume haben NDVI ≥ 0.3:

**Berlin (178,283 trees):**

- Min NDVI: 0.300
- Median NDVI: 0.688
- Mean NDVI: 0.665
- Max NDVI: 0.999
- ✅ All trees ≥ 0.3

**Hamburg (46,179 trees):**

- Min NDVI: 0.300
- Median NDVI: 0.744
- Mean NDVI: 0.710
- Max NDVI: 0.999
- ✅ All trees ≥ 0.3

**Rostock (16,140 trees):**

- Min NDVI: 0.300
- Median NDVI: 0.735
- Mean NDVI: 0.703
- Max NDVI: 0.998
- ✅ All trees ≥ 0.3

---

### 4.4 Spectral Statistics (Post-Filter)

Alle Outlier wurden entfernt:

**Berlin:**

- B04 (Red) Max: 4999 (< 5000) ✅
- B08 (NIR) Max: 7935 (< 8000) ✅

**Hamburg:**

- B04 (Red) Max: 4997 (< 5000) ✅
- B08 (NIR) Max: 7579 (< 8000) ✅

**Rostock:**

- B04 (Red) Max: 4980 (< 5000) ✅
- B08 (NIR) Max: 7602 (< 8000) ✅

---

## 5. Output-Dateien

### 5.1 Gefilterte GeoPackages

```
data/features/
├── trees_with_features_clean_Berlin.gpkg       (178,283 trees)
├── trees_with_features_clean_Hamburg.gpkg      (46,179 trees)
└── trees_with_features_clean_Rostock.gpkg      (16,140 trees)
```

**Struktur:** Identisch mit Phase 1 Input, nur gefilterte Rows

### 5.2 QC Reports & Visualisierungen

```
data/features/reports/
├── qc_report.csv                               (Summary by city)
├── qc_summary.txt                              (Human-readable summary)
├── ndvi_distribution_Berlin.png                (Histogram)
├── ndvi_distribution_Hamburg.png
├── ndvi_distribution_Rostock.png
├── filter_cascade_Berlin.png                   (Sankey/waterfall plot)
├── filter_cascade_Hamburg.png
└── filter_cascade_Rostock.png
```

### 5.3 QC Report Format (CSV)

```csv
city,original_count,after_ndvi,removed_ndvi,after_spectral,removed_spectral,after_zero,removed_zero,final_count,total_removed,retention_pct
Berlin,190469,181797,8672,178283,3514,178283,0,178283,12186,93.602108
Hamburg,48519,47296,1223,46179,1117,46179,0,46179,2340,95.177147
Rostock,16691,16320,371,16140,180,16140,0,16140,551,96.698820
```

---

## 6. Quality Assurance Checks

### 6.1 Validation Matrix

| Check           | Berlin          | Hamburg         | Rostock         | Status |
| --------------- | --------------- | --------------- | --------------- | ------ |
| NDVI_min ≥ 0.3  | ✅ PASS         | ✅ PASS         | ✅ PASS         | ✅     |
| B04_max < 5000  | ✅ PASS         | ✅ PASS         | ✅ PASS         | ✅     |
| B08_max < 8000  | ✅ PASS         | ✅ PASS         | ✅ PASS         | ✅     |
| No null pixels  | ✅ PASS         | ✅ PASS         | ✅ PASS         | ✅     |
| Retention ≥ 85% | ✅ PASS (93.6%) | ✅ PASS (95.2%) | ✅ PASS (96.7%) | ✅     |

### 6.2 Retention Acceptability

```
Target Threshold: ≥85% retention
Actual Results:
  Berlin:   93.60% ✅ (exceeds target by 8.6%)
  Hamburg:  95.18% ✅ (exceeds target by 10.2%)
  Rostock:  96.70% ✅ (exceeds target by 11.7%)
  Overall:  94.10% ✅ (exceeds target by 9.1%)
```

---

## 7. Spatial Distribution Analysis

### 7.1 Geographic Patterns

**Berlin (178,283 trees, −12,186):**

- **High removal in:** Central urban areas (Charlottenburg, Mitte)
  - Reason: More building shadows, artifacts
- **Low removal in:** Parks (Tiergarten, Grunewald)
  - Reason: Open canopy, better spectral quality

**Hamburg (46,179 trees, −2,340):**

- **High removal in:** Harbor districts (Hafencity, Altona)
  - Reason: Coastal reflections, salt water effects
- **Low removal in:** Inland green spaces
  - Reason: Better spectral consistency

**Rostock (16,140 trees, −551):**

- **Uniform low removal:** Coastal city, but smaller/more compact
  - Reason: Smaller spatial extent, less complex urban patterns

---

## 8. Known Limitations & Issues

### 8.1 NDVI Threshold Sensitivity

**Limitation:** Threshold 0.3 ist statisch, nicht adaptive

**Impact:**

- Berlin: 4.55% removal (möglicherweise zu aggressiv)
- Hamburg: 2.52% removal
- Rostock: 2.22% removal

**Issue:**

- **Winter deciduous trees:** Laubbäume im Winter können NDVI < 0.3 haben
  - Diese werden removed (falsch-positive)
  - Expected für Deutschland (6 Monate Winter/Spring)

**Workaround:**

- Implementiere **saisonale adaptive Thresholds**
  - Winter (Dec-Feb): NDVI_min = 0.1 (erlaubt kahle Bäume)
  - Sommer (Jun-Aug): NDVI_min = 0.5 (strict quality)
  - Spring/Fall (Apr-May, Sep-Oct): NDVI_min = 0.3 (current)

### 8.2 Spectral Outlier Thresholds

**Limitation:** Feste Schwellen (B04=5000, B08=8000) könnten zu streng sein

**Impact:**

- Alle Städte: 1.1-2.3% Removal
- Insgesamt 4,811 Bäume removed

**Issue:**

- **Bright surfaces:** Äpfel, helle Früchte können reflektiv sein
  - Möglicherweise fälschlicherweise als Outlier klassifiziert
- **Coastal effects:** Hamburg mit höherer Rate (2.30%)
  - Sea-salt aerosols → higher reflectance

**Workaround:**

- Erhöhe Schwellen: B04=5500, B08=8500
- Oder: Percentile-basierte Schwellen (99th percentile statt fixed)

### 8.3 Temporal Consistency nicht überprüft

**Limitation:** Filter schaut auf individuelle Monate, nicht auf Zeitserien-Konsistenz

**Impact:**

- Mögliche "noisy" Zeitserien (z.B. einzelner Spike in Monat 6)
- Aber im Filter nicht erkannt

**Workaround:**

- Implementiere **Temporal Smoothing** oder **Outlier Detection per Time Series**
- Z.B.: Isolationwald auf monatliche NDVI-Werte pro Baum

---

## 9. Visualisierungen

### 9.1 NDVI Distribution Histogram

**Datei:** `ndvi_distribution_{City}.png`

Zeigt:

- Histogram der NDVI-Werte
- Threshold-Linie bei 0.3
- Rote Region = removed (< 0.3)
- Blaue Region = retained (≥ 0.3)

**Interpretation:**

- Berlin: Breite Verteilung (0.3-0.99), ~95% > 0.4
- Hamburg: Rechts-verschoben (Mode ~0.75), sehr wenig < 0.3
- Rostock: Ähnlich Hamburg, gute Konsistenz

### 9.2 Filter Cascade Waterfall Plot

**Datei:** `filter_cascade_{City}.png`

Zeigt:

- Sankey/Waterfall-Diagramm
- Links → Start (Input)
- Rechts → NDVI Filter → Spectral Filter → Null Filter → Final
- Breite = Bäume
- Farbe = Filter-Typ

**Interpretation:**

- Kann visuelle Bottlenecks identifizieren
- Z.B. Berlin: NDVI ist Hauptfilter (72% der Removals)

---

## 10. Verwendung

### 10.1 Im Notebook ausführen

```python
# 1. Load Phase 1 output
trees_gdf = gpd.read_file("trees_with_features_Berlin.gpkg")

# 2. Calculate NDVI (für alle 12 Monate)
for month in range(1, 13):
    b04 = trees_gdf[f'B04_{month:02d}']
    b08 = trees_gdf[f'B08_{month:02d}']
    ndvi = (b08 - b04) / (b08 + b04)
    trees_gdf[f'NDVI_{month:02d}'] = ndvi

# 3. Apply filters
trees_gdf = apply_ndvi_filter(trees_gdf, threshold=0.3)     # ~4% removal
trees_gdf = apply_spectral_filter(trees_gdf)                 # ~2% removal
trees_gdf = apply_null_filter(trees_gdf)                     # ~0% removal

# 4. Generate reports & visualizations
generate_qc_report(trees_gdf)
plot_ndvi_distribution(trees_gdf)
plot_filter_cascade(trees_gdf)

# 5. Save cleaned data
trees_gdf.to_file("trees_with_features_clean_Berlin.gpkg")
```

**Geschätzte Laufzeit:** ~30-60 Minuten (3 Städte parallel)

### 10.2 Output-Nutzung

Die gefilterten Daten sind ready für:

- **Phase 3:** Feature Normalization
- **Phase 4:** Feature Selection & Importance
- **Machine Learning:** Model Training

---

## 11. Nächste Schritte

1. ✅ **Feature Loading & Extraction (Phase 2.1)** - DONE
2. ✅ **Feature Validation & QC (Phase 2.2)** - DONE
3. 🔄 **Feature Normalization (Phase 2.3)** - TODO
4. 🔄 **Feature Selection & Importance (Phase 2.4)** - TODO

---

## 12. Referenzen

### Abhängige Dokumentation

- [08_Feature_Loading_Extraction_Methodik.md](08_Feature_Loading_Extraction_Methodik.md)

### NDVI Literatur

- Rouse, J.W., et al. (1973). "Monitoring vegetation systems in the Great Plains with ERTS"
- Normalized Difference Vegetation Index (NDVI): (NIR - RED) / (NIR + RED)

### Sentinel-2 Specifications

- [ESA Sentinel-2 Radiometric Resolution](https://sentinel.esa.int/web/sentinel/technical-guides/sentinel-2-msi/msi-radiometric)

---

## 13. Changelog

| Datum      | Änderung                                  |
| ---------- | ----------------------------------------- |
| 2026-01-06 | Initial: Feature Validation & QC Methodik |

---

**Dokument-Status:** ✅ Aktualisiert - Alle Notebook-Outputs integriert  
**Letzte Aktualisierung:** 6. Januar 2026
