# Methodische Grundlagen & Designentscheidungen

**Datum:** 6. Januar 2026  
**Autor:** Silas Pignotti  
**Zielgruppe:** Wissenschaftler, Methodologen

---

## 1. Theoretische Grundlagen

### 1.1 Spektrale Fernerkundung (Remote Sensing)

#### Sentinel-2 Sensor Spezifikation

```
Sentinel-2 MSI (Multi-Spectral Instrument):

Spatial Resolution:
  - 10m: Bands 2,3,4,8 (Blue, Green, Red, NIR) - Best for tree phenology
  - 20m: Bands 5,6,7,8A,11,12 - Red Edge, SWIR
  - 60m: Bands 1,9,10 - Coastal, Water Vapor, Cirrus

Temporal Resolution:
  - 5 days (at equator, dual constellation)
  - 2-3 days revisit time (Europe)

Radiometric Resolution:
  - 12-bit (raw) → 16-bit L1C (TOA Reflectance)
  - L2A Bottom-of-Atmosphere (BOA Corrected)
```

**Warum Sentinel-2 für Baumklassifizierung?**

- Red Edge Bänder (705nm) → Vegetation Stress erkennen
- 12-Monats-Zeitserien → Phänologie-Muster (Blattfall, Laubaustrieb)
- 10m Auflösung → Einzelbäume möglich (urban)
- Frei verfügbar (EU, Open Data Policy)
- Atmosphären-korrigiert (L2A)

#### Vegetation Indizes (Theoretischer Hintergrund)

**NDVI (Normalized Difference Vegetation Index)**

$$\text{NDVI} = \frac{\text{NIR} - \text{RED}}{\text{NIR} + \text{RED}} = \frac{B8 - B4}{B8 + B4}$$

- **Range:** [-1, 1] (negative = water/concrete, 0 = bare soil, >0.6 = dense vegetation)
- **Für Bäume:** NDVI >0.3 = ausreichend Blattwerk vorhanden
- **Saisonalität:** NDVI sinkt im Winter (Laubfall), steigt im Sommer (Begrünung)

**Red Edge Indizes (NEW in Sentinel-2)**

$$\text{NDre} = \frac{\text{B8A} - \text{B5}}{\text{B8A} + \text{B5}}$$

- Narrow NIR (B8A) vs. Red Edge (B5)
- **Advantage:** Sensitive zu physiologischen Unterschieden in Vegetation
- **Use Case:** Unterscheidung ähnliche Laubbäume (TILIA vs. ACER)

**kNDVI (Kernel NDVI)**

$$\text{kNDVI} = \tanh\left(\frac{\text{NDVI}}{2}\right) \times \text{NDVI}^2$$

- Nicht-linear Normalisierung
- **Better sensitivity:** zu moderaten Vegetation-Levels
- **Advantage:** Weniger saturiert bei hohem NDVI

### 1.2 Canopy Height Model (CHM)

#### Theoretischer Hintergrund

```
CHM = DOM - DGM

where:
  DOM (Digital Surface Model) = highest surface (tree tops, buildings)
  DGM (Digital Terrain Model) = bare ground elevation
  CHM = Canopy Height (Difference)
```

**Physical Interpretation:**

- CHM > 0: Vegetation vorhanden
- CHM in [0-3]m: Strauch/Unterholz
- CHM in [3-30]m: Bäume (urban, bis ~30m)

#### Warum CHM für Baumklassifizierung?

1. **Artspezifische Höhen:**

   - TILIA (Linde): 15-25m (mittel-groß)
   - QUERCUS (Eiche): 15-30m (groß, langlebig)
   - BETULA (Birke): 10-20m (schlank)
   - SORBUS (Eberesche): 8-15m (klein)

2. **Struktur-Features:**

   - CHM_std (Standardabweichung): Misst Krone-Irregularität
   - Schmale TILIA → Low Std
   - Breite QUERCUS → High Std

3. **Robustheit:**
   - CHM ist saisonunabhängig (Höhe ändert sich nicht mit Jahreszeit)
   - Komplementär zu Spektraldaten (die SEHR saisonal sind)

### 1.3 Phänologie & Zeitliche Muster

**Konzept:** Verschiedene Baumarten zeigen charakteristische jahreszeitliche Muster in ihrer Spektralsignatur.

