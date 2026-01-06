# Improvements & Roadmap

**Datum:** 6. Januar 2026  
**Zweck:** Sammlung von methodischen Varianten, Ablationsstudien und Optimierungen, die noch nicht implementiert wurden aber potenzielle Verbesserungen darstellen.

---

## 📋 Status-Legende

- 🔄 **In Progress** - Aktuell in Bearbeitung
- 📋 **Planned** - Geplant für zukünftige Phasen
- 💡 **Proposed** - Idee/Vorschlag, noch nicht genehmigt
- ❌ **Rejected** - Verworfen nach Evaluation
- ✅ **Completed** - Implementiert und dokumentiert

---

## 1. Phase 1: Data Processing Improvements

### 1.1 Alternative Interpolationsmethoden für CHM

**Status:** 💡 Proposed

**Aktuell:** Mean/Max/Std Aggregation (1m → 10m) via windowed resampling

**Alternative Ansätze:**

- **Spline Interpolation:** Smooth transitions zwischen Pixeln
- **LOESS (Locally Estimated Scatterplot Smoothing):** Adaptive lokale Regression
- **Kriging:** Geostatistische Interpolation mit Spatial Autocorrelation

**Potenzielle Vorteile:**

- Glattere Höhenmodelle
- Weniger Artefakte an Blockgrenzen
- Bessere Repräsentation von Kronenformen

**Potenzielle Nachteile:**

- Erhöhte Rechenzeit
- Oversmoothing → Verlust von Kronendetails
- Schwieriger zu interpretieren

**Nächste Schritte:**

- Literaturrecherche: CHM-Interpolation Best Practices
- Prototyp mit scipy.interpolate.RBFInterpolator
- Vergleichsstudie: Mean vs Spline (visuell + quantitativ)

---

## 2. Phase 2: Feature Engineering Improvements

### 2.1 Sentinel-2 Zeitfenster: 7 Monate vs 12 Monate

**Status:** 💡 Proposed

**Aktuell:** 12 Monate (Jan-Dez 2021) mit monatlichen Medianen

**Alternative:** 7 Monate (Apr-Okt) - Vegetationsperiode only

**Begründung für 7-Monats-Variante:**

- **Phänologische Vollständigkeit:** Austrieb → Vollbelaubung → Herbstfärbung
- **Cloud Coverage:** Deutlich höher in Vegetationsperiode (70-100% Verfügbarkeit vs. 30-50% Winter)
- **Literatur:** +1-2% OA für zweites Jahr, aber nicht proportional zum Aufwand
- **Feature Reduktion:** 10 Bänder × 7 Monate = 70 Features (statt 120)

**Trade-offs:**
| Aspekt | 12 Monate (aktuell) | 7 Monate (alternativ) |
|---|---|---|
| **Phänologie** | Vollständig inkl. Winter-Ruhe | Nur Vegetationsperiode |
| **Cloud Coverage** | Problematisch (Winter 30-50%) | Sehr gut (70-100%) |
| **Feature-Anzahl** | 120 spektrale Features | 70 spektrale Features |
| **Dimensionalität** | Höher → ggf. Overfitting | Niedriger → bessere Generalisierung? |
| **Evergreens vs Deciduous** | Winterdifferenzierung möglich | Nur Sommer-Signaturen |

**Ablationsstudie (geplant für Exp 4):**

- Train Modell A: 12 Monate (aktuell)
- Train Modell B: 7 Monate (Apr-Okt)
- Vergleich: OA, F1 pro Genus, Confusion Matrix
- Hypothese: Deciduous profitieren von 7-Monats (weniger Noise), Evergreens ggf. schlechter

**Implementierung:**

- Feature Extraction Notebook anpassen: `MONTHS = [4,5,6,7,8,9,10]`
- Feature Matrix neu exportieren
- Normalization/Training pipeline unverändert

---

### 2.2 IQR-basierte Outlier Detection (Alternative zu spektralem Threshold)

**Status:** 💡 Proposed

**Aktuell:** NDVI < 0.3 + spektrale Hard-Thresholds (B04 > 8000, B08 > 8000)

