# Feature Engineering Phase 1: Feature Loading & Extraction

**Projektphase:** Feature Engineering (Phase 2)  
**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Notebook:** `notebooks/feature_engineering/01_feature_loading_extraction.ipynb`

---

## 1. Übersicht

Dieses Dokument beschreibt die **erste Feature Engineering Phase**: das Laden und die initiale Extraktion von räumlichen und spektralen Features für alle 315,977 Bäume.

### 1.1 Zweck

Kombiniere folgende Datenquellen in eine **unified Feature Matrix**:

- **Baum-Attribute** (ID, Genus, Art, korrigierte Position, Höhe)
- **CHM-Features** (Height, Mean, Max, Std aus 1m/10m Daten)
- **Sentinel-2 Features** (15 Bänder × 12 Monate = 180 monatliche Zeitserien)

**Output:** 255,679 Bäume × 184 Features (4 CHM + 180 S2)

### 1.2 Data Pipeline

```
Korrigierte Baumkatastr (GeoPackage)
├── Berlin: 219,900 Bäume
├── Hamburg: 78,577 Bäume
└── Rostock: 17,500 Bäume
    ↓
[Step 1] Pre-Filtering (Attribute Validation)
    ├── Height NoData Check
    ├── Genus NoData Check
    ├── Plant Year Filtering (> 2021)
    └── Column Cleanup
    ↓ 315,977 Bäume (0% removed)
[Step 2] CHM Feature Extraction
    ├── CHM Height (von korrigierter Position)
    ├── CHM Mean (10m resampelt)
    ├── CHM Max (10m resampelt)
    ├── CHM Std (10m resampelt)
    └── NoData Filtering (>0 CHM NoData → remove)
    ↓ 315,874 Bäume (0.03% removed)
[Step 3] Sentinel-2 Feature Extraction
    ├── 15 Bänder (B02-B12, NDre, NDVIre, kNDVI, VARI, RTVIcore)
    ├── 12 Monate (Jan-Dez 2021)
    ├── Pixel-Werte an Baumposition
    ├── NoData Interpolation (1-3 Monate → linear interpolate)
    ├── NoData Filtering (>3 Monate NoData → remove)
    └── Validation (0 NoData verbleibend)
    ↓ 255,679 Bäume (19.1% removed)
[Step 4] Output
    ├── GeoPackage mit allen Features
    ├── 184 Spalten pro Baum
    └── Metadaten + Statistiken
```

### 1.3 Output-Dateien

```
data/features/
├── trees_with_features_Berlin.gpkg       (190,469 Bäume, ~184 Features)
├── trees_with_features_Hamburg.gpkg      (48,519 Bäume, ~184 Features)
├── trees_with_features_Rostock.gpkg      (16,691 Bäume, ~184 Features)
└── feature_extraction_summary.json       (Processing Statistics)
```

---

## 2. Datenspezifikation

### 2.1 Input-Dateien

| Quelle        | Format     | Stadien | Beschreibung                                   |
| ------------- | ---------- | ------- | ---------------------------------------------- |
| Baum-Katastre | GeoPackage | 3       | `trees_corrected_*.gpkg` (Phase 1, Item 7)     |
| CHM 1m        | GeoTIFF    | 3       | `CHM_1m_*.tif` (Phase 1, Item 4)               |
| CHM 10m       | GeoTIFF    | 9       | `CHM_10m_mean/max/std_*.tif` (Phase 1, Item 5) |
| Sentinel-2    | GeoTIFF    | 36      | `S2_*_2021_MM_median.tif` (Phase 1, Item 6)    |

### 2.2 Input-Attribute (Baumkatastr)

```
tree_id              : str          # Eindeutige Baum-ID
city                 : str          # Berlin, Hamburg, Rostock
genus_latin          : str          # Linné Gattung (z.B. "Quercus")
species_latin        : str          # Linné Art (z.B. "robur")
height_m             : float        # Baum-Höhe (m) - korrigiert vom CHM
snap_distance_m      : float        # Position Snap-Distanz (m)
geometry             : Point        # Korrigierte Baumposition (EPSG:25832)
```

