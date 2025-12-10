# CHM-Erstellung: Methodik und Dokumentation

**Projektphase:** Datenverarbeitung
**Datum:** 9. Dezember 2025
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieses Dokument beschreibt die **vollständige Pipeline** zur Berechnung und Verarbeitung des **Canopy Height Model (CHM)** aus harmonisierten DOM- und DGM-Daten für Berlin, Hamburg und Rostock.

### 1.1 Definition

Das **Canopy Height Model (CHM)** repräsentiert die Höhe von Objekten über dem Gelände:

$$CHM = DOM - DGM$$

Wobei:

- **DOM (Digitales Oberflächenmodell):** Höhe der Erdoberfläche inklusive Vegetation und Gebäuden
- **DGM (Digitales Geländemodell):** Höhe des nackten Geländes

Das CHM zeigt somit die **normalisierte Höhe** von Vegetation und Gebäuden.

### 1.2 Pipeline-Übersicht

```
DOM/DGM (1m)
    ↓
[1] CHM-Berechnung (create_chm.py)
    ↓
CHM 1m (roh, mit Artefakten)
    ↓
[2] Verteilungsanalyse (analyze_chm_distribution.py)
    ↓
Statistiken über negative/hohe Werte
    ↓
[3] CHM-Harmonisierung (harmonize_chm.py)
    ↓
CHM 1m (gefiltert, 0-50m Wertebereich)
    ↓
[4] Resampling zu 10m (resample_chm.py)
    ↓
CHM 10m (mean, max, std) - für Feature Extraction
```

### 1.3 Ausgabedaten

| Datenprodukt       | Auflösung | Wertebereich | Format  | Verwendung                         |
| ------------------ | --------- | ------------ | ------- | ---------------------------------- |
| CHM 1m (roh)       | 1m        | -XX bis XXm  | GeoTIFF | Qualitätskontrolle, Archiv         |
| CHM 1m (gefiltert) | 1m        | 0-50m        | GeoTIFF | Basis für Resampling               |
| CHM 10m (mean)     | 10m       | 0-50m        | GeoTIFF | Feature Extraction (Hauptwert)     |
| CHM 10m (max)      | 10m       | 0-50m        | GeoTIFF | Feature Extraction (Kronenspitzen) |
| CHM 10m (std)      | 10m       | 0-XXm        | GeoTIFF | Feature Extraction (Heterogenität) |

---

## 2. Voraussetzungen

### 2.1 Harmonisierte Eingangsdaten

Die CHM-Berechnung setzt **harmonisierte** DOM- und DGM-Daten voraus (siehe `04_Hoehendaten_DOM_DGM_Methodik.md`):

| Anforderung               | Beschreibung                                        |
| ------------------------- | --------------------------------------------------- |
| Identische Dimensionen    | DOM und DGM müssen exakt gleiche Pixel-Anzahl haben |
| Identisches Grid          | Gleiche Transform (Ursprung, Pixelgröße)            |
| Einheitlicher NoData-Wert | Beide Raster: NoData = -9999                        |
| Gleiches CRS              | EPSG:25832                                          |

### 2.2 Eingabedateien

```
data/CHM/raw/
├── berlin/
│   ├── dom_1m.tif    (harmonisiert)
│   └── dgm_1m.tif    (harmonisiert)
├── hamburg/
│   ├── dom_1m.tif    (harmonisiert)
│   └── dgm_1m.tif    (harmonisiert)
└── rostock/
    ├── dom_1m.tif    (harmonisiert)
    └── dgm_1m.tif    (harmonisiert)
```

---

## 3. Phase 1: CHM-Berechnung (Roh)

### 3.1 Verarbeitungsschritte

```
1. Lade DOM und DGM (NoData → NaN)
2. Prüfe Dimensionsübereinstimmung
3. Berechne CHM = DOM - DGM
4. Erstelle Stadtgrenzen-Maske (ohne Buffer)
5. Berechne Statistiken innerhalb Stadtgrenzen
6. Speichere CHM als GeoTIFF
```

### 3.2 CHM-Berechnung

Die Berechnung ist eine einfache Pixel-für-Pixel-Subtraktion:

```python
chm = dom - dgm

# NoData-Propagation: NaN wo DOM oder DGM NaN
chm[np.isnan(dom) | np.isnan(dgm)] = np.nan
```

