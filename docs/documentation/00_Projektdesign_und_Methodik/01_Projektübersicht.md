# Projektübersicht: Automatische Baumklassifizierung

**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Status:** Abgeschlossen

---

## Executive Summary

Dieses Projekt entwickelt ein **Machine Learning System zur automatischen Klassifizierung von Stadtbäumen** in sieben Gattungen basierend auf spektralen und räumlichen Daten.

**Kernfrage:** Können wir Baumarten automatisch erkennen, indem wir multispektrale Satellite-Bilder (Sentinel-2), hochauflösende Höhendaten (CHM) und Waldstruktur-Indizes kombinieren?

---

## 1. Projektkontext

### 1.1 Motivation

**Urban Forestry Challenge:**

- Viele Städte haben unvollständige oder veraltete Baumkataster
- Manuelle Kartierung von 100k+ Bäumen ist teuer und zeitintensiv
- Automatische Klassifizierung könnte Biodiversität-Monitoring, Planung und Bewirtschaftung revolutionieren

**Technologische Lösung:**

- Kostenlos verfügbare Satellitendaten (Copernicus Sentinel-2)
- Open-source GIS-Tools (QGIS, GeoPandas, GDAL)
- Machine Learning Algorithmen (Random Forest, XGBoost, Neural Networks)

### 1.2 Geopolitische Relevanz

**IPCC Fokus (2023):** Urbane Wälder als Klima-Adaptation & Biodiversity Hubs  
**EU Green Deal:** Biodiversität-Monitoring Pflicht für städtische Grünflächen  
**Nachhaltigkeitsziele (SDGs):**

- SDG 11: Nachhaltige Städte
- SDG 13: Klimaschutz
- SDG 15: Biodiversität

---

## 2. Projektumfang (Scope)

### 2.1 Forschungsfragen

1. **Primär:** Welche Baumgattungen können mittels Multispektral + CHM-Daten zuverlässig unterschieden werden?

2. **Sekundär:**
   - Wie beeinflussen saisonale Variationen (NDVI über 12 Monate) die Klassifizierung?
   - Wie generalisiert ein Modell (Hamburg) zu unsichtbaren Städten (Rostock)?
   - Kann Fine-Tuning mit wenig Daten (1,400 samples) Generalisierung verbessern?

### 2.2 Geografisches Scope

| Stadt       | Größe   | Bäume   | Fokus                     |
| ----------- | ------- | ------- | ------------------------- |
| **Berlin**  | 891 km² | 219,900 | Große heterogene Stadt    |
| **Hamburg** | 755 km² | 78,577  | Hafen-/Hafenkantstadt     |
| **Rostock** | 107 km² | 17,500  | Kleine Küstenstadt (Test) |

**Gesamtumfang:** 315,977 Bäume (nach Data Cleaning)

### 2.3 Genus-Fokus

**7 Ziel-Gattungen (häufigste, balanciert):**

| Gattung (lat.) | Deutsch         | Häufigkeit | Auswahlgrund                 |
| -------------- | --------------- | ---------- | ---------------------------- |
| TILIA          | Linde           | 104,136    | Häufigste in Deutschland     |
| ACER           | Ahorn           | 57,936     | Zweithäufigste               |
| QUERCUS        | Eiche           | 45,467     | Langlebig, ikonisch          |
| BETULA         | Birke           | 10,760     | Pionierart, wichtig          |
| FRAXINUS       | Esche           | 7,412      | Bedroht (Eschentriebsterben) |
| PRUNUS         | Kirsche/Pflaume | 5,160      | Obstbäume, Parks             |
| SORBUS         | Eberesche       | 3,522      | Biodiversity Indicator       |

**Ausschluss:** Monospezifische Genera (<500/city), exotische Arten

### 2.4 Feature-Scope

**184 Features insgesamt:**

```
Sentinel-2 Spektralbänder (120):
  - 10 spektrale Bänder × 12 Monate = 120 Features
  - Erfassen zeitliche Vegetation-Dynamik

Vegetation Indizes (60):
  - 5 Indizes × 12 Monate = 60 Features
  - Normalisierte Differenzen (NDVI, NDre, kNDVI, VARI, RTVIcore)
  - Robuster gegen Atmosphären-Effekte

CHM Features (4):
  - Baumhöhe (Peak von Canopy Height Model)
  - CHM Mean, Max, Std in 30m Buffer
  - Erfassen Struktur & Kompaktheit
```

**Ausschluss:** Color features (RGB), Texturen, Neighborhood-Features (Komplexität)

### 2.5 Output-Scope

**Deliverables:**

