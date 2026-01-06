# Experimentstrategie: Phase 3 Model Training (Exp 0-3)

**Projektphase:** Phase 3 - Model Training & Evaluation  
**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Status:** 📋 Geplant (noch nicht durchgeführt)

---

## 1. Übersicht

Dieses Dokument beschreibt die **methodische Strategie** für vier systematische Machine-Learning-Experimente zur Baumartenklassifizierung.

### 1.1 Zielsetzung

**Forschungsfragen:**

1. **Methodenwahl (Exp 0):** Welches ML-Verfahren (RF vs. CNN) ist am besten geeignet?
2. **Maximalleistung (Exp 1):** Wie gut können wir innerhalb einer Stadt klassifizieren?
3. **Generalisierung (Exp 2):** Wie gut übertragen sich Modelle auf neue Städte (Cross-City Transfer)?
4. **Adaptation (Exp 3):** Kann minimales lokales Training die Generalisierung verbessern?

### 1.2 Experimenthierarchie

```
Exp 0: Baseline-Etablierung (RF vs CNN)
  ├─→ Entscheidung: Welches Modell für Exp 1-3?
  │
  ├─→ Exp 1: Single-City Performance (Hamburg, Berlin separat)
  │     ├─→ Referenz für Transfer Loss
  │     │
  │     └─→ Exp 2: Cross-City Transfer (Hamburg/Berlin → Rostock)
  │           ├─→ Zero-Shot Performance messen
  │           │
  │           └─→ Exp 3: Fine-Tuning (Rostock-Adaptation)
  │                 └─→ Minimum Data Requirements quantifizieren
```

---

## 2. Experiment 0: Baseline-Etablierung (RF vs. CNN)

### 2.1 Ziel

Vergleich **Random Forest** vs. **1D-CNN** zur Bestimmung des Hauptmodells für Exp. 1-3.

**Forschungsfrage:**

> Ist ein klassisches ML-Verfahren (RF) ausreichend, oder benötigen wir Deep Learning (CNN) für diese Klassifikationsaufgabe?

### 2.2 Datensatz

**Quelle:** `data/model_ready/experiment_0_1_single_city/`

**Varianten:**

- **Hamburg:** 8,371 Train / 2,129 Val
- **Berlin:** 8,299 Train / 1,989 Val

**Wahl:** Hamburg **ODER** Berlin (nur eine Stadt für Baseline-Vergleich)

**Begründung:**

- Exp 0 etabliert Methode, nicht geografische Unterschiede
- Berlin bevorzugt (größere Diversität an Mikroklimata)

### 2.3 Modelle

#### 2.3.1 Random Forest

**Hyperparameter-Tuning:** Grid Search mit 5-Fold CV

**Suchraum:**

- `n_estimators`: [100, 200, 300]
- `max_depth`: [20, 30, None]
- `min_samples_split`: [2, 5, 10]
- `min_samples_leaf`: [1, 2, 4]
- `class_weight`: ['balanced']

**Erwartete Performance:** OA 85-92%

**Vorteile:**

- Interpretierbar (Feature Importance via SHAP)
- Schnelles Training (<1h)
- Robust gegen Overfitting

#### 2.3.2 1D-Convolutional Neural Network

**Architektur:**

```
Input: (184 Features, 1 Channel)
├─ Conv1D(64, kernel_size=3) + ReLU + MaxPooling
├─ Conv1D(128, kernel_size=3) + ReLU + MaxPooling
├─ Conv1D(256, kernel_size=3) + ReLU + GlobalMaxPooling
├─ Dense(128) + ReLU + Dropout(0.5)
└─ Dense(7, softmax)  # 7 Gattungen
```

**Training:**

- Optimizer: Adam
- Loss: Sparse Categorical Crossentropy
- Batch Size: 32
- Epochs: 50 (mit Early Stopping, patience=10)
- Learning Rate Scheduling: ReduceLROnPlateau (patience=5)

**Erwartete Performance:** OA 80-87%

**Vorteile:**

- Kann räumliche/temporale Muster in Features lernen
- State-of-the-Art in vielen Remote Sensing Tasks

**Nachteile:**

- Längeres Training (2-4h auf GPU)
- Weniger interpretierbar
- Höherer Datenaufwand

### 2.4 Evaluationsmetriken

**Primärmetriken:**

