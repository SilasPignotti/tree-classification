# Projekt-Gesamtmethodologie: Tree Classification

**Projekt:** Automatische Baumartenklassifizierung mittels multispektraler Daten & Canopy Height Model  
**Zeitraum:** 2021 (Fokus auf Berlin, Hamburg, Rostock)  
**Status:** Phase 0-2 abgeschlossen, Phase 3 in Planung  
**Letzte Aktualisierung:** 6. Januar 2026

---

## Executive Summary

Dieses Projekt entwickelt ein **Machine-Learning-System zur automatischen Baumartenklassifizierung** auf Gattungsebene (Genus) mittels:

1. **Hochauflösender Höhendaten:** CHM (Canopy Height Model, 1m/10m)
2. **Multispektraler Satellitendaten:** Sentinel-2 (10m, 15 Bänder, 12 Monate)
3. **Präziser Baum-Lokalisierung:** Snap-to-Peak korrigierte Positionen & Höhen

**Datengrundlage:** 315,977 Bäume → 28,866 ML-Ready Samples (7 Gattungen, balanciert)

**Forschungsfokus:** Cross-City Transfer Learning (Hamburg+Berlin → Rostock)

---

## Dokumentationsstruktur

### Phase 0: Projektdesign & Methodische Grundlagen

**Ordner:** [00_Projektdesign_und_Methodik/](00_Projektdesign_und_Methodik/)

Übergreifende Konzepte, theoretische Grundlagen und Systemarchitektur:

#### [01_Projektübersicht.md](00_Projektdesign_und_Methodik/01_Projektübersicht.md)

- Executive Summary, Forschungsfragen, Timeline

#### [02_Methodische_Grundlagen.md](00_Projektdesign_und_Methodik/02_Methodische_Grundlagen.md)

- Spektrale Theorie, Phänologie, ML-Paradigmen, Experimentdesign

#### [03_Datapipeline_Architektur.md](00_Projektdesign_und_Methodik/03_Datapipeline_Architektur.md)

- Systemdesign, Module, CRS, GEE-Backend, Cloud-Masking

---

### Phase 1: Data Processing & Preprocessing ✅

**Ordner:** [01_Data_Processing/](01_Data_Processing/)  
**Status:** Abgeschlossen (7 Methodikdokumente)

Sammlung, Validierung und Standardisierung aller Input-Daten:

#### [01_Stadtgrenzen_Methodik.md](01_Data_Processing/01_Stadtgrenzen_Methodik.md)

- OSM-Boundaries Download & Harmonisierung
- CRS-Transformation zu EPSG:25832
- Clipping-Layer für räumliche Eingrenzung

#### [02_Baumkataster_Methodik.md](01_Data_Processing/02_Baumkataster_Methodik.md)

- Download kommunaler Baumregister (Berlin: 648k, Hamburg: 256k, Rostock: 52k)
- Schema-Harmonisierung (Gattung, Höhe, Position, Pflanzjahr)
- Edge-Filter Varianten (0m, 15m, 20m, 30m)
- Output: 363,571 Bäume (8 Gattungen) für edge_15m

#### [03_Hoehendaten_DOM_DGM_Methodik.md](01_Data_Processing/03_Hoehendaten_DOM_DGM_Methodik.md)

- DOM (Digital Surface Model) & DGM (Digital Terrain Model)
- 1m Auflösung, LiDAR-basiert
- Validierung: Höhenbereiche, NoData-Behandlung

#### [04_CHM_Erstellung_Methodik.md](01_Data_Processing/04_CHM_Erstellung_Methodik.md)

- CHM = DOM - DGM (Vegetationshöhe)
- Filterung: 0-50m Wertebereich (NoData für <-2m und >50m)
- Verteilungsanalyse: Negative Werte, Hochhaus-Artefakte

#### [05_CHM_Resampling_Methodik.md](01_Data_Processing/05_CHM_Resampling_Methodik.md)

- Windowed Resampling: 1m → 10m (Sentinel-2 Auflösung)
- 3 Aggregationsmethoden: Mean, Max, Std
- Output: 9 CHM-Varianten (3 Städte × 3 Methoden)

