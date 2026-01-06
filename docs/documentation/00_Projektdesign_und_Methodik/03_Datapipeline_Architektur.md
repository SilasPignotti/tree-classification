# Datapipeline-Architektur & System-Design

**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Zielgruppe:** Entwickler, Techniker, DevOps

---

## 1. System-Architektur (Übersicht)

### 1.1 Datenfluss (High-Level)

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT LAYER - Raw Geospatial Data                           │
├─────────────────────────────────────────────────────────────┤
│ OSM (Boundaries) → Tree Cadastres → Elevation (DOM/DGM)    │
│ Sentinel-2 L2A (GEE) → Monthly Composites (36 files)       │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA PROCESSING (7 Stages)                         │
├─────────────────────────────────────────────────────────────┤
│ 1.1: Boundary Standardization (CRS, clipping)              │
│ 1.2: Tree Registry Harmonization (schema, validation)      │
│ 1.3: Elevation Data Ingestion (GeoTIFF)                    │
│ 1.4: CHM Derivation (DOM - DGM)                            │
│ 1.5: CHM Resampling (1m → 10m windowed)                    │
│ 1.6: Sentinel-2 Composite Stack                            │
│ 1.7: Tree Position Correction (Snap-to-Peak)              │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
         OUTPUT: Processed Datasets (315,977 trees)
         - CHM_1m_*.tif (3 files)
         - CHM_10m_*.tif (9 files)
         - S2_*_median.tif (36 files)
         - trees_corrected_*.gpkg (3 files)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: FEATURE ENGINEERING (5 Stages)                    │
├─────────────────────────────────────────────────────────────┤
│ 2.1: Feature Loading & Extraction (CHM + S2)              │
│ 2.2: Feature Validation & QC (NDVI, Spectral filtering)   │
│ 2.3: Dataset Balancing (7 viable genera, 1,500/class)     │
│ 2.4: Spatial Block Split (500×500m, 80/20 train/val)      │
│ 2.5: Feature Normalization (Z-Score, Label Encoding)      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
      OUTPUT: ML-Ready Datasets (28,866 trees × 184 features)
      - experiment_0_1_single_city/ (Hamburg, Berlin)
      - experiment_2_cross_city/ (Hamburg+Berlin → Rostock)
      - experiment_3_finetuning/ (Rostock adaptation)
      - .npy arrays (X_train, y_train, X_val, y_val, X_test)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: MODEL TRAINING (Planned)                           │
├─────────────────────────────────────────────────────────────┤
│ 3.1: Baseline Models (RFC, XGBoost)                        │
│ 3.2: Deep Learning (CNN, Transformer)                      │
│ 3.3: Hyperparameter Tuning (GridSearch, RandomSearch)      │
│ 3.4: Cross-Validation (5-Fold, Stratified)                 │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
         OUTPUT: Trained Models (.pkl, .h5)
         - model_hamburg_rf.pkl
         - model_combined_xgb.pkl
         - model_rostock_finetuned.h5
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: INFERENCE & VALIDATION (Planned)                  │
├─────────────────────────────────────────────────────────────┤
│ 4.1: Model Evaluation (Accuracy, F1, Confusion Matrix)     │
│ 4.2: Error Analysis (Misclassification patterns)           │
│ 4.3: Inference Pipeline (Apply to new data)                │
│ 4.4: Export Predictions (GeoPackage)                       │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
         OUTPUT: Final Predictions
         - predictions_hamburg.gpkg (predictions + geometry)
         - predictions_berlin.gpkg
         - predictions_rostock.gpkg
         - accuracy_report.csv
```

---

## 2. Module & Dependencies

### 2.1 Phase 1: Data Processing

```python
MODULES:
├── boundaries/
│   └── download_city_boundaries.py
│       ├── Input: OSM API
│       ├── Output: city_boundaries_*.gpkg
│       └── Deps: osmnx, geopandas
│
├── tree_cadastres/
│   ├── download_tree_cadastres.py (municipal data)
│   ├── harmonize_tree_cadastres.py (schema align)
│   └── filter_trees.py (basic QC)
│       └── Deps: geopandas, pandas
│
├── elevation/
│   ├── berlin/ & hamburg/ & rostock/
│   │   └── download_elevation.py (DEM/DSM)
│   └── Deps: rasterio, numpy, GDAL
│
├── chm/
│   ├── create_chm.py (CHM = DOM - DGM)
│   ├── harmonize_chm.py (standardization)
│   └── analyze_chm_distribution.py (QC stats)
│       └── Deps: rasterio, numpy, scipy
│
└── sentinels/
    └── (Part of Phase 1.6: Google Earth Engine)
        └── Deps: google-earth-engine, geemap