1. **Overall Accuracy (OA):** Anteil korrekt klassifizierter Bäume
2. **F1-Score (makro-gewichtet):** Harmonisches Mittel aus Precision/Recall
3. **Confusion Matrix:** Systematische Verwechslungsmuster

**Sekundärmetriken:**

- **Producer's Accuracy (Recall):** Vollständigkeit pro Genus
- **User's Accuracy (Precision):** Zuverlässigkeit pro Genus
- **Feature Importance (nur RF):** SHAP Values

### 2.5 Entscheidungsregel

**Kriterium:** Welches Modell wird Hauptmodell für Exp 1-3?

| Szenario                   | Bedingung                    | Entscheidung                              |
| -------------------------- | ---------------------------- | ----------------------------------------- |
| **RF dominiert**           | RF OA ≥ 88% **UND** RF > CNN | RF wird Hauptmodell                       |
| **CNN signifikant besser** | CNN > RF + 3%                | Beide Modelle parallel in Exp 1-3         |
| **Ähnlich**                | \|RF - CNN\| < 3%            | RF wird Hauptmodell (Interpretierbarkeit) |

**Begründung:**

- RF ist Standard in Remote Sensing (Interpretierbarkeit, Schnelligkeit)
- CNN nur wenn deutlicher Vorteil (>3% OA)
- Bei ähnlicher Performance: RF wegen Feature Importance

### 2.6 Outputs

**Gespeicherte Artefakte:**

- `results/experiment_0/rf_model.pkl`
- `results/experiment_0/cnn_model.h5`
- `results/experiment_0/metrics_comparison.csv`
- `results/experiment_0/confusion_matrix_rf.png`
- `results/experiment_0/confusion_matrix_cnn.png`
- `results/experiment_0/feature_importance_rf.png` (SHAP)
- `results/experiment_0/training_history_cnn.png`

---

## 3. Experiment 1: Single-City Performance

### 3.1 Ziel

Maximale erreichbare Genauigkeit **innerhalb jeder Stadt** (ohne geografische Transferprobleme).

**Forschungsfrage:**

> Wie gut können wir Baumarten klassifizieren, wenn Training und Test in derselben Stadt stattfinden?

### 3.2 Datensatz

**Quelle:** `data/model_ready/experiment_0_1_single_city/`

**Städte:**

- **Hamburg:** 8,371 Train / 2,129 Val
- **Berlin:** 8,299 Train / 1,989 Val

**Setup:**

- Trainiere **2 separate Modelle** (Hamburg-Modell, Berlin-Modell)
- Jedes Modell: Train & Test in derselben Stadt
- Räumlich stratifiziert (500×500m Blocks, kein Spatial Leakage)

### 3.3 Methodik

**Modell:** Bestes Modell aus Exp. 0 (typischerweise Random Forest)

**Training:**

- Hyperparameter: Übernehme Best Params aus Exp. 0
- Fitten: Einmal für Hamburg, einmal für Berlin
- Keine weitere Hyperparameter-Optimierung (Übertragbarkeit auf Exp 2)

**Beispiel (RF):**

```
Hamburg-Modell: RandomForestClassifier(**best_params_exp0)
  ├─ Fit auf X_train_hamburg, y_train_hamburg
  └─ Predict auf X_val_hamburg

Berlin-Modell: RandomForestClassifier(**best_params_exp0)
  ├─ Fit auf X_train_berlin, y_train_berlin
  └─ Predict auf X_val_berlin
```

### 3.4 Evaluationsmetriken

**Pro Stadt:**

- **Overall Accuracy (OA)**
- **F1-Score (makro)**
- **Confusion Matrix**
- **Producer's Accuracy / User's Accuracy** pro Genus

**Vergleichende Analyse:**

1. **Stadtvergleich:** Hamburg OA vs. Berlin OA
2. **Genus-Vergleich:** Welche Gattungen sind in beiden Städten schwierig?
3. **Feature Importance (RF):** Unterscheiden sich wichtige Features zwischen Städten?

### 3.5 Erwartete Ergebnisse

**Literatur-Baseline:** 85-92% OA bei CHM+Sentinel-2 Kombination

**Hypothesen:**

- **Hamburg:** ~87-90% OA (maritimes Klima, homogener)
- **Berlin:** ~85-88% OA (kontinentaler, höhere Diversität)
- **Schwierige Genera:** FRAXINUS, PRUNUS (spektral ähnlich zu TILIA/ACER)