#### [06_Sentinel2_Verarbeitung_Methodik.md](01_Data_Processing/06_Sentinel2_Verarbeitung_Methodik.md)

- Google Earth Engine Backend (COPERNICUS/S2_SR_HARMONIZED)
- 12 monatliche Mediankomposite (Jan-Dez 2021)
- 15 Bänder: 10 spektral + 5 Vegetation Indizes
- SCL-basiertes Cloud Masking (Whitelist: 4,5,7)
- Output: 36 GeoTIFF Dateien (12 Monate × 3 Städte)

#### [07_Baumkorrektur_Methodik.md](01_Data_Processing/07_Baumkorrektur_Methodik.md)

- Snap-to-Peak: Verschiebung zu CHM-Maximum (±5m Radius)
- Höhenkorrektur: Kataster-Höhe → CHM-Höhe (height_m)
- Output: 315,977 korrigierte Bäume

---

### Phase 2: Feature Engineering ✅

**Ordner:** [02_Feature_Engineering/](02_Feature_Engineering/)  
**Status:** Abgeschlossen (5 Methodikdokumente)

Extraktion, Validierung, Balancierung und ML-Vorbereitung:

#### [01_Feature_Loading_Extraction_Methodik.md](02_Feature_Engineering/01_Feature_Loading_Extraction_Methodik.md)

- CHM-Features: 4 (height_m, CHM_mean, CHM_max, CHM_std)
- Sentinel-2: 180 Features (10 Bänder + 5 Indizes × 12 Monate)
- NoData-Handling: Interpolation (≤3 Monate), Ausschluss (>3 Monate)
- Output: 255,679 Bäume × 184 Features

#### [02_Feature_Validation_Quality_Control_Methodik.md](02_Feature_Engineering/02_Feature_Validation_Quality_Control_Methodik.md)

- NDVI-Filter: < 0.3 entfernt (Non-Vegetation)
- Spektrale Outlier: B04/B08 > 8000
- Null/Zero-Filtering
- Output: 240,602 Bäume (94.1% Retention)

#### [03_Dataset_Balancing_Class_Stratification_Methodik.md](02_Feature_Engineering/03_Dataset_Balancing_Class_Stratification_Methodik.md)

- Viable Genera: ≥500 Samples in allen Städten
- 7 Gattungen: TILIA, ACER, QUERCUS, FRAXINUS, BETULA, SORBUS, PRUNUS
- Stratified Downsampling: 1,500 Samples/Genus
- Output: 28,866 balancierte Bäume

#### [04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md](02_Feature_Engineering/04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md)

- 500×500m Spatial Blocks (verhindert Spatial Leakage)
- Hamburg: 8,371 Train / 2,129 Val
- Berlin: 8,299 Train / 1,989 Val
- Rostock: 6,675 Zero-Shot Test / 1,403 Fine-Tune Eval
- Output: 6 spatially disjoint Datasets

#### [05_Feature_Normalization_Model_Ready_Export_Methodik.md](02_Feature_Engineering/05_Feature_Normalization_Model_Ready_Export_Methodik.md)

- StandardScaler (Z-Score Normalization)
- Label Encoding: ACER(0) ... TILIA(6)
- 3 Experiment-Setups:
  - Exp 0/1: Single-City (Hamburg/Berlin separat)
  - Exp 2: Cross-City (Hamburg+Berlin → Rostock)
  - Exp 3: Fine-Tuning (Rostock-Adaptation)
- Output: NumPy Arrays (.npy), Pickles (Scaler, Encoder)

---

### Phase 3: Model Training & Evaluation 📋

**Ordner:** [03_Model_Training/](03_Model_Training/)  
**Status:** Geplant (1 Methodikdokument dokumentiert)

Machine Learning Experimente zur Baumartenklassifizierung:

#### [01_Experimentstrategie_Methodik.md](03_Model_Training/01_Experimentstrategie_Methodik.md)

**Experiment 0:** Baseline-Etablierung (Random Forest vs. 1D-CNN)  
**Experiment 1:** Single-City Performance (Hamburg/Berlin separat)  
**Experiment 2:** Cross-City Transfer (Hamburg+Berlin → Rostock Zero-Shot)  
**Experiment 3:** Fine-Tuning (Rostock-Adaptation mit 50/100/200 Samples)

