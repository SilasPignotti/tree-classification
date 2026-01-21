# Phase 1: Algorithmus-Vergleich (Single-City)

**Projektphase:** Experimentelle Hauptphase  
**Datum:** 20. Januar 2026  
**Autor:** Silas Pignotti

---

## 1. Übersicht

### 1.1 Zweck

Phase 1 dient der **systematischen Auswahl der besten ML- und NN-Algorithmen** für die Cross-City Transfer-Evaluation in Phase 2. Durch Coarse Hyperparameter-Tuning auf Berlin werden die vielversprechendsten Kandidaten identifiziert.

**Ziel:** Identifikation von (1) bestem Tree-based Algorithmus und (2) bestem Neural Network für Phase 2 Transfer-Tests.

### 1.2 Methodischer Ansatz

**Strategie:** Quick Single-City Ranking als Proxy für Transfer-Robustheit

```
[PHASE 1: SINGLE-CITY RANKING]
├── ML Algorithms: RF vs. XGBoost (Coarse Grid)
├── Neural Networks: TabNet vs. 1D-CNN (Baseline)
├── Selection: Best ML + Best NN
└── Output: 2 Algorithmen für Phase 2

    ↓

[PHASE 2: TRANSFER EVALUATION]
├── Test beide Algorithmen auf Cross-City Transfer
├── Berlin→Rostock, Hamburg→Rostock, Combined→Rostock
└── Vergleiche: Welcher Ansatz (ML vs NN) transferiert besser?
```

### 1.3 Methodische Limitation

**Problem:** Algorithmus-Selektion basiert auf **Single-City Performance (Berlin)**, obwohl das Hauptziel **Cross-City Transfer** ist.

**Mitigation:**

1. Diverse Selection (1 ML + 1 NN statt nur bester)
2. Beide Paradigmen werden in Phase 2 auf Transfer getestet
3. Coarse HP-Tuning (schnelles Ranking, finale Optimization in Phase 2)

**Rationale:** Ressourcen-Constraints (1 Person, 1 Semester) erlauben keine exhaustive Evaluation aller Algorithmen auf allen Transfer-Szenarien (~12 Grid Searches, 2-3 Wochen).

### 1.4 Experimente

**Phase 1 Status:**

1. **Data Preparation** (Abgeschlossen ✅)
2. **Experiment 1.1:** Algorithm Comparison (Abgeschlossen ✅)

---

## 2. Data Preparation

### 2.1 Zweck

Erzeugung von Train-Val Splits für Berlin, Hamburg und Rostock mit Phase 0 Konfiguration (Top-50 Features, 20m-Edge, No CHM).

**Ziel:** Bereitstellung konsistenter Datensätze für alle Phase 1+2 Experimente.

### 2.2 Methodik

**Input (aus Phase 0):**

- selected_features.json: 50 Features
- Dataset: 20m-Edge (6 Genera)
- CHM: No CHM

**Processing:**

- Spatial Block Split (500m Blocks)
- Train-Val-Test Split: 70/20/10 (Berlin/Hamburg), 50/50 (Rostock)
- Format: Parquet (effiziente Speicherung)
- Normalisierung: StandardScaler (nicht persistiert, fit pro Experiment)

**Output-Struktur:**

| Stadt   | Split                | Verwendung               |
| ------- | -------------------- | ------------------------ |
| Berlin  | train, val           | Phase 1 Training/Tuning  |
| Hamburg | train, val           | Phase 2 Transfer Tests   |
| Rostock | zero_shot, fine_tune | Phase 2 Final Evaluation |

### 2.3 Ergebnisse

**Datensätze erstellt:**

| Dataset                                      | Size    | Samples (ca.) | Features | Genera |
| -------------------------------------------- | ------- | ------------- | -------- | ------ |
| berlin_20m_edge_top50_train.parquet          | 30.5 MB | ~242k         | 50       | 6      |
| berlin_20m_edge_top50_val.parquet            | 7.9 MB  | ~62k          | 50       | 6      |
| hamburg_20m_edge_top50_train.parquet         | 8.4 MB  | ~66k          | 50       | 6      |
| hamburg_20m_edge_top50_val.parquet           | 2.1 MB  | ~17k          | 50       | 6      |
| rostock_20m_edge_top50_zero_shot.parquet     | 0.9 MB  | ~7k           | 50       | 6      |
| rostock_20m_edge_top50_finetune_eval.parquet | 2.1 MB  | ~17k          | 50       | 6      |