### 3.6 Outputs

- `results/experiment_1/hamburg_model.pkl`
- `results/experiment_1/berlin_model.pkl`
- `results/experiment_1/metrics_single_city.csv`
- `results/experiment_1/confusion_matrix_hamburg.png`
- `results/experiment_1/confusion_matrix_berlin.png`
- `results/experiment_1/genus_performance_comparison.png`

---

## 4. Experiment 2: Cross-City Transfer (Zero-Shot)

### 4.1 Ziel

Quantifizierung des **Genauigkeitsverlusts** bei Übertragung auf unbekannte Stadt (Rostock).

**Forschungsfrage:**

> Wie gut generalisiert ein Modell, das auf Hamburg+Berlin trainiert wurde, auf die völlig unbekannte Stadt Rostock?

### 4.2 Datensatz

**Quelle:** `data/model_ready/experiment_2_cross_city/`

**Training:**

- Hamburg: 8,371 Train
- Berlin: 8,299 Train
- **Combined:** 16,670 Train (Hamburg + Berlin zusammengeführt)

**Validation:**

- Hamburg: 2,129 Val
- Berlin: 1,989 Val

**Test (Zero-Shot):**

- **Rostock:** 6,675 Test (100% unseen, keine Samples in Training!)

### 4.3 Methodik

**Szenarien:**

#### Szenario A: Hamburg → Rostock

```
Train: Hamburg (8,371)
Test:  Rostock Zero-Shot (6,675)
```

**Erwartung:** Mittlerer Transfer (maritimes Klima ähnlich)

#### Szenario B: Berlin → Rostock

```
Train: Berlin (8,299)
Test:  Rostock Zero-Shot (6,675)
```

**Erwartung:** Schwächerer Transfer (kontinental vs. maritim)

#### Szenario C: Hamburg+Berlin → Rostock (Multi-City)

```
Train: Hamburg + Berlin Combined (16,670)
Test:  Rostock Zero-Shot (6,675)
```

**Erwartung:** Bester Transfer (höchste Diversität)

#### Optional: Hamburg ↔ Berlin Cross-Transfer

```
Hamburg → Berlin Test
Berlin → Hamburg Test
```

**Zweck:** Benchmarking des Transfer Loss innerhalb derselben Klimazone

### 4.4 Evaluationsmetriken

**Primärmetriken:**

- **Zero-Shot OA:** Accuracy auf Rostock (ohne Rostock-Training)
- **Transfer Loss:** `Single-City OA (Exp 1) - Zero-Shot OA`
- **Confusion Matrix Rostock:** Systematische Fehler in neuer Stadt?

**Sekundäranalysen:**

1. **Genus-spezifische Transferability:**
   - Welche Gattungen generalisieren gut? (z.B. TILIA, ACER)
   - Welche leiden unter Domain Shift? (z.B. SORBUS, PRUNUS)
2. **Feature-Mismatch Analyse:**

   - Sind CHM-Werte in Rostock systematisch verschieden?
   - Spektrale Shifts zwischen Städten (z.B. NDVI-Mittelwerte)?

3. **Klimatische Korrelation:**
   - Zusammenhang zwischen geografischer Distanz und Transfer Loss?
   - Köppen-Geiger-Klassifikation als Proxy?

### 4.5 Erwartete Ergebnisse

**Literatur:** Cross-Domain Transfer typischerweise -5% bis -15% OA

| Setup              | Single-City Baseline (Exp 1) | Erwartet Zero-Shot | Transfer Loss |
| ------------------ | ---------------------------- | ------------------ | ------------- |
| Hamburg → Rostock  | 87-90%                       | 75-80%             | -10% bis -12% |
| Berlin → Rostock   | 85-88%                       | 72-77%             | -13% bis -15% |
| Combined → Rostock | -                            | 78-83%             | -8% bis -10%  |

**Hypothesen:**

- **H1:** Hamburg → Rostock besser als Berlin → Rostock (beide maritim)
- **H2:** Combined reduziert Transfer Loss durch höhere Trainings-Diversität
- **H3:** Häufige Genera (TILIA, ACER) transferieren besser als seltene

### 4.6 Fallback-Strategie

**Kriterium:** Falls Hamburg+Berlin → Rostock OA < 70%

**Aktivierung:**