**Alternative:** IQR-Methode (Interquartile Range)

**Methodischer Ansatz:**

```python
# Pro Feature:
Q1 = feature.quantile(0.25)
Q3 = feature.quantile(0.75)
IQR = Q3 - Q1

lower_bound = Q1 - 1.5 * IQR
upper_bound = Q3 + 1.5 * IQR

# Remove trees outside [lower_bound, upper_bound]
```

**Begründung:**

- **Adaptiv:** Automatische Schwellenwerte pro Feature
- **Robust:** Funktioniert für alle spektralen Bänder/Indizes
- **Literatur-Standard:** Weit verbreitete statistische Methode

**Potenzielle Vorteile:**

- Erkennt mehr Artefakte (z.B. Cloud-Masking-Fehler, Sensor-Rauschen)
- Kein manuelles Tuning von Schwellenwerten nötig

**Potenzielle Nachteile:**

- Verlust von ~5-10% Daten (je nach Contamination)
- Schwieriger zu interpretieren (was ist "Ausreißer" bei Baumart?)

**Nächste Schritte:**

- Prototyp in Feature Validation Notebook
- Vergleich: Spektral-Threshold vs IQR (Datenverlust, OA, F1)
- Visuell: Welche Bäume werden entfernt? (QGIS Plots)

---

### 2.3 Multivariate Outlier Detection: Isolation Forest

**Status:** 💡 Proposed

**Aktuell:** Univariate Outlier Detection (pro Feature einzeln)

**Alternative:** Isolation Forest (sklearn.ensemble.IsolationForest)

**Methodischer Ansatz:**

```python
from sklearn.ensemble import IsolationForest

iso_forest = IsolationForest(
    contamination=0.05,  # 5% als Outlier
    random_state=42
)

# Fit auf alle Features gleichzeitig
outliers = iso_forest.fit_predict(X_features)  # -1 = outlier

# Remove outliers
trees_cleaned = trees[outliers == 1]
```

**Begründung:**

- **Multivariate:** Erkennt ungewöhnliche **Feature-Kombinationen**
- **Geisterbäume:** Label-Fehler im Kataster (z.B. "QUERCUS" aber spektral wie TILIA)
- **Literatur:** Standard für anomaly detection in high-dimensional data

**Potenzielle Vorteile:**

- Findet Bäume mit physikalisch unmöglichen Feature-Kombinationen
- Reduziert Label-Noise

**Potenzielle Nachteile:**

- Verlust von weiteren ~5% Daten
- Rechenintensiv bei 240k+ Bäumen
- Hyperparameter-Tuning (contamination) subjektiv

**Nächste Schritte:**

- Prototyp mit 10% Datensample
- Analyse: Welche Bäume werden als Outlier markiert? (Feature-Plots)
- Ablation: Modell mit/ohne Isolation Forest Filtering

---

## 3. Phase 3: Model Training Improvements (Planned)

### 3.1 Hyperparameter Optimization: Bayesian vs Grid Search

**Status:** 📋 Planned

**Aktuell:** Geplant GridSearchCV für Random Forest

**Alternative:** Bayesian Optimization (z.B. Optuna, scikit-optimize)

**Begründung:**

- **Effizienter:** Intelligente Suche statt brute-force
- **Literatur:** 10-50× schneller als Grid Search bei gleicher Performance

**Nächste Schritte:**

- Vergleichsstudie: GridSearch vs Bayesian (Runtime, Best Params, OA)

---

### 3.2 Deep Learning: Transformer-based Models (Optional)

**Status:** 💡 Proposed

**Aktuell:** CNN (Convolutional Neural Network) geplant

**Alternative:** Vision Transformer (ViT) oder Swin Transformer

**Begründung:**

- **State-of-the-Art:** Transformers übertreffen CNNs in vielen Remote Sensing Tasks
- **Attention Mechanism:** Lernt wichtige spektrale Bänder/Zeitpunkte automatisch

**Trade-offs:**

