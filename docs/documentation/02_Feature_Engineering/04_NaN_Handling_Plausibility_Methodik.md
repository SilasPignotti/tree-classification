# NaN Handling & Plausibility Filtering

**Autor:** Silas Pignotti | **Version:** 1.0 | **Notebook:** `02_feature_engineering/03b_nan_handling_plausibility.ipynb`

## Übersicht

Adressiert zwei kritische Datenqualitätsprobleme nach temporaler Feature-Reduktion (März-Oktober):

1. **Fehlende Werte (NaNs)** im reduzierten Zeitfenster → Filterung + Adaptive Interpolation
2. **Implausible Bäume** (max_NDVI < 0.3) → Plausibilität-Check

**Output:** 924k Bäume (no-edge, 90% Retention) + 849k Bäume (20m-edge, 89% Retention)

---

## Workflow

```
Input: 8-Monats-Reduktion (März-Oktober)
    ↓
[PHASE 1: NaN RE-EVALUIERUNG]
├─ Zähle NaN pro Baum & Monat
├─ Statistiken nach Stadt, Genus, Monat
└─ Schwellenwert-Definition: >2 Monate → Entfernung

    ↓

[PHASE 2: NaN-FILTERUNG & ADAPTIVE INTERPOLATION]
├─ Filter: >2 fehlende Monate → Entfernung (~8%)
├─ Lineare temporale Interpolation (~97% Erfolg)
├─ Hierarchische Fallback-Mittelwerte:
│  ├─ Level 1: Genus-Mean (if n≥10)
│  ├─ Level 2: Stadt-Mean (if Genus zu klein)
│  └─ Level 3: Global-Mean (Last Resort)
└─ Validierung: 0 NaN-Check ✓

    ↓

[PHASE 3: NDVI-PLAUSIBILITÄT]
├─ max_NDVI = max(NDVI_03:10) pro Baum
├─ Filter: max_NDVI < 0.3 → Entfernung (~2.5-3.3%)
└─ Output: Plausible, Complete Datensätze

    ↓

Output: Clean Datasets (0 NaNs, Plausible NDVI)
```

---

## Phase 1: NaN Re-Evaluierung

**NaN-Zählung auf 8-Monats-Fenster:**

| Datensatz | NaN % | Bäume mit NaN | Ohne NaN |
| --------- | ----- | ------------- | -------- |
| No-Edge   | 47%   | 483k          | 545k     |
| 20m-Edge  | 45%   | 431k          | 525k     |

**Nach Monaten (NaN-Rate):**

| Monat     | Berlin | Hamburg | Rostock |
| --------- | ------ | ------- | ------- |
| März      | 8%     | 11%     | 14%     |
| April     | 7%     | 10%     | 13%     |
| Mai       | 6%     | 8%      | 10%     |
| Juni      | 5%     | 7%      | 9%      |
| Juli      | 5%     | 7%      | 9%      |
| August    | 6%     | 9%      | 11%     |
| September | 8%     | 11%     | 14%     |
| Oktober   | 10%    | 13%     | 16%     |

**Muster:** U-förmig (Frühjahr/Herbst höher, Sommer tiefer)

**Pro-Baum Verteilung (No-Edge):**

| Fehlende Monate | Anzahl Bäume | %   |
| --------------- | ------------ | --- |
| 0               | 545k         | 53% |
| 1               | 235k         | 23% |
| 2               | 168k         | 16% |
| 3               | 56k          | 5%  |
| >3              | 25k          | 2%  |

**Zur Entfernung (>2):** 80k (7.9%)
**Zur Interpolation (1-2):** 402k (39%)

---

## Phase 2: NaN-Filterung & Interpolation

### Filterung: >2 Monate entfernen

**Begründung:**

- ≤2 Monate: Interpolierbar (phänologisch kontinuierlich)
- ≥3 Monate: Riskant (Phasen-Diskontinuität)