```

### 2.2 Phase 2: Feature Engineering

```python
MODULES:
├── notebooks/feature_engineering/
│   ├── 01_tree_correction.ipynb
│   │   └── Snap-to-Peak CHM correction
│   │
│   ├── 02_sentinel2_gee_download.ipynb
│   │   └── Monthly S2 composites
│   │
│   ├── 03_chm_resampling.ipynb
│   │   └── 1m → 10m windowed resampling
│   │
│   ├── 04_feature_extraction.ipynb
│   │   ├── CHM features (4)
│   │   └── S2 features (180)
│   │
│   ├── 05_feature_validation_qc.ipynb
│   │   ├── NDVI filtering
│   │   └── Spectral outlier detection
│   │
│   ├── 06_dataset_balancing.ipynb
│   │   └── Stratified downsampling
│   │
│   ├── 07_spatial_block_split.ipynb
│   │   └── 500×500m block-level splits
│   │
│   └── 08_feature_normalization.ipynb
│       ├── StandardScaler (Z-Score)
│       └── Label Encoding (0-6)
│
└── Deps: geopandas, rasterio, scikit-learn, numpy
```

### 2.3 Phase 3: Model Training (Planned)

```python
MODULES (Planned):
├── models/
│   ├── baseline_rf.py
│   │   └── Random Forest (sklearn)
│   │
│   ├── baseline_xgb.py
│   │   └── XGBoost (xgboost library)
│   │
│   ├── deep_learning_cnn.py
│   │   └── Convolutional Neural Network (TensorFlow/Keras)
│   │
│   └── deep_learning_transformer.py
│       └── Vision Transformer (optional, advanced)
│
├── training/
│   ├── train_single_city.py
│   ├── train_cross_city.py
│   └── train_finetune.py
│
├── validation/
│   ├── cross_validation.py (k-fold)
│   ├── hyperparameter_tuning.py
│   └── model_evaluation.py (metrics)
│
└── Deps: scikit-learn, xgboost, tensorflow/keras
```

---

## 3. Data Formats & Storage

### 3.1 Input Formats

| Stage          | Format                  | Example                      | Size       |
| -------------- | ----------------------- | ---------------------------- | ---------- |
| Boundaries     | GeoPackage              | city_boundaries_Berlin.gpkg  | 5 MB       |
| Tree Cadastres | GeoPackage/Shapefile    | trees_Berlin.gpkg            | 50 MB      |
| Elevation      | GeoTIFF (LZW)           | DOM_Berlin_1m.tif            | 2-3 GB     |
| Sentinel-2     | Cloud-Optimized GeoTIFF | S2_Berlin_2021_06_median.tif | 100-200 MB |

### 3.2 Intermediate Formats (Phase 1 Output)

| File            | Format     | Size       | Records                |
| --------------- | ---------- | ---------- | ---------------------- |
| CHM_1m          | GeoTIFF    | 1-2 GB     | Raster (1m pixels)     |
| CHM_10m         | GeoTIFF    | 100-200 MB | Raster (10m pixels)    |
| S2_Composite    | GeoTIFF    | 150 MB     | Raster (10m, 15 bands) |
| trees_corrected | GeoPackage | 50 MB      | 315,977 trees          |

### 3.3 Final Formats (Phase 2 Output)

| File               | Format       | Shape         | Dtype          |
| ------------------ | ------------ | ------------- | -------------- |
| X_train.npy        | NumPy Binary | (16,670, 184) | float32        |
| y_train.npy        | NumPy Binary | (16,670,)     | int32          |
| scaler.pkl         | Pickle       | -             | sklearn object |
| label_encoder.pkl  | Pickle       | -             | sklearn object |
| feature_names.json | JSON         | -             | Metadata       |

---

## 4. Computing Infrastructure

### 4.1 Local Development

```
Machine: MacBook Pro
├── CPU: Apple Silicon M1
├── RAM: 16 GB
└── Storage: 500 GB SSD

Software:
├── Python 3.9
├── QGIS 3.28
├── Git/GitHub
└── VS Code
```

### 4.2 Cloud Processing (Google Colab)

```
Google Colab Notebook Environment:
├── CPU: 2+ vCPU (varies)
├── RAM: 12-15 GB
├── GPU: Optional (T4, P100, V100)
├── Storage: Drive mounted (100 GB)
└── Runtime: ~12 hours per session