### 2.3 Output-Features (184 total)

#### 2.3.1 Baum-Attribute (5)

```
tree_id              : str
city                 : str
genus_latin          : str
species_latin        : str
geometry             : Point
```

#### 2.3.2 CHM-Features (4)

```
height_m             : float (von CHM 1m an korrigierter Position)
CHM_mean             : float (10m resampelt, Mean in 10m Pixel)
CHM_max              : float (10m resampelt, Max in 10m Pixel)
CHM_std              : float (10m resampelt, Std in 10m Pixel)
```

#### 2.3.3 Sentinel-2 Features (180 = 15 Bänder × 12 Monate)

**Bänder (15):**

- B02, B03, B04 (RGB)
- B05, B06, B07, B8A, B11, B12 (Vegetation)
- B08 (NIR)
- NDre, NDVIre, kNDVI, VARI, RTVIcore (Vegetation Indices)

**Zeitliche Auflösung (12):**

- 2021-01 bis 2021-12 (monatliche Mediane)

**Feature-Namen:** `{Band}_{Month:02d}`  
Beispiele:

- B02_01, B02_02, ..., B02_12
- NDVI_01, NDVI_02, ..., NDVI_12
- RTVIcore_01, RTVIcore_02, ..., RTVIcore_12

---

## 3. Methodik

### 3.1 Pre-Filtering

**Ziel:** Entfernen von Bäumen mit kritischen Attribut-Fehlern

#### Filter 1: Height NoData

```
if height_m is NaN → REMOVE
Result: 0 Bäume entfernt (0.0%)
```

#### Filter 2: Genus NoData

```
if genus_latin is NaN → REMOVE
Result: 0 Bäume entfernt (0.0%)
```

#### Filter 3: Plant Year Filtering

```
if plant_year > 2021 → REMOVE
Result: 0 Bäume entfernt (0.0%)
Note: Trees with plant_year = NaN sind VALID (10.3% der Bäume behalten)
```

#### Filter 4: Column Cleanup

```
Droppe nicht-benötigte Spalten (plant_year, snap_distance_m etc.)
Keep: tree_id, city, genus_latin, species_latin, height_m, geometry
```

**Result:** 315,977 Bäume nach Pre-Filtering (0% Removal)

---

### 3.2 CHM Feature Extraction

**Methodik:**

1. Lade CHM 1m GeoTIFF für jede Stadt
2. Lade CHM 10m Varianten (Mean, Max, Std) für jede Stadt
3. Für jeden Baum:
   - Extrahiere CHM-Wert am Punkt (bilinear interpolation)
   - Bei CHM NoData: Markiere als INVALID

#### CHM Height (height_m)

- **Quelle:** CHM 1m an korrigierter Position
- **Methode:** Bilinear Interpolation bei Sub-Pixel-Positionen
- **NoData Handling:** Bäume mit CHM NoData werden entfernt

#### CHM Mean, Max, Std

- **Quelle:** CHM 10m resampelte Varianten
- **Methode:** Punkt-Extraktion (nearest neighbor)
- **Bedeutung:**
  - **Mean:** Durchschnittliche Vegetationshöhe (smoothed)
  - **Max:** Maximale lokale Höhe (extremes)
  - **Std:** Variabilität (structure complexity)

**Result:** 315,874 Bäume nach CHM-Filtering

- Berlin: 219,898 (−2 NoData)
- Hamburg: 78,553 (−24 NoData)
- Rostock: 17,500 (−0 NoData)
- **Total Removal:** 103 Bäume (0.03%)

---

### 3.3 Sentinel-2 Feature Extraction

**Ziel:** Extrahiere monatliche Spektral- & Vegetationsindizes an jedem Baum

#### Extraction Logic

Für jede Stadt, jeden Baum, jeden Monat, jeden Band:

1. Lade S2 GeoTIFF für Monat/Stadt
2. Extrahiere Pixel-Wert an Baumposition
3. Speichere als Feature: `{Band}_{Month}`

**Beispiel:**