#### Saisonale Dynamik von Laubbäumen

| Phase        | Zeitfenster | Spektrales Signal     | Saisonales Muster                  |
| ------------ | ----------- | --------------------- | ---------------------------------- |
| **Winter**   | Dez-Feb     | Niedrig (kahl)        | NDVI ~0.2-0.3                      |
| **Frühling** | März-Mai    | Knospenaustrieb       | Timing artspezifisch               |
| **Sommer**   | Juni-Aug    | Maximal (vollbelaubt) | Stabiler High NDVI >0.7            |
| **Herbst**   | Sept-Nov    | Verfärbung + Laubfall | Timing + Farbverlauf artspezifisch |

**Beispiel Unterschiede:**

- TILIA (Linde): Früher Blattaustrieb (März), später Laubfall (Oktober)
- ACER (Ahorn): Ähnliches Muster, aber häufig intensivere Herbstfärbung
- BETULA (Birke): Sehr früher Austrieb (Februar/März), feines Blattwerk

**Phänologische Metriken:**

- Start of Season (SOS): Wann beginnt Grünung?
- Peak of Season (POS): Maximale Vegetation (meist Juni-Juli)
- End of Season (EOS): Wann sinkt NDVI wieder?

**Temporale Erfassung im Projekt:**

- 12 monatliche Mediankomposite (Jan-Dez) erfassen diese Muster
- Genug Auflösung für phänologische Unterschiede
- Robust gegen einzelne Wolkenaufnahmen

---

## 2. Stadtauswahl & Untersuchungsdesign

### 2.1 Primärstrategie: Hamburg + Berlin → Rostock

**Trainingsstädte:**

| **Stadt** | **Baumkataster**     | **CHM**             | **Köppen-Geiger**  | **Entfernung zu Rostock** | **Rolle**                                     |
| --------- | -------------------- | ------------------- | ------------------ | ------------------------- | --------------------------------------------- |
| Hamburg   | ✅ Transparenzportal | ✅ LGV Hamburg      | Cfb (maritim)      | ~170 km                   | Primärtraining (maritimes Küstenklima)        |
| Berlin    | ✅ FIS Broker        | ✅ Berlin Open Data | Cfb/Dfb (Übergang) | ~230 km                   | Multi-City-Training (kontinentale Diversität) |

**Teststadt:**

| **Stadt** | **Entfernung zu Zielregion Wismar** | **Köppen-Geiger** | **Daten**                                 | **Begründung**                                                     |
| --------- | ----------------------------------- | ----------------- | ----------------------------------------- | ------------------------------------------------------------------ |
| Rostock   | ~30 km                              | Cfb (maritim)     | ✅ Baumkataster (GeoMV), ✅ CHM (LAiV MV) | Klimatisch identisch zur Zielregion, unabhängig von Trainingsdaten |

**Rationale:**

Die Kombination Hamburg (maritimes Küstenklima) + Berlin (Übergangsklima) ermöglicht die Erfassung sowohl küstenspezifischer als auch kontinentaler phänologischer Muster. Rostock dient als Teststadt, da es klimatisch nahezu identisch zur operativen Zielregion Wismar ist (~30 km, beide Ostseeküste, Köppen-Geiger Cfb), aber unabhängig von den Trainingsdaten bleibt. Dies ermöglicht eine realistische Evaluierung der Modellgeneralisierung auf neue geografische Regionen innerhalb derselben Klimazone.

**Datenverfügbarkeit:**

Alle drei Städte verfügen über hochwertige, öffentlich verfügbare Baumkataster und digitale Höhenmodelle. Hamburg und Berlin gehören zu Deutschlands größten städtischen Baumbeständen (>100.000 Bäume), während Rostock eine ausreichende Stichprobe für zuverlässige Validierung bietet.

### 2.2 Überlegung: Regionale Fallback-Optionen

Während die Primärstrategie (Hamburg + Berlin) sich in der praktischen Implementierung als suffizient erwiesen hat, wurden als Fallback-Optionen regional nähere Städte (Lübeck ~80 km, Schwerin ~85 km) konzeptionell erwogen. Dies würde nur bei signifikantem Transferierungsverlust (OA < 70%) aktiviert werden. Die Fallback-Optionen sind jedoch bis dato nicht notwendig gewesen.

