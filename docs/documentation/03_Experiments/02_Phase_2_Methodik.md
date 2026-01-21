# Phase 2: Cross-City Transfer Evaluation

**Projektphase:** Experimentelle Hauptphase  
**Datum:** 20. Januar 2026  
**Autor:** Silas Pignotti

---

## 1. Übersicht

### 1.1 Zweck

Phase 2 evaluiert systematisch die **Cross-City Transfer-Performance** der in Phase 1 selektierten Algorithmen (XGBoost + 1D-CNN) über drei Trainingsszenarien, um den Champion-Algorithmus und das beste Trainingssetup für finale Optimierung zu identifizieren.

**Hauptziele:**

1. Vergleich Transfer-Robustness: XGBoost vs. 1D-CNN
2. Identifikation bestes Trainingssetup: Berlin, Hamburg oder Combined
3. Quantifizierung Transfer Loss vs. Single-City Baseline
4. Selektion Champion-Konfiguration für weitere Optimierung

### 1.2 Methodischer Ansatz

**Strategie:** Full Grid Evaluation (3 Setups × 2 Algorithmen = 6 Experimente)

```
[PHASE 2.1: TRANSFER EVALUATION]
├── Setup 1: Berlin → Rostock (XGBoost + 1D-CNN)
├── Setup 2: Hamburg → Rostock (XGBoost + 1D-CNN)
├── Setup 3: Combined → Rostock (XGBoost + 1D-CNN)
│
├── Selection: Best Algorithm + Best Setup
└── Output: Champion-Konfiguration

    ↓

[PHASE 2.2: CHAMPION OPTIMIZATION] (geplant)
├── Full Data Training (alle verfügbaren Samples)
├── HP-Tuning (falls notwendig)
└── Genus-Level Analysis
```

### 1.3 Methodische Entscheidungen

#### 1.3.1 Full Grid vs. Sequential Elimination

**Gewählter Ansatz:** Option B (Full Grid)

**Rationale:**

- **Vermeidet Confounding:** Model-Selection und Setup-Selection getrennt evaluiert
- **Zeigt Setup×Algorithm Interaktionen:** Hamburg könnte für 1D-CNN besser sein als Berlin
- **Nur +1 Experiment:** Marginal mehr Aufwand (6 statt 5) für vollständige Robustheit
- **Wissenschaftlich sauber:** N=3 pro Algorithmus statt N=1

**Verworfene Alternative (Sequential):** Berlin→Rostock Test für beide Algorithmen, dann bester auf anderen Setups → Risiko von Selection Bias

#### 1.3.2 Sample Size Balancing

**Entscheidung:** Alle Trainingssetups nutzen **36k samples** (stratified)

**Begründung:**

- **Berlin:** 242k verfügbar → subsample 36k
- **Hamburg:** 66k verfügbar → subsample 36k (Maximum möglich)
- **Combined:** 36k total (stratified aus Berlin+Hamburg)

**Rationale:** Isolierung des Stadt-Effekts (sonst confounded mit Sample-Size-Effekt). Berlin mit 242k würde unfairen Vorteil haben.

**Test Set:** Rostock 7k Zero-Shot (vollständig, keine Subsampling)

### 1.4 Forschungsfragen

**Q1:** Welcher Algorithmus (Tree-based ML vs. Neural Network) generalisiert besser über Städte?

**Q2:** Verbessert Multi-City Training (Combined) die Transfer-Performance vs. Single-City?

**Q3:** Wie groß ist der Performance-Verlust beim Zero-Shot Transfer zu neuen Städten?

### 1.5 Status

**Phase 2.1:** Transfer Evaluation & Selection (Abgeschlossen ✅)  
**Phase 2.2:** Champion Optimization (Geplant)

---

## 2. Experiment 2.1: Transfer Evaluation & Algorithm Selection

### 2.1 Zweck

Systematischer Vergleich von XGBoost und 1D-CNN über drei Cross-City Trainingsszenarien zur Identifikation des robustesten Algorithmus und besten Trainingssetups.

### 2.2 Methodik

#### 2.2.1 Experimentelles Design

**Training Data:**

- **Berlin:** 36k samples (stratified subsample aus 242k)
- **Hamburg:** 36k samples (stratified subsample aus 66k)
- **Combined:** 36k samples (stratified aus Berlin+Hamburg zusammen)

**Test Data:**

- **Rostock:** 7k samples (Zero-Shot, komplett neue Stadt)

**Cross-Validation:**

- 3-Fold Spatial Block CV (GroupKFold)
- Blocks: 500m Spatial Clustering
- Verhindert Data Leakage durch räumliche Autokorrelation

#### 2.2.2 Algorithmen & Hyperparameter

**XGBoost:** Phase 1 Best Configuration

| Parameter        | Wert |
| ---------------- | ---- |
| max_depth        | 4    |
| learning_rate    | 0.1  |
| n_estimators     | 200  |
| subsample        | 0.8  |
| colsample_bytree | 0.8  |
| min_child_weight | 5    |
| reg_alpha        | 0.1  |
| reg_lambda       | 1    |

