# Methodische Verbesserungen - Feature Engineering

**Status:** Action Required
**Letzte Aktualisierung:** 21. Januar 2026

---

## 🔴 KRITISCH - Muss vor Experimenten behoben werden

### 1. Data Leakage durch NaN-Imputation

**Problem:**
Hierarchische NaN-Interpolation (Genus-Mean → Stadt-Mean → Global-Mean) verursacht Data Leakage. Means werden über **alle** Daten (inkl. Test-Set) berechnet.

**Betroffene Dateien:**
- Notebook: `03b_nan_handling_plausibility.ipynb`
- Dokumentation: `04_NaN_Handling_Plausibility_Methodik.md`

**Lösung:**
Berechne Means nur auf Training-Set, wende dieselben Means auf Test-Set an.

**Priorität:** 🔴 HÖCHSTE
**Aufwand:** 2-4 Stunden

---

### 2. Jeffries-Matusita Berechnung validieren

**Problem:**
JM-Distanzen zeigen niedrige Werte. Tendenz stimmt, aber Algorithmus sollte gegen Referenz-Implementierung validiert werden.

**Betroffene Dateien:**
- Notebook: `03a_temporal_feature_selection_JM.ipynb`
- Dokumentation: `03_Temporal_Feature_Selection_JM_Methodik.md`

**Lösung:**
1. Validiere JM-Formel gegen Literatur (Bruzzone et al. 1995)
2. Test mit Toy-Dataset (bekannte JM-Werte)
3. Korrigiere falls nötig, re-run

**Priorität:** 🔴 HOCH
**Aufwand:** 4-8 Stunden

---

### 3. crown_ratio Feature entfernen

**Problem:**
`crown_ratio = CHM_mean / height_m` basiert auf CHM_mean, das aufgrund von Nachbarbaum-Kontamination (10m Resampling) als unreliabel identifiziert wurde.

**Betroffene Dateien:**
- Notebook: `03c_chm_relevance_assessment.ipynb`
- Dokumentation: `05_CHM_Relevance_Assessment_Methodik.md`, `06_Correlation_Analysis_Redundancy_Reduction_Methodik.md`

**Entscheidung:**
Nur folgende CHM-Features behalten:
- ✅ `height_m` (aus Kataster)
- ✅ `height_m_norm` (Z-Score normalisiert)
- ✅ `height_m_percentile` (Percentile-Rank)
- ❌ ~~`crown_ratio`~~ (entfernen)

**Priorität:** 🔴 HOCH
**Aufwand:** 2-3 Stunden

---

## 🟡 WICHTIG - Sollte dokumentiert/verbessert werden

### 4. NDVI Schwellenwert 0.3 nicht rigoros begründet

**Problem:**
Schwellenwert max_NDVI < 0.3 erscheint ad-hoc gewählt. Keine Sensitivitätsanalyse.

**Betroffene Datei:** `04_NaN_Handling_Plausibility_Methodik.md`

**Lösung:**
- Sensitivitätsanalyse: Teste 0.25, 0.30, 0.35
- Dokumentiere Trade-off (Retention vs. Plausibilität)

**Priorität:** 🟡 MITTEL
**Aufwand:** 2-3 Stunden

---

### 5. Outlier-Detection Schwellenwerte begründen

**Problem:**
- Z-Score "≥10 Features" erscheint willkürlich
- Mahalanobis α=0.0001 sehr konservativ - keine Begründung

**Betroffene Datei:** `07_Outlier_Detection_Final_Filtering_Methodik.md`

**Lösung:**
- Dokumentiere Z-Score Rationale: "≥10 von 144 = 7%, deutlich über Zufall (0.3%)"
- Dokumentiere Mahalanobis α: "0.0001 für ultra-konservative Filterung"

**Priorität:** 🟡 MITTEL
**Aufwand:** 1 Stunde

---

### 6. Korrelations-Schwellenwert r=0.95 dokumentieren

**Problem:**
Standard-Wert aus Literatur, aber nicht projektspezifisch dokumentiert.

**Betroffene Datei:** `06_Correlation_Analysis_Redundancy_Reduction_Methodik.md`

**Lösung:**
- Füge Literatur-Referenz hinzu: Kuhn & Johnson (2013)
- Erwähne VIF als alternative Methode (nicht implementiert)

**Priorität:** 🟡 NIEDRIG
**Aufwand:** 30 Minuten

---

### 7. Block-Größe 500×500m dokumentieren

**Problem:**
Trade-off diskutiert, aber nicht quantitativ validiert.

**Betroffene Datei:** `08_Spatial_Splits_Stratification_Methodik.md`