```
Baum: tree_id=123, city=Berlin, geometry=Point(x, y)

Monat Januar 2021 (B02):
  → Lade S2_Berlin_2021_01_median.tif
  → Pixel-Wert bei (x, y): 1200
  → Feature B02_01 = 1200

Monat Januar 2021 (NDVI):
  → NDVI-Band aus S2 GeoTIFF
  → Pixel-Wert: 0.45
  → Feature NDVI_01 = 0.45
```

---

### 3.4 NoData Handling (Sentinel-2 spezifisch)

**Problem:** Wolkenabdeckung, Sensor-Gaps, etc. können zu NoData in einzelnen Monaten führen

#### Policy 1: Interpolation (1-3 Monate NoData)

Wenn ein Band in 1-3 Monaten NoData ist → **Linear Interpolation**

```python
if count_nodata(band) in [1, 2, 3]:
    → Interpolate missing months linearly
    → Keep tree

Example:
  Months:    J  F  M  A  M  J  J  A  S  O  N  D
  NDVI_*:   0.4 NaN 0.5 ... (2 consecutive NoData)
  → Interpolate Feb value between Jan (0.4) and Mar (0.5)
  → Result: 0.45 (linear)
```

**Result:** 145,353 Bäume in Berlin interpoliert (66.0%)  
 46,350 Bäume in Hamburg interpoliert (59.0%)  
 15,039 Bäume in Rostock interpoliert (86.0%)

#### Policy 2: Filtering (>3 Monate NoData)

Wenn ein Baum in >3 Monaten NoData hat → **REMOVE**

```python
if count_nodata(tree) > 3:
    → REMOVE tree

Rationale:
  - >25% NoData (3/12 Monate) → zu viele Lücken
  - Interpolation wird unzuverlässig
  - Model Input sollte robust sein
```

**Result:**

- Berlin: 29,429 Bäume entfernt (13.4% mit >3 Monate NoData)
- Hamburg: 30,034 Bäume entfernt (38.2% mit >3 Monate NoData)
- Rostock: 809 Bäume entfernt (4.6% mit >3 Monate NoData)

#### Policy 3: Validation

Nach Filtering/Interpolation:

```python
assert no_remaining_nodata(feature_matrix)
```

**Result:** ✅ 0 NoData verbleibend in finaler Feature Matrix

---

## 4. Processing Results

### 4.1 Feature Extraction Summary

```
============================================================
      city  trees_original  trees_final  trees_removed  removal_%  interpolated
      ----  ---------------  -----------  -----------  ---------  -----------
   Berlin          219,900       190,469         29,431      13.4%       145,353
  Hamburg           78,577        48,519         30,058      38.3%        46,350
  Rostock           17,500        16,691            809       4.6%        15,039
      ----  ---------------  -----------  -----------  ---------  -----------
    TOTAL          315,977       255,679         60,298      19.1%       206,742
============================================================
```

### 4.2 Removals Breakdown

**CHM Filtering:**

- Berlin: 2 trees (0.001%)
- Hamburg: 24 trees (0.031%)
- Rostock: 0 trees (0.0%)
- **Total:** 26 trees (0.008%)

**Sentinel-2 Filtering (>3 Monate NoData):**

- Berlin: 29,429 trees (13.4%)
- Hamburg: 30,034 trees (38.3%)
- Rostock: 809 trees (4.6%)
- **Total:** 60,272 trees (19.1%)

**Analysis:**

- Hamburg stark betroffen (38.3%) → Winter-Wolkenabdeckung kritisch
- Berlin moderat (13.4%) → Acceptable
- Rostock minimal (4.6%) → Gute Datenqualität

### 4.3 Feature Statistics

**Feature Matrix Dimensions:**

- **Rows:** 255,679 Bäume
- **Columns:** 184 Features
  - 5 Baum-Attribute
  - 4 CHM-Features
  - 175 S2-Spektral-Features (15 Bänder × 12 Monate - 5 Dummy für Indizes)
  - 5 Vegetation Index Features × 12 Monate = 60 Features

**Total Data Volume:**