1. Prüfe systematische Feature-Shifts (CHM, NDVI)
2. Erweitere Training mit regionalen Daten (z.B. Lübeck, Schwerin)
3. Domain Adaptation Techniken (Exp 4 - Advanced, nicht in Baseline)

### 4.7 Outputs

- `results/experiment_2/model_hamburg_to_rostock.pkl`
- `results/experiment_2/model_berlin_to_rostock.pkl`
- `results/experiment_2/model_combined_to_rostock.pkl`
- `results/experiment_2/metrics_transfer.csv`
- `results/experiment_2/confusion_matrix_rostock_hh.png`
- `results/experiment_2/confusion_matrix_rostock_be.png`
- `results/experiment_2/confusion_matrix_rostock_combined.png`
- `results/experiment_2/genus_transferability.csv`
- `results/experiment_2/transfer_loss_comparison.png`

---

## 5. Experiment 3: Fine-Tuning mit lokalen Daten

### 5.1 Ziel

Minimaler lokaler Datenaufwand zur Wiederherstellung von Single-City Performance.

**Forschungsfrage:**

> Wie viele lokale Samples (Rostock) benötigen wir, um das Combined-Modell (Hamburg+Berlin) anzupassen und Exp 1-Level Performance zu erreichen?

### 5.2 Datensatz

**Basis-Modell:** Bestes Modell aus Exp. 2 (typisch: Hamburg+Berlin → Rostock)

**Fine-Tuning Samples:**

- Gezogen aus **Rostock Zero-Shot Test** (6,675 verfügbar)
- Stratifiziert: Gleiche Anzahl pro Gattung

**Evaluation:**

- **Rostock Fine-Tune Eval:** 1,403 Samples (20%, komplett unseen)

**Setup:**

| Variante       | Fine-Tuning Samples      | Samples pro Genus | Total |
| -------------- | ------------------------ | ----------------- | ----- |
| **Variante 1** | 50 pro Genus             | 50                | 350   |
| **Variante 2** | 100 pro Genus            | 100               | 700   |
| **Variante 3** | 200 pro Genus (optional) | 200               | 1,400 |

### 5.3 Methodik

#### 5.3.1 Random Forest Fine-Tuning

**Ansatz 1: Inkrementelles Training**

```
Basis-Modell: model_combined (Hamburg+Berlin, 16,670)
Fine-Tuning: Kombiniere Combined Train + Rostock Fine-Tune Samples

X_train_ft = Combined Train (16,670) + Rostock Samples (50/100/200 per genus)
y_train_ft = Combined Labels + Rostock Labels

model_finetuned = RandomForestClassifier(**same_params)
model_finetuned.fit(X_train_ft, y_train_ft)
```

**Begründung:**  
RF kann nicht "warm_start" wie Neural Networks, daher vollständiges Retraining mit erweiterten Daten

#### 5.3.2 CNN Fine-Tuning (falls CNN in Exp 0 gewählt)

**Ansatz: Transfer Learning**

```
Basis-Modell: model_combined (Hamburg+Berlin)

1. Freeze frühe Layer (Conv1D-Schichten)
2. Trainiere nur letzte Dense Layer (128 → 7)
3. Epochs: 20, Batch Size: 16

model_finetuned = load_model('model_combined.h5')
for layer in model_finetuned.layers[:-2]:
    layer.trainable = False

model_finetuned.compile(...)
model_finetuned.fit(X_finetune, y_finetune, epochs=20)
```

**Begründung:**  
CNN kann vortrainierte Features (Spektral-Muster) wiederverwenden, nur Klassifikations-Head anpassen

### 5.4 Evaluationsmetriken

**Primärmetriken:**

- **Fine-Tuned OA:** Accuracy auf Rostock Fine-Tune Eval (1,403 unseen)
- **Improvement:** `Fine-Tuned OA - Zero-Shot OA (Exp 2)`

**Vergleich:**

| Baseline  | OA (Exp 2) | + 50 Samples | + 100 Samples | + 200 Samples |
| --------- | ---------- | ------------ | ------------- | ------------- |
| Zero-Shot | 78-83%     | +3-5% ?      | +5-8% ?       | +7-10% ?      |

**Sekundäranalysen:**

1. **Kosten-Nutzen-Kurve:** OA vs. Sample Size
2. **Genus-spezifische Verbesserung:**
   - Profitieren seltene Genera (SORBUS, PRUNUS) stärker?