**Wichtig:** In dieser Phase werden **keine Qualitätsfilter** angewendet:

- Negative Werte (DOM < DGM) bleiben erhalten
- Hohe Werte (>60m) bleiben erhalten

Diese Werte werden nur **gezählt**, nicht entfernt, um die Rohdaten zu bewahren.

### 3.3 Statistik-Berechnung

Statistiken werden **nur für Pixel innerhalb der Stadtgrenzen** berechnet (ohne 500m Buffer):

| Metrik               | Beschreibung                       |
| -------------------- | ---------------------------------- |
| `pixels_in_boundary` | Anzahl Pixel innerhalb Stadtgrenze |
| `pixels_valid`       | Anzahl Pixel mit gültigem CHM-Wert |
| `coverage_percent`   | Anteil gültiger Pixel (%)          |
| `min`, `max`         | Wertebereich                       |
| `mean`, `median`     | Zentrale Tendenz                   |
| `std`                | Standardabweichung                 |
| `p25`, `p75`, `p95`  | Perzentile                         |
| `negative_pixels`    | Anzahl Pixel mit CHM < 0           |
| `pixels_above_60m`   | Anzahl Pixel mit CHM > 60m         |

### 3.4 Ausgabedateien Phase 1

```
data/CHM/processed/
├── CHM_1m_Berlin.tif       (Roh-CHM)
├── CHM_1m_Hamburg.tif      (Roh-CHM)
├── CHM_1m_Rostock.tif      (Roh-CHM)
├── stats_berlin.json       (Roh-Statistiken)
├── stats_hamburg.json      (Roh-Statistiken)
└── stats_rostock.json      (Roh-Statistiken)
```

### 3.5 Script

```bash
uv run python scripts/chm/create_chm.py
```

---

## 4. Phase 2: Verteilungsanalyse

### 4.1 Zweck

Analysiert die Verteilung von **negativen** und **sehr hohen** CHM-Werten, um fundierte Entscheidungen für Filterstrategien zu treffen.

### 4.2 Analysierte Kategorien

**Negative Werte:**

| Kategorie       | Bereich     | Interpretation                  |
| --------------- | ----------- | ------------------------------- |
| Sehr negativ    | < -5m       | Wasserflächen, starke Artefakte |
| Moderat negativ | -5m bis -2m | Brücken, Interpolationsfehler   |
| Leicht negativ  | -2m bis 0m  | Kleine Interpolationsfehler     |

**Hohe Werte:**

| Kategorie | Bereich | Interpretation                        |
| --------- | ------- | ------------------------------------- |
| Hoch      | > 50m   | Hochhäuser, unrealistisch für Bäume   |
| Sehr hoch | > 60m   | Hochhäuser, wahrscheinlich Messfehler |

### 4.3 Ergebnisse

| Stadt   | Negativ % | <-5m % | -5 to -2m % | -2 to 0m % | >50m % | >60m % | 0-50m % |
| ------- | --------- | ------ | ----------- | ---------- | ------ | ------ | ------- |
| Berlin  | 7.0%      | 0.0%   | 0.0%        | 7.0%       | 0.03%  | 0.02%  | 93.0%   |
| Hamburg | 18.0%     | 1.1%   | 2.4%        | 14.5%      | 0.03%  | 0.01%  | 82.0%   |
| Rostock | 27.0%     | 0.0%   | 0.0%        | 27.0%      | 0.01%  | 0.00%  | 73.0%   |

**Interpretation:**

- **Berlin:** Nur 7% negative Werte, fast alle leicht (-2m bis 0m) → geringe Filterung nötig
- **Hamburg:** 18% negativ (davon 14.5% leicht, 3.5% moderat/stark) → moderate Filterung, wahrscheinlich Wasserflächen (Elbe, Hafen)
- **Rostock:** 27% negativ (fast alle leicht) → höchster Anteil, Küstenlage mit Ostsee-Einfluss
- **Hohe Werte (>50m):** Vernachlässigbar (<0.03% aller Pixel) → hauptsächlich Hochhäuser

### 4.4 Ausgabedateien Phase 2

```
data/CHM/analysis/
├── chm_distribution_analysis.json    (Detaillierte Statistiken)
└── chm_distribution_summary.csv      (Zusammenfassung)
```

### 4.5 Script