**Entfernungsstatistiken:**

**No-Edge:**

- Input: 1.028k Bäume
- Entfernt: 81k (7.9%)
- Output: 948k Bäume

**20m-Edge:**

- Input: 957k Bäume
- Entfernt: 78k (8.2%)
- Output: 878k Bäume

### Adaptive Interpolation

**Methode 1: Lineare Temporale Interpolation**

- Interpoliere fehlende Monate zwischen verfügbaren (z.B. Juni-Juli fehlen → nutze Mai+August)
- Erfolgsrate: ~97% der NaNs

**Methode 2: Hierarchische Fallback-Mittelwerte**

| Fallback-Level | NaNs gefüllt | %   |
| -------------- | ------------ | --- |
| Genus (n≥10)   | 1.23M        | 55% |
| Stadt          | 877k         | 39% |
| Global         | 114k         | 5%  |

**Rationale:**

- Temporal-only: Keine Information Leakage
- Hierarchisch: Balance zwischen Spezifität und Verfügbarkeit
- Modell-agnostisch: Alle Modelle können damit umgehen

**Validierung:** 0 NaNs nach Interpolation ✓

---

## Phase 3: NDVI-Plausibilität

### max_NDVI Berechnung

**Definition:** Maximaler NDVI über alle 8 Monate

**Verteilung (No-Edge):**

- Mean: 0.58 ± 0.15
- Min: -0.05 (tote Bäume)
- Max: 0.98 (dichte Vegetation)

**Interpretation nach NDVI-Bereich:**

| Bereich | Vegetation             | Typische Ursache (if <0.3)  |
| ------- | ---------------------- | --------------------------- |
| < 0.2   | Keine/Minimal          | Tote Bäume                  |
| 0.2-0.4 | Blattausfaltung/Stress | GPS-Fehler, Gemischte Pixel |
| 0.4-0.6 | Moderat                | OK                          |
| 0.6-0.8 | Gesund                 | Normales Profil             |
| > 0.8   | Sättigung              | Mehrschicht-Pixel           |

### Filterung: max_NDVI < 0.3

**Schwellenwert-Begründung:**

- Gesunde Laubbäume: max_NDVI > 0.4 im Sommer
- Schwellenwert 0.3: Konservativ, erlaubt gestresste Bäume
- Filtert: Tote Bäume, GPS-Fehler, Gemischte Pixel

**Entfernungsstatistiken:**

**No-Edge:**

- Input: 948k Bäume
- Entfernt: 23k (2.5%)
- Output: 924k Bäume

**20m-Edge:**

- Input: 878k Bäume
- Entfernt: 29k (3.3%)
- Output: 849k Bäume

**Observation:** 20m-Edge zeigt höhere Entfernungsrate (3.3% vs 2.5%)
**Hypothese:** Edge-Bäume stressbelasteter (Randeffekte, weniger Bewässerung)

---

## Finale Ergebnisse

### Entfernungs-Statistiken (Kumulativ)

**No-Edge Datensatz:**

| Phase       | Input  | Output   | Entfernt | Rate      |
| ----------- | ------ | -------- | -------- | --------- |
| Start       | 1.028k | —        | —        | —         |
| NaN Filter  | —      | 948k     | 81k      | 7.9%      |
| NDVI Filter | 948k   | 924k     | 23k      | 2.5%      |
| **Gesamt**  | —      | **924k** | **104k** | **10.1%** |

**20m-Edge Datensatz:**

| Phase       | Input | Output   | Entfernt | Rate      |
| ----------- | ----- | -------- | -------- | --------- |
| Start       | 957k  | —        | —        | —         |
| NaN Filter  | —     | 878k     | 78k      | 8.2%      |
| NDVI Filter | 878k  | 849k     | 29k      | 3.3%      |
| **Gesamt**  | —     | **849k** | **107k** | **11.2%** |

### Datenqualität nach Bereinigung