**Geplante weitere Dokumente:**

- `02_Experiment_0_Baseline_RF_CNN.md` - Methodenvergleich & Entscheidungsregel
- `03_Experiment_1_Single_City.md` - Stadtspezifische Baselines
- `04_Experiment_2_Cross_City_Transfer.md` - Transfer Loss Quantifizierung
- `05_Experiment_3_Fine_Tuning.md` - Minimum Data Requirements

---

## Datenfluss (Pipeline-Übersicht)

```
OSM Boundaries → Tree Cadastres → Elevation (DOM/DGM) → Sentinel-2 (GEE)
         ↓               ↓                ↓                      ↓
   PHASE 1: DATA PROCESSING
         ↓
   - CHM Derivation (DOM - DGM)
   - CHM Resampling (1m → 10m: Mean/Max/Std)
   - Sentinel-2 Monthly Composites (12 × 15 Bands)
   - Tree Position Correction (Snap-to-Peak)
         ↓
   315,977 corrected trees + CHM_10m + S2_composites
         ↓
   PHASE 2: FEATURE ENGINEERING
         ↓
   - Feature Extraction (CHM: 4, S2: 180)
   - Quality Control (NDVI, Outliers)
   - Balancing (7 Genera, 1,500/class)
   - Spatial Split (500×500m blocks, 80/20)
   - Normalization (StandardScaler)
         ↓
   28,866 trees × 184 features (ML-Ready)
         ↓
   PHASE 3: MODEL TRAINING (Geplant)
         ↓
   - Exp 0: RF vs CNN Baseline
   - Exp 1: Single-City Models
   - Exp 2: Transfer Learning (Hamburg+Berlin → Rostock)
   - Exp 3: Fine-Tuning Adaptation
         ↓
   Trained Models + Evaluation Metrics
```

---

## Kernmethodische Entscheidungen

### Räumliches Referenzsystem

**CRS:** EPSG:25832 (UTM Zone 32N)  
**Begründung:** Metrische Genauigkeit für Deutschland, minimale Verzerrung

### Zeitliches Referenzsystem

**Jahr:** 2021  
**Limitation:** Kühles/nasses Ausnahmejahr, verzögerte Phänologie  
**Implikation:** Modelle sind 2021-spezifisch, Transfer auf andere Jahre ggf. eingeschränkt

### Cloud Computing

**Sentinel-2 Backend:** Google Earth Engine (GEE)  
**Begründung:** Schnelle parallele Processing, kostenlos für Forschung

### Spatial Autocorrelation

**Strategie:** 500×500m Block-basierte Splits  
**Begründung:** Verhindert Data Leakage (Roberts et al., 2017)

### Class Balancing

**Strategie:** Stratified Downsampling zu 1,500/Genus  
**Resultat:** Perfekt balanciert (14% pro Klasse), keine Class Weights nötig

### Edge-Filter

**Varianten:** 0m, 15m, 20m, 30m  
**Aktuell genutzt:** 15m (Balance zwischen Datenmenge & spektraler Reinheit)

[07_Baumkorrektur_Methodik](01_Data_Processing/07_Baumkorrektur_Methodik.md)

- Snap-to-Peak: GPS Position → CHM Peak
- Höhen-Extraktion vom CHM
- Quality Filter (DIN 18916 Mindesthöhe 3m)
- Output: 315,977 korrigierte Bäume (86.9% Retention)

**Data Pipeline Summary:**

```
Raw Data (GIS Quellen)
    ↓
[Phase 1] Standardisierung & Validierung (Geospatiale Basis)
    ├── CHM 1m (hochauflösend)
    ├── CHM 10m (resampelt für S2-Auflösung)
    ├── Sentinel-2 15 Bänder (monatlich)
    └── Korrekte Baumpositionen & Höhen
    ↓
Ready for Feature Engineering
```

---

## Statistische Zusammenfassung

### Datenvolumen (nach Phasen)