3. **Diminishing Returns:**
   - Ab welcher Sample-Größe flacht Kurve ab?

### 5.5 Erwartete Ergebnisse

**Hypothese:**

- Zero-Shot Baseline: 78-83% OA
- - 50 Samples/Genus: 81-86% OA (+3-5%)
- - 100 Samples/Genus: 83-88% OA (+5-8%)
- - 200 Samples/Genus: 85-90% OA (+7-10%)

**Praktische Implikation:**

> Für eine neue Stadt (z.B. Wismar) benötigt man ca. **100 lokale Samples pro Gattung** (700 total), um 85-88% OA zu erreichen - vergleichbar mit Single-City Performance (Exp 1).

### 5.6 Outputs

- `results/experiment_3/model_finetuned_50.pkl`
- `results/experiment_3/model_finetuned_100.pkl`
- `results/experiment_3/model_finetuned_200.pkl` (optional)
- `results/experiment_3/metrics_finetuning.csv`
- `results/experiment_3/confusion_matrix_ft_50.png`
- `results/experiment_3/confusion_matrix_ft_100.png`
- `results/experiment_3/finetuning_curve.png` (OA vs Sample Size)
- `results/experiment_3/genus_improvement.csv`

---

## 6. Übergreifende Evaluationsmetriken

### 6.1 Primärmetriken (alle Experimente)

| Metrik                    | Formel                                            | Interpretation                                   |
| ------------------------- | ------------------------------------------------- | ------------------------------------------------ |
| **Overall Accuracy (OA)** | `(TP + TN) / Total`                               | Anteil korrekt klassifizierter Bäume             |
| **F1-Score (makro)**      | `2 * (Precision * Recall) / (Precision + Recall)` | Harmonisches Mittel, balanciert für alle Klassen |
| **Producer's Accuracy**   | `TP / (TP + FN)`                                  | Recall pro Genus (Vollständigkeit)               |
| **User's Accuracy**       | `TP / (TP + FP)`                                  | Precision pro Genus (Zuverlässigkeit)            |

### 6.2 Sekundärmetriken

**Genus-spezifische Metriken:**

- F1-Score pro Genus (identifiziert schwierige Arten)
- Confusion Matrix (systematische Verwechslungen)

**Feature-basierte Analysen:**

- **SHAP Values (RF):** Wichtigste Features pro Experiment
- **Feature Contribution:** CHM vs. Sentinel-2 vs. Vegetation Indizes

**Transfer-spezifische Metriken:**

- **Transfer Loss:** `OA_Single-City - OA_Zero-Shot`
- **Transferability Index:** `OA_Zero-Shot / OA_Single-City` (0-1, höher = besser)

### 6.3 Visualisierungen

**Standard-Plots (pro Experiment):**

1. **Confusion Matrix** (Heatmap)
2. **F1-Score pro Genus** (Balkendiagramm)
3. **Feature Importance** (SHAP, nur RF)

**Vergleichsplots (experimentübergreifend):**

1. **Transfer Loss Comparison** (Exp 2: Hamburg/Berlin/Combined)
2. **Fine-Tuning Curve** (Exp 3: OA vs. Sample Size)
3. **Genus Transferability** (Exp 2: welche Arten generalisieren?)

---

## 7. Experimentelle Randbedingungen

### 7.1 Räumliche Stratifizierung (alle Experimente)

**Problem:** Spatial Autocorrelation

**Lösung:** 500×500m Block-basierte Splits (Phase 2.4)

**Implementierung:**

- Alle Bäume in **Block_i** → Training ODER Validation (nicht gemischt!)
- Hamburg+Berlin: ~80/20 Block-Split
- Rostock: 100% als Testset

**Referenz:** Roberts et al. (2017), _"Cross-validation strategies for data with spatial structure"_

### 7.2 Class Balancing

**Problem:** TILIA/ACER dominant vs. SORBUS/PRUNUS selten

**Lösung (Phase 2.3):** Stratified Downsampling zu 1,500 Samples/Genus

**Resultat:**

- Alle 7 Genera: ~14% Anteil (perfekt balanciert)
- Keine Class Weights nötig

### 7.3 Feature Normalisierung

**Scaler-Strategie (Phase 2.5):**