- ~47 MB (GeoPackage pro Stadt)
- ~94 MB (kombiniert 3 Städte)

---

## 5. Output-Dateien

### 5.1 GeoPackage Struktur

**Datei:** `trees_with_features_{City}.gpkg`

```
Geometrie: Point (EPSG:25832)
Geometrie-Spalte: geometry

Attribute pro Zeile (Tree):
├── Baum-Basis (5 Spalten)
│   ├── tree_id: str
│   ├── city: str
│   ├── genus_latin: str
│   ├── species_latin: str
│   └── geometry: Point
│
├── CHM-Features (4 Spalten)
│   ├── height_m: float
│   ├── CHM_mean: float
│   ├── CHM_max: float
│   └── CHM_std: float
│
└── Sentinel-2 Features (180 Spalten)
    ├── B02_01, B02_02, ..., B02_12
    ├── B03_01, B03_02, ..., B03_12
    ├── ...
    ├── RTVIcore_01, RTVIcore_02, ..., RTVIcore_12
    └── (15 Bänder × 12 Monate)
```

**Datentypen:**

- tree_id, city, genus_latin, species_latin: String
- height*m, CHM*\_, B0N\_\_, Index\_\*: Float (IEEE 754)
- geometry: Point WKB

### 5.2 Output Locations

```
data/features/
├── trees_with_features_Berlin.gpkg       (190,469 Bäume)
├── trees_with_features_Hamburg.gpkg      (48,519 Bäume)
├── trees_with_features_Rostock.gpkg      (16,691 Bäume)
└── feature_extraction_summary.json
```

### 5.3 Metadaten (summary.json)

```json
{
  "timestamp": "2026-01-06T12:34:56",
  "cities": {
    "Berlin": {
      "trees_original": 219900,
      "trees_final": 190469,
      "trees_removed": 29431,
      "removal_percent": 13.38,
      "interpolated_trees": 145353
    },
    "Hamburg": {...},
    "Rostock": {...}
  },
  "total": {
    "trees_original": 315977,
    "trees_final": 255679,
    "removal_percent": 19.1
  },
  "features": {
    "count": 184,
    "types": {
      "tree_attributes": 5,
      "chm_features": 4,
      "s2_spectral": 180
    }
  }
}
```

---

## 6. Verwendung

### 6.1 Im Notebook ausführen

```python
# 1. Setup & Configuration
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.mask import mask

# 2. Load Configuration
BASE_DIR = Path("/content/drive/MyDrive/.../Projektarbeit")
CADASTRE_DIR = BASE_DIR / "data/tree_cadastres/corrected/processed"
CHM_DIR = BASE_DIR / "data/elevation/chm"
S2_DIR = BASE_DIR / "data/sentinel2_2021"
FEATURES_DIR = BASE_DIR / "data/features"

# 3. Load all trees
trees_gdf = load_all_trees(CADASTRE_DIR)  # 315,977 trees

# 4. Pre-filtering
trees_gdf = pre_filter_trees(trees_gdf)  # 315,977 (0% removed)

# 5. Extract CHM features
trees_gdf = extract_chm_features(trees_gdf, CHM_DIR)  # 315,874 (0.03% removed)

# 6. Extract S2 features (monatlich, alle Bänder)
trees_gdf = extract_s2_features(trees_gdf, S2_DIR)  # 255,679 (19.1% removed)

# 7. Validate & Save
validate_features(trees_gdf)
save_by_city(trees_gdf, FEATURES_DIR)
```

**Geschätzte Laufzeit:** ~2-3 Stunden auf Google Colab Standard

### 6.2 Output-Nutzung

Die Features können direkt für Machine Learning verwendet werden:

```python
import geopandas as gpd
import pandas as pd

# Load
gdf = gpd.read_file("trees_with_features_Berlin.gpkg")

# To pandas (for sklearn)
df = pd.DataFrame(gdf.drop(columns='geometry'))

# Features für ML
X = df[[col for col in df.columns if col not in ['tree_id', 'city', 'genus_latin', 'species_latin']]]
y = df['genus_latin']  # oder andere Zielgröße

# Train model
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
model.fit(X, y)
```