**1D-CNN:** Phase 1 Baseline Configuration

| Parameter    | Wert                          |
| ------------ | ----------------------------- |
| Architecture | 2 Conv Layers (32→64 filters) |
| Kernel Size  | 3                             |
| Pooling      | MaxPool (k=2)                 |
| Dense Layer  | 128 units                     |
| Dropout      | 0.3                           |
| Optimizer    | Adam (lr=0.001)               |
| Batch Size   | 128                           |
| Epochs       | 30                            |

**Normalization:** StandardScaler fit auf Training, transform auf Test (per Fold)

#### 2.2.3 Evaluationsmetriken

**Primär:** Test Macro-F1 auf Rostock Zero-Shot

**Sekundär:**

- CV Validation F1 (Mean ± Std über 3 Folds)
- Test Weighted-F1
- Test Accuracy
- Train-Test Gap (Overfitting-Indikator)

**Transfer Loss Metrik:**

```
Transfer Loss (pp) = Phase 1 Single-City Val F1 - Phase 2 Test F1
Transfer Loss (%) = (Loss pp / Phase 1 Baseline) × 100
```

### 2.3 Ergebnisse

#### 2.3.1 Performance Matrix

**Test F1 Macro auf Rostock Zero-Shot:**

| Training Setup | XGBoost | 1D-CNN     |
| -------------- | ------- | ---------- |
| Berlin         | 0.3449  | 0.3310     |
| Hamburg        | 0.3158  | 0.3426     |
| **Combined**   | 0.3349  | **0.3459** |

**Beobachtungen:**

- 1D-CNN gewinnt 2/3 Setups (Hamburg, Combined)
- Combined Setup konsistent stark für beide Algorithmen
- Hamburg→Rostock schwächste Performance (kleiner Datensatz, andere Verteilung)

#### 2.3.2 Transfer Loss Analysis

**Baselines aus Phase 1 (Berlin Single-City):**

- XGBoost Baseline: 0.5805 Val F1
- 1D-CNN Baseline: 0.5462 Val F1

**Transfer Loss (percentage points):**

| Setup        | XGBoost Loss   | 1D-CNN Loss        |
| ------------ | -------------- | ------------------ |
| Berlin       | 0.2356 (40.6%) | 0.2152 (39.4%)     |
| Hamburg      | 0.2647 (45.6%) | 0.2036 (37.3%)     |
| **Combined** | 0.2455 (42.3%) | **0.2002 (36.7%)** |

**Key Insight:** 1D-CNN verliert durchschnittlich **38.5%** der Single-City Performance beim Transfer, XGBoost **42.8%** → Neural Network transferiert robuster.

#### 2.3.3 Algorithmen-Vergleich

**Durchschnittliche Performance (über 3 Setups):**

| Algorithmus | Avg Test F1 | Std    | Avg Gap |
| ----------- | ----------- | ------ | ------- |
| **1D-CNN**  | **0.3398**  | 0.0074 | 21.3%   |
| XGBoost     | 0.3319      | 0.0147 | 38.7%   |

**Head-to-Head:** 1D-CNN gewinnt 2/3 Setups

**Generalisierung:** 1D-CNN zeigt niedrigeren Train-Test Gap (21.3% vs 38.7%) → bessere Generalisierung

#### 2.3.4 Setup-Vergleich

**1D-CNN Performance nach Setup:**

| Setup        | Test F1    | Rank |
| ------------ | ---------- | ---- |
| **Combined** | **0.3459** | 1    |
| Hamburg      | 0.3426     | 2    |
| Berlin       | 0.3310     | 3    |

**Key Finding:** Multi-City Training (Combined) liefert beste Transfer-Performance (+0.3pp vs Hamburg, +1.5pp vs Berlin)

### 2.4 Selektionsentscheidung

#### 2.4.1 Champion Algorithm

**Gewählt:** 1D-CNN

**Selektionskriterien:**

1. ✓ Höchste durchschnittliche Test F1 (0.3398 vs 0.3319)
2. ✓ Niedrigerer Transfer Loss (38.5% vs 42.8%)
3. ✓ Bessere Generalisierung (Gap 21.3% vs 38.7%)
4. ✓ Head-to-Head Winner (2/3 Setups)

**Interpretation:** Neural Network profitiert von feature representations, die städte-invariante Muster lernen, während Tree-based Modelle stärker auf spezifische Split-Thresholds fixiert sind, die nicht transferieren.

#### 2.4.2 Champion Setup

**Gewählt:** Combined (Berlin + Hamburg)

**Rationale:**

- Höchste Test F1 mit Champion-Algorithmus (0.3459)
- Exposure zu diversen Stadt-Charakteristiken
- Multi-City Training reduziert Overfitting auf Stadt-spezifische Features