```bash
uv run python scripts/chm/analyze_chm_distribution.py
```

---

## 5. Phase 3: CHM-Harmonisierung (Filterung)

### 5.1 Zweck

Entfernt unrealistische CHM-Werte, die für die Baumklassifikation nicht relevant oder störend sind.

### 5.2 Angewendete Filter

Basierend auf der Verteilungsanalyse werden folgende Filter angewendet:

| Filter | Bedingung      | Aktion   | Begründung                                         |
| ------ | -------------- | -------- | -------------------------------------------------- |
| 1      | -2m ≤ CHM < 0m | → 0      | Leichte Interpolationsfehler auf Boden setzen      |
| 2      | CHM < -2m      | → NoData | Wasserflächen, Brücken, starke Artefakte entfernen |
| 3      | CHM > 50m      | → NoData | Hochhäuser, unrealistisch für Baumhöhen            |

**Begründung der Schwellwerte:**

- **-2m Schwelle:** Verteilungsanalyse zeigt, dass 96-99% der negativen Werte zwischen -2m und 0m liegen (Berlin: 7.0% gesamt, Hamburg: 14.5%, Rostock: 27.0%). Diese werden als Messunsicherheit interpretiert und auf Boden (0m) gesetzt.
- **50m Schwelle:** Höchste Bäume in Deutschland ~45-50m (Douglasien, Tannen). Werte >50m sind fast ausschließlich Gebäude.

### 5.3 Auswirkungen

| Stadt   | Original Valid | Auf 0 gesetzt | Entfernt (negativ) | Entfernt (>50m) | Final Valid | Verlust % |
| ------- | -------------- | ------------- | ------------------ | --------------- | ----------- | --------- |
| Berlin  | 941,156,477    | 67,158,822    | 83,237             | 297,879         | 940,775,361 | 0.04%     |
| Hamburg | 746,987,228    | 116,299,235   | 26,732,768         | 185,620         | 720,068,840 | 3.60%     |
| Rostock | 219,188,150    | 66,877,094    | 77,819             | 15,797          | 219,094,534 | 0.04%     |

**Interpretation:**

- **Berlin:** Minimale Filterung (0.04%), fast alle negativen Werte sind leicht (-2m bis 0m). Hochwertige Eingangsdaten.
- **Hamburg:** Deutlich höhere Filterung (3.60%), hauptsächlich durch stark negative Werte (26.7M Pixel, ~3.6% der Originaldaten). Ursache: Wasserflächen (Elbe, Hafen, Kanäle). Trotzdem 96.4% der Daten erhalten.
- **Rostock:** Minimale Filterung (0.04%), vergleichbar mit Berlin. Obwohl die Verteilungsanalyse 27% negative Werte zeigte, sind die meisten davon zwischen -2m und 0m (in den Filter 1 konvertiert) oder bereits im DGM berücksichtigt.

### 5.4 Wichtige Hinweise

⚠️ **WARNUNG:** Dieses Script **überschreibt** die originalen CHM-Dateien in `data/CHM/processed/`!

**Vor Ausführung:**

1. Backup erstellen: `cp -r data/CHM/processed data/CHM/processed_backup`
2. Script mit Bestätigung ausführen

### 5.5 Script

```bash
# Backup erstellen
cp -r data/CHM/processed data/CHM/processed_backup

# Harmonisierung durchführen (fragt nach Bestätigung)
uv run python scripts/chm/harmonize_chm.py

# Neue Statistiken berechnen (aktualisiert stats_*.json)
uv run python scripts/chm/create_chm.py
```

---

## 6. Phase 4: Resampling zu 10m

### 6.1 Zweck

Sentinel-2 Daten haben eine Auflösung von 10m. Um CHM-Werte mit Sentinel-2 Pixeln zu kombinieren, muss das CHM auf 10m resampelt werden.

### 6.2 Aggregationsmethoden

Für jedes 10m×10m Pixel (= 100 Pixel bei 1m Auflösung) werden **drei Varianten** berechnet:

| Variante     | Methode            | Bedeutung                                               |
| ------------ | ------------------ | ------------------------------------------------------- |
| **CHM_mean** | Mittelwert         | Durchschnittliche Vegetationshöhe im 10m-Pixel          |
| **CHM_max**  | Maximum            | Höchster Punkt (Kronenspitzen) im 10m-Pixel             |
| **CHM_std**  | Standardabweichung | Höhenvariabilität (niedrig = homogen, hoch = heterogen) |