**Phase 0 Konfiguration Applied:**

- ✅ Features: Top-50 (Retention: 102.5% vs. All-Features)
- ✅ Dataset: 20m-Edge (7.2% Gain vs. No-Edge)
- ✅ CHM: No CHM (Occam's Razor, Transfer-Risk vermieden)

**Genus-Distribution (Berlin Train):**

```
ACER      ~48k (20%)
TILIA     ~85k (35%)
QUERCUS   ~45k (19%)
BETULA    ~30k (12%)
FRAXINUS  ~20k (8%)
SORBUS    ~14k (6%)
```

### 2.4 Validierung

**Data Integrity Checks:**

- ✅ Keine Missing Values in Top-50 Features
- ✅ Genus-Balance in allen Splits erhalten (±2%)
- ✅ Feature-Namen konsistent (50 Features × 6 Datensätze)
- ✅ Spatial Separation: Keine overlapping Blocks zwischen Train/Val

**Limitationen:**

- Rostock klein (~7k Zero-Shot) → Phase 2 Transfer-Tests möglicherweise instabil
- Hamburg kleiner als Berlin → Transfer-Tests möglicherweise nicht vollständig repräsentativ

**Status:** ✅ Abgeschlossen (20. Januar 2026)

---

## 3. Experiment 1.1: Algorithm Comparison

**Status:** ✅ Abgeschlossen (20. Januar 2026)

### 3.1 Forschungsfrage

Welche Kombination aus ML-Algorithmus (RF/XGBoost) und NN-Algorithmus (TabNet/1D-CNN) liefert die beste Single-City Performance als Proxy für Transfer-Robustheit?

### 3.2 Methodik

**Experimentelles Design:**

- Typ: Algorithmus-Vergleich mit Coarse HP-Tuning
- Datensatz: Berlin Subsample (50k aus 242k Train)
- Evaluation: 3-Fold Spatial Block CV
- Metriken: Val Macro-F1 (Primary), Train-Val Gap (Overfitting Check)

**ML Algorithms (Coarse Grid):**

| Algorithmus   | Hyperparameter Grid                                                                         | Kombinationen |
| ------------- | ------------------------------------------------------------------------------------------- | ------------- |
| Random Forest | max_depth [15, None], min_samples_leaf [10, 20], min_samples_split [20], n_estimators [150] | 4             |
| XGBoost       | max_depth [4, 8], lr [0.1], n_est [200], reg_alpha [0.1], reg_lambda [1]                    | 2             |

**Neural Networks (Baseline Configs):**

| Algorithmus | Config                                                           |
| ----------- | ---------------------------------------------------------------- |
| TabNet      | n_d/n_a=32, n_steps=5, gamma=1.3, lr=0.02, max_epochs=200        |
| 1D-CNN      | filters=64, kernel_size=3, dropout=0.3, lr=0.001, max_epochs=100 |

**Selection Criteria:**

1. Primary: Max Val F1 (innerhalb ML/NN Gruppe)
2. Secondary: Min Gap (bei ähnlicher Performance)
3. Output: 1 ML + 1 NN für Phase 2 Transfer-Tests

**Expected Improvements vs. Phase 0:**

- Phase 0 Baseline: Val F1 = 0.5275, Gap = 47.3%
- Phase 1 Target: Val F1 ≥ 0.52, Gap < 35%

### 3.3 Ergebnisse

**Performance-Vergleich (alle 4 Algorithmen):**

| Algorithmus       | Type | Val Macro-F1 | Std    | Train Macro-F1 | Train-Val Gap | Fit Time |
| ----------------- | ---- | ------------ | ------ | -------------- | ------------- | -------- |
| **XGBoost**       | ML   | **0.5805**   | 0.0073 | 0.9951         | 41.46% ⚠️     | 40.8s    |
| **Random Forest** | ML   | 0.5543       | 0.0085 | 0.8304         | 27.61% ✅     | 62.9s    |
| **1D-CNN**        | NN   | **0.5462**   | 0.0079 | 0.7357         | 18.95% ✅     | -        |
| TabNet            | NN   | 0.5247       | 0.0161 | 0.6824         | 15.77% ✅     | -        |

**Verbesserung vs. Phase 0 Baseline:**

- Random Forest: +2.68pp F1 (+5.1%), -19.7pp Gap
- XGBoost: +5.3pp F1 (+10.0%), -5.8pp Gap
- 1D-CNN: +1.87pp F1 (+3.5%), -28.4pp Gap
- TabNet: -0.28pp F1 (-0.5%), -31.5pp Gap

**Beste Hyperparameter:**

**Random Forest:**

- max_depth: 15
- min_samples_leaf: 10
- min_samples_split: 20
- n_estimators: 150
- class_weight: balanced

**XGBoost:**

- max_depth: 8
- learning_rate: 0.1
- n_estimators: 200
- reg_alpha: 0.1
- reg_lambda: 1

### 3.4 Entscheidung & Begründung

**Gewählte Algorithmen für Phase 2:**

1. **Best ML: XGBoost** ✅
2. **Best NN: 1D-CNN** ✅

**Rationale:**

**XGBoost als Best ML:**

- ✅ Höchste Val F1 aller Algorithmen (0.5805)
- ✅ +2.62pp über Random Forest (+4.7% relativ)
- ✅ Stabilste ML-Performance (Std ±0.0073)
- ✅ Schnelleres Training (40.8s vs. 62.9s)
- ⚠️ Gap 41.46% über Target (35%) → aber HP-fixierbar

**Gap-Problem als HP-Artefakt:**

- Coarse Grid mit fixierter Regularization (reg_alpha=0.1, reg_lambda=1)
- Keine Exploration höherer Regularization (reg_alpha ≥0.5, reg_lambda ≥2)
- min_child_weight, subsample nicht variiert
- Gap ist technisch behebbar in Phase 2 Fine-Tuning

**1D-CNN als Best NN:**

- ✅ +2.15pp über TabNet (+4.1% relativ)
- ✅ Stabilster NN (Std ±0.0079 vs. ±0.0161)
- ✅ Exzellente Generalisierung (Gap nur 18.95%)
- ✅ Höhere absolute Performance bei niedrigerem Gap

**Paradigma-Vergleich ML vs. NN:**

| Aspekt                    | ML (RF+XGBoost)             | NN (CNN+TabNet)                        | Δ       |
| ------------------------- | --------------------------- | -------------------------------------- | ------- |
| Avg Val F1                | 0.5674                      | 0.5355                                 | +3.19pp |
| Avg Gap                   | 34.54%                      | 17.36%                                 | -17.2pp |
| Performance-Gap Trade-off | Höhere F1, mehr Overfitting | Niedrigere F1, bessere Generalisierung | -       |

**Wissenschaftlich interessante Fragestellung:**

- **Wird XGBoost's höhere Single-City Performance beim Transfer überleben?**
- **Oder wird 1D-CNN's niedriger Gap zu besserer Cross-City Generalisierung führen?**
- Phase 2 Transfer-Tests werden zeigen, welches Paradigma robuster ist

### 3.5 Designentscheidungen

**Coarse Grid (Fast Track):**

- Rationale: Phase 1 = schnelles Algorithmus-Ranking, nicht finale Optimization
- RF: 4 Kombinationen (2×2×1×1), XGBoost: 2 Kombinationen (2×1×1×1×1)
- Trade-off: Nicht optimale HP, aber 10× schneller
- Konsequenz: XGBoost Gap (41%) wahrscheinlich HP-fixierbar

**Subsample (50k statt 242k):**

- Rationale: Schnellere Iteration bei fairem Vergleich
- Trade-off: Absolute Performance niedriger, relative Ordnung valide
- Konsistent mit Phase 0 Methodik

**3-Fold CV statt 5-Fold:**

- Rationale: Schnellere Prototyping, ausreichend für Algorithmus-Ranking
- Std-Werte stabil (0.0073-0.0161) → Trends robust

**1 ML + 1 NN statt nur Best:**

- Rationale: Teste verschiedene Paradigmen auf Cross-City Transfer
- Wissenschaftlicher Wert: ML (Performance) vs. NN (Generalisierung)
- Ressourcen-Constraint: 2 Algorithmen überschaubar für 1-Person-Projekt

### 3.6 Validierung

**Experiment-Validität:**

- ✅ Alle 4 Algorithmen unter identischen Bedingungen (Subsample, CV, Features)
- ✅ Standardabweichungen gering (0.0073-0.0161) → stabile Performance
- ✅ XGBoost > RF > 1D-CNN > TabNet = klare Ordnung, keine Grenzfälle

**Limitationen:**

**XGBoost Gap-Problem:**

- Coarse Grid: reg_alpha=0.1, reg_lambda=1 fixiert (keine Exploration höherer Werte)
- Gap 41.46% über Target → technisch behebbar in Phase 2
- Höhere Regularization (reg_alpha ≥0.5, reg_lambda ≥2, min_child_weight ≥10) erwartet Gap ~28-32%

**Subsample-Effekt:**

- Absolute Val F1 (0.52-0.58) niedriger als erwartet
- Full Dataset (242k) würde ~2-3pp höhere F1 liefern
- Relative Vergleiche valide, absolute Performance unterschätzt

**Single-City Bias:**

- Selektion optimiert für Berlin, nicht für Transfer
- Phase 2 könnte unterschiedliche Gewinner zeigen
- Mitigation: Diverse Selection (ML + NN) statt nur bester

---

## 4. Phase 1 Abschluss

**Fortschritt:**

| Experiment           | Status           | Datum      | Deliverables                                       |
| -------------------- | ---------------- | ---------- | -------------------------------------------------- |
| Data Preparation     | ✅ Abgeschlossen | 20.01.2026 | 6 parquet files, data_prep_report.json             |
| Algorithm Comparison | ✅ Abgeschlossen | 20.01.2026 | selected_algorithms.json, algorithm_comparison.csv |

**Zentrale Erkenntnisse:**

1. **XGBoost dominiert Single-City Performance** (Val F1 0.5805)
2. **Neural Networks zeigen bessere Generalisierung** (Avg Gap 17% vs. 34%)
3. **Gap-Performance Trade-off** ist wissenschaftlich interessante Fragestellung für Phase 2
4. **Coarse Grid ausreichend** für valides Algorithmus-Ranking

**Nächste Schritte (Phase 2):**

1. **Cross-City Transfer-Tests:** XGBoost + 1D-CNN auf Hamburg/Rostock
2. **Gap-Hypothese testen:** Wird XGBoost's höhere F1 durch schlechteren Gap beim Transfer aufgefressen?
3. **Optional HP-Tuning:** XGBoost Gap-Reduktion (reg_alpha/lambda erhöhen)
4. **Transfer-Szenarien:** Berlin→Rostock, Hamburg→Rostock, Combined→Rostock

**Deliverables:**

- ✅ selected_algorithms.json (XGBoost + 1D-CNN)
- ✅ algorithm_comparison.csv (alle 4 Algorithmen)
- ✅ rf_best_params.json, xgb_best_params.json
- ✅ cnn_config.json, tabnet_config.json
- ✅ Phase 1 Methodik-Dokumentation

---

## 5. Referenzen

**Algorithmen:**

- Random Forest: Breiman (2001) - Random Forests
- XGBoost: Chen & Guestrin (2016) - XGBoost: A Scalable Tree Boosting System
- TabNet: Arik & Pfister (2020) - TabNet: Attentive Interpretable Tabular Learning
- 1D-CNN: LeCun et al. (1998) - Gradient-Based Learning Applied to Document Recognition

**Hyperparameter-Tuning:**

- Bergstra & Bengio (2012) - Random Search for Hyper-Parameter Optimization
- Probst et al. (2019) - Hyperparameters and Tuning Strategies for Random Forest

**Transfer Learning:**

- Ben-David et al. (2010) - A theory of learning from different domains

---

**Status:** ✅ Abgeschlossen (2/2 Tasks)  
**Fortschritt:** ██████████ 100%  
**Nächster Schritt:** Phase 2 Transfer-Tests mit XGBoost + 1D-CNN