**Lösung:**
- Dokumentiere Rationale: ~30-60 Bäume/Block
- Literatur-Referenz: Roberts et al. (2017) - Spatial Cross-Validation

**Priorität:** 🟡 NIEDRIG
**Aufwand:** 30 Minuten

---

## 🟠 PIPELINE-PROBLEME - Strukturelle Issues

### 8. species_latin Metadaten-Spalte geht verloren

**Problem:**
Die Art-Information (`species_latin`) geht irgendwo in der Pipeline verloren und ist in den finalen Datensätzen nicht mehr verfügbar.

**Betroffene Notebooks:** Zu identifizieren (vermutlich 03b-03e)

**Lösung:**
- Identifiziere wo die Spalte verloren geht
- Stelle sicher dass species_latin bis zum finalen Export erhalten bleibt

**Priorität:** 🟡 MITTEL
**Aufwand:** 1-2 Stunden

---

### 9. Deutsche Gattungs- und Artnamen fehlen

**Problem:**
Für die finale Darstellung und Interpretation der Ergebnisse werden deutsche Bezeichnungen benötigt. Aktuell existieren nur lateinische Namen (`genus`, `species_latin`).

**Benötigte Spalten:**
- `genus_german` (deutscher Gattungsname, z.B. "Linde" für Tilia)
- `species_german` (deutscher Artname, z.B. "Winterlinde" für Tilia cordata)

**Lösung:**
- Erstelle Mapping-Tabelle lateinisch → deutsch
- Füge Spalten in Feature Extraction oder späterer Pipeline-Stufe hinzu
- Stelle sicher dass Spalten bis zum finalen Export erhalten bleiben

**Priorität:** 🟡 MITTEL
**Aufwand:** 1-2 Stunden

---

### 10. Berlin-Only Datensatz fehlt

**Problem:**
Die aktuelle Pipeline erstellt nur Cross-City-gefilterte Datensätze (≥500 Bäume pro Gattung in ALLEN Städten). Für Berlin-Only Experimente fehlt ein Datensatz ohne diese Einschränkung.

**Kontext:**
- Aktuell: 20 viable Gattungen (Cross-City Filterung)
- Berlin-Only könnte mehr Gattungen haben (nur Berlin-Minimum erforderlich)

**Lösung:**
In `08_Spatial_Splits` oder separatem Notebook:
- Erstelle zusätzlichen Berlin-Only Datensatz
- Ohne Cross-City Gattungs-Filterung
- Mit eigenem Train/Val Split

**Priorität:** 🟡 MITTEL (falls Berlin-Only Experimente geplant)
**Aufwand:** 2-3 Stunden

---

### 11. Spatial Splits überdenken bei Experiment-Änderungen

**Problem:**
Die aktuelle Split-Strategie ist auf Cross-City Transfer optimiert. Bei Änderungen der Experimentstrategie (z.B. Berlin-Only) muss die Split-Logik angepasst werden.

**Betroffene Datei:** `08_Spatial_Splits_Stratification_Methodik.md`

**Hinweis:**
Dokumentiere verschiedene Split-Varianten für verschiedene Experiment-Szenarien.

**Priorität:** 🟡 NIEDRIG (nur bei Experiment-Änderungen)

---

## 🟢 NICE-TO-HAVE - Falls Zeit nach Experimenten

### 12. Spatial Consistency Check für CHM

**Was:** Berechne Within-Genus Spatial Autocorrelation für CHM-Features um Neighbor-Kontamination zu quantifizieren.

**Wann:** Falls Experiment 0 zeigt CHM bringt <1% Accuracy-Gewinn

**Aufwand:** 1-2 Stunden

---

### 13. Multivariate JM Distance

**Was:** JM über Band-Kombinationen statt univariat pro Band

**Wann:** Falls Baseline overfittet bei <10k Samples/Genus

**Aufwand:** 4-6 Stunden

---

### 14. VIF-Analyse statt Correlation

**Was:** Variance Inflation Factor für multivariate Redundanz

**Wann:** Falls Feature-Importance viele irrelevante Features zeigt

**Aufwand:** 2-3 Stunden

---

### 15. Temporal Consistency Check

**Was:** NaN-Rates pro Stadt & Monat vergleichen

**Wann:** Falls unexplained month-specific performance drops

**Aufwand:** 30 Minuten

---

### 16. Robust Mahalanobis (MCD)

**Was:** Minimum Covariance Determinant für robuste Outlier-Detection

**Wann:** Falls kleine Genera (<5k Samples) problematisch

**Aufwand:** 1 Stunde

---

**Version:** 1.1 | **Aktualisiert:** 21. Januar 2026