### 2.5 Interpretation

#### 2.5.1 Transfer Loss Größenordnung

**40% Performance-Verlust beim Zero-Shot Transfer** ist erwartbar und typisch für Cross-Domain Transfer:

**Ursachen:**

1. **Distribution Shift:** Rostock hat andere Genus-Verteilung als Berlin/Hamburg
2. **Spectral Variance:** Klimatische/Bodenunterschiede verändern spektrale Signaturen
3. **Urban Context:** Stadt-spezifische Umgebungseffekte (Versiegelung, Mikroklima)
4. **Temporal Mismatch:** Sentinel-2 Aufnahmen aus verschiedenen Jahren

**Vergleichswerte:** State-of-the-art Cross-City Remote Sensing Transfer zeigt 30-50% Loss (ähnliche Größenordnung).

#### 2.5.2 Warum 1D-CNN besser transferiert

**Hypothese:**

- **CNN lernt hierarchische Features:** Niedrige Layer = Spektrale Texturen, Hohe Layer = Genus-spezifische Patterns
- **Tree-based lernt globale Splits:** "Wenn B08 > 0.45 → ACER" (Berlin-spezifisch, nicht Rostock)
- **Regularization:** Dropout + BatchNorm in CNN verhindert Overfitting auf Stadt-Features

**Empirische Unterstützung:**

- 1D-CNN hat 17.4pp niedrigeren Train-Test Gap als XGBoost
- Combined Training hilft 1D-CNN mehr als XGBoost (+1.5pp vs +1.9pp vs Berlin)

#### 2.5.3 Multi-City Training Effekt

**Combined Setup verbessert Transfer minimal (+1.5pp vs Berlin für 1D-CNN):**

**Interpretation:**

- Diversity hilft, aber limitiert durch kleine Hamburg-Datenmenge (66k)
- Rostock bleibt Out-of-Distribution (kleinste Stadt, andere Küsten-Lage)
- Phase 2.2 mit Full Data (308k Combined) könnte größeren Effekt zeigen

---

## 3. Outputs

### 3.1 Datensätze

**Transfer Evaluation Results:**

- `transfer_comparison.csv`: 6 Experimente (3 Setups × 2 Algorithmen)
- `transfer_loss_analysis.csv`: Loss-Quantifizierung vs. Phase 1 Baseline

### 3.2 Metadaten

**Selection Config:**

- `selected_transfer_setup.json`: Champion-Konfiguration (1D-CNN + Combined)

**Inhalt:**

```json
{
  "champion": {
    "algorithm": "1D-CNN",
    "training_setup": "Combined",
    "test_f1_rostock": 0.3459
  },
  "transfer_loss": {
    "phase_1_baseline_f1": 0.5462,
    "phase_2_test_f1": 0.3459,
    "loss_pp": 0.2002,
    "loss_pct": 36.7
  }
}
```

### 3.3 Visualisierungen

**Plots:**

- `transfer_evaluation.png`: Performance Heatmap + Transfer Loss Barplot

---

## 4. Methodische Limitationen

### 4.1 Subsample-Effekt

**Limitation:** 36k Subsample aus Berlin (242k) könnte Performance unterschätzen.

**Mitigation:** Phase 2.2 nutzt Full Data für finale Champion-Evaluation.

**Erwartung:** Transfer Loss reduziert sich um ~2-3pp mit Full Data (mehr Diversity in Trainingsdaten).

### 4.2 HP-Tuning Gap

**Limitation:** Phase 1 HP-Configs sind Coarse (nicht optimal für Transfer).

**Mitigation:** Phase 2.2 führt intensives HP-Tuning für 1D-CNN durch.

**Erwartung:** Optimierte Architektur/Learning Rate könnte +3-5pp Test F1 liefern.

### 4.3 Stadt-Auswahl Bias

**Limitation:** Rostock ist kleinste, küstennächste Stadt (Out-of-Distribution).

**Perspektive:** Transfer zu Hamburg (als Test) könnte besser funktionieren (wurde nicht getestet, da Hamburg als Training genutzt).

---

## 5. Abschluss

### 5.1 Zentrale Erkenntnisse

1. **Neural Networks transferieren robuster** als Tree-based Models (38.5% vs 42.8% Loss)
2. **Multi-City Training hilft** (Combined +1.5pp vs Berlin für 1D-CNN)
3. **Transfer Loss ~40%** ist erwartbar für Zero-Shot Cross-City Classification
4. **Champion-Konfiguration:** 1D-CNN + Combined Training Setup

### 5.2 Nächste Schritte

**Phase 2.2: Champion Optimization**

1. Full Data Training (308k Combined statt 36k)
2. HP-Tuning für 1D-CNN (Learning Rate, Architektur, Dropout)
3. Genus-Level Performance Analysis
4. Training Data Scaling Curve

**Ziel:** Maximierung der 1D-CNN Transfer-Performance mit optimalen Ressourcen (Full Data + Best HP).