| Experiment          | Scaler gefittet auf              | Begründung                              |
| ------------------- | -------------------------------- | --------------------------------------- |
| **Exp 0/1 Hamburg** | Hamburg Train (8,371)            | Keine Kontamination mit anderen Städten |
| **Exp 0/1 Berlin**  | Berlin Train (8,299)             | Separate Single-City Baselines          |
| **Exp 2**           | Hamburg+Berlin Combined (16,670) | Multi-City Scaler für Transfer          |
| **Exp 3**           | Hamburg+Berlin Combined (reused) | Kein Data Leakage, konsistent mit Exp 2 |

**Kritisch:** Scaler wird NIE auf Test-Daten gefittet!

### 7.4 Label Encoding

**Strategie:** Label Encoder gefittet auf allen 7 viable Genera

```
0: ACER
1: BETULA
2: FRAXINUS
3: PRUNUS
4: QUERCUS
5: SORBUS
6: TILIA
```

**Begründung:**

- Einheitliche Encoding für alle Experimente
- Vermeidet Inkonsistenzen zwischen Train/Val/Test

---

## 8. Reproduzierbarkeit & Technische Infrastruktur

### 8.1 Compute Environment

**Plattform:** Google Colab (Free Tier)

**Ressourcen:**

- CPU: 2+ vCPU
- RAM: 12-15 GB
- GPU: Optional (T4/P100/V100 für CNN)
- Runtime: ~12h pro Session
- Storage: Google Drive (100 GB)

### 8.2 Random Seeds

**Reproduzierbarkeit:**

```python
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)  # falls CNN
```

### 8.3 Checkpointing

**Strategie:**

- Speichere Modelle nach jedem Experiment
- Speichere Metriken in CSV (für spätere Analyse)
- Google Drive als persistent storage

---

## 9. Erwartete Gesamtergebnisse (Zusammenfassung)

### 9.1 Performance-Matrix (Schätzungen)

| Experiment               | Setup               | Erwartete OA | F1-Score (makro) |
| ------------------------ | ------------------- | ------------ | ---------------- |
| **Exp 0 (RF)**           | Berlin Single-City  | 85-92%       | 0.82-0.88        |
| **Exp 0 (CNN)**          | Berlin Single-City  | 80-87%       | 0.77-0.83        |
| **Exp 1 (Hamburg)**      | Hamburg Single-City | 87-90%       | 0.84-0.87        |
| **Exp 1 (Berlin)**       | Berlin Single-City  | 85-88%       | 0.82-0.85        |
| **Exp 2 (Hamburg→ROS)**  | Zero-Shot           | 75-80%       | 0.71-0.76        |
| **Exp 2 (Berlin→ROS)**   | Zero-Shot           | 72-77%       | 0.68-0.73        |
| **Exp 2 (Combined→ROS)** | Zero-Shot           | 78-83%       | 0.74-0.79        |
| **Exp 3 (+50 Samples)**  | Fine-Tuned          | 81-86%       | 0.77-0.82        |
| **Exp 3 (+100 Samples)** | Fine-Tuned          | 83-88%       | 0.80-0.85        |

### 9.2 Kernerkenntnisse (erwartet)

**Methodenwahl (Exp 0):**

- RF wahrscheinlich ausreichend (85-92% OA)
- CNN nur marginal besser oder gleichauf
- **Entscheidung:** RF wird Hauptmodell (Interpretierbarkeit + Geschwindigkeit)

**Single-City Performance (Exp 1):**

- Hamburg: ~88% OA (maritim, homogener)
- Berlin: ~86% OA (kontinental, diverser)
- **Schwierige Genera:** FRAXINUS, SORBUS, PRUNUS

**Transfer Loss (Exp 2):**

- Hamburg→Rostock: -10% Transfer Loss (beide maritim)
- Berlin→Rostock: -13% Transfer Loss (klimatisch verschieden)
- **Combined→Rostock: -8% Transfer Loss** (beste Generalisierung)

**Fine-Tuning (Exp 3):**

- 100 Samples/Genus: +5-8% OA Verbesserung
- **Praktisch:** 700 lokale Bäume für operationelle Nutzung

---

## 10. Nächste Schritte & Implementation

### 10.1 Aktueller Status (Phase 2 abgeschlossen)