Cost: FREE (for research)
```

### 4.3 Production Deployment (Future)

```
Potential Setup:
├── Cloud Provider: Google Cloud / AWS / Azure
├── Compute: Virtual Machine (4 vCPU, 16GB RAM)
├── Storage: Cloud Storage (S3, GCS)
├── Database: PostgreSQL + PostGIS (for spatial queries)
└── API: Flask/FastAPI for inference
```

---

## 5. Dependencies & Environment

### 5.1 Python Packages (Core)

```txt
# Geospatial
geopandas==0.13.0
rasterio==1.3.0
shapely==2.0.0
pyproj==3.4.0

# Data Processing
numpy==1.24.0
pandas==2.0.0
scipy==1.10.0

# Machine Learning
scikit-learn==1.3.0
xgboost==2.0.0
tensorflow==2.13.0  # Optional for deep learning

# Utilities
matplotlib==3.7.0
seaborn==0.12.0
```

### 5.2 System Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin libgdal-dev

# macOS (Homebrew)
brew install gdal
```

### 5.3 Virtual Environment Setup

```bash
# Create environment
python -m venv env_trees
source env_trees/bin/activate

# Install from requirements.txt
pip install -r requirements.txt

# Or: Google Colab (auto-installs most)
!pip install geopandas rasterio xgboost
```

---

## 6. Räumliche & Technische Spezifikationen

### 6.1 Koordinatenreferenzsystem (CRS): EPSG:25832

**Wahl: UTM Zone 32N (Universal Transverse Mercator)**

```
EPSG Code:     25832
Name:          ETRS89 / UTM zone 32N
Type:          Projected (Planar)
Datum:         ETRS89 (European Terrestrial Reference System 1989)
Units:         Meters (m)
```

**Begründung:**

| Kriterium                          | EPSG:25832                             | Alternative (EPSG:4326)          |
| ---------------------------------- | -------------------------------------- | -------------------------------- |
| **Geographischer Geltungsbereich** | Genau für Deutschland/Nord-Europa      | Global, Kompromiss               |
| **Verzerrung**                     | Minimal (metrische Genauigkeit)        | ±100m auf dieser Breite          |
| **Distanzberechnung**              | Direkt in Metern                       | Erfordert Approximation          |
| **Flächen-Berechnung**             | Exakt (für Waldschäden)                | Approximativ                     |
| **Praktisch**                      | Bundesamt für Kartographie nutzt 25832 | Nicht für Öko-Analysen empfohlen |

**Implementierung:**

- Alle OSM Boundaries: EPSG:4326 → EPSG:25832 (reprojiziert)
- Alle Tree Cadastres: Original CRS → EPSG:25832 (harmonisiert)
- Alle Elevation Daten: GeoTIFF in EPSG:25832 (native)
- Sentinel-2: GEE nutzt EPSG:4326 intern, aber GeoTIFF-Output in EPSG:25832 exportiert

### 6.2 Sentinel-2 Processing: Google Earth Engine Backend

**Cloud Computing Infrastruktur (Nicht lokal!)**

```
Provider:           Google Earth Engine (GEE)
Collection:         COPERNICUS/S2_SR_HARMONIZED (L2A, atmosphärisch korrigiert)
Verarbeitung:       Server-seitig (Google-Rechenzentren)
Zugriff:            Python API (ee library) über Jupyter Notebooks
```

**Warum Google Earth Engine (nicht openEO)?**

| Aspekt                      | GEE                                      | openEO                                        |
| --------------------------- | ---------------------------------------- | --------------------------------------------- |
| **Standardisierung**        | Google-proprietärer Standard             | Open Standard (EU-Projekt)                    |
| **Verfügbarkeit**           | Alle Sentinel-2 L2A Daten vorverarbeitet | Abhängig vom Backend-Anbieter                 |
| **Performance**             | Sehr schnell (parallele Processing)      | Variabel                                      |
| **Kostenlos für Forschung** | Ja                                       | Ja (mit Limits)                               |
| **Nutzer-Community**        | Große Community, viele Tutorials         | Kleiner, wachsend                             |
| **Gewählt für Projekt**     | ✅ Ja                                    | ❌ Nein (zu komplex für schnelle Prototyping) |

**Sentinel-2 Daten-Pipeline (Phase 1.6):**