| Phase             | Input                    | Output                   | Retention |
| ----------------- | ------------------------ | ------------------------ | --------- |
| **Phase 1.1-1.6** | 956,380 Bäume (Rohdaten) | 363,571 Bäume (edge_15m) | 38%       |
| **Phase 1.7**     | 363,571 Bäume            | 315,977 Bäume            | 87%       |
| **Phase 2.1**     | 315,977 Bäume            | 255,679 Bäume            | 81%       |
| **Phase 2.2**     | 255,679 Bäume            | 240,602 Bäume            | 94%       |
| **Phase 2.3**     | 240,602 Bäume            | 28,866 Bäume             | 12%       |
| **Phase 2.4-2.5** | 28,866 Bäume             | 28,866 Bäume (ML-Ready)  | 100%      |

**Gesamt:** 956,380 → 28,866 (3% Retention)  
**Begründung:** Aggressive Qualitätskontrolle + Balancierung für robuste ML-Modelle

---

## Daten-Architektur

```
Tree Classification Pipeline
================================

INPUT LAYER (Geospatiale Rohdaten)
├── City Boundaries (OSM)
├── Tree Cadastres (Municipal DBs)
├── DOM/DGM (Höhendaten, 1m)
└── Sentinel-2 L2A (GEE, 10m)

DATA PROCESSING LAYER (Phase 1)
├── Boundary Standardization → EPSG:25832
├── Tree Registry Harmonization
├── CHM Derivation (DOM - DGM)
├── CHM Resampling (1m → 10m)
├── S2 Composite Stack (12 months)
└── Tree Position Correction (Snap-to-Peak)

OUTPUT: Processed Datasets
├── CHM_1m_*.tif (3 cities)
├── CHM_10m_mean/max/std_*.tif (9 files)
├── S2_*_*_2021_MM_median.tif (36 files)
└── trees_corrected_*.gpkg (3 cities, 315,977 trees)

FEATURE ENGINEERING LAYER (Phase 2)
├── Spatial Features (CHM metrics)
├── Spectral Features (S2 indices, time series)
├── Structural Features (crown morphology)
└── Feature Normalization

OUTPUT: Feature Matrix
├── Feature_Matrix.csv (315,977 × ~100)
└── Feature_Metadata.json

MACHINE LEARNING LAYER (Phases 3-4)
├── Model Training (XGBoost, RF, etc.)
├── Model Validation (CV, Hold-out test)
└── Model Deployment

OUTPUT: Predictions
└── Tree_Class_Predictions.gpkg
```

---

## Statistiken & KPIs

### Data Volume

| Entity                   | Berlin  | Hamburg | Rostock | Total     |
| ------------------------ | ------- | ------- | ------- | --------- |
| Input Trees              | 245,614 | 97,275  | 20,682  | 363,571   |
| Output Trees             | 219,900 | 78,577  | 17,500  | 315,977   |
| Retention Rate           | 89.5%   | 80.8%   | 84.6%   | **86.9%** |
| Area (km²)               | 891     | 755     | 107     | 1,753     |
| Tree Density (trees/km²) | 247     | 104     | 163     | 180       |

### Data Coverage

| Source                  | Coverage                         |
| ----------------------- | -------------------------------- |
| CHM Valid Pixels        | 46-61% (rest: no vegetation)     |
| Sentinel-2 Valid Pixels | 28-99% (seasonal, cloudy winter) |
| CHM Availability        | 99.6-100%                        |
| S2 Scenes Acquired      | 12 Monate, 36 Dateien            |

### Processing Performance

| Phase             | Component               | Time                 | Status |
| ----------------- | ----------------------- | -------------------- | ------ |
| 1.4               | CHM Calculation         | ~30h                 | ✅     |
| 1.5               | CHM Resampling          | ~25 min              | ✅     |
| 1.6               | S2 Download & Export    | ~3-5h (parallel GEE) | ✅     |
| 1.7               | Tree Correction         | ~2h                  | ✅     |
| **Total Phase 1** | **All Data Processing** | **~35-40h**          | ✅     |

---

## Technologie-Stack

### Languages & Frameworks