---

## 3. Machine Learning Paradigmen

### 3.1 Multi-Class Classification

**Problem Formulierung:**

```
Given:
  - X: Feature Matrix (28,866 trees × 184 features)
  - y: Labels (7 genera)

Find: f(X) → y such that:
  - P(f(x_i) = y_i) is maximized
  - Model generalizes to unseen data (Rostock)
```

**Klassen-Balancing:**

- Ohne Balancing: TILIA 15-24% (dominant) vs. PRUNUS 5-8% (minimal)
- Mit Balancing: Alle 7 Klassen gleichgewichtet (~14% each)
- **Why:** Balanced classes → Unbiased loss function, Equal error penalty

### 3.2 Transfer Learning

**Motivation:**

Urban forests in different cities have similar structure:

- Berlin (urban, large): Similar tree distribution to Hamburg
- Rostock (coastal, small): Different but partly overlap-able

**Setup:**

```
Source Domain (Hamburg + Berlin):
  - 16,670 training samples
  - Model learns urban tree patterns

Target Domain (Rostock):
  - 6,675 zero-shot test samples
  - Evaluate generalization
  - 1,403 fine-tune samples for adaptation
```

### 3.3 Experimentelles Rahmenwerk

**Überblick der vier Kernexperimente:**

#### Experiment 0: Baseline & Methodenvergleich

**Ziel:** Etabliere das beste Klassifikationsverfahren (Random Forest vs. XGBoost)

| Aspekt           | Details                                         |
| ---------------- | ----------------------------------------------- |
| **Daten**        | Berlin: 80% Training, 20% Validation (Hold-Out) |
| **Modelle**      | Random Forest, XGBoost                          |
| **Metriken**     | Overall Accuracy, F1-Score (makro)              |
| **Entscheidung** | Welches Modell ist Baseline für Exp 1-3?        |

**Analysen:**

- Confusion Matrix pro Modell
- Feature Importance Rankings (SHAP für RF)
- Art-weise Performance

#### Experiment 1: Single-City Performance

**Ziel:** Maximale erreichbare Genauigkeit ohne geografische Transferprobleme

| Aspekt       | Details                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| **Daten**    | Hamburg (80/20), Berlin (80/20), Rostock (80/20) jeweils separat        |
| **Setup**    | Train & Test in derselben Stadt (räumlich stratifiziert)                |
| **Output**   | Stadtspezifische Baseline-Modelle (z.B. Hamburg-Modell nur auf Hamburg) |
| **Metriken** | OA, F1-Score, Pro-Klasse Metrics (Producer's/User's Accuracy)           |

**Analysen:**

- Vergleich der Maximal-Leistung pro Stadt
- Identifikation schwieriger Arten (niedrigere F1)
- Stadtspezifische Verwechslungsmuster

#### Experiment 2: Cross-City Transfer (Zero-Shot)

**Ziel:** Quantifiziere Genauigkeitsverlust bei Übertragung auf unbekannte Stadt

| Aspekt                 | Details                                                        |
| ---------------------- | -------------------------------------------------------------- |
| **Szenario A**         | Train: Hamburg → Test: Rostock                                 |
| **Szenario B**         | Train: Berlin → Test: Rostock                                  |
| **Szenario C**         | Train: Hamburg + Berlin → Test: Rostock                        |
| **Entscheidungspunkt** | Falls OA < 70%, prüfe Fallback-Strategie (regionales Training) |

**Analysen:**

- Transfer-Loss quantifizieren (OA-Single-City minus OA-Transfer)
- Art-spezifische Transferability (welche Arten generalisieren besser?)
- Fehleranalyse: Systematische Verwechslungsmuster in Rostock

#### Experiment 3: Fine-Tuning mit lokalen Daten

**Ziel:** Kann minimale lokale Datenerhebung die Rostock-Performance wiederherstellung?

| Aspekt               | Details                                                               |
| -------------------- | --------------------------------------------------------------------- |
| **Basis**            | Bestes Multi-City-Modell aus Experiment 2 (Hamburg+Berlin)            |
| **Setup**            | Fine-Tune mit 1,403 Rostock-Samples (vollständiger lokaler Datensatz) |
| **Scaler & Encoder** | Bleiben unverändert (keine Overfitting-Gefahr)                        |
| **Output**           | Performance-Verbesserung vs. Zero-Shot dokumentieren                  |