```
INPUT:  Stadt Boundaries (EPSG:4326 → GEE)
  ↓
FILTERING:
  - Date Range: 2021-01-01 bis 2021-12-31
  - Cloud Cover: < 10%
  - Result: ~300-500 Sentinel-2 Bilder pro Stadt
  ↓
CLOUD MASKING (Details siehe 6.3):
  - SCL Band (Scene Classification Layer)
  - Whitelist: [4, 5, 7] (Vegetation, Non-veg, Shadow)
  - Blacklist: [0,1,2,3,6,8,9,10,11] (Clouds, Water, Dark, etc.)
  ↓
MONTHLY AGGREGATION:
  - 12 Monatsmediane pro Jahr (Jan-Dez 2021)
  - Bilinear Resampling: 20m/60m → 10m
  - Output: 12 Composite-Bilder pro Stadt
  ↓
BAND EXPORT:
  - 10 Bänder insgesamt:
    * Blue (B2, 10m native)
    * Green (B3, 10m native)
    * Red (B4, 10m native)
    * NIR (B8, 10m native)
    * Red-Edge (B5,B6,B7,B8A, 20m→10m)
    * SWIR (B11,B12, 20m→10m)
  - Output: 36 GeoTIFF Dateien (12 Monate × 3 Städte)
```

### 6.3 Cloud Masking via SCL Band (Scene Classification Layer)

**Problem:** Sentinel-2 Bilder enthalten Wolken, Wasser, Schnee, Schatten – diese verfälschen Spektralsignaturen.

**Lösung: Scene Classification Layer (SCL)**

GEE nutzt das **SCL-Band** von Sentinel-2 L2A – eine Pixel-weise Klassifizierung der Szene:

| SCL Wert | Klasse                   | GEE Behandlung | Grund                                             |
| -------- | ------------------------ | -------------- | ------------------------------------------------- |
| 0        | No Data                  | ❌ Blacklist   | Keine Daten                                       |
| 1        | Saturated/Defective      | ❌ Blacklist   | Sensor-Fehler                                     |
| 2        | Dark Area Pixels         | ❌ Blacklist   | Schatten (nicht repräsentativ)                    |
| 3        | Cloud Shadows            | ❌ Blacklist   | Indirekte Wolken-Effekte                          |
| 4        | Vegetation               | ✅ Whitelist   | **Bäume & Vegetation**                            |
| 5        | Non-Vegetated            | ✅ Whitelist   | Gebäude, Asphalt, Boden                           |
| 6        | Water                    | ❌ Blacklist   | Keine Baum-Daten dort                             |
| 7        | Unclassified             | ✅ Whitelist   | Randfälle (grenzwertiges Klassifikation)          |
| 8        | Cloud Medium Probability | ❌ Blacklist   | Wahrscheinlich Wolke                              |
| 9        | Cloud High Probability   | ❌ Blacklist   | Definitiv Wolke                                   |
| 10       | Thin Cirrus              | ❌ Blacklist   | Dünne Zirruswolken                                |
| 11       | Snow/Ice                 | ❌ Blacklist   | Im Januar möglich, aber rarität in Hamburg/Berlin |

**GEE Implementierung (Pseudocode):**

```javascript
// GEE SCL Filtering
function maskClouds(image) {
  var scl = image.select("SCL");
  var mask = scl.isin([4, 5, 7]); // Vegetation, Non-veg, Unclassified
  return image.updateMask(mask);
}

// Apply to all S2 images in collection
var cloudFreeComposite = s2Collection.map(maskClouds).median(); // Monthly median ignores remaining outliers
```

**Resultat:**

- Qualitativ saubere Sentinel-2 Spektralsignaturen
- Keine wolkenkontaminierten Pixel in Trainings-Features
- Robuste Spektral-Indizes (NDVI, etc.)

---

## 7. Workflow & Execution

### 7.1 Local Workflow

```bash
# 1. Clone repository
git clone https://github.com/SilasPignotti/tree-classification.git
cd tree-classification

# 2. Setup environment
python -m venv env
source env/bin/activate
pip install -r requirements.txt

# 3. Download data (Phase 1 Scripts)
python scripts/boundaries/download_city_boundaries.py
python scripts/tree_cadastres/download_tree_cadastres.py

# 4. Run QGIS for visualization
qgis

# 5. Run Colab notebooks (Phases 1-2)
# → Upload to Google Colab, execute
```

### 6.2 Colab Workflow (Preferred for Heavy Lifting)

```python
# In Google Colab:
from google.colab import drive
drive.mount('/content/drive')

# Install packages
!pip install geopandas rasterio xgboost

# Import data from Drive
import geopandas as gpd
trees = gpd.read_file('/content/drive/MyDrive/.../trees_corrected.gpkg')

# Run analysis
# ... (notebook cells)

# Export results
trees.to_file('/content/drive/MyDrive/.../output.gpkg')
```

---

## 7. Error Handling & Validation

### 7.1 Data Validation Checks