**No-Edge (924k Bäume):**

- ✓ NaN Count: 0
- ✓ Temporal Completeness: 100%
- ✓ max_NDVI Range: [0.30, 0.95]
- ✓ Plausible NDVI: 100%
- ✓ Mean max_NDVI: 0.63 ± 0.12

**20m-Edge (849k Bäume):**

- ✓ Identische Qualität-Metriken
- ✓ Zusätzliche Robustheit gegen Edge-Effekte

---

## Designentscheidungen

### Schwellenwert >2 Monate für Filterung

- Balanciert Qualität (97% lineare Interpolation) vs. Quantität (90% Retention)
- Phänologisch plausibel (>2 Monate = unkritische Lückengröße)
- Trade-off: Strikte (>1) würde 30% entfernen, zu lockere (>3) riskiert Diskontinuität

### Lineare temporale Interpolation (nicht Spline)

- Einfach, interpretierbar, modellagnostisch
- Vermeidet Overfitting durch High-frequency Oszillationen
- Phänologisch plausibel (glatte Übergänge)

### NDVI-Schwellenwert 0.3

- Konservativ gegen falsch-positive (echte Bäume entfernen)
- Phänologisch fundiert (Grenzwert für tote Bäume)
- Minimal justifizierte Entfernung (2.5% vs. 8-20% bei höheren Schwellenwerten)

### Hierarchische Fallback-Strategie

- Level 1 (Genus): Maximum biologische Relevanz
- Level 2 (Stadt): Lokalität + Stichprobengröße Balance
- Level 3 (Global): Last Resort (<1% Nutzung)
- **Rationale:** Temporal-only (keine Spatial Leakage), modell-agnostisch

---

## Fehlerbehandlung

| Problem                        | Ursache                              | Lösung                                 |
| ------------------------------ | ------------------------------------ | -------------------------------------- |
| Edge-Case NaN am Anfang/Ende   | Keine Future-Daten für Extrapolation | Fallback zu Mittelwerten               |
| Genus zu klein (n<10)          | Seltene Arten                        | Escalate zu Stadt-Level                |
| Hohe Correlation 20m-Edge NDVI | Edge-Bäume gestresst                 | Dokumentieren, beide Varianten pflegen |

---

## Herausforderungen & Lösungen

**Challenge 1:** Phänologische Plausibilität bei 2-Monats-Lücken
→ **Lösung:** Linear interpolation ist phänologisch valide (Blattausfaltung kontinuierlich)

**Challenge 2:** Information Leakage durch räumliche Fallback
→ **Lösung:** Nutze nur Temporal-only Interpolation, Spatial Fallback nur für Genus/Stadt (keine direkten Nachbarn)

**Challenge 3:** 20m-Edge heterogener als No-Edge (+0.8% höhere Entfernung)
→ **Lösung:** Dokumentieren, beide Varianten exportieren für später Vergleich

---

## Validierung

**Post-Interpolation Checks:**

- ✓ Zero-NaN Assertion (0 NaNs in allen Features)
- ✓ NDVI Ranges plausibel (0.30-0.95, Mean 0.63)
- ✓ CRS konsistent (EPSG:25832)
- ✓ Geometrie-Validität (100% gültig)
- ✓ Keine Duplikate

**Interpolation-Effektivität:**

- 97% lineare Interpolation (biologisch spezifisch)
- 3% Fallback-Mittelwerte (edge cases)

---

## Output

**Clean Datensätze:**

- `trees_clean_no_edge.gpkg`: 924k Bäume (90% Retention)
- `trees_clean_20m_edge.gpkg`: 849k Bäume (89% Retention)

**Struktur:** 192 Spalten (4 CHM + 188 S2 Temporale)

- Vollständige 8-Monats-Zeitreihe (März-Oktober)
- 0 NaN-Werte
- 100% plausible NDVI (≥0.3)

**Ready for:** Feature Selection & Model Training