### 6.3 Implementierung

Die Aggregation erfolgt mit folgenden Methoden:

**Mean & Max:** `rasterio.warp.reproject()` mit entsprechender Resampling-Methode

- Mean: `Resampling.average` - Mittelwert über 10×10 Pixel
- Max: `Resampling.max` - Maximum über 10×10 Pixel

**Std:** Vectorisierte Block-Aggregation mit `numpy.nanstd()`

- Effiziente Berechnung via Array-Reshape und Aggregation
- Ignoriert NaN-Werte (NoData) automatisch

**Wichtig:**

- Grid-Alignment mit Sentinel-2: Transform ist exakt identisch
- NoData-Behandlung: Nur Pixel mit gültigen Werten aggregieren
- Alle drei Varianten nutzen das gleiche 10m × 10m Sentinel-2 Grid

### 6.4 Ausgabedateien Phase 4

```
data/CHM/processed/CHM_10m/
├── CHM_10m_mean_Berlin.tif      (Durchschnittliche CHM-Höhe)
├── CHM_10m_max_Berlin.tif       (Maximale Kronenspitze)
├── CHM_10m_std_Berlin.tif       (Höhenvariabilität)
├── CHM_10m_mean_Hamburg.tif
├── CHM_10m_max_Hamburg.tif
├── CHM_10m_std_Hamburg.tif
├── CHM_10m_mean_Rostock.tif
├── CHM_10m_max_Rostock.tif
└── CHM_10m_std_Rostock.tif
```

**Dateigröße pro Variante:** ~8-10 MB (komprimiert mit LZW)

### 6.5 Qualitätssicherung Resampling

| Stadt   | CHM_mean | CHM_max | CHM_std | Coverage (Stadtgebiet)        | Grid-Align |
| ------- | -------- | ------- | ------- | ----------------------------- | ---------- |
| Berlin  | 0-49.9m  | 0-50m   | 0-24.8m | 99.5% (mean/max), 98.6% (std) | ✓          |
| Hamburg | 0-50.0m  | 0-50m   | 0-24.5m | 97.0% (mean/max), 95.1% (std) | ✓          |
| Rostock | 0-49.6m  | 0-50m   | 0-21.9m | 99.7% (mean/max), 82.7% (std) | ✓          |

**Interpretation:**

- **Coverage > 95%:** Hervorragende Datenabdeckung für Berlin und Hamburg (mean/max)
- **Berlin/Hamburg std niedriger (95-98%):** Pixels mit zu vielen NaN-Werten in 10×10 Block werden zu NoData
- **Rostock std 82.7%:** Etwas niedriger, aber ausreichend
- **Grid exakt identisch mit Sentinel-2:** Transform und Shape stimmen überein

### 6.6 Scripts

**Resampling durchführen (erzeugt alle 9 Dateien):**

```bash
uv run python scripts/chm/resample_chm.py
```

**Statistiken mit Stadtgrenzen-basiertem Coverage berechnen:**

```bash
uv run python scripts/chm/recalc_chm_stats.py
```

---

## 7. Interpretation der CHM-Werte

### 7.1 CHM 1m (gefiltert)

| CHM-Wert | Interpretation                  | Verwendung                      |
| -------- | ------------------------------- | ------------------------------- |
| 0 m      | Boden (Straßen, Plätze, Wiesen) | Nicht-Vegetation                |
| 0-3 m    | Niedriger Bewuchs, Sträucher    | Nicht-Baum-Vegetation           |
| 3-15 m   | Kleine/mittlere Bäume           | Jungbäume, Stadtbäume           |
| 15-30 m  | Große Bäume                     | Altbäume, Parkbäume             |
| 30-50 m  | Sehr hohe Bäume                 | Douglasien, Tannen, alte Eichen |

### 7.2 CHM 10m (aggregiert)

**CHM_mean:**

- Repräsentiert die **durchschnittliche Vegetationshöhe** im 10m-Pixel
- Werte ~0m: Offene Flächen, Straßen
- Werte 5-15m: Typische Stadtbäume
- Werte >20m: Wälder, alte Baumbestände

**CHM_max:**