**Praktische Implikation:**
Ein Modell, das nur auf Hamburg+Berlin trainiert wurde, benötigt ca. 1,400 _lokal erhobene_ Bäume zur Anpassung. Für Zielregion Wismar: Kommunale Datenerhebung von ~1,400 Bäumen ermöglicht Modellnutzung mit hoher Genauigkeit.

### 3.4 Erfolgskriterien (Experimentebene)

**MUSS-Kriterien (Exp 0-2):**

- ✅ Baseline-Modell etabliert (OA > 80% in Single-City)
- ✅ Transfer-Loss quantifiziert (Rostock Zero-Shot dokumentiert)
- ✅ Confusion Matrices pro Experiment

**SOLL-Kriterien (Exp 1-3):**

- ✅ Art-spezifische Analyse (welche Genera schwierig?)
- ✅ Feature-Importance dokumentiert
- ✅ Fine-Tuning-Potenzial demonstriert

---

## 4. Machine Learning Paradigmen (Theoretische Grundlagen)

### 4.1 Multi-Class Classification

**Expected Performance Drop:**

- Hamburg→Hamburg Val: ~85% accuracy (same city)
- Hamburg+Berlin→Rostock Zero-Shot: ~60-70% accuracy (new domain)
- Rostock Zero-Shot→Fine-Tuned: ~75-80% accuracy (domain adaptation)

### 2.3 Spatial Autocorrelation & Block-Based CV

**Problem: Spatial Autocorrelation**

```
Random Train/Val Split:
  Tree A (Train) at (620,000, 5,875,000)
  Tree B (Val) at (620,100, 5,875,100)  [100m apart!]

Issue:
  - Trees A & B are spatially close
  - Similar spectral/structural properties
  - Modell kann gut vorhersagen (aber nur weil räumlich nah)
  - Generalisierung zu neuer Region fails!
```

**Solution: Block-Based Cross-Validation**

```
Block-Level Split:
  - Define 500×500m grid cells (blocks)
  - All trees in BLOCK_i → Train or Val (not mixed!)
  - Spatial independence guaranteed between Train/Val
  - Realistic generalization estimate
```

**Theorie:**

- Moran's I: Statistisches Maß für Spatial Autocorrelation
- Block CV addresses this by ensuring spatial disjointness
- Ref: Roberts et al. (2017), "Cross-validation strategies for data with temporal, spatial, or phylogenetic structure"

---

## 3. Feature Engineering Prinzipien

### 3.1 Feature Selection Strategie

**Kategorie 1: Spectral Features (120 aus Sentinel-2)**

```
Why 12 months?
  - Phänologische Signatur (Bäume unterscheiden sich saisonal)
  - TILIA: Blattfall im Herbst (NDVI sinkt)
  - BETULA: Früher Laubaustrieb (NDVI steigt früher)

Why 15 Bands + 5 Indizes?
  - Raw Bands: Direct reflectance (not pre-processed)
  - Indizes: Normalized, robust to atmospheric effects
  - Redundancy ok (model handles correlation)
```

**Kategorie 2: Structural Features (4 CHM)**

```
Why height + statistics?
  - height_m: Direkte Artmerkmal
  - CHM_mean: Durchschnittliche Kronendicke
  - CHM_max: Peak-Höhe (ähnlich to height_m, aber robuster)
  - CHM_std: Crown Irregularität
```

**Kategorie 3: Ausgeschlossene Features**

