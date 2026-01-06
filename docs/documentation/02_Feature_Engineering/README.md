# Feature Engineering - Dokumentation

**Projektphase:** Feature Extraction & Engineering  
**Datum:** 6. Januar 2026  
**Status:** ✅ Abgeschlossen (5 Phasen dokumentiert)

---

## Übersicht

Diese Dokumentation beschreibt die **Feature Engineering Pipeline**, die räumliche, spektrale und strukturelle Features aus den vorverarbeiteten Daten extrahiert:

- **CHM-Daten** (Canopy Height Model) in 1m und 10m Auflösung
- **Sentinel-2 Daten** (15 Bänder: 10 spektral + 5 Indizes)
- **Korrekte Baumpositionen & -höhen** (aus Snap-to-Peak)

---

## Dokumentierte Phasen (Feature Engineering Pipeline)

Diese fünf Phasen bilden eine komplette Pipeline von rohen Features bis zu ML-Ready Daten:

### Phase 2.1: Feature Loading & Extraction

**Inputs:** Corrected Trees (315,977), CHM 10m, Sentinel-2 (36 Dateien)  
**Processing:** CHM aggregation (4 features), S2 extraction (180 features), NoData interpolation  
**Outputs:** 255,679 trees × 184 features (19.1% removed due to >3m NoData)  
**Dokument:** [01_Feature_Loading_Extraction_Methodik.md](01_Feature_Loading_Extraction_Methodik.md) | ✅ Abgeschlossen

---

### Phase 2.2: Feature Validation & Quality Control

**Inputs:** Feature Matrix (255,679 trees)  
**Processing:** NDVI filter (< 0.3), Spectral outlier detection (B04/B08), Null filtering  
**Outputs:** 240,602 trees (94.1% retention)  
**Dokumentation:** [02_Feature_Validation_Quality_Control_Methodik.md](02_Feature_Validation_Quality_Control_Methodik.md) | ✅ Abgeschlossen

---

### Phase 2.3: Dataset Balancing & Class Stratification

**Inputs:** Feature Matrix (240,602 trees, 8+ genera)  
**Processing:** Min threshold (≥500/city), Viable genera selection (7), Downsampling to 1,500/genus  
**Outputs:** 28,866 balanced trees in 7 genera  
**Dokumentation:** [03_Dataset_Balancing_Class_Stratification_Methodik.md](03_Dataset_Balancing_Class_Stratification_Methodik.md) | ✅ Abgeschlossen

---

### Phase 2.4: Spatial Block Split & Train/Val Stratification

**Inputs:** Balanced datasets (28,866 trees)  
**Processing:** 500×500m spatial blocks, 80/20 block-based splits, Transfer learning setup (Rostock)  
**Outputs:** 6 spatially disjoint splits (Hamburg/Berlin train/val + Rostock zero-shot/finetune)  
**Dokumentation:** [04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md](04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md) | ✅ Abgeschlossen

---

### Phase 2.5: Feature Normalization & Model-Ready Export

**Inputs:** Split datasets (28,866 trees × 184 features)  
**Processing:** Label encoding (0-6), StandardScaler normalization, 3 experiment setups  
**Outputs:** Normalized .npy arrays ready for ML + pickle files (scalers, encoders)  
**Dokumentation:** [05_Feature_Normalization_Model_Ready_Export_Methodik.md](05_Feature_Normalization_Model_Ready_Export_Methodik.md) | ✅ Abgeschlossen

---

## Übersichtstabelle

| Phase | Dokument                                                                                                                   | Status           |
| ----- | -------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1     | [01_Feature_Loading_Extraction_Methodik.md](01_Feature_Loading_Extraction_Methodik.md)                                     | ✅ Abgeschlossen |
| 2     | [02_Feature_Validation_Quality_Control_Methodik.md](02_Feature_Validation_Quality_Control_Methodik.md)                     | ✅ Abgeschlossen |
| 3     | [03_Dataset_Balancing_Class_Stratification_Methodik.md](03_Dataset_Balancing_Class_Stratification_Methodik.md)             | ✅ Abgeschlossen |
| 4     | [04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md](04_Spatial_Block_Split_Train_Val_Stratification_Methodik.md) | ✅ Abgeschlossen |
| 5     | [05_Feature_Normalization_Model_Ready_Export_Methodik.md](05_Feature_Normalization_Model_Ready_Export_Methodik.md)         | ✅ Abgeschlossen |

---

## Abhängigkeiten

Diese Phase **baut auf** den Ergebnissen der Data Processing Phase auf:

- ✅ [01_Stadtgrenzen_Methodik](../01_Data_Processing/01_Stadtgrenzen_Methodik.md)
- ✅ [02_Baumkataster_Methodik](../01_Data_Processing/02_Baumkataster_Methodik.md)
- ✅ [05_CHM_Resampling_Methodik](../01_Data_Processing/05_CHM_Resampling_Methodik.md)
- ✅ [06_Sentinel2_Verarbeitung_Methodik](../01_Data_Processing/06_Sentinel2_Verarbeitung_Methodik.md)
- ✅ [07_Baumkorrektur_Methodik](../01_Data_Processing/07_Baumkorrektur_Methodik.md)

---

## Ergebnisse

**Output-Format:**

- GeoPackage (.gpkg) mit allen Features pro Baum
- CSV-Export für Machine Learning
- Visualisierungen (Feature-Verteilungen, Korrelationen)

**Größe (aktuell nach Phase 2.5):**

**Training Data:**

- Hamburg Train: 8,371 Bäume × 184 Features
- Berlin Train: 8,299 Bäume × 184 Features
- Total Train: 16,670 Bäume

**Validation Data:**

- Hamburg Val: 2,129 Bäume × 184 Features
- Berlin Val: 1,989 Bäume × 184 Features
- Total Val: 4,118 Bäume

**Test Data (Transfer Learning):**

- Rostock Zero-Shot: 6,675 Bäume × 184 Features
- Rostock Fine-Tune: 1,403 Bäume × 184 Features

**Overall:** 28,866 Bäume × 184 Features (normalized, stratified, balanced)

---

## Changelog

| Datum      | Änderung                 |
| ---------- | ------------------------ |
| 2026-01-06 | Initial: README Struktur |

---

**Dokumentation Status:** ✅ Feature Engineering Pipeline Abgeschlossen  
**Nächste Phase:** Phase 3 - Model Training & Evaluation  
**Letzte Aktualisierung:** 6. Januar 2026