- Repräsentiert die **höchste Kronenspitze** im 10m-Pixel
- Wichtig für Baumarten mit spitzen Kronen (Tannen, Fichten)
- CHM_max > CHM_mean + 5m: Einzelbäume oder heterogene Bestände

**CHM_std:**

- Repräsentiert die **Höhenvariabilität** im 10m-Pixel
- Niedrige Werte (<2m): Homogene Vegetation (Rasenflächen, gleichaltrige Bestände)
- Hohe Werte (>5m): Heterogene Vegetation (Mischwald, unterschiedliche Altersklassen)

---

## 8. Bekannte Anomalien und Limitationen

### 8.1 Negative CHM-Werte (vor Harmonisierung)

**Beobachtung:**

- Berlin: ~7% negative Pixel
- Hamburg: ~18% negative Pixel
- Rostock: ~27% negative Pixel

**Ursachen:**

1. **Wasserflächen:** DOM misst Wasseroberfläche, DGM interpoliert Gewässergrund
   - Besonders ausgeprägt in Hamburg (Elbe, Hafen) und Rostock (Ostsee)
2. **Brücken:** DGM zeigt Brückenhöhe, DOM zeigt Wasser darunter
3. **Interpolationsfehler:** An Datenkanten und bei fehlenden Punkten
4. **Zeitliche Unterschiede:** DOM und DGM aus verschiedenen Befliegungen

**Lösung:** Harmonisierungsfilter (siehe Abschnitt 5)

### 8.2 Sehr hohe Werte (>50m, vor Harmonisierung)

**Ursachen:**

1. **Hochhäuser:** Besonders in Innenstädten (Berlin: Fernsehturm, Hamburg: Elbphilharmonie)
2. **Industrieanlagen:** Schornsteine, Kräne
3. **Messfehler:** Outlier in den Rohdaten

**Lösung:** Harmonisierungsfilter entfernt Werte >50m

### 8.3 Limitationen der 10m-Aggregation

- **Kleine Bäume (<10m Kronendurchmesser):** Können in CHM_mean unterschätzt werden
- **Randpixel:** An Waldrändern kann CHM_mean durch Straßen/Gebäude verzerrt sein
- **Heterogene Pixel:** CHM_mean kann irreführend sein bei Mischung aus Bäumen und Gebäuden

→ Daher werden **alle drei Varianten** (mean, max, std) für die Feature Extraction verwendet

---

## 9. Dateistruktur

```
data/CHM/
├── raw/                          # Harmonisierte DOM/DGM-Eingangsdaten
│   ├── berlin/
│   │   ├── dom_1m.tif
│   │   └── dgm_1m.tif
│   ├── hamburg/
│   │   ├── dom_1m.tif
│   │   └── dgm_1m.tif
│   └── rostock/
│       ├── dom_1m.tif
│       └── dgm_1m.tif
├── processed/                    # CHM 1m (roh + gefiltert)
│   ├── CHM_1m_Berlin.tif        (nach Harmonisierung: gefiltert)
│   ├── CHM_1m_Hamburg.tif
│   ├── CHM_1m_Rostock.tif
│   ├── stats_berlin.json
│   ├── stats_hamburg.json
│   ├── stats_rostock.json
│   └── CHM_10m/                 # CHM 10m (resampelt)
│       ├── CHM_10m_mean_Berlin.tif
│       ├── CHM_10m_max_Berlin.tif
│       ├── CHM_10m_std_Berlin.tif
│       ├── CHM_10m_mean_Hamburg.tif
│       ├── CHM_10m_max_Hamburg.tif
│       ├── CHM_10m_std_Hamburg.tif
│       ├── CHM_10m_mean_Rostock.tif
│       ├── CHM_10m_max_Rostock.tif
│       └── CHM_10m_std_Rostock.tif
├── analysis/                     # Analyse-Outputs
│   ├── chm_distribution_analysis.json
│   └── chm_distribution_summary.csv
└── processed_backup/             # Backup vor Harmonisierung
    └── [Original CHMs]
```

---

## 10. Verwendung (Komplette Pipeline)

### 10.1 Voraussetzungen

```bash
# DOM/DGM harmonisiert (siehe 04_Hoehendaten_DOM_DGM_Methodik.md)
uv run python scripts/elevation/harmonize_elevation.py
```

### 10.2 Phase 1: CHM-Berechnung (Roh)

```bash
uv run python scripts/chm/create_chm.py
```