| Stage             | Check              | Threshold       | Action           |
| ----------------- | ------------------ | --------------- | ---------------- |
| **Boundaries**    | Missing geometries | 0%              | Fail if any      |
| **Tree Cadastre** | Duplicates         | 0%              | Remove           |
| **CHM**           | NaN pixels         | <50%            | Interpolate/Warn |
| **S2 Composite**  | Cloud cover        | >80% (temporal) | Filter month     |
| **Features**      | Outliers (3σ)      | Allow <2%       | Flag in report   |
| **Labels**        | Missing classes    | Must have all 7 | Fail if missing  |

### 7.2 Quality Metrics (Phase-wise)

```python
# Phase 1 Validation
assert trees_cleaned.shape[0] / trees_input.shape[0] > 0.80  # >80% retained

# Phase 2.1 Validation
assert X_features.shape == (255679, 184)
assert X_features.isnull().sum().sum() < 1000  # <1000 NaN

# Phase 2.5 Validation
assert X_train.mean() < 0.01  # ~0 mean
assert X_train.std() < 1.01   # ~1 std
assert y_train.unique().size == 7  # 7 classes
```

---

## 8. Performance & Scalability

### 8.1 Computational Complexity

| Operation            | Complexity                | Time (3 cities) |
| -------------------- | ------------------------- | --------------- |
| CHM Creation         | O(n_pixels)               | ~30 hours       |
| CHM Resampling       | O(n_blocks × buffer)      | ~25 minutes     |
| S2 Download (GEE)    | O(n_months × n_scenes)    | ~3-5 hours      |
| Feature Extraction   | O(n_trees × n_features)   | ~2 hours        |
| Model Training (RF)  | O(n_samples × n_features) | ~1-5 minutes    |
| Model Training (CNN) | O(n_epochs × n_batches)   | ~10-30 minutes  |

### 8.2 Memory Footprint

```
Single Raster (1m CHM, 20km×20km):
  ~400 million pixels × 4 bytes (float32) = ~1.6 GB

Feature Matrix (28,866 trees × 184 features):
  ~28,866 × 184 × 4 bytes = ~21 MB (very manageable)

Model Artifacts:
  RFC model: ~50-100 MB
  CNN model: ~200-500 MB
```

---

## 9. Documentation & Reproducibility

### 9.1 File Organization

```
tree-classification/
├── docs/
│   ├── documentation/
│   │   ├── 00_Projektdesign_und_Methodik/
│   │   ├── 01_Data_Processing/
│   │   ├── 02_Feature_Engineering/
│   │   └── METHODOLOGY_OVERVIEW.md
│   └── Projektdesign.json
│
├── scripts/
│   ├── boundaries/
│   ├── tree_cadastres/
│   ├── elevation/
│   ├── chm/
│   └── sentinels/
│
├── notebooks/
│   ├── feature_engineering/
│   │   ├── 01_tree_correction.ipynb
│   │   ├── 02_sentinel2_gee_download.ipynb
│   │   └── ... (8 total)
│   └── model_training/
│       ├── 01_baseline_models.ipynb
│       └── ... (planned)
│
├── data/
│   ├── boundaries/
│   ├── tree_cadastres/
│   ├── elevation/
│   ├── chm/
│   ├── sentinels/
│   ├── features/
│   ├── splits/
│   └── model_ready/
│
├── src/
│   └── utils.py (shared functions)
│
├── requirements.txt
├── README.md
└── .gitignore
```

### 9.2 Reproducibility Checklist

- ✅ **Seeds:** All random seeds fixed (random_state=42)
- ✅ **Versions:** All package versions pinned in requirements.txt
- ✅ **Documentation:** Every step documented in Methodology
- ✅ **Code:** All code in version control (GitHub)
- ✅ **Data:** Data lineage tracked (input → output)
- ✅ **Results:** All results exportable & replicable

---

## 10. Monitoring & Logging

### 10.1 Logging Strategy

```python
import logging

logging.basicConfig(
    filename='pipeline.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info('Starting Phase 1 processing...')
logger.warning('Detected 100 cloud pixels in S2 composite')
logger.error('CHM resampling failed: Invalid raster')
```

### 10.2 Metrics Tracking

```
Phase 1 Metrics:
├── Input trees: 363,571
├── Output trees: 315,977
├── Retention rate: 86.9%
└── Processing time: 35-40h

Phase 2 Metrics:
├── Features per tree: 184
├── Data after QC: 240,602 trees
├── Data after balancing: 28,866 trees
├── Train/Val split: 16,670 / 4,118
└── Processing time: 20-25h
```

---

**Dokument-Status:** ✅ Abgeschlossen  
**Letzte Aktualisierung:** 6. Januar 2026