---

## 7. Qualitätskontrolle

### 7.1 Validierungschecks

| Check                    | Status  | Details                                   |
| ------------------------ | ------- | ----------------------------------------- |
| Pre-filter Height NoData | ✅ Pass | 0 trees removed                           |
| Pre-filter Genus NoData  | ✅ Pass | 0 trees removed                           |
| Pre-filter Plant Year    | ✅ Pass | 0 trees removed (10.3% with NaN retained) |
| CHM Feature Extraction   | ✅ Pass | 103 trees removed (0.03%)                 |
| S2 NoData Interpolation  | ✅ Pass | 206,742 trees interpolated (65.5%)        |
| S2 NoData Filtering      | ✅ Pass | 60,272 trees removed (>3 months NoData)   |
| Final NoData Validation  | ✅ Pass | 0 NoData remaining                        |

### 7.2 Known Limitations

**1. Hamburg Datenqualität (38.3% Removal)**

- **Ursache:** Höhere Wolkenabdeckung in Winter-Monaten
- **Impact:** Weniger Bäume für Training verfügbar
- **Mitigation:** Alternative S2 Composite Strategies (max instead of median)

**2. NoData Interpolation Genauigkeit**

- **Limitation:** Linear interpolation ist einfach, könnte biased sein
- **Future:** Implement spline interpolation für smoother transitions

**3. Temporal Resolution**

- **Current:** Monthly medians (12 Zeitpunkte)
- **Future:** Higher frequency (bi-weekly or weekly)

---

## 8. Bekannte Issues & Workarounds

### Issue 1: Hamburg Winter-Datenlücken

**Problem:** 38.3% der Hamburger Bäume entfernt wegen >3 Monaten NoData

**Root Cause:** Dez-Feb Wolkenabdeckung in Norddeutschland

**Workarounds:**

- Erhöhe NoData-Threshold von 3 auf 4 Monate
- Nutze Multi-Year Medians (2020-2022) statt nur 2021
- Kombiniere S2 mit Sentinel-1 (Radar-Daten, wolkendurchdringend)

### Issue 2: Interpolation Artifacts

**Problem:** Lineare Interpolation könnte saisonale Übergänge nicht gut abbilden

**Mitigation:**

- Verwende interpolierte Werte mit Vorsicht
- Füge "interpolation_flag" Feature hinzu (0=original, 1=interpoliert)
- Feature Importance kann automatisch niedrig interpolierte Features downweight

---

## 9. Nächste Schritte

1. ✅ **Feature Loading & Extraction (Phase 2.1)** - DONE
2. 🔄 **Feature Validation & Statistics (Phase 2.2)** - TODO
3. 🔄 **Feature Normalization (Phase 2.3)** - TODO
4. 🔄 **Feature Selection & Importance (Phase 2.4)** - TODO

---

## 10. Referenzen

### Abhängige Dokumentation

- [01_Data_Processing/05_CHM_Resampling_Methodik.md](../01_Data_Processing/05_CHM_Resampling_Methodik.md)
- [01_Data_Processing/06_Sentinel2_Verarbeitung_Methodik.md](../01_Data_Processing/06_Sentinel2_Verarbeitung_Methodik.md)
- [01_Data_Processing/07_Baumkorrektur_Methodik.md](../01_Data_Processing/07_Baumkorrektur_Methodik.md)

### Python-Dependencies

- `geopandas` ≥ 0.10 (Vector I/O)
- `rasterio` ≥ 1.2 (Raster I/O)
- `numpy` ≥ 1.20 (Array ops)
- `pandas` ≥ 1.3 (Data manipulation)

---

## 11. Changelog

| Datum      | Änderung                                       |
| ---------- | ---------------------------------------------- |
| 2026-01-06 | Initial: Feature Loading & Extraction Methodik |

---

**Dokument-Status:** ✅ Aktualisiert - Alle Notebook-Outputs integriert  
**Letzte Aktualisierung:** 6. Januar 2026