**Output:** `CHM_1m_*.tif` (roh), `stats_*.json`

### 10.3 Phase 2: Verteilungsanalyse

```bash
uv run python scripts/chm/analyze_chm_distribution.py
```

**Output:** `chm_distribution_analysis.json`, `chm_distribution_summary.csv`

### 10.4 Phase 3: CHM-Harmonisierung

```bash
# Backup erstellen
cp -r data/CHM/processed data/CHM/processed_backup

# Harmonisierung (überschreibt CHM_1m_*.tif!)
uv run python scripts/chm/harmonize_chm.py

# Neue Statistiken berechnen
uv run python scripts/chm/create_chm.py
```

**Output:** Gefilterte `CHM_1m_*.tif`, aktualisierte `stats_*.json`

### 10.5 Phase 4: Resampling zu 10m

**PLATZHALTER - Nach Script-Erstellung:**

```bash
uv run python scripts/chm/resample_chm.py
```

**Output:** `CHM_10m_mean_*.tif`, `CHM_10m_max_*.tif`, `CHM_10m_std_*.tif`

---

## 11. Qualitätssicherung

### 11.1 Nach Phase 1 (Roh-CHM)

**Prüfe `stats_*.json`:**

| Metrik         | Erwartung (Roh)             |
| -------------- | --------------------------- |
| Coverage       | >95% innerhalb Stadtgrenzen |
| Mean           | 3-7m (städtische Gebiete)   |
| Negative Pixel | 5-30% (je nach Stadt)       |
| Pixel >50m     | <1% der gültigen Pixel      |

### 11.2 Nach Phase 3 (Harmonisiert)

**Prüfe aktualisierte `stats_*.json`:**

| Metrik         | Erwartung (Gefiltert)           |
| -------------- | ------------------------------- |
| Coverage       | 70-90% (durch Filter reduziert) |
| Mean           | 4-10m (städtische Gebiete)      |
| Min            | 0m (keine negativen Werte)      |
| Max            | ≤50m (gefiltert)                |
| Negative Pixel | 0                               |
| Pixel >50m     | 0                               |

### 11.3 Nach Phase 4 (Resampelt)

**PLATZHALTER - Validierungskriterien nach Resampling:**

- Grid-Alignment mit Sentinel-2 prüfen
- Wertebereich plausibel (0-50m)
- CHM_mean < CHM_max (immer erfüllt)
- CHM_std ≥ 0 (immer erfüllt)

### 11.4 Visuelle Prüfung

CHM in QGIS öffnen und prüfen:

- **Straßen:** ~0m
- **Parks:** 5-20m (Baumkronen)
- **Wälder:** Homogene Werte 15-30m
- **Wasserflächen:** NoData (nach Harmonisierung)
- **Gebäude:** NoData (nach Harmonisierung, wenn >50m)

---

## 12. Referenzen

### 12.1 Skripte

| Script                                    | Zweck                           |
| ----------------------------------------- | ------------------------------- |
| `scripts/chm/create_chm.py`               | CHM-Berechnung + Statistiken    |
| `scripts/chm/analyze_chm_distribution.py` | Verteilungsanalyse              |
| `scripts/chm/harmonize_chm.py`            | Filterung unrealistischer Werte |
| `scripts/chm/resample_chm.py`             | Resampling zu 10m (PLATZHALTER) |

### 12.2 Konfiguration

- `scripts/config.py` - Pfade und Parameter

### 12.3 Dokumentation

- `docs/documentation/04_Hoehendaten_DOM_DGM_Methodik.md` - DOM/DGM-Methodik

### 12.4 Abhängigkeiten

- `numpy`: Array-Operationen
- `rasterio`: GeoTIFF I/O
- `geopandas`: Stadtgrenzen laden
- `pandas`: Statistik-Tabellen
- `matplotlib`: Visualisierungen (Analyse-Phase)

---

## 13. Changelog

| Datum      | Änderung                                                  |
| ---------- | --------------------------------------------------------- |
| 2025-12-09 | Initial: CHM-Berechnung (Roh)                             |
| 2025-12-09 | Erweitert: Verteilungsanalyse, Harmonisierung, Resampling |

---

**Dokument-Status:** In Arbeit (Platzhalter für Analyse-Ergebnisse und Resampling)
**Letzte Aktualisierung:** 9. Dezember 2025
