# Phase 0: Setup Fixierung

**Projektphase:** Experimentelle Vorbereitung  
**Datum:** 19. Januar 2026  
**Autor:** Silas Pignotti

---

## 1. Übersicht

### 1.1 Zweck

Phase 0 dient der **systematischen Fixierung aller Pipeline-Komponenten vor den Hauptexperimenten**. Durch kontrollierte Ablation-Tests werden Designentscheidungen validiert und für Phase 1-3 festgeschrieben.

**Ziel:** Eliminierung konfundierender Variablen in späteren Algorithmus-Vergleichen durch vorab fixierte Feature-Sets, Datensätze und Modell-Baselines.

### 1.2 Output

**Fixierte Konfiguration für Phase 1-3:**

- CHM-Strategie (mit/ohne Höhen-Features)
- Dataset-Wahl (No-Edge vs. 20m-Edge)
- Feature-Set (Top-k vs. All Features)

**Dokumentation:**

- decision\_\*.md: Entscheidungsbegründungen mit empirischer Evidenz
- exp\_\*.json: Vollständige Ergebnisse und Metriken
- selected_features.json: Feature-Liste für Phase 1

### 1.3 Experimente

1. **Experiment 0.1:** CHM-Strategie (Abgeschlossen ✅)
2. **Experiment 0.2:** Dataset Selection (Abgeschlossen ✅)
3. **Experiment 0.3:** Feature Reduction (Abgeschlossen ✅)

---

## 2. Experiment 0.1: CHM-Strategie

### 2.1 Forschungsfrage

Können CHM-Features (Baumhöhe) zur Klassifikation beitragen, ohne dass das Modell primär aus stadtspezifischer Höhen-Morphologie lernt (Shortcut Learning)?

**Hypothese:** Engineered Height-Features (normalized, percentile-rank) erlauben generalisierbares Lernen bei <25% CHM-Feature-Importance.

**Null-Hypothese:** CHM führt zu >25% Importance → Shortcut Learning / Overfitting.

### 2.2 Methodik

**Experimentelles Design:**

- Typ: Ablation Study (5 Varianten)
- Datensatz: Berlin Training (Subsample 50k aus 635k)
- Modell: Random Forest (Default-HP: 500 trees, balanced weights)
- Evaluation: 3-Fold Spatial Block Cross-Validation

**Varianten:**

| ID  | CHM-Features        | Beschreibung                        | Feature Count |
| --- | ------------------- | ----------------------------------- | ------------- |
| A   | Keine               | Nur spektrale Features (Baseline)   | 144           |
| B   | height_m_norm       | Z-Score normalisiert (genus+city)   | 145           |
| C   | height_m_percentile | Percentile-Rank (0-1)               | 145           |
| D   | Both Engineered     | height_m_norm + height_m_percentile | 146           |
| E   | height_m (raw)      | Original-Höhe (Overfitting-Risiko)  | 145           |

**Feature-Basis (alle Varianten):**

- 144 spektrale Features: Sentinel-2 Bänder (64) + VIs (80) × 8 Monate März-Oktober

**Entscheidungskriterium:**

- Performance-Gain <2% → Baseline bevorzugen
- CHM Rank #1 Feature → Transfer-Risk erkannt

### 2.3 Ergebnisse

**Performance-Vergleich:**