✅ **Phase 1:** Data Processing (CHM, Sentinel-2, Boundaries, Tree Cadastres)  
✅ **Phase 2:** Feature Engineering (Extraction, Validation, Balancing, Split, Normalization)  
📋 **Phase 3:** Model Training (Exp 0-3) - **NOCH NICHT DURCHGEFÜHRT**

### 10.2 Implementation-Roadmap

**Schritt 1: Experiment 0 - Baseline** (Priorität: HIGH)

- [ ] Random Forest Hyperparameter-Tuning (GridSearchCV)
- [ ] 1D-CNN Training (50 Epochs, Early Stopping)
- [ ] Metriken-Vergleich (OA, F1, Confusion Matrix)
- [ ] Entscheidung: RF oder CNN für Exp 1-3?

**Schritt 2: Experiment 1 - Single-City** (Priorität: HIGH)

- [ ] Trainiere Hamburg-Modell (mit Best Params aus Exp 0)
- [ ] Trainiere Berlin-Modell
- [ ] Baseline-Performance dokumentieren (Referenz für Transfer Loss)

**Schritt 3: Experiment 2 - Cross-City Transfer** (Priorität: HIGH)

- [ ] Hamburg → Rostock
- [ ] Berlin → Rostock
- [ ] Combined → Rostock
- [ ] Transfer Loss quantifizieren

**Schritt 4: Experiment 3 - Fine-Tuning** (Priorität: MEDIUM)

- [ ] Fine-Tuning mit 50 Samples/Genus
- [ ] Fine-Tuning mit 100 Samples/Genus
- [ ] (Optional) Fine-Tuning mit 200 Samples/Genus
- [ ] Kosten-Nutzen-Analyse (OA vs. Sample Size)

### 10.3 Dokumentation während Training

**Pro Experiment:**

1. Training Logs (Colab Notebook Output)
2. Metrics CSV (für Thesis-Tabellen)
3. Confusion Matrices (Visualisierungen)
4. Feature Importance Plots (SHAP)
5. Summary Report (Markdown)

---

## 11. Literatur & Methodische Referenzen

**Machine Learning für Remote Sensing:**

- Fassnacht et al. (2016). "Review of studies on tree species classification from remotely sensed data". _Remote Sensing of Environment_.
- Grabska et al. (2019). "Forest Stand Species Mapping Using the Sentinel-2 Time Series". _Remote Sensing_.

**Spatial Cross-Validation:**

- Roberts et al. (2017). "Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure". _Ecography_.
- Meyer et al. (2018). "Importance of spatial predictor variable selection in machine learning applications". _Ecological Modelling_.

**Transfer Learning & Domain Adaptation:**

- Tuia et al. (2016). "Domain Adaptation for the Classification of Remote Sensing Data: An Overview". _IEEE Geoscience and Remote Sensing Magazine_.
- Bruzzone & Marconcini (2010). "Domain Adaptation Problems: A DASVM Classification Technique and a Circular Validation Strategy". _IEEE TPAMI_.

**Random Forest Best Practices:**

- Breiman (2001). "Random Forests". _Machine Learning_.
- Belgiu & Drăguţ (2016). "Random forest in remote sensing: A review of applications and future directions". _ISPRS Journal_.

---

## 12. Anhang: Methodische Prinzipien

### 12.1 Transparenz über Perfektion

- **no_edge Variante:** Zeigt urbane Realität (keine künstliche Reinheit)
- **Transfer Loss dokumentieren:** Ehrlich über Limitationen

### 12.2 Baselines sind heilig

- RF/CNN mit identischen Features (kein Äpfel-Birnen-Vergleich)
- Single-City vor Cross-City (definiert "machbar")

### 12.3 Spatial Leakage vermeiden

- Grid-basiertes Blocking durchgängig
- Rostock = 100% Holdout (Zero-Shot-Test)

### 12.4 Ablationen > Blackbox

- Exp 0: RF vs CNN
- Exp 1: Single-City Baseline
- Exp 2: Transfer Loss quantifizieren
- Exp 3: Fine-Tuning-Potenzial

### 12.5 Operationelle Relevanz

- Fine-Tuning (Exp 3): "Was braucht eine Kommune?"
- Praktische Empfehlung: 100 Samples/Genus für neue Stadt

---

**Ende der methodischen Experimentstrategie**

**Status:** 📋 Dokumentiert, bereit zur Implementierung  
**Nächster Schritt:** Experiment 0 - Baseline Training (RF vs CNN)
