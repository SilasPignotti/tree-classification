> **Ziel der Seite:** Ein reproduzierbarer, klar nachvollziehbarer Experiment-Plan (Phasen 0–4) inklusive Entscheidungskriterien und Output-Artefakten.

---

## Übersicht: Phasen und Experimente

| Phase | Ziel                       | Experimente | Output                              |
| ----- | -------------------------- | ----------- | ----------------------------------- |
| 0     | Setup fixieren             | 0.1–0.3     | CHM-Strategie, Dataset, Feature-Set |
| 1     | Algorithmus-Vergleich      | 1.1–1.4     | Beste Modelle + HP-Konfigurationen  |
| 2     | Cross-City Transfer        | 2.1–2.3     | Transfer-Performance-Baseline       |
| 3     | Fine-Tuning                | 3.1–3.2     | Fine-Tuning-Effizienz-Kurve         |
| 4     | Berlin Maximum Performance | 4.1–4.6     | Upper Bound + Interpretierbarkeit   |
| 5     | Post-hoc Analysen          | 5.1–5.4     | Transfer-Analysen + Robustheit      |

---

## Phase 0: Ablation – Setup fixieren

**Ziel:** Fixiere CHM-Strategie, Dataset und Feature-Set bevor Algorithmen verglichen werden.

**Reihenfolge ist kritisch:** CHM zuerst, weil Overfitting alle anderen Entscheidungen verfälscht.

---

### Exp 0.1: CHM-Strategie (Overfitting-Risiko)

| Aspekt             | Spezifikation                                                                         |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Frage**          | Können CHM-Features verwendet werden, ohne dass der Algorithmus nur daraus lernt?     |
| **Dataset**        | No-Edge (härter Test mit 13 Genera)                                                   |
| **Modell**         | Random Forest (Default-HP: n_estimators=500, max_depth=None, class_weight='balanced') |
| **Normalisierung** | StandardScaler (fit auf Train)                                                        |
| **CV**             | 5-Fold Spatial Block CV auf Berlin                                                    |

**Varianten:**

| Variante | CHM-Features                        | Beschreibung                                    |
| -------- | ----------------------------------- | ----------------------------------------------- |
| A        | Keine                               | Nur spektrale Features (144) – Baseline         |
| B        | height_m_norm                       | Z-Score normalisiert (genus- & city-spezifisch) |
| C        | height_m_percentile                 | Perzentil-Rang (0-1)                            |
| D        | height_m_norm + height_m_percentile | Beide engineered Features                       |
| E        | height_m (raw)                      | Original-Höhe (bekanntes Overfitting-Risiko)    |

**Metriken:**

| Metrik                      | Zweck                 | Schwellwert                 |
| --------------------------- | --------------------- | --------------------------- |
| Macro-F1                    | Performance-Vergleich | –                           |
| Feature Importance (Top-10) | CHM-Dominanz erkennen | CHM &gt;25% = problematisch |
| Train vs. Val Macro-F1 Gap  | Overfitting-Indikator | Gap &gt;10% = problematisch |
| Std über Folds              | Stabilität            | –                           |

**Entscheidungslogik:**

- **Wenn** Variante E (raw height_m) &gt;30% Importance:
  - → E ausschließen (bestätigt bekanntes Problem)
- **Wenn** alle CHM-Varianten (B, C, D) &gt;25% Importance auf CHM:
  - → CHM komplett weglassen, Variante A verwenden