- **Data Hungry:** Benötigt deutlich mehr Trainingsdaten
- **Rechenintensiv:** GPU-Training nötig
- **Komplexität:** Schwieriger zu interpretieren

**Nächste Schritte:**

- Literaturrecherche: Transformer für Vegetation Classification
- Prototyp nur wenn Random Forest/CNN-Baselines etabliert

---

## 4. Phase 4: Ablation Studies (Exp 4)

### 4.1 Edge-Filter Ablation: Trade-off Quantifizierung

**Status:** 📋 Planned

**Aktuell:** 4 Varianten implementiert (no_edge, 15m, 20m, 30m), aber nur edge_15m trainiert

**Ablationsstudie:**

| Variant      | Datenmenge             | Spektrale Reinheit   | Erwartete OA | Trade-off               |
| ------------ | ---------------------- | -------------------- | ------------ | ----------------------- |
| **no_edge**  | 1,140,172 Bäume (100%) | Niedrig (Mischpixel) | Baseline     | Urbane Realität         |
| **edge_15m** | 363,571 Bäume (32%)    | Mittel-Hoch          | +2-5% ?      | Remote Sensing Standard |
| **edge_20m** | 280,522 Bäume (25%)    | Hoch                 | +3-7% ?      | Balance                 |
| **edge_30m** | 195,117 Bäume (17%)    | Sehr Hoch            | +5-10% ?     | Upper Bound             |

**Forschungsfragen:**

1. Wie viel OA gewinnen wir pro Filter-Stufe?
2. Gibt es Genera-spezifische Effekte? (z.B. TILIA profitiert mehr als BETULA?)
3. Ab welchem Filter-Level flacht Kurve ab? (Diminishing Returns)

**Implementierung:**

- Train 4 separate Random Forest Modelle (identische Hyperparameter)
- Evaluate auf identischem Testset (z.B. Rostock Zero-Shot)
- Plot: Edge-Distance vs OA/F1

**Literatur-Kontext:**

- Remote Sensing Best Practice: 2× Pixelgröße (= 20m für 10m Pixel)
- Hyperspektral-Analogie: 3× Pixelgröße für vollständige Isolation

---

### 4.2 CHM-only vs S2-only vs Combined (Feature Importance)

**Status:** 📋 Planned

**Ablation:**

- **Modell A (CHM-only):** Nur height_mean, height_max, height_std (3 Features)
- **Modell B (S2-only):** Nur Sentinel-2 Spektral + Indizes (180 Features)
- **Modell C (Combined):** Alle Features (184 Features)

**Erwartete Resultate:**

- CHM-only: ~60-70% OA (Literatur: Höhe allein ist starker Prädiktor)
- S2-only: ~80-85% OA (Spektral enthält meiste Information)
- Combined: ~87-92% OA (Synergieeffekt)

**Nächste Schritte:**

- Train alle 3 Varianten
- Feature Importance Analysis (SHAP values)
- Confusion Matrix Vergleich: Welche Genera profitieren von CHM?

---

## 5. Data Quality Improvements

### 5.1 Temporale Diskrepanz: CHM 2021 vs plant_year Filter

**Status:** ❌ Rejected / Nicht mehr relevant

**Kontext (historisch):**

- Alte Planung: CHM 2021, aber S2 2024 → Zeitliche Diskrepanz
- Problem: Bäume wachsen ~0,3-0,5m/Jahr → Systematische Höhenunterschätzung

**Aktueller Stand:**

- **Gelöst:** Projekt nutzt Sentinel-2 2021 (identisch mit CHM)
- Filter `plant_year ≤ 2021` ist jetzt irrelevant

**Dokumentation:** Keine Aktion nötig, bereits korrekt implementiert.

---

## 6. Cross-City Transfer Enhancements

### 6.1 Domain Adaptation: Adversarial Learning (Advanced)

**Status:** 💡 Proposed (Forschungsrichtung)

**Kontext:**

- Aktuell: Naive Transfer (Hamburg+Berlin → Rostock)
- Problem: Distribution Shift zwischen Städten

**Alternative:** Domain Adversarial Neural Network (DANN)