| Variant              | Val Macro-F1 | Std    | Train-Val Gap | CHM Importance      |
| -------------------- | ------------ | ------ | ------------- | ------------------- |
| **E** (height_m raw) | **0.3389**   | 0.0070 | 0.657         | **3.67%** (Rank #1) |
| D (Both Eng.)        | 0.3279       | 0.0071 | 0.672         | 3.18%               |
| B (height_m_norm)    | 0.3277       | 0.0067 | 0.672         | 2.11%               |
| C (height_m_perc)    | 0.3257       | 0.0077 | 0.674         | 1.95%               |
| **A (No CHM)**       | **0.3246**   | 0.0045 | 0.661         | 0.00%               |

**Delta (Best vs. Baseline):** +0.0143 (1.4%, relativ +4.4%)

**Feature Importance Top-3:**

- Variant A (Baseline): VARI_04 (1.33%), VARI_10 (1.28%), NDVI_03 (1.17%)
- Variant E (height_m): **height_m (3.67%)**, VARI_04 (1.28%), VARI_10 (1.24%)

### 2.4 Entscheidung & Begründung

**Gewählte Variante: A (No CHM)**

**Rationale:**

1. **Marginaler Gain:** 1.4% liegt unter 2%-Threshold → nicht substantiell
2. **CHM-Dominanz:** height_m ist Rank #1 trotz nur 1 von 145 Features → Over-Reliance
3. **Transfer-Risk:** Raw height kodiert city-specific Morphologie (bekannt aus Literatur)
4. **Engineered Features nicht besser:** Varianten B/C/D zeigen nur 0.1-0.3% Gain über Baseline
5. **Occam's Razor:** Einfacheres Modell (144 statt 145 Features) für bessere Robustheit

**Output:**

- decision_chm.md: Entscheidung "No CHM" mit Begründung
- exp_0.1_results.json: Vollständige Metriken aller 5 Varianten

### 2.5 Designentscheidungen

**Subsample (50k statt 635k):**

- Rationale: Relative Vergleiche valide, absolute Performance irrelevant für Ablation
- Trade-off: 10× schnellere Iteration, niedrigere absolute Accuracy akzeptiert

**Default-HP statt Tuning:**

- Rationale: Fair Comparison, kein HP-Konfounding zwischen Varianten
- Trade-off: Performance nicht optimal, aber gleiches Bias für alle Varianten

**3-Fold CV statt 5-Fold:**

- Rationale: Schnelleres Prototyping, ausreichend für Trend-Erkennung
- Trade-off: Phase 1 wird 5-Fold verwenden

**Spatial Block CV:**

- Rationale: Vermeidet Spatial Leakage, realistische Generalisierungsschätzung
- Kritisch für Transfer-Bewertung

### 2.6 Validierung

**Experiment-Validität:**

- ✅ Alle 5 Varianten unter identischen Bedingungen (Subsample, HP, CV)
- ✅ Standardabweichungen über Folds gering (0.0045-0.0077) → stabile Trends
- ✅ Feature Importance konsistent über alle 3 Folds

**Limitationen:**

- Absolute Performance niedrig (32% Macro-F1) → erwartet durch Subsample + Default-HP
- Keine empirische Transfer-Validierung (Train Berlin → Test Hamburg)
- Nur Random Forest getestet (XGBoost/DL könnte CHM anders nutzen)

---

## 3. Experiment 0.2: Dataset Selection

### 3.1 Forschungsfrage

Welches Trainings-Dataset optimiert das Trade-off zwischen Quantität (mehr Samples) und Qualität (spektrale Reinheit)?

**Hypothese:** No-Edge Dataset performt besser (mehr Samples → bessere Generalisierung).

**Null-Hypothese:** 20m-Edge Dataset performt besser (spektrale Reinheit > Genera-Diversität).

### 3.2 Methodik

**Experimentelles Design:**

- Typ: Controlled Comparison (3 Varianten)
- Datensatz: Berlin Training (Subsample 50k pro Variante)
- Modell: Random Forest (Default-HP), 3-Fold Spatial Block CV

**Varianten:**

| ID           | Name               | Genera | Beschreibung                               |
| ------------ | ------------------ | ------ | ------------------------------------------ |
| A            | No-Edge (Baseline) | 13     | Alle Genera, keine Edge-Filter             |
| A_controlled | No-Edge (Fair)     | 6      | Nur gemeinsame Genera für fairen Vergleich |
| B            | 20m-Edge           | 6      | Edge-Filter >20m von Gebäuden/Straßen      |

**Entscheidungskriterium:**

- Fair Comparison: A_controlled vs. B (gleiche Genera)
- Delta >5% → 20m-Edge bevorzugen
- Delta <2% → No-Edge bevorzugen (mehr Genera-Diversität)

### 3.3 Ergebnisse

**Performance-Vergleich:**

| Variant             | Genera | Val Macro-F1 | Std        | Train-Val Gap     |
| ------------------- | ------ | ------------ | ---------- | ----------------- |
| A (Baseline)        | 13     | 0.3315       | 0.0083     | 0.652 (65.2%)     |
| A_controlled (Fair) | 6      | 0.4545       | -          | 0.535 (53.5%)     |
| **B (20m-Edge)**    | **6**  | **0.5261**   | **0.0032** | **0.474 (47.4%)** |

**Fair Delta (A_controlled vs. B):** -7.2% (20m-Edge besser)

**Genus-Level F1 (6 gemeinsame Genera):**

- TILIA: A_ctrl 0.753 → B 0.875 (+12.2%)
- ACER: A_ctrl 0.561 → B 0.709 (+14.8%)
- QUERCUS: A_ctrl 0.511 → B 0.666 (+15.5%)
- BETULA: A_ctrl 0.249 → B 0.421 (+17.2%)
- SORBUS: A_ctrl 0.249 → B 0.249 (±0%)
- FRAXINUS: A_ctrl 0.151 → B 0.237 (+8.6%)

### 3.4 Entscheidung & Begründung

**Gewählte Variante: B (20m-Edge)**

**Rationale:**

1. **Signifikanter Gain:** 7.2% liegt über 5%-Threshold → substantiell
2. **Weniger Overfitting:** Gap 47.4% vs. 53.5% → bessere Generalisierung
3. **Spectral Purity kritisch:** 5 von 6 Genera profitieren vom Edge-Filter
4. **Faire Vergleich bestanden:** A_controlled (gleiche Genera) zeigt echten Edge-Effekt

**Wichtige Erkenntnis:**

- Ursprünglicher Delta (A vs. B): 19.5% war konfundiert durch Genera-Selektion
- Fairer Delta (A_controlled vs. B): 7.2% ist reiner Edge-Filter-Effekt
- 12.3% des ursprünglichen Deltas kam durch schwierigere Genera in No-Edge

**Output:**

- decision_dataset.md: Entscheidung "20m-Edge" mit fairer Begründung
- exp_0.2_results.json: Metriken aller 3 Varianten

### 3.5 Designentscheidungen

**A_controlled Variante (Fair Comparison):**

- Rationale: Isoliert Edge-Filter-Effekt von Genera-Schwierigkeit
- Kritisch: Ohne A_controlled wäre Interpretation konfundiert
- Zeigt: 12.3% des Gains kam durch Genera-Selektion, 7.2% durch Edge-Filter

**Subsample (50k pro Variante):**

- Rationale: Konsistent mit Experiment 0.1, schnellere Iteration
- Trade-off: Absolute Performance niedriger, aber relative Vergleiche valide

### 3.6 Validierung

**Experiment-Validität:**

- ✅ Fair Comparison durch A_controlled (gleiche Genera)
- ✅ Edge-Filter-Effekt isoliert: 7.2% (nicht konfundiert)
- ✅ Overfitting-Reduktion: 6.1% Gap-Verbesserung

**Limitationen:**

- Nur 6 Genera getestet (aber repräsentativ: 80% der Bäume)
- Keine empirische Transfer-Validierung (Hamburg/Rostock)

---

## 4. Experiment 0.3: Feature Reduction

### 4.1 Forschungsfrage

Wie viele Features sind optimal für das Trade-off zwischen Performance, Robustheit und Effizienz?

**Hypothese:** Feature Reduction verbessert Generalisierung (weniger Overfitting) bei <2% Performance-Verlust.

**Null-Hypothese:** Alle Features (144) performen am besten - Reduktion kostet >2% Performance.

### 4.2 Methodik

**Experimentelles Design:**

- Typ: Top-k Feature Selection (5 Varianten)
- Datensatz: Berlin 20m-Edge (Subsample 50k, 6 Genera)
- Modell: Random Forest (Default-HP), 3-Fold Spatial Block CV
- Features: 144 spektrale (aus Experiment 0.1)

**Ablauf:**

1. **Phase 1:** Baseline-Training mit allen 144 Features, Feature Importance Ranking
2. **Phase 2:** Training mit Top-20, 50, 80, 100, 144 Features
3. **Phase 3:** Pareto-Analyse, Entscheidung nach Retention-Kriterium

**Varianten:**

| ID  | Name           | Features | Beschreibung                      |
| --- | -------------- | -------- | --------------------------------- |
| A   | Top-20         | 20       | Core Features (~14% von Baseline) |
| B   | Top-50         | 50       | Reduced Set (~35% von Baseline)   |
| C   | Top-80         | 80       | Balanced Set (~56% von Baseline)  |
| D   | Top-100        | 100      | Extended Set (~69% von Baseline)  |
| E   | All (Baseline) | 144      | Full Feature Set (100%)           |

**Entscheidungskriterium:**

- Retention ≥98% → kleinste Set bevorzugen (Pareto-Effizienz)
- Retention <98% → Knee Point der Performance-Kurve

### 4.3 Ergebnisse

**Performance-Vergleich:**

| Variant          | Features | Val Macro-F1 | Std    | Train-Val Gap | Retention  |
| ---------------- | -------- | ------------ | ------ | ------------- | ---------- |
| A (Top-20)       | 20       | 0.4984       | 0.0064 | 0.502 (50.2%) | 94.5%      |
| **B (Top-50)**   | **50**   | **0.5405**   | 0.0125 | 0.460 (45.9%) | **102.5%** |
| C (Top-80)       | 80       | 0.5428       | 0.0148 | 0.457 (45.7%) | 102.9%     |
| D (Top-100)      | 100      | 0.5421       | 0.0137 | 0.458 (45.8%) | 102.8%     |
| E (All/Baseline) | 144      | 0.5275       | 0.0151 | 0.472 (47.3%) | 100.0%     |

**Delta vs. Baseline:**

- Top-20: -2.9% (zu viel Verlust)
- Top-50: +2.5% (besser als Baseline!)
- Top-80: +2.9% (marginal besser)
- Top-100: +2.8% (marginal besser)

**Feature Importance Top-10:**

1. B8A_09 (1.71%), B08_09 (1.59%), EVI_03 (1.42%)
2. B06_09 (1.41%), IRECI_03 (1.37%), NDVI_03 (1.32%)
3. NDWI_06 (1.20%), VARI_03 (1.16%), VARI_10 (1.15%)

**Cumulative Importance:**

- Top-20: 24.3%, Top-50: 49.5%, Top-80: 68.8%, Top-100: 79.8%

### 4.4 Entscheidung & Begründung

**Gewählte Variante: B (Top-50)**

**Rationale:**

1. **Pareto-Effizienz:** 102.5% Retention mit 65% weniger Features
2. **Erfüllt Kriterium:** ≥98% Retention → kleinste Set bevorzugen
3. **Marginaler Unterschied:** Top-80/100 nur +0.2% besser bei +30-50 Features
4. **Overfitting-Reduktion:** Gap von 47.3% → 45.9% (1.4% Verbesserung)
5. **Noise-Minimierung:** Top-50 = 49.5% Cumulative Importance → Core Signal
6. **Occam's Razor:** Einfacheres Model bei gleicher/besserer Performance

**Wichtige Erkenntnis:**

- Features 51-144 enthalten mehr **Noise als Signal**
- Feature Reduction **verbessert** Performance (Curse of Dimensionality)
- Long Tail (50.5% Importance) degradiert Generalisierung

**Output:**

- decision_features.md: Entscheidung "Top-50" mit Pareto-Analyse
- selected_features.json: 50 Features für Phase 1
- exp_0.3_results.json: Metriken aller 5 Varianten
- exp_0.3_feature_ranking.json: Alle 144 Features ranked

### 4.5 Designentscheidungen

**Feature Ranking fresh (nicht reused von 0.1):**

- Rationale: Experiment 0.1 hatte andere Genera (13 vs. 6) → Importance könnte abweichen
- Top-50 auf 20m-Edge Dataset gerankt (identisch mit Phase 1 Setup)

**Top-50 statt Top-80 (beste Performance):**

- Rationale: Pareto-Kriterium priorisiert Effizienz bei negligiblem Trade-off
- +0.2% Gain für +30 Features = 0.0077% pro Feature → nicht gerechtfertigt
- Kleineres Set robuster für Hamburg Transfer

**Temporale Struktur bewahrt:**

- März-Features dominieren Top-20 (8/20) → Frühjahr diskriminativ
- Juli-Features in Bottom-10 (9/10) → Hochsommer wenig Information
- Phänologisches Muster emergiert aus Feature Importance (nicht forced)

### 4.6 Validierung

**Experiment-Validität:**

- ✅ Fair Comparison: Identische CV-Folds für alle Varianten
- ✅ Feature Importance stabil: Top-20 konsistent über alle 3 Folds
- ✅ Pareto-Kurve zeigt klaren Knee Point bei Top-50

**Limitationen:**

- Feature-Auswahl optimiert für Tree-based Models (RF)
- NN-basierte Models könnten andere Features bevorzugen (Raw Bands > VIs)
- Out-of-Scope: Algorithm-spezifische Feature Selection

**⚠️ KRITISCHES PROBLEM: Extremes Overfitting**

```
Baseline (144 Features):
  Train Macro-F1: 1.0000 (100% perfekt)
  Val Macro-F1:   0.5275 (53% real)
  Gap:            47.3% ← METHODISCH PROBLEMATISCH

Top-50 Reduction:
  Gap: 45.9% (nur 1.4% Verbesserung)
```

**Was das bedeutet:**

- Model **memoriert Training Data** komplett (Train F1 = 100%)
- Feature Reduction löst Overfitting **NICHT** → Problem liegt bei Model Complexity
- **Ursachen:** max_depth=None, Sample Size (50k), Spatial Block Size (500m)

**Action für Phase 1:**

- ⚠️ **HIGH PRIORITY:** RF Hyperparameter Tuning (max_depth, min_samples_leaf)
- ⚠️ **ESSENTIELL:** Hamburg Transfer Test zur Validierung echter Generalisierung
- Phase 0 Entscheidungen bleiben valide (strukturelle Unterschiede robust)

---

## 5. Phase 0 Abschluss

**Fixierte Konfiguration für Phase 1-3:**

| Komponente    | Entscheidung              | Begründung                            |
| ------------- | ------------------------- | ------------------------------------- |
| CHM-Strategie | No CHM                    | Marginaler Gain (1.4%), Transfer-Risk |
| Dataset       | 20m-Edge (6 Genera)       | 7.2% Gain, bessere Spectral Purity    |
| Feature-Set   | Top-50 (aus 144 spektral) | 102.5% Retention, 65% Effizienz       |
| Feature Count | 50                        | Pareto-optimal                        |

**Phase 0 Status:** ✅ Abgeschlossen (3/3 Experimente)

**Nächste Schritte (Phase 1):**

1. **Overfitting adressieren** (HIGH PRIORITY):
   - RF: max_depth=10-20, min_samples_leaf=5-20
   - XGBoost: L1/L2 Regularization
   - Spatial Block Size: 500m → 1000m

2. **Algorithmus-Vergleich:**
   - RF (tuned), XGBoost, TabNet/1D-CNN
   - Mit Top-50 Features (aus selected_features.json)

3. **Generalisierung validieren** (ESSENTIELL):
   - Hamburg Transfer Test
   - Expected: Tuned Model Gap <30% (statt 47%)

**Deliverables:**

- ✅ decision_chm.md, decision_dataset.md, decision_features.md
- ✅ exp_0.1_results.json, exp_0.2_results.json, exp_0.3_results.json
- ✅ selected_features.json (50 Features für Phase 1)
- ✅ exp_0.3_feature_ranking.json (alle 144 Features ranked)

---

## 5. Referenzen

**Experimentelles Design:**

- Montgomery (2017) - Design and Analysis of Experiments

**Spatial CV:**

- Roberts et al. (2017) - Cross-validation strategies for spatial data

**Transfer Learning:**

- Ben-David et al. (2010) - A theory of learning from different domains

---

**Status:** ✅ Abgeschlossen (3/3 Experimente)  
**Fortschritt:** ██████████ 100%