- **Python 3.8+** (Core processing)
- **GeoPandas** (Vector GIS)
- **Rasterio** (Raster I/O)
- **Google Earth Engine Python API** (Satellite data)
- **NumPy, SciPy** (Array processing)
- **Pandas** (Data manipulation)
- **Scikit-learn** (ML baseline)
- **XGBoost / LightGBM** (Tree-based models)

### Geospatial Tools

- **QGIS** (Visualization & validation)
- **GDAL/OGR** (CLI for raster/vector ops)
- **Google Earth Engine** (Cloud processing)

### Data Formats

- **GeoPackage** (.gpkg) - Vector output
- **GeoTIFF** (LZW) - Raster output
- **Cloud-Optimized GeoTIFF** (COG) - S2 data
- **JSON** - Metadata & statistics
- **CSV** - Feature matrices

### Infrastructure

- **Google Colab** (Notebook execution, 12+ GB RAM)
- **Google Drive** (Storage: ~100 GB)
- **Local Machine** (QGIS, final analysis)

---

## Dokumentations-Index

### Phase 1: Data Processing

**Ordner:** `01_Data_Processing/`

| Phase | Datei                                 | Topics                          |
| ----- | ------------------------------------- | ------------------------------- |
| 1.1   | 01_Stadtgrenzen_Methodik.md           | OSM, GIS, CRS                   |
| 1.2   | 02_Baumkataster_Methodik.md           | Tree Registry, Harmonization    |
| 1.3   | 03_Hoehendaten_DOM_DGM_Methodik.md    | Elevation Data, GeoTIFF         |
| 1.4   | 04_CHM_Erstellung_Methodik.md         | CHM Derivation, Algebra         |
| 1.5   | 05_CHM_Resampling_Methodik.md         | Windowed Processing, Resampling |
| 1.6   | 06_Sentinel2_Verarbeitung_Methodik.md | GEE, Composite Stack, S2 L2A    |
| 1.7   | 07_Baumkorrektur_Methodik.md          | Snap-to-Peak, Quality Filter    |

### Phase 2: Feature Engineering

**Ordner:** `01_Feature_Engineering/`

| Phase | Datei                                                       | Topics                                 |
| ----- | ----------------------------------------------------------- | -------------------------------------- |
| 2.0   | README.md                                                   | Overview & Pipeline                    |
| 2.1   | 08_Feature_Loading_Extraction_Methodik.md                   | ✅ CHM & S2 Feature Extraction         |
| 2.2   | 09_Feature_Validation_Quality_Control_Methodik.md           | ✅ NDVI, Spectral Filtering            |
| 2.3   | 10_Dataset_Balancing_Class_Stratification_Methodik.md       | ✅ Class Balancing (7 Genera)          |
| 2.4   | 11_Spatial_Block_Split_Train_Val_Stratification_Methodik.md | ✅ Spatial Block Split, Transfer Learn |
| 2.5   | 12_Feature_Normalization_Model_Ready_Export_Methodik.md     | ✅ Label Encoding, Normalization, .npy |

---

## Nächste Schritte

1. ✅ **Phase 1 Abschluss:** Data Processing dokumentiert und validiert
2. 🔄 **Phase 2 Start:** Feature Engineering Methodology dokumentieren
3. 🔄 **Feature Extraction:** CHM + S2 Features implementieren
4. 📋 **Model Development:** Train/Validate/Test Pipeline

---

## Ressourcen & Referenzen

### Interne Dokumentation

- Data Processing Methodologie (Phase 1)
- Feature Engineering Planung (Phase 2)
- Machine Learning Guidelines (Phase 3-4)

### Externe Ressourcen

- [Copernicus Sentinel-2 Handbook](https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi)
- [Google Earth Engine Docs](https://developers.google.com/earth-engine)
- [QGIS Dokumentation](https://docs.qgis.org)
- [GeoPandas Documentation](https://geopandas.org)

---

## Kontakt & Autor

**Projektleitung:** Silas Pignotti  
**Erstellt:** 6. Januar 2026  
**Zuletzt aktualisiert:** 6. Januar 2026

---

**Gesamtstatus:** Phase 1 ✅ | Phase 2 ✅ | Phase 3-4 📋