| Feature Type                  | Reason                                  |
| ----------------------------- | --------------------------------------- |
| RGB Color                     | Already encoded in multispectral bands  |
| Texture (GLCM)                | Computational overhead, marginal gain   |
| Neighborhood (# nearby trees) | Changes with sampling, not stable       |
| Land Cover Class              | Circular reasoning (trees = land cover) |

### 3.2 NoData Handling Strategie

**Problem: Missing Sentinel-2 Pixels (Cloud Cover)**

```
Scenario: Tree in Hamburg has S2 data for 9/12 months
  (3 months cloudy = NoData)

Option 1: Exclude tree
  - Lose 19.1% of data
  - But guaranteed clean data

Option 2: Interpolate
  - Forward/backward fill
  - Linear interpolation between months
  - But introduces artifacts
```

**Decision: Hybrid Approach**

```
Rule:
  - ≤ 3 months NoData → Interpolate (linear)
  - > 3 months NoData → Exclude tree

Rationale:
  - 1-3 months gap = Short-term cloud, interpolate safe
  - > 3 months gap = Systematic (season?), exclude unsafe

Result:
  - Kept 80.9% of data
  - Removed 19.1% (highly affected by winter clouds)
  - Hamburg 38% removal (coastal clouds) vs. Rostock 4.6% (better weather)
```

---

## 4. Herausforderungen bei Stadtbaumklassifizierung

### 4.1 Räumliche Auflösung & Sub-Pixel Problem

**Challenge:**

- Stadtbaumkrone: Durchschnitt 5-15m Durchmesser
- Sentinel-2 Pixel: 10m × 10m
- **Konsequenz:** Viele Bäume sind Sub-Pixel oder füllen nur 1-2 Pixel

**Auswirkungen:**

- Mixed Pixels (Baum + Straße + Gebäude + Bürgersteig)
- Geringe räumliche Redundanz für sichere Merkmalsextraktion
- Spektralsignatur nicht "rein" vom Baum allein

**Mitigation im Projekt:**

- Puffer-Strategie: Mindestens 15m Distanz zu Bestandsgrenzen (Phase 2.1)
- CHM als strukturelles Anker (räumlich unabhängig von Spektral-Pixeln)
- Qualitätsfilter: Nur Bäume mit stabilen NDVI-Signaturen (Phase 2.2)

### 4.2 Urbane Umgebungsfaktoren

**Spezifische Probleme in Städten:**

| Problem                                       | Effekt                                   | Lösung im Projekt                                  |
| --------------------------------------------- | ---------------------------------------- | -------------------------------------------------- |
| **Schatten** (Gebäude, andere Bäume)          | Verringerte Reflexion, fehlerhafter NDVI | Temporale Aggregation (12 Monate mittelt Schatten) |
| **Versiegelte Flächen** (Straßen, Parkplätze) | Mixed Pixels, falsche Features           | NDVI-Threshold (>0.3) filtert diese                |
| **Diverser Untergrund**                       | Nicht-homogene Hintergründe              | CHM-Features robust gegen Untergrund               |
| **Baumzustände** (Krankheit, Stress)          | Atypische Spektralsignaturen             | Spektral-Outlier-Filterung (Phase 2.2)             |

**Im Wald vs. in der Stadt:**

```
Waldbestand:
  - Homogene Flächen (viele Pixel derselben Art)
  - Geschlossene Kronen, keine Lücken
  - Einfacherer spektraler Hintergrund

Stadtbäume:
  - Einzeln stehend oder in kleinen Gruppen
  - Offene Kronen, Lichteinstrahlung von unten
  - Komplexer urbaner Hintergrund
  - Unterschiedliche Zustände (gepflegt, vernachlässigt, gestresst)
```

### 4.3 Datenqualitätsprobleme

**Baumkataster-Probleme (Phase 1 gelöst):**

- GPS-Ungenauigkeit (±5-15m in Städten) → Snap-to-Peak Korrektur
- Veraltete Einträge (gefällte Bäume) → Höhenfilter (DIN 18916: ≥3m)
- Falsche Art-Labels → Quality Control in Phase 1.7

**Satellitenbilder-Probleme (Phase 2 gelöst):**

- Wolkenbedeckung → Hybrid NoData-Handling (≤3 Monate interpolieren, >3 ausschließen)
- Geolokalisierungsfehler → Toleranzbuffer im Spatial Join
- Saisonale Lücken (Winter wolkig) → 12 Monate Erfassung für Robustheit

### 4.4 Klassenungleichgewicht

**Typisches Problem:**

```
Berlin Baumkataster (tatsächlich):
  - TILIA (Linde): 104,136 (44%)
  - ACER (Ahorn): 57,936 (25%)
  - QUERCUS (Eiche): 45,467 (19%)
  - BETULA (Birke): 10,760 (5%)
  - FRAXINUS (Esche): 7,412 (3%)
  - PRUNUS (Kirsche): 5,160 (2%)
  - SORBUS (Eberesche): 3,522 (1%)

Risk: Modell optimiert für häufige Arten (TILIA), ignoriert seltene (SORBUS)
```

**Lösung im Projekt (Phase 2.3):**

- Stratified Downsampling: 1,500 Samples pro Genus (oder weniger wenn nicht verfügbar)
- Ergebnis: Alle 7 Genera mit ~14% Anteil (perfekt balanciert)
- Keine Class-Weights nötig, da Klassen gleich häufig

### 4.5 Referenzjahr 2021 & Klimatische Anomalie

**Entscheidung:** Einheitliches Referenzjahr **2021** für Sentinel-2 und CHM

**Kritische Limitation (2021 Ausnahmejahr):**

2021 war ein **ungewöhnlich kühles und nasses Jahr** mit anomalen phänologischen Mustern:

| Charakteristik            | Auswirkung                                       | Konsequenz für Modell                                                                |
| ------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------ |
| **Kühl-nass**             | Deutlich unter klimatologischem Mittel           | Verzögerter Vegetationsstart                                                         |
| **Kalter Frühling**       | Spätes Leaf-Out vs. normal                       | Frühe saisonale Signaturen gedämpft (v.a. NIR/Red-Edge)                              |
| **Gleichmäßige Anomalie** | Hamburg, Berlin, Rostock alle betroffen          | Vergleichbarkeit zwischen Städten erhalten                                           |
| **Generalisierbarkeit**   | Spektrale Zeitreihen spiegeln Ausnahmejahr wider | Modelle sind robust für 2021, aber NICHT automatisch auf "normale" Jahre übertragbar |

**Implikation für Transfer Learning:**

- Cross-City Transfer (Hamburg+Berlin → Rostock) ist validiert für 2021-ähnliche Bedingungen
- Modelle auf anderen Jahren könnten andere Performance zeigen
- Empfehlung: Ggf. Retraining mit Multi-Jahr-Daten für operationale Robustheit

### 4.6 Edge-Filter & Sub-Pixel Mischpixel

**Problem:** Sub-Pixel-Kontamination bei 10m Pixelgröße

Wenn zwei Bäume unterschiedlicher Art direkt nebeneinander stehen (z.B. beide im gleichen 10m Pixel), ist die Spektralsignatur eine Mischung aus beiden Baumarten – nicht "reines" Trainingssignal.

**Lösung: Mehrere Edge-Filter Varianten**

| Filter  | Distanz                 | Interpretation                                        | Trade-off                          |
| ------- | ----------------------- | ----------------------------------------------------- | ---------------------------------- |
| **15m** | ~Pixel-Diagonale (~14m) | Leichter Filter, akzeptiert kleine Mischpixel         | Hohe Datenmenge, aber weniger rein |
| **20m** | ~2× Pixelgröße          | Mittelstrenge Variante, deutlich sauberere Signaturen | Balance zwischen Daten & Qualität  |
| **30m** | ~3× Pixelgröße          | Maximale Reinheit der Trainingsdaten                  | Stark reduzierte Datenmenge        |

**Empirische Prüfung:** Mehrere Edge-Filter Varianten wurden getestet, um empirisch zu prüfen, welcher Trade-off das beste Modell liefert.

### 4.7 Räumliche Stratifizierung: 500×500m Blocks

**Alte Überlegung:** 1-km-Gitter für räumlich stratifiziertes Sampling

**Aktuelle Implementierung:** 500×500m Block-Split (Phase 2.4)

**Problem: Räumliche Autokorrelation**

Nahe beieinander stehende Bäume sind oft ähnlich (Alleen, gleiche Pflanzung, gleiche Umgebung). Bei Random Train/Val Split können räumlich nahe Bäume (100m) zufällig in Train und Val landen, was zu überoptimistischen Accuracy-Schätzungen führt.

**Lösung: Block-basierte Cross-Validation**

```
Strategie:
  - 500×500m Gitterzellen (blocks) definieren
  - Alle Bäume in BLOCK_i → Training ODER Validation (nicht gemischt!)
  - Räumliche Unabhängigkeit zwischen Train/Val garantiert
  - Realistische Generalisierung zu neuer Region

Resultat:
  - Hamburg+Berlin: ~80/20 Aufteilung auf Block-Ebene
  - Rostock: 100% als unabhängiges Test-Set
```

**Theoretischer Hintergrund:** Roberts et al. (2017), "Cross-validation strategies for data with temporal, spatial, or phylogenetic structure"

---

## 5. Design Decisions & Trade-offs

### 5.1 Block Size Selection (500×500m)

| Block Size     | Pros                                 | Cons                               | Decision      |
| -------------- | ------------------------------------ | ---------------------------------- | ------------- |
| **250×250m**   | Fine-grain, many blocks              | Sparse samples/block (1-2)         | ❌ Too fine   |
| **500×500m**   | Good balance, 3-4 trees/block median | Mid-size                           | ✅ CHOSEN     |
| **1000×1000m** | Coarse, 10+ trees/block              | Too coarse, loses spatial variance | ❌ Too coarse |

**Chosen: 500×500m**

- Matches typical urban block size (cities)
- Adequate samples per block for stability
- Prevents leakage while maintaining diversity

### 5.2 Train/Val/Test Split Ratio

```
Original: Hamburg (10,500) + Berlin (10,288) + Rostock (8,078) = 28,866 total

Split:
  Hamburg: 80% Train (8,371) / 20% Val (2,129)
  Berlin:  80% Train (8,299) / 20% Val (1,989)
  Rostock: 82.6% Zero-Shot (6,675) / 17.4% Fine-Tune (1,403)

Rationale:
  - Hamburg+Berlin: Standard 80/20 (enough data)
  - Rostock: 82/17 (small dataset, need more zero-shot for robust test)
```

### 5.3 Normalization Method (StandardScaler vs. RobustScaler)

| Method             | Formula                     | When to Use                      |
| ------------------ | --------------------------- | -------------------------------- |
| **StandardScaler** | $(x - \mu) / \sigma$        | Normal distribution, no outliers |
| **RobustScaler**   | $(x - \text{median}) / IQR$ | Many outliers, skewed dist.      |

**Decision: StandardScaler**

- Sentinel-2 data mostly normal (after QC filtering)
- Already removed spectral outliers (Phase 2.2)
- Standard practice in ML (CNN/RFC both expect ~0,1)

---

## 6. Literaturverzeichnis

### Remote Sensing & Vegetation Indices

- Rouse, J. W., et al. (1973). "Monitoring vegetation systems in the Great Plains with ERTS". NASA Technical Report 371942.
- Delegido, J., et al. (2011). "Red-edge vegetation indices using Sentinel-2". IEEE Geoscience and Remote Sensing Letters.
- Fassnacht, F. E., et al. (2016). "Review of studies on tree species classification from remotely sensed data". Remote Sensing of Environment.

### Machine Learning & Validation

- Roberts, D. R., et al. (2017). "Cross-validation strategies for data with temporal, spatial, or phylogenetic structure". Ecography, 40(8), 913-929.
- Tuia, D., et al. (2016). "Learning using target-oriented weighting for transfer learning". IEEE Journal of Selected Topics in Applied Earth Observations.
- He, H., & Garcia, E. A. (2009). "Learning from imbalanced data". IEEE Transactions on Knowledge and Data Engineering.

### Urban Forestry & Canopy Height

- Popescu, S. C. (2007). "Estimating biomass of individual pine trees using airborne LiDAR". Biomass & Bioenergy.
- Immitzer, M., et al. (2012). "Species classification of individual trees by combining very high spatial resolution satellite imagery with airborne lidar data". International Journal of Applied Earth Observation.

---

## 7. Offene Forschungsfragen

1. **Seasonal Effect:** Wie stark beeinflussen saisonale Muster die Klassifizierung vs. artenspezifische Signaturen?

2. **Generalization:** Warum sinkt Accuracy von 80% (Hamburg+Berlin) auf 60% (Rostock Zero-Shot)? Ist es distribution shift oder genuines Lernproblem?

3. **Fine-Tuning Trade-off:** Wieviele Rostock-Samples (50, 200, 1,403) sind nötig um +10% Accuracy zu erreichen?

4. **Rare Classes:** Warum SORBUS & FRAXINUS schwerer zu klassifizieren (F1 < 70%) vs. TILIA & QUERCUS (>85%)?

---

**Dokument-Status:** ✅ Abgeschlossen  
**Letzte Aktualisierung:** 6. Januar 2026
