# Methodische Verbesserungen - Experiments

**Status:** Action Required
**Letzte Aktualisierung:** 21. Januar 2026

---

## 🟡 WICHTIG - Dokumentation

### 1. Experiment 0.1 Schwellenwerte nicht begründet

**Problem:**
"CHM Feature Importance >25%" nicht rigoros begründet.

**Zu dokumentieren in `00_Experiment_Design.md`:**

- Rationale: 25% = deutlich über Chance (1/148 Features = 0.7%)
- Decision Rule: "WENN CHM >25% UND <3% Performance-Gewinn DANN weglassen"
- Limitation: Threshold basiert auf Heuristik

**Priorität:** 🟡 MITTEL
**Aufwand:** 30 Minuten

---

## 🟠 Optionale Verbesserungen

### 2. Phase 0: Overfitting Deep-Dive

**Was fehlt:**
Systematische Analyse der Overfitting-Ursachen in Phase 0 (47% Train-Val Gap).

**Hypothesen:**

1. max_depth=None: Bäume wachsen bis perfekte Trennung
2. Sample Size: 50k evtl. zu klein für 6 Klassen × 144 Features
3. Spatial Block Size: 500m zu klein → Spatial Autocorrelation nicht kontrolliert
4. n_estimators=100: Zu wenige Bäume für stabile Predictions

**Wann:** Falls Phase 1 Tuning nicht ausreicht

**Priorität:** HIGH (falls Phase 1 Gap >35%)
**Aufwand:** 3-4 Stunden

---

### 3. Phase 0: Transfer Sanity Check (Hamburg)

**Was fehlt:**
Empirische Validierung, dass height_m bei Cross-City Transfer schlechter performt.

**Methode:**

1. Train auf Berlin mit Variant E (height_m raw)
2. Test auf Hamburg (1000 stratifizierte Samples)
3. Vergleiche Variant A (No CHM) vs. Variant E (height_m)

**Wann:** Falls Reviewer fragen: "Warum glauben Sie, height_m ist transfer-problematisch?"

**Priorität:** MEDIUM
**Aufwand:** 1-2 Stunden

---

### 4. Feature Reduction Alternatives

**Was fehlt:**
Alternative Feature Selection Strategien (nicht nur Importance-based).

**Methoden:**

1. Temporal Aggregation: Mean/Std/Max pro Band über 8 Monate
2. Group-wise Selection: Pro Monat Top-3 Features erzwingen
3. Correlation-based Pruning: Remove Features mit r>0.95

**Wann:** Falls NN-basierte Models mit Top-50 schlecht performen

**Priorität:** LOW
**Aufwand:** 1-2 Tage pro Methode

---

### 5. Algorithm-spezifische Feature Selection

**Was fehlt:**
Top-50 ist für Tree-based Models optimiert. NN könnte andere Features brauchen.

**Wann:** Falls NN in Phase 1 deutlich schlechter als RF

**Priorität:** MEDIUM (nur wenn NN >5% schlechter)
**Aufwand:** 2-3 Tage

---

### 6. Direkte Transfer-basierte Algorithmus-Selektion

**Was fehlt:**
Algorithmus-Ranking basierend auf Cross-City Transfer Performance statt Single-City.

**Aktuelle Limitation:**
Phase 1 wählt Algorithmen basierend auf Berlin Single-City Performance, testet diese dann erst in Phase 2 auf Transfer.

**Wann:** Falls ein Phase 1 Algorithmus in Phase 2 schlecht transferiert

**Priorität:** MEDIUM-HIGH (methodisch besser, aber out-of-scope für Baseline)
**Aufwand:** +2-3 Stunden für Quick Transfer Baselines

---

### 7. Hyperparameter-Tuning auf Full Data

**Was fehlt:**
Phase 1 nutzt 50k Subsample für Coarse Grid Search. Finale Modelle sollten auf Full Data tuned werden.

**Wann:** Falls Phase 2 Transfer-Performance enttäuschend

**Priorität:** MEDIUM
**Aufwand:** 4-8 Stunden

---

### 8. Code-Cleanup: YAML-Erstellung entfernen

**Was:**
Entferne CONFIG_PARTIAL_*.yaml Erstellung aus allen Phase 0 Notebooks.

**Begründung:** Colab-Workflow benötigt keine YAML-Configs, decision_*.md + exp_*.json sind ausreichend.

**Priorität:** LOW
**Aufwand:** 10-15 Minuten

---

**Version:** 1.0 | **Aktualisiert:** 21. Januar 2026