**Methodischer Ansatz:**

- Trainiere Klassifikator + Domain Discriminator gleichzeitig
- Klassifikator lernt genus-features
- Discriminator versucht Stadt zu erraten
- Adversarial Loss: Klassifikator täuscht Discriminator

**Begründung:**

- **Literatur:** State-of-the-Art für Domain Transfer in Remote Sensing
- **Ziel:** City-invariante Features lernen

**Trade-offs:**

- Sehr komplex
- Benötigt Deep Learning Infrastructure
- Nur sinnvoll wenn naive Transfer nicht funktioniert

**Nächste Schritte:**

- Erst Exp 2 (naive Transfer) durchführen
- Wenn OA < 70%: Domain Adaptation evaluieren
- Literatur: Ganin et al. (2016) "Domain-Adversarial Training"

---

## 7. Operationelle Deployment

### 7.1 Fine-Tuning Strategie: Minimum Data Requirements

**Status:** 📋 Planned (Exp 3)

**Forschungsfrage:**

> Wie viele gelabelte Bäume benötigt eine neue Stadt (z.B. Wismar) mindestens für akzeptable Performance?

**Ablationsstudie (geplant):**

- Baseline: Hamburg+Berlin → Rostock (Zero-Shot)
- Exp 3.1: + 50 Rostock Samples (Fine-Tuning)
- Exp 3.2: + 100 Rostock Samples
- Exp 3.3: + 500 Rostock Samples

**Metrik:**

- OA vs. Anzahl Fine-Tuning Samples
- Kosten-Nutzen-Analyse: Labeling-Aufwand vs. Accuracy-Gewinn

**Nächste Schritte:**

- Rostock Subset sampling (stratified by genus)
- Iteratives Fine-Tuning mit wachsenden Samples

---

## 8. Visualization & Interpretability

### 8.1 SHAP Values für Feature Importance

**Status:** 📋 Planned

**Ziel:** Erklärbarkeit der Random Forest Predictions

**Implementierung:**

```python
import shap

explainer = shap.TreeExplainer(rf_model)
shap_values = explainer.shap_values(X_test)

# Plot: Feature Importance pro Genus
shap.summary_plot(shap_values, X_test, class_names=genus_labels)
```

**Output:**

- Welche Features sind wichtig für TILIA vs QUERCUS?
- Phänologische Muster: Welche Monate sind entscheidend?

---

## 9. Literatur & Methodische Referenzen

**Spatial Autocorrelation:**

- Roberts et al. (2017). "Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure". _Ecography_.

**Remote Sensing Best Practices:**

- Fassnacht et al. (2016). "Review of studies on tree species classification from remotely sensed data". _Remote Sensing of Environment_.

**Domain Adaptation:**

- Ganin et al. (2016). "Domain-Adversarial Training of Neural Networks". _JMLR_.

**Outlier Detection:**

- Liu et al. (2008). "Isolation Forest". _IEEE ICDM_.

---

## 10. Prioritäten & Roadmap

### Kurzfristig (Phase 3 - Model Training)

1. ✅ Edge-Filter Ablation (Exp 4.1) - **HIGH Priority**
2. ✅ CHM-only vs S2-only (Exp 4.2) - **HIGH Priority**
3. 📋 Hyperparameter Optimization (Grid Search) - **MEDIUM Priority**

### Mittelfristig (Nach Baseline)

1. 💡 Sentinel-2 Zeitfenster (7 vs 12 Monate) - **MEDIUM Priority**
2. 💡 IQR/Isolation Forest Outlier Detection - **LOW Priority**
3. 💡 Bayesian Optimization - **LOW Priority**

### Langfristig (Advanced Research)

1. 💡 Transformer-based Models - **Optional**
2. 💡 Domain Adaptation (DANN) - **Only if necessary**

---

## 11. Change Log

| Datum      | Autor          | Änderung                                                     |
| ---------- | -------------- | ------------------------------------------------------------ |
| 2026-01-06 | Silas Pignotti | Initial creation, methodische Entscheidungen aus alten Chats |
