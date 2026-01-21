# Methodische Grundlagen & Designentscheidungen

## Untersuchungsgebiete

| Stadt       | Rolle    | Klima              | Besonderheit                              |
| ----------- | -------- | ------------------ | ----------------------------------------- |
| **Hamburg** | Training | Maritim (Küste)    | ~170 km zu Rostock                        |
| **Berlin**  | Training | Übergang (Cfb/Dfb) | ~230 km zu Rostock                        |
| **Rostock** | Test     | Maritim (Küste)    | ~30 km zu Wismar; unabhängig vom Training |

**Logik:** Hamburg + Berlin erfassen maritime und kontinentale phänologische Muster. Rostock liegt klimatisch identisch zu Hamburg (beide Ostseeküste), bleibt aber unabhängig für echte Validierung der Modellgeneralisierung.

## Theoretische Grundlagen

### Sentinel-2 Fernerkundung

**Auflösung:** 10m räumlich, 2-3 Tage Revisitzeit in Europa  
**Spektrum:** Multispektral (Blue, Green, Red, NIR, Red-Edge, SWIR)  
**Vorteil:** Red-Edge-Bänder erfassen Vegetationsstress; multitemporale Zeitserien zeigen phänologische Muster (Blattfall, Austrieb)  
**Datenkost:** Frei verfügbar, Atmosphäre-korrigiert (L2A)

**Warum für Baumklassifizierung:** Reicht für Einzelbaum-Erkennung (10m Pixel), zeigt phänologische Unterschiede zwischen Arten

### Vegetation-Indizes

Multispektrale Bänder kombiniert zu normalisierten Kennwerten (z.B. NDVI). Zeitliche Aggregation erfasst artcharakteristische Muster (Blattaustriebszeitpunkt, Herbstfärbung).

### Canopy Height Model (CHM)

CHM = Oberflächenhöhe (Baumkronen, Gebäude) − Geländehöhe = Baum-/Vegetationshöhe  
**Vorteil:** Räumlich unabhängig von Spektral-Pixeln; robust gegen urbane Hintergrundheterogenität

### Phänologie & Zeitliche Muster

Baumarten zeigen artcharakteristische jahreszeitliche Spektralsignaturen:

- **Winter (Dez–Feb):** Kahl, niedriges NDVI (~0.2–0.3)
- **Frühling (März–Mai):** Austrieb; Timing artspezifisch (z.B. Linde früh, Birke sehr früh)
- **Sommer (Juni–Aug):** Vollbelaubt, stabiles hohes NDVI (>0.7)
- **Herbst (Sept–Nov):** Verfärbung + Laubfall; Farbe und Timing artspezifisch

**Im Projekt:** Monatliche Mediankomposite während der Vegetationsperiode erfassen diese Muster mit ausreichender Auflösung, robust gegen einzelne Wolkenaufnahmen

## Stadtauswahl – Primärstrategie

**Hamburg + Berlin (Training) → Rostock (Test)**

- **Hamburg:** Maritimes Küstenklima (Cfb), ~170 km zu Rostock
- **Berlin:** Übergangsklima (Cfb/Dfb), ~230 km zu Rostock, kontinentale Diversität
- **Rostock:** Maritimes Küstenklima (Cfb), ~30 km zur Zielregion Wismar, unabhängig vom Training

**Logik:** Hamburg + Berlin erfassen unterschiedliche phänologische Muster. Rostock ist klimatisch zu Hamburg identisch (kein Transfer-Fehler durch Klima), aber räumlich unabhängig → echte Generalisierungsprüfung.

**Datenverfügbarkeit:** Alle drei Städte haben öffentliche Baumkataster (>100k Bäume für Hamburg/Berlin, ausreichend für Rostock) und DHMs.

**Fallback-Optionen:** Regional nähere Städte (Lübeck ~80 km, Schwerin ~85 km) wurden konzeptionell erwogen, aber nicht nötig.

## Herausforderungen & Lösungen

### Sub-Pixel Problem

**Problem:** Baumkronen (5–15m) sind bei 10m Pixelgröße oft sub-pixel oder füllen nur 1–2 Pixel → Mixed Pixels (Baum + Straße + Gebäude)

**Lösungen:**

- Puffer-Strategie: Mindestdistanz zu anderen Baumarten
- Strukturelle Höhendaten als räumlich unabhängiger Anker
- Vegetationsindex-basierte Filterung

### Urbane Faktoren

| Problem                | Effekt                   | Lösung                            |
| ---------------------- | ------------------------ | --------------------------------- |
| Schatten               | Niedriges NDVI           | Temporale Aggregation mittelt     |
| Versiegelte Flächen    | Mixed Pixels             | Vegetationsindex-Filterung        |
| Heterogener Untergrund | Falsche Features         | Strukturelle Features als Anker   |
| Baumstress             | Anomale Spektralsignatur | Outlier-Filterung                 |

**Unterschied Wald ↔ Stadt:**

- **Wald:** Homogene Flächen, geschlossene Kronen, einfacher Hintergrund
- **Stadt:** Einzelbäume, offene Kronen, komplexer Hintergrund, variable Zustände

### Datenqualität

**Baumkataster-Probleme:**

- GPS-Ungenauigkeit → Positionskorrektur mittels Höhenmodell
- Veraltete Einträge (gefällte Bäume) → Höhenfilter
- Falsche Art-Labels → Quality Control & Outlier-Filterung

**Satellitendaten-Probleme:**

- Wolkenbedeckung → NoData-Handling und temporale Aggregation
- Saisonale Lücken → Fokus auf Vegetationsperiode mit besserer Datenverfügbarkeit

### Klassenungleichgewicht

Seltene Baumarten werden übersehen, wenn häufige Arten überrepräsentiert sind.

**Lösungen:** Stratified Sampling, Class Weights, Threshold-Adjustments

### Referenzjahr 2021 – Klimatische Anomalie

**Festlegung:** Einheitlich 2021 für alle Städte (Sentinel-2 + CHM)

**Limitation:** 2021 war ungewöhnlich kühl und nass → Verzögerter Vegetationsstart, gedämpfte Frühjahrssignale

**Konsequenz:**

- Modelle validiert für 2021-ähnliche Bedingungen
- Cross-City Transfer (Hamburg+Berlin → Rostock) ist für 2021 valide
- Multi-Jahr-Retraining empfohlen für operationale Robustheit

### Räumliche Autokorrelation

**Problem:** Räumlich nahe Bäume sind ähnlich (Alleen, gleiche Pflanzung); zufällige Train/Test-Splits führen zu unrealistisch guten Genauigkeiten.

**Lösung:** Block-basierte Cross-Validation (500×500m Gitterzellen). Alle Bäume einer Zelle landen entweder im Training oder Test → räumlich unabhängig, realistische Generalisierungsschätzungen.

---

**Version:** 1.1 | **Aktualisiert:** 21. Januar 2026