| Deliverable     | Format                                  | Zielgruppe           |
| --------------- | --------------------------------------- | -------------------- |
| Feature Matrix  | GeoPackage + CSV                        | Data Scientists      |
| Model Artifacts | .pkl, .h5 (scikit-learn, TensorFlow)    | Researchers          |
| Predictions     | GeoPackage (28,866 trees + predictions) | Urban Planners       |
| Methodology     | 12+ Methodikdokumente                   | Scientific Community |
| Code            | Python Notebooks (Google Colab)         | Developers           |

---

## 3. Ziele & Erfolgsmetriken

### 3.1 Primäre Ziele

| Ziel                      | Metriken                   | Zielwert |
| ------------------------- | -------------------------- | -------- |
| **Genus-Klassifizierung** | Overall Accuracy, F1-Score | ≥ 80%    |
| **Generalisierung**       | Rostock Zero-Shot Accuracy | ≥ 60%    |
| **Transferability**       | Fine-Tune Improvement      | +10-15%  |
| **Reproduzierbarkeit**    | Code & Doc Coverage        | 100%     |

### 3.2 Sekundäre Ziele

- Identifiziere hochwertige Features (Feature Importance Analysis)
- Vergleiche Algorithmen (RFC vs. XGBoost vs. CNN)
- Bewerte saisonale Abhängigkeiten

### 3.3 Erfolgskriterien

✅ **Wissenschaftlich:**

- Publikationstaugliche Accuracy-Metriken
- Ablation Study durchgeführt
- Fehler-Analyse dokumentiert

✅ **Technisch:**

- Reproducible Pipeline (Seed-Management, Versioning)
- Dokumentierte Hyperparameter
- Cross-Validation implementiert

✅ **Praktisch:**

- Model-Inference auf GPU möglich
- Vorhersagen exportierbar als GeoPackage
- API für neue Städte einfach zu erweitern

---

## 4. Forschungsfrage & Experimentelles Rahmenwerk

### 4.1 Zentrale Forschungsfrage

> **Wie gut generalisieren Machine-Learning-basierte Baumartenklassifikationsmodelle, die mit Fernerkundungsdaten (Sentinel-2, CHM) in einer Stadt trainiert wurden, wenn sie auf unbekannte Städte innerhalb derselben Klimazone übertragen werden?**

### 4.2 Untersuchungsziele

1. **Methodenvergleich:** Benchmark zwischen etabliertem Random Forest und modernem XGBoost
2. **Single-City Performance:** Maximale erreichbare Genauigkeit in einer Stadt
3. **Cross-City Transfer:** Quantifizierung des Genauigkeitsverlusts bei geografischem Transfer (Hamburg+Berlin → Rostock)
4. **Fine-Tuning Potential:** Kann minimales lokales Training die Generalisierung verbessern?

**Wissenschaftliche Relevanz:** Bestehende Studien zeigen hohe Genauigkeiten _innerhalb_ einzelner Städte (>85%), aber systematische Analysen zur _stadtübergreifenden_ Transferierbarkeit fehlen noch.

### 4.3 Experimentelle Struktur

| Experiment | Fokus                    | Ziel                                          |
| ---------- | ------------------------ | --------------------------------------------- |
| **Exp 0**  | Baseline & Methodenvergl | RF vs. XGBoost, Benchmark für weitere Tests   |
| **Exp 1**  | Single-City Performance  | Maximale Genauigkeit: HH (separat), BE (s.v.) |
| **Exp 2**  | Cross-City Transfer      | HH+BE → Rostock Zero-Shot, OA-Verlust messen  |
| **Exp 3**  | Fine-Tuning              | Rostock-Adaptation mit 1,403 lokalen Samples  |