- **Wenn** Variante A nur ≤3% schlechter als beste CHM-Variante:
  - → Variante A wählen (Occam's Razor, Transfer-Robustheit)
- **Wenn** Variante B, C oder D deutlich besser (&gt;3%) **und** CHM-Importance &lt;25%:
  - → Diese Variante verwenden
- **Bei Gleichstand** (B vs. C vs. D):
  - → Variante B (height_m_norm) bevorzugen (interpretierbar)

**Optional – Transfer-Sanity-Check:**

| Check               | Design                                     | Zweck                                               |
| ------------------- | ------------------------------------------ | --------------------------------------------------- |
| CHM-Transfer-Risiko | Train Berlin → Test Hamburg (1000 Samples) | Prüfe ob CHM-Variante zwischen Städten funktioniert |
| Entscheidung        | Wenn Δ Macro-F1 &gt;15%                    | CHM weglassen trotz guter Single-City-Performance   |

**Output Exp 0.1:**

- `decision_chm.md`: Gewählte Variante + Begründung
- `chm_comparison.csv`: Alle Varianten mit Metriken
- `feature_importance_per_variant.csv`

---

### Exp 0.2: Dataset-Wahl (No-Edge vs. 20m-Edge)

| Aspekt             | Spezifikation                                            |
| ------------------ | -------------------------------------------------------- |
| **Frage**          | Welches Dataset liefert bessere Single-City-Performance? |
| **Voraussetzung**  | CHM-Strategie aus 0.1 fixiert                            |
| **Modell**         | Random Forest (Default-HP, class_weight='balanced')      |
| **Normalisierung** | StandardScaler (fit auf Train)                           |
| **CV**             | 5-Fold Spatial Block CV auf Berlin                       |

**Varianten:**

| Variante | Dataset  | Genera | Samples (ca.) |
| -------- | -------- | ------ | ------------- |
| A        | No-Edge  | 13     | 635k          |
| B        | 20m-Edge | 6      | 222k          |

**Metriken:**

| Metrik         | Zweck                                      |
| -------------- | ------------------------------------------ |
| Macro-F1       | Performance-Vergleich                      |
| Std über Folds | Stabilität                                 |
| Genus-wise F1  | Welche Genera profitieren von Edge-Filter? |

**Entscheidungslogik:**

- **Wenn** No-Edge Macro-F1 ≥ (20m-Edge Macro-F1 - 2%):
  - → No-Edge wählen (mehr Genera = mehr wissenschaftliche Aussagekraft)
- **Wenn** 20m-Edge deutlich besser (&gt;5%):
  - → 20m-Edge wählen (spektrale Reinheit wichtiger)
- **Wenn** Δ zwischen 2–5%:
  - → No-Edge bevorzugen, aber in Phase 4 nochmal prüfen

**Output Exp 0.2:**

- `decision_dataset.md`: Gewähltes Dataset + Begründung
- `dataset_comparison.csv`: Beide Varianten mit Metriken

---

### Exp 0.3: Feature Reduction

| Aspekt            | Spezifikation                                                      |
| ----------------- | ------------------------------------------------------------------ |
| **Frage**         | Kann Feature-Reduktion Performance halten bei weniger Komplexität? |
| **Voraussetzung** | CHM-Strategie + Dataset aus 0.1/0.2 fixiert                        |
| **Methode**       | RF Feature Importance → Top-k Features                             |
| **Modell**        | RF (Default-HP)                                                    |
| **CV**            | 5-Fold Spatial Block CV auf Berlin                                 |

**Varianten:**

| Variante | Features    |
| -------- | ----------- |
| A        | Top-50      |
| B        | Top-80      |
| C        | Top-100     |
| D        | Alle (≈148) |

**Metriken:**

| Metrik                     | Zweck                      |
| -------------------------- | -------------------------- |
| Macro-F1 vs. Feature Count | Pareto-Optimum finden      |
| Feature-Gruppen in Top-k   | Welche Gruppen dominieren? |

**Entscheidungslogik:**

- Wähle kleinstes k mit: `Macro-F1_k ≥ (Macro-F1_all - 1%)`

**Output Exp 0.3:**

- `decision_features.md`: Gewähltes Feature-Set + Begründung
- `feature_reduction_curve.csv`
- `pareto_curve.png`
- `selected_features.txt`: Liste der finalen Features

---

### Phase 0 Abschluss

**Output Phase 0:**

- `decision_chm.md`: Gewählte CHM-Strategie
- `decision_dataset.md`: Gewähltes Dataset
- `decision_features.md`: Gewähltes Feature-Set
- `experiment_0.3.json`: Finale Konfiguration (Top-50 Features)
- `selected_features.json`: Liste der finalen Features

**Fixierte Konfiguration für Phase 1:**

```json
{
  "dataset": "20m_edge",
  "chm_strategy": "none",
  "features": {
    "count": 50,
    "source": "experiment_0.3/selected_features.json"
  },
  "normalization": "StandardScaler",
  "class_balancing": "algorithm_internal",
  "random_seed": 42
}
```

---

## Phase 1: Algorithmus-Ranking (Single-City)

**Ziel:** Quick Ranking von ML und NN Algorithmen → Selektion von 1 ML + 1 NN für Phase 2.

**Strategie:** Coarse Hyperparameter-Tuning auf Berlin Subsample als Proxy für Transfer-Robustheit.

**Methodische Limitation:** Selektion basiert auf Single-City Performance (Berlin), obwohl Hauptziel Cross-City Transfer ist. **Mitigation:** 1 ML (Tree-based) + 1 NN (Gradient-based) statt nur bester Algorithmus → Architectural Comparison in Phase 2.

**Voraussetzung:** Fixierte Konfiguration aus Phase 0 (20m-Edge, No CHM, Top-50 Features).

**Gemeinsame Parameter für alle Exp 1.x:**

| Aspekt              | Spezifikation                                                        |
| ------------------- | -------------------------------------------------------------------- |
| **Daten**           | Berlin 20m-Edge, Top-50 Features, 50k stratified sample              |
| **Normalisierung**  | StandardScaler (fit auf Train pro Fold)                              |
| **CV**              | 3-Fold Spatial Block CV (500m)                                       |
| **Class Balancing** | Algorithmus-intern (class_weight / scale_pos_weight / class_weights) |
| **HP-Tuning**       | GridSearchCV (Coarse Grid) für schnelles Ranking                     |
| **Random Seed**     | 42                                                                   |

**Metriken (alle Experimente):**

| Metrik            | Beschreibung      |
| ----------------- | ----------------- |
| Macro-F1          | Primäre Metrik    |
| Weighted-F1       | Sekundär          |
| Overall Accuracy  | Sekundär          |
| Genus-wise F1     | Für Fehleranalyse |
| Confusion Matrix  | Für Fehleranalyse |
| Train vs. Val Gap | Overfitting-Check |
| Fit Time          | Praktikabilität   |

---

### Exp 1.1: Random Forest (Coarse Grid)

**Fokus:** Regularization gegen Phase 0 Overfitting (47% Gap).

| Parameter         | Suchraum (Coarse)  | Reasoning                            |
| ----------------- | ------------------ | ------------------------------------ |
| max_depth         | [10, 15, 20, None] | Phase 0: None = 100% Train → 47% Gap |
| min_samples_leaf  | [5, 10, 20]        | Regularization                       |
| min_samples_split | [10, 20]           | Zusätzliche Regularization           |
| n_estimators      | [200]              | Fixed (Zeit-Constraint)              |
| class_weight      | ['balanced']       | Fixed (aus Phase 0)                  |

**Kombinationen:** 4 × 3 × 2 = 24 Configs  
**Expected Runtime:** ~1-1.5h

**Output:**

- `rf_grid_search_results.csv`
- `rf_best_params.json`
- `rf_cv_metrics.csv`

---

### Exp 1.2: XGBoost (Coarse Grid)

**Erwartung:** Bessere Regularization als RF (oft Gap 20-28%).

| Parameter        | Suchraum (Coarse) | Reasoning                      |
| ---------------- | ----------------- | ------------------------------ |
| max_depth        | [4, 6, 8]         | XGBoost braucht flachere Trees |
| learning_rate    | [0.05, 0.1]       | Standard-Range                 |
| n_estimators     | [200, 300]        | Mehr Trees bei lower LR        |
| subsample        | [0.8]             | Fixed (Standard)               |
| colsample_bytree | [0.8]             | Fixed (Standard)               |
| min_child_weight | [3, 5]            | Regularization                 |
| reg_alpha        | [0, 0.1]          | L1 Regularization              |
| reg_lambda       | [1, 2]            | L2 Regularization              |

**Kombinationen:** 3 × 2 × 2 × 2 × 2 = 48 Configs  
**Expected Runtime:** ~1.5-2h

**Output:**

- `xgb_grid_search_results.csv`
- `xgb_best_params.json`
- `xgb_cv_metrics.csv`

---

### Exp 1.3: 1D-CNN (Optional)

**Status:** Optional - nur wenn Zeit nach RF/XGBoost/TabNet.

**Architecture:** Temporal Convolution über Monate (8 Zeitschritte).

| Parameter     | Baseline Config                   | Reasoning                |
| ------------- | --------------------------------- | ------------------------ |
| n_conv_blocks | 2                                 | Simple Architecture      |
| filters       | 64                                | Standard                 |
| kernel_size   | 3                                 | Capture 3-Month Patterns |
| dropout       | 0.3                               | Regularization           |
| dense_units   | 128                               | Post-Conv Dense          |
| learning_rate | 1e-3                              | Standard für CNN         |
| batch_size    | 128                               | Smaller for Stability    |
| epochs        | 100 + EarlyStopping (patience=10) | Mit EarlyStopping        |

**Expected Runtime:** ~1-2h

**Output:**

- `cnn_baseline_results.csv`
- `cnn_config.json`
- `training_history.png`

---

### Exp 1.4: TabNet (Baseline)

**Architecture:** Attention-based Deep Learning für tabulare Daten.

| Parameter     | Baseline Config                   | Reasoning                    |
| ------------- | --------------------------------- | ---------------------------- |
| n_d / n_a     | 32                                | Decision/Attention Dimension |
| n_steps       | 5                                 | Multi-Step Reasoning         |
| gamma         | 1.3                               | Attention Relaxation         |
| lambda_sparse | 1e-3                              | Sparsity Regularization      |
| learning_rate | 0.02                              | Standard für TabNet          |
| batch_size    | 512                               | Balance: Speed vs. Stability |
| epochs        | 200 + EarlyStopping (patience=15) | Mit EarlyStopping            |

**Expected Runtime:** ~30-45 min

**Output:**

- `tabnet_baseline_results.csv`
- `tabnet_config.json`
- `tabnet_feature_importance.csv`

---

### Phase 1 Abschluss: Selection

**Selection Strategy: 1 ML + 1 NN (nicht nur bester Overall!)**

```
ML Champion: Best of {RF, XGBoost}
NN Champion: Best of {TabNet, optional CNN}

Reasoning:
- Teste beide Paradigmen (Tree-based vs. Neural)
- Vergleiche Transfer-Robustness in Phase 2
- Falls einer schlecht transferiert → Backup vorhanden
```

**Entscheidungskriterien:**

1. **Filter:** Val F1 ≥ 0.50 (keine Regression vs. Phase 0)
2. **Filter:** Gap < 35% (Overfitting unter Kontrolle)
3. **Primary:** Max Val F1 (innerhalb ML bzw. NN Gruppe)
4. **Tie-Break:** Min Gap (bessere Generalisierung)

**Output Phase 1:**

- `algorithm_comparison.csv`: Alle 4 Algorithmen mit Metriken
- `selected_algorithms.json`: {best_ml, best_nn} mit Reasoning
- `decision_algorithms.md`: Entscheidungsbegründung + Limitation
- `rf_best_params.json`, `xgb_best_params.json`, `tabnet_config.json`

---

## Phase 2: Transfer Evaluation + Fine HP-Tuning

**Ziel:**

1. Quantifiziere Cross-City Transfer (Berlin → Rostock, Hamburg → Rostock)
2. Fine Hyperparameter-Tuning auf Combined Data (Berlin + Hamburg)
3. Vergleiche ML vs. NN Transfer-Robustheit

**Voraussetzung:** Best ML + Best NN aus Phase 1 mit Coarse HP.

**Gemeinsame Parameter:**

| Aspekt              | Spezifikation                                      |
| ------------------- | -------------------------------------------------- |
| **Modelle**         | Best ML + Best NN aus Phase 1                      |
| **Normalisierung**  | StandardScaler (fit auf Training-Stadt(en))        |
| **Test**            | Rostock Test-Split (30% von Rostock)               |
| **Class Balancing** | Wie in Phase 1                                     |
| **HP Strategy**     | Phase 1 Coarse HP für 2.1/2.2, Fine Tuning für 2.3 |

**Metriken:**

| Metrik                     | Zweck                           |
| -------------------------- | ------------------------------- |
| Macro-F1                   | Primär                          |
| Weighted-F1                | Sekundär                        |
| Overall Accuracy           | Sekundär                        |
| Genus-wise F1              | Transfer-Analyse pro Genus      |
| Δ zu Single-City (Phase 1) | Transfer-Verlust quantifizieren |
| Confusion Matrix           | Systematische Verwechslungen    |

---

### Exp 2.1: Berlin → Rostock

| Aspekt       | Spezifikation                        |
| ------------ | ------------------------------------ |
| **Training** | Berlin 100% (Train + Val kombiniert) |
| **Test**     | Rostock Test-Split (30%)             |
| **Modelle**  | Top-2 aus Phase 1                    |

**Output:**

- `results.json`
- `confusion_matrix_\\\{model\\\}.png`
- `genus_wise_f1.csv`

---

### Exp 2.2: Hamburg → Rostock

| Aspekt       | Spezifikation                         |
| ------------ | ------------------------------------- |
| **Training** | Hamburg 100% (Train + Val kombiniert) |
| **Test**     | Rostock Test-Split (30%)              |
| **Modelle**  | Top-2 aus Phase 1                     |

**Output:** Analog zu Exp 2.1.

---

### Exp 2.3: Berlin + Hamburg → Rostock

| Aspekt       | Spezifikation                    |
| ------------ | -------------------------------- |
| **Training** | Berlin + Hamburg 100% kombiniert |
| **Test**     | Rostock Test-Split (30%)         |
| **Modelle**  | Top-2 aus Phase 1                |

**Output:** Analog zu Exp 2.1.

---

### Phase 2 Abschluss

**Output Phase 2:**

- `transfer_performance_table.csv`: 6 Zeilen (3 Setups × 2 Modelle)
- `genus_transfer_robustness.csv`: Δ F1 pro Genus (Single-City vs. Transfer)
- `phase_2_[summary.md](http://summary.md)`: Bestes Transfer-Setup für Phase 3

---

## Phase 3: Fine-Tuning

**Ziel:** Wie viel lokale Daten kompensieren Transfer-Verlust?

**Voraussetzung:** Bestes Modell + Setup aus Phase 2 (vermutlich Exp 2.3).

---

### Exp 3.1: Fine-Tuning-Kurve

| Aspekt           | Spezifikation                                              |
| ---------------- | ---------------------------------------------------------- |
| **Basis-Modell** | Bestes aus Exp 2.3 (trainiert auf Berlin + Hamburg)        |
| **Test**         | Rostock Test-Split (30%) – unverändert über alle Varianten |

**Varianten:**

| Variante | Fine-Tuning-Daten | Beschreibung                                          |
| -------- | ----------------- | ----------------------------------------------------- |
| A        | 0%                | Keine lokalen Daten (= Exp 2.3 Ergebnis)              |
| B        | 10%               | 10% von Rostock Train-Split (~4.4k Samples bei 70/30) |
| C        | 25%               | 25% von Rostock Train-Split                           |
| D        | 50%               | 50% von Rostock Train-Split                           |
| E        | 100%              | 100% von Rostock Train-Split                          |

**Fine-Tuning-Methode (modellabhängig):**

| Modell  | Methode                                                |
| ------- | ------------------------------------------------------ |
| RF      | Zusätzliche Trees trainieren (warm_start) oder Retrain |
| XGBoost | Continue training (xgb_model Parameter)                |
| 1D-CNN  | Unfreeze letzte Layers, niedriger LR                   |
| TabNet  | Continue training mit niedrigem LR                     |

**Metriken:**

| Metrik                            | Zweck                    |
| --------------------------------- | ------------------------ |
| Macro-F1 vs. Fine-Tuning-Fraction | Hauptergebnis            |
| Δ zu 0% (Transfer-Baseline)       | Recovery quantifizieren  |
| Δ zu 100% (From-Scratch)          | Vergleich mit Obergrenze |

**Output:**

- `finetuning_curve.csv`
- `finetuning_curve.png`
- `analysis.md`: Empfehlung minimale Datenmenge

---

### Exp 3.2: From-Scratch-Baseline (Rostock Only)

| Aspekt       | Spezifikation                                 |
| ------------ | --------------------------------------------- |
| **Frage**    | Was ist die Obergrenze mit nur lokalen Daten? |
| **Training** | Rostock Train-Split 100% (70% von Rostock)    |
| **Test**     | Rostock Test-Split (30%)                      |
| **Modelle**  | Top-2 aus Phase 1 (mit HP-Tuning auf Rostock) |

**Zweck:**

- Obergrenze für lokale Performance
- Vergleich: Ist Transfer + Fine-Tuning besser als From-Scratch?

**Output:**

- `results.json`
- `comparison_transfer_vs_scratch.csv`

---

### Phase 3 Abschluss

**Output Phase 3:**

- `finetuning_efficiency.csv`: Macro-F1 vs. Datenmenge
- `finetuning_curve.png`: Visualisierung
- `phase_3_summary.md`: Empfehlungen

---

## Phase 4: Berlin Maximum Performance

**Ziel:** Etablierung der maximalen erreichbaren Single-City-Performance als Upper Bound Reference.

**Algorithmus:** XGBoost (beste Single-City Performance aus Phase 1: 0.5805 F1)

**Rationale:**

- XGBoost hatte beste Berlin-Performance vs. 1D-CNN (0.5805 vs 0.5462)
- Native Feature Importance (gain-based)
- Schnelleres Training (~41s vs hours für CNN)
- 1D-CNN hat bessere Transfer-Robustness (irrelevant für Single-City Upper Bound)

**Voraussetzung:** Fixierte Konfiguration aus Phase 0 (20m-Edge, No CHM, Top-50 Features).

**Gemeinsame Parameter:**

| Aspekt              | Spezifikation                    |
| ------------------- | -------------------------------- |
| **Daten**           | Berlin 20m-Edge, Top-50 Features |
| **Train/Val Split** | Spatial Block (500m), 242k / 62k |
| **Normalisierung**  | StandardScaler (fit auf Train)   |
| **Class Balancing** | scale_pos_weight (XGBoost)       |
| **Random Seed**     | 42                               |

**Erwartete Performance:**

- Phase 1 Baseline: 0.5805 F1 (50k subsample, coarse HP, Gap 41%)
- Phase 4 Optimized: ~0.62-0.65 F1 (full data, tuned HP, Gap ~30%)
- Improvement: +4-7pp F1 (~7-12% relativ)

---

### Exp 4.1: Baseline Performance

| Aspekt       | Spezifikation                            |
| ------------ | ---------------------------------------- |
| **Frage**    | Wie ist die Baseline mit Phase 1 HPs?    |
| **Daten**    | Berlin full (242k train, 62k val)        |
| **Modell**   | XGBoost mit Phase 1 Coarse HP            |
| **Metriken** | Train/Val F1, Gap, Per-Genus Performance |

**Phase 1 HPs:**

- max_depth: 8
- learning_rate: 0.1
- n_estimators: 200
- reg_alpha: 0.1, reg_lambda: 1

**Expected:** Val F1 ~0.58-0.60 (vs 0.5805 auf 50k subsample)

**Output:**

- `baseline_results.json`
- `baseline_genus_performance.csv`

---

### Exp 4.2: Hyperparameter Optimization

| Aspekt       | Spezifikation                                       |
| ------------ | --------------------------------------------------- |
| **Frage**    | Welche HP-Konfiguration optimiert für Single-City?  |
| **Fokus**    | Gap Reduction (41% → ~30%) + Performance-Steigerung |
| **Methode**  | GridSearchCV (3-Fold Spatial Block CV)              |
| **Metriken** | CV Macro-F1, Train/Val F1, Gap                      |

**HP-Tuning Grid:**

| Parameter        | Suchraum        | Reasoning              |
| ---------------- | --------------- | ---------------------- |
| reg_alpha        | [0.1, 0.5, 1.0] | L1 Regularization      |
| reg_lambda       | [1, 2, 5]       | L2 Regularization      |
| min_child_weight | [5, 10, 20]     | Leaf Regularization    |
| subsample        | [0.7, 0.8, 0.9] | Sample Regularization  |
| colsample_bytree | [0.7, 0.8, 0.9] | Feature Regularization |
| max_depth        | [8]             | Fixed (aus Phase 1)    |
| learning_rate    | [0.1]           | Fixed                  |
| n_estimators     | [200]           | Fixed                  |

**Kombinationen:** 243 (3×3×3×3×3)
**Expected Runtime:** ~2-3h

**Goal:** Gap < 30%, Val F1 ≥ 0.62

**Output:**

- `berlin_xgboost_optimized.json` (best HP config)
- `grid_search_results.csv`

---

### Exp 4.3: Final Training & Genus Analysis

| Aspekt     | Spezifikation                           |
| ---------- | --------------------------------------- |
| **Frage**  | Detaillierte Genus-Level Performance    |
| **Modell** | XGBoost mit optimierten HPs aus Exp 4.2 |
| **Daten**  | Berlin full (242k train, 62k val)       |

**Analysen:**

1. **Per-Genus Performance**
   - Precision/Recall/F1 pro Genus
   - Sample-Size-Korrelation mit F1
   - Identifikation Best/Worst Performer

2. **Confusion Matrix**
   - Absolute counts
   - Normalisiert (percentage)
   - Most confused genus pairs

3. **Sample-Size Analysis**
   - Pearson Correlation (samples vs F1)
   - Interpretation: Sample-driven vs. Separability-driven

**Output:**

- `genus_performance_berlin.csv`
- `confusion_matrix_berlin.csv/png`
- `confusion_pairs.csv`
- `genus_performance_comparison.png`
- `sample_size_correlation.png`

---

### Exp 4.4: Feature Importance Analysis

| Aspekt       | Spezifikation                             |
| ------------ | ----------------------------------------- |
| **Frage**    | Welche Features sind kritisch für Berlin? |
| **Modell**   | Optimiertes XGBoost aus Exp 4.3           |
| **Methoden** | (1) Native Gain, (2) Permutation          |

**Methode 1: XGBoost Native Gain**

- Built-in feature importance (split gain)
- Schnell, direkt aus Modell abrufbar
- Top-20 Features nach Gain

**Methode 2: Permutation Importance**

- Feature-wise Δ F1 durch Shuffling
- Rechenintensiv (~10 min, n_repeats=10)
- Model-agnostic, zeigt echte Performance-Impact

**Expected Top Features:**

- Spectral Bands: B08 (NIR), B11/B12 (SWIR)
- Vegetation Indices: NDVI, EVI, NDRE
- Temporal: Jun-Aug Features dominierend

**Output:**

- `feature_importance_gain.csv`
- `feature_importance_permutation.csv`
- `feature_importance_top20.png` (beide Methoden)

---

### Exp 4.5: Temporal Analysis

| Aspekt      | Spezifikation                                   |
| ----------- | ----------------------------------------------- |
| **Frage**   | Welche Monate sind kritisch für Klassifikation? |
| **Methode** | Month-wise Ablation (8 Modelle)                 |
| **Modell**  | Optimiertes XGBoost aus Exp 4.2                 |

**Ablation Design:**

Für jeden Monat (Apr-Nov):

1. Entferne alle Features dieses Monats (z.B. `_04_` für April)
2. Trainiere Modell ohne diese Features
3. Δ F1 = F1_full - F1_ablated
4. Höherer Δ F1 = kritischerer Monat

**Hypothese:**

- Jun-Aug kritisch (peak vegetation season)
- Apr/Nov weniger wichtig (Beginn/Ende Saison)

**Expected Runtime:** ~10 min (8 Trainings)

**Output:**

- `temporal_importance.csv` (month ranking by Δ F1)
- `temporal_contribution.png` (bar plot, top-3 highlighted)

---

### Exp 4.6: Tree Type Analysis

| Aspekt     | Spezifikation                      |
| ---------- | ---------------------------------- |
| **Frage**  | Genus-spezifische Charakteristiken |
| **Modell** | Optimiertes XGBoost aus Exp 4.3    |
| **Daten**  | Berlin val (62k)                   |

**Analysen:**

1. **Tree Type Distribution**
   - Deciduous vs Coniferous Genera
   - Note: Alle 6 Genera im Dataset sind deciduous

2. **Best/Worst Performer**
   - Highest F1 Genus + Charakteristiken
   - Lowest F1 Genus + Ursachen

3. **Confusion Pairs**
   - Top-10 verwechselte Genus-Paare
   - Percentage of true class
   - Hypothesen: ACER-TILIA (morphologisch ähnlich)?

**Limitation:**

- Coniferous-Analyse nicht möglich mit aktuellem Dataset
- Erweiterter Datensatz (PINUS, PICEA) benötigt

**Output:**

- `genus_characteristics.csv`
- `confusion_pairs.csv`
- Analysis in final summary

---

### Phase 4 Abschluss

**Output Phase 4:**

**Models & Configs:**

- `berlin_xgboost_optimized.json` (best HP config für zukünftigen Datensatz)
- `berlin_xgboost_model.pkl` (trained model + scaler + label_encoder)
- `model_metadata.json` (human-readable summary)

**Performance Metrics:**

- `baseline_results.json`
- `genus_performance_berlin.csv`
- `confusion_matrix_berlin.csv`

**Feature Analysis:**

- `feature_importance_gain.csv`
- `feature_importance_permutation.csv`
- `temporal_importance.csv`
- `confusion_pairs.csv`

**Visualizations (8 PNGs):**

- `confusion_matrix_berlin.png`
- `genus_performance_comparison.png`
- `sample_size_correlation.png`
- `feature_importance_top20.png`
- `temporal_contribution.png`

**Documentation:**

- `phase_4_summary.md`: Performance, Insights, Next Steps

**Key Insights für erweiterten Datensatz:**

1. Optimale HP-Konfiguration identifiziert (für 10+ Genera wiederverwendbar)
2. Kritische Features/Monate bekannt → Data Collection Fokus
3. Confusion Patterns → Zusätzliche Features für problematische Paare
4. Sample-Size-Effekt quantifiziert → Mindest-Samples pro Genus

---

## Phase 5: Post-hoc Analysen

**Ziel:** Transfer-spezifische Analysen und Robustness-Tests nach Abschluss der Kernexperimente.

**Voraussetzung:** Phase 1-4 abgeschlossen.

---

### Exp 5.1: Genus-spezifische Transfer-Analyse

| Aspekt      | Spezifikation                                               |
| ----------- | ----------------------------------------------------------- |
| **Frage**   | Welche Genera transferieren robust, welche nicht?           |
| **Daten**   | Ergebnisse aus Phase 1 (Single-City) und Phase 2 (Transfer) |
| **Methode** | Vergleiche Genus-wise F1: Single-City vs. Transfer          |

**Robustheit-Klassifikation:**

| Δ F1      | Klassifikation |
| --------- | -------------- |
| &lt;0.05  | Robust         |
| 0.05–0.15 | Mittel         |
| &gt;0.15  | Nicht robust   |

**Output:**

- `transfer_robustness_ranking.csv`
- `confusion_comparison.png`: Single-City vs. Transfer nebeneinander
- `genus_transfer_[analysis.md](http://analysis.md)`

---

### Exp 5.2: Feature-Gruppen-Contribution

| Aspekt      | Spezifikation                                          |
| ----------- | ------------------------------------------------------ |
| **Frage**   | Welche Feature-Gruppen treiben (Transfer-)Performance? |
| **Methode** | Ablation: Modell ohne bestimmte Feature-Gruppe         |
| **Modell**  | Bestes aus Phase 2 (Transfer-Setup)                    |

**Varianten:**

| Variante | Entfernte Features              | Verbleibend                          |
| -------- | ------------------------------- | ------------------------------------ |
| Baseline | Keine                           | Alle                                 |
| A        | Spektral-Bänder (B02–B12)       | VIs + CHM                            |
| B        | Broadband-VIs (NDVI, EVI, VARI) | Spektral + RedEdge + Water + CHM     |
| C        | Red-Edge-VIs (5 Indizes)        | Spektral + Broadband + Water + CHM   |
| D        | Water-VIs (NDWI, NDII)          | Spektral + Broadband + RedEdge + CHM |
| E        | CHM (falls verwendet)           | Nur Spektral + VIs                   |

**Output:**

- `ablation_results.csv`
- `feature_group_contribution.png`
- `feature_groups_[analysis.md](http://analysis.md)`

---

### Exp 5.3: Real-World-Robustheit

| Aspekt         | Spezifikation                                                 |
| -------------- | ------------------------------------------------------------- |
| **Frage**      | Wie performt das Modell auf unbereinigten "Real-World"-Daten? |
| **Modell**     | Bestes aus Phase 2/3                                          |
| **Test-Daten** | Verschiedene Bereinigungsstufen von Rostock                   |

**Varianten:**

| Variante | Rostock-Daten           | Pipeline-Stand | Beschreibung                   |
| -------- | ----------------------- | -------------- | ------------------------------ |
| A        | Bereinigt (Standard)    | Nach 03e       | Kontrollgruppe                 |
| B        | Nach NaN-Handling       | Nach 03b       | Ohne Outlier-Removal           |
| C        | Nach Temporal Selection | Nach 03a       | Kein Edge-Filter, kein Outlier |
| D        | Nach Tree-Correction    | Nach 01        | Nur height≥3m + NDVI≥0.3       |

**Daten-Vorbereitung:**

- Exportiere Rostock-Daten aus verschiedenen Pipeline-Zwischenständen.
- Wende gleiche Feature-Extraktion an (ohne Outlier-Filter).

**Interpretation:**

| Δ Macro-F1 | Bewertung                                            |
| ---------- | ---------------------------------------------------- |
| &lt;5%     | Robust, operativ einsetzbar                          |
| 5–15%      | Moderate Sensitivität, QA empfohlen                  |
| &gt;15%    | Hohe Sensitivität, nur mit bereinigten Daten nutzbar |

**Output:**

- `results_per_variant.csv`
- `robustness_[analysis.md](http://analysis.md)`
- `real_world_robustness.png`

---

### Exp 5.4: Outlier-Removal Ablation

| Aspekt      | Spezifikation                                                  |
| ----------- | -------------------------------------------------------------- |
| **Frage**   | Verbessert zusätzliche Outlier-Removal die Modell-Performance? |
| **Modell**  | Beste Modelle aus Phase 1 (ML + NN)                            |
| **Daten**   | Berlin Train/Val mit vs. ohne outlier_flag-Filter              |
| **Methode** | Vergleiche Standard-Datasets vs. Outlier-gefilterte Datasets   |

**Varianten:**

| Variante | Daten                   | Beschreibung                                             |
| -------- | ----------------------- | -------------------------------------------------------- |
| A        | Standard (mit Outliers) | Baseline aus Phase 1 (alle Bäume nach Standard-Filter)   |
| B        | No Outliers             | Zusätzlicher outlier_flag-Filter aus Feature Engineering |

**Datensätze (erstellt in Data Preparation):**

- `berlin_20m_edge_top50_train.parquet` (Standard)
- `berlin_20m_edge_top50_train_no_outliers.parquet` (Gefiltert)
- `berlin_20m_edge_top50_val.parquet` (Standard)
- `berlin_20m_edge_top50_val_no_outliers.parquet` (Gefiltert)

**Hypothesen:**

| Effekt           | Erwartung                                           |
| ---------------- | --------------------------------------------------- |
| Val Macro-F1     | +0-3% (weniger Noise)                               |
| Train-Val Gap    | -2-5% (bessere Generalisierung)                     |
| Genus-Balance    | Unverändert (Filter sollte klassen-agnostisch sein) |
| Training Samples | -3-7% (je nach Outlier-Rate)                        |

**Metriken:**

| Metrik                     | Zweck                         |
| -------------------------- | ----------------------------- |
| Δ Val Macro-F1             | Performance-Verbesserung      |
| Δ Train-Val Gap            | Generalisierungs-Verbesserung |
| Δ Training Samples         | Kosten-Nutzen-Ratio           |
| Genus-wise F1 Δ            | Welche Genera profitieren?    |
| Confusion Matrix Vergleich | Systematische Unterschiede    |

**Entscheidungslogik:**

- **Wenn** Val F1 Improvement > 1% **und** Gap Reduction > 2%:
  - → Outlier-Removal empfohlen für finale Pipeline
- **Wenn** Val F1 Improvement < 1% **oder** keine Gap-Verbesserung:
  - → Standard-Daten beibehalten (Occam's Razor)
- **Wenn** Val F1 sinkt:
  - → Outlier-Removal verwirft wichtige Edge Cases

**Transfer-Test (Optional):**

- Teste ob Outlier-Removal auch Transfer-Performance verbessert
- Berlin (no outliers) → Rostock (standard) vs. Berlin (standard) → Rostock (standard)

**Output:**

- `outlier_removal_comparison.csv`: Metriken für beide Varianten
- `outlier_removal_analysis.md`: Entscheidung + Begründung
- `confusion_matrix_comparison.png`: A vs. B nebeneinander
- `genus_wise_impact.csv`: Δ F1 pro Genus

---

### Phase 5 Abschluss

**Output Phase 5:**

- `transfer_robustness_ranking.csv` (Exp 5.1)
- `feature_group_contribution.csv` (Exp 5.2)
- `real_world_robustness.csv` (Exp 5.3)
- `outlier_removal_analysis.md` (Exp 5.4)
- `phase_5_summary.md`: Zusammenfassung aller Post-hoc Insights

---

## Experiment-Tracking-Struktur

### Ordnerstruktur

```
experiments/
├── config/
│   ├── CONFIG_FINAL.yaml
│   ├── hp_rf.yaml
│   ├── hp_xgb.yaml
│   ├── hp_cnn.yaml
│   ├── hp_tabnet.yaml
│   └── spatial_splits.yaml
├── phase_0_ablation/
│   ├── exp_0.1_chm_strategy/
│   ├── exp_0.2_dataset_choice/
│   └── exp_0.3_feature_reduction/
├── phase_1_algorithm/
├── phase_2_transfer/
├── phase_3_finetuning/
├── phase_4_berlin_maximum/
│   ├── exp_4.1_baseline/
│   ├── exp_4.2_hp_optimization/
│   ├── exp_4.3_genus_analysis/
│   ├── exp_4.4_feature_importance/
│   ├── exp_4.5_temporal_analysis/
│   └── exp_4.6_tree_type/
├── phase_5_posthoc/
│   ├── exp_5.1_transfer_analysis/
│   ├── exp_5.2_feature_groups/
│   ├── exp_5.3_real_world/
│   └── exp_5.4_outlier_removal/
├── models/
├── data/
└── summary/
```

---

### Standardisierte Datei-Formate

#### `results.json` (pro Experiment)

```json
{
  "experiment_id": "exp_2.1_berlin_to_rostock",
  "timestamp": "2026-01-18T14:30:00",
  "phase": 2,
  "config": {
    "dataset": "no_edge",
    "chm_strategy": "none",
    "features": {
      "count": 80,
      "list_file": "selected_features.txt"
    },
    "normalization": "StandardScaler",
    "model": "rf",
    "hp_config": "hp_best_rf.yaml",
    "class_balancing": "balanced"
  },
  "data": {
    "train_cities": ["Berlin"],
    "train_samples": 245614,
    "test_city": "Rostock",
    "test_samples": 18723,
    "n_genera": 13,
    "genera": ["ACER", "AESCULUS", "..."]
  },
  "metrics": {
    "macro_f1": 0.623,
    "weighted_f1": 0.671,
    "overall_accuracy": 0.684,
    "cohen_kappa": 0.598,
    "train_val_gap": null
  },
  "notes": "Transfer von Berlin nach Rostock ohne Fine-Tuning"
}
```

---

### Naming-Konventionen

| Element          | Format                                    | Beispiel                            |
| ---------------- | ----------------------------------------- | ----------------------------------- |
| Experiment-ID    | `exp_{phase}.{nummer}_{kurzbeschreibung}` | `exp_2.1_berlin_to_rostock`         |
| Modell-Dateien   | `{modell}_best.{ext}`                     | `rf_best.joblib`                    |
| Scaler-Dateien   | `scaler_{scope}.joblib`                   | `scaler_combined.joblib`            |
| Plots            | `{beschreibung}.png`                      | `confusion_matrix.png`              |
| Config-Dateien   | `{element}.yaml`                          | `CONFIG_FINAL.yaml`, `best_hp.yaml` |
| Metriken-Dateien | `{beschreibung}.csv`                      | `metrics_per_fold.csv`              |
| Entscheidungen   | `decision_{thema}.md`                     | `decision_chm.md`                   |

---

## Checklisten

### Checkliste vor jedem Experiment

- [ ] Experiment-ID vergeben
- [ ] Ordner angelegt: `experiments/phase_{X}_{name}/exp_{X.Y}_{beschreibung}/`
- [ ] Vorherige Phase abgeschlossen (falls abhängig)
- [ ] Korrektes Dataset geladen (no_edge / 20m_edge)
- [ ] Korrektes Feature-Set (nach Phase 0 Entscheidung)
- [ ] Train/Test-Split korrekt (kein Leakage)
- [ ] Normalisierung nur auf Train gefittet
- [ ] HP-Konfiguration dokumentiert
- [ ] Class Balancing aktiviert
- [ ] Random Seed gesetzt: 42
- [ ] Baseline-Experiment referenziert (falls Vergleich)
- [ ] Timestamp erfasst
- [ ] `results.json` gespeichert
- [ ] `metrics_per_fold.csv` gespeichert (falls CV)
- [ ] Confusion Matrix gespeichert
- [ ] `experiment_log.csv` aktualisiert
- [ ] Entscheidung dokumentiert (falls Phase 0)

### Checkliste nach jeder Phase

- [ ] Alle Experimente der Phase abgeschlossen
- [ ] `phase_{X}_summary.md` geschrieben
- [ ] Entscheidungen für nächste Phase dokumentiert
- [ ] `CONFIG_FINAL.yaml` aktualisiert (falls Phase 0)
- [ ] Modelle gespeichert (falls Phase 1)
- [ ] `experiment_log.csv` vollständig