**Detaillierte Experimentbeschreibung:** Siehe [Methodische_Grundlagen.md](Methodische_Grundlagen.md#24-experimentelles-rahmenwerk)

---

## 5. Projektstruktur & Timeline

### 5.1 Phasen

```
Phase 1: Data Processing (2025-2026)
  ├── 1.1 Boundary Standardization ✅
  ├── 1.2 Tree Registry Harmonization ✅
  ├── 1.3 Elevation Data Processing ✅
  ├── 1.4 CHM Derivation ✅
  ├── 1.5 CHM Resampling ✅
  ├── 1.6 Sentinel-2 Download ✅
  └── 1.7 Tree Position Correction ✅

Phase 2: Feature Engineering (2026)
  ├── 2.1 Feature Loading & Extraction ✅
  ├── 2.2 Feature Validation & QC ✅
  ├── 2.3 Dataset Balancing ✅
  ├── 2.4 Spatial Block Split ✅
  └── 2.5 Feature Normalization ✅

Phase 3: Model Training (2026)
  ├── 3.1 Baseline Models (RF, XGBoost) 📋
  ├── 3.2 Deep Learning (CNN, Transformer) 📋
  ├── 3.3 Hyperparameter Tuning 📋
  └── 3.4 Cross-Validation 📋

Phase 4: Validation & Deployment (2026)
  ├── 4.1 Model Evaluation 📋
  ├── 4.2 Error Analysis 📋
  ├── 4.3 Inference Pipeline 📋
  └── 4.4 Documentation & Release 📋
```

### 5.2 Zeitschätzung

| Phase     | Aufwand       | Status                |
| --------- | ------------- | --------------------- |
| Phase 1   | ~35-40h       | ✅ Abgeschlossen      |
| Phase 2   | ~20-25h       | ✅ Abgeschlossen      |
| Phase 3   | ~30-40h       | 📋 In Planung         |
| Phase 4   | ~15-20h       | 📋 In Planung         |
| **Total** | **~100-125h** | **50% abgeschlossen** |

---

## 6. Team & Rollen

| Role               | Person          | Verantwortung                           |
| ------------------ | --------------- | --------------------------------------- |
| **Project Lead**   | Silas Pignotti  | Konzept, Implementierung, Dokumentation |
| **Data Scientist** | (Intern/Extern) | Model Selection, Tuning, Evaluation     |
| **GIS Specialist** | (Optional)      | Spatial Analysis, Validation            |

---

## 7. Ressourcen & Infrastruktur

### 7.1 Datenquellen

| Source                   | Format                  | Size       | Kosten           |
| ------------------------ | ----------------------- | ---------- | ---------------- |
| Copernicus Sentinel-2    | Cloud-Optimized GeoTIFF | ~50 GB     | Free ✅          |
| OpenStreetMap            | GeoPackage              | ~100 MB    | Free ✅          |
| Municipal Tree Cadastres | GeoPackage/Shapefile    | ~1 GB      | Free/Proprietary |
| GEBCO/COPDEM Elevation   | GeoTIFF                 | ~10 GB     | Free ✅          |
| **Total**                |                         | **~60 GB** | **Mostly Free**  |

### 7.2 Computing Resources

| Resource      | Spec                    | Used For                |
| ------------- | ----------------------- | ----------------------- |
| Google Colab  | 12 GB RAM, GPU optional | Preprocessing, Training |
| Google Drive  | 100 GB                  | Storage                 |
| Local Machine | 16 GB RAM, SSD          | QGIS, Analysis          |

### 7.3 Software Stack

**Languages:** Python 3.8+

**Libraries:**

- **Geospatial:** GeoPandas, Rasterio, GDAL
- **Data:** NumPy, Pandas, Scikit-learn
- **ML:** XGBoost, LightGBM, TensorFlow/Keras
- **Visualization:** Matplotlib, QGIS
- **Cloud:** Google Earth Engine API

---

## 8. Risiken & Mitigationsmaßnahmen

### 8.1 Technische Risiken

| Risk                             | Impact                           | Probability | Mitigation                                 |
| -------------------------------- | -------------------------------- | ----------- | ------------------------------------------ |
| **Sentinel-2 Cloud Cover**       | Missing data (especially winter) | High        | Temporal interpolation, Multi-year medians |
| **Tree Misclassification**       | Ground truth errors              | Medium      | Manual validation subset                   |
| **Class Imbalance**              | Model bias to common classes     | Medium      | Stratified sampling, Class weights         |
| **Overfitting (Urban Patterns)** | Poor Rostock generalization      | Medium      | Spatial block split, Cross-validation      |

### 8.2 Ressourcen-Risiken

| Risk                      | Impact             | Mitigation                               |
| ------------------------- | ------------------ | ---------------------------------------- |
| **GPU Memory Shortage**   | CNN training fails | Use smaller batch sizes, cloud resources |
| **Storage Quota (Drive)** | Can't store models | Compression, selective export            |

---

## 9. Verwandte Arbeiten

### 9.1 Literatur

- **Tree Species Classification:** Immitzer et al. (2012), Fassnacht et al. (2016)
- **Sentinel-2 Vegetation Index:** Rouse et al. (1973), Delegido et al. (2011)
- **Transfer Learning in RS:** Long et al. (2015), Tuia et al. (2016)

### 9.2 Verwandte Projekte

- [Urban Tree Canopy Assessment](https://www.americanforests.org/) (USA)
- [CityTreeS Database](https://www.citytrees.de/) (Germany)
- [Treepol Project](https://www.treepol.eu/) (EU)

---

## 10. Nächste Schritte

1. ✅ **Phase 1-2 Complete:** Data Processing & Feature Engineering dokumentiert
2. 🔄 **Phase 3 Start:** Model Training (Baseline RF/XGBoost)
3. 📋 **Phase 4:** Evaluation & Deployment

**Kontakt:** silas@example.com

---

**Dokument-Status:** ✅ Abgeschlossen  
**Letzte Aktualisierung:** 6. Januar 2026
