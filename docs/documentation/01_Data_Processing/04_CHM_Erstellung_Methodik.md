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

### 1.2 Pipeline-Übersicht (Scripts)

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
```

**Fortsetzung in Notebooks/Colab:**

- [4] Resampling zu 10m (mean, max, std)
- [5] Feature-Extraction und Sentinel-2 Integration

### 1.3 Ausgabedaten (Scripts-Phase)

| Datenprodukt       | Auflösung | Wertebereich | Format  | Verwendung                       |
| ------------------ | --------- | ------------ | ------- | -------------------------------- |
| CHM 1m (roh)       | 1m        | -XX bis XXm  | GeoTIFF | Qualitätskontrolle, Archiv       |
| CHM 1m (gefiltert) | 1m        | 0-50m        | GeoTIFF | Input für Notebooks (Resampling) |

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

## 6. Qualitätssicherung

### 6.1 Nach Phase 1 (Roh-CHM)

**Prüfe `stats_*.json`:**

| Metrik         | Erwartung (Roh)             |
| -------------- | --------------------------- |
| Coverage       | >95% innerhalb Stadtgrenzen |
| Mean           | 3-7m (städtische Gebiete)   |
| Negative Pixel | 5-30% (je nach Stadt)       |
| Pixel >50m     | <1% der gültigen Pixel      |

### 6.2 Nach Phase 3 (Harmonisiert)

**Prüfe aktualisierte `stats_*.json`:**

| Metrik         | Erwartung (Gefiltert)           |
| -------------- | ------------------------------- |
| Coverage       | 70-90% (durch Filter reduziert) |
| Mean           | 4-10m (städtische Gebiete)      |
| Min            | 0m (keine negativen Werte)      |
| Max            | ≤50m (gefiltert)                |
| Negative Pixel | 0                               |
| Pixel >50m     | 0                               |

### 6.3 Visuelle Prüfung

CHM in QGIS öffnen und prüfen:

- **Straßen:** ~0m
- **Parks:** 5-20m (Baumkronen)
- **Wälder:** Homogene Werte 15-30m
- **Wasserflächen:** NoData (nach Harmonisierung)
- **Gebäude:** NoData (nach Harmonisierung, wenn >50m)

---

## 7. Ausführung

### 7.1 Schritt-für-Schritt Workflow

**Voraussetzung:** Harmonisierte DOM/DGM Daten (siehe `03_Hoehendaten_DOM_DGM_Methodik.md`)

```bash
# 1. CHM-Berechnung (Roh)
uv run python scripts/chm/create_chm.py
# Output: CHM_1m_*.tif (roh), stats_*.json

# 2. Verteilungsanalyse
uv run python scripts/chm/analyze_chm_distribution.py
# Output: chm_distribution_analysis.json, chm_distribution_summary.csv

# 3. Backup erstellen (wichtig!)
cp -r data/CHM/processed data/CHM/processed_backup

# 4. CHM-Harmonisierung (gefiltert, überschreibt CHM_1m_*.tif!)
uv run python scripts/chm/harmonize_chm.py

# 5. Statistiken neu berechnen
uv run python scripts/chm/create_chm.py
# Output: aktualisierte stats_*.json
```

### 7.2 Ausgabedateien

```
data/CHM/processed/
├── CHM_1m_Berlin.tif        (gefiltert)
├── CHM_1m_Hamburg.tif       (gefiltert)
├── CHM_1m_Rostock.tif       (gefiltert)
├── stats_berlin.json        (aktualisiert)
├── stats_hamburg.json       (aktualisiert)
└── stats_rostock.json       (aktualisiert)

data/CHM/analysis/
├── chm_distribution_analysis.json
└── chm_distribution_summary.csv
```

---

## 8. Referenzen

### 8.1 Skripte

| Script                                    | Zweck                        |
| ----------------------------------------- | ---------------------------- |
| `scripts/chm/create_chm.py`               | CHM-Berechnung + Statistiken |
| `scripts/chm/analyze_chm_distribution.py` | Verteilungsanalyse           |
| `scripts/chm/harmonize_chm.py`            | Filterung                    |

### 8.2 Konfiguration

- `scripts/config.py` - Pfade und Parameter

### 8.3 Abhängige Dokumentation

- `03_Hoehendaten_DOM_DGM_Methodik.md` - DOM/DGM-Akquise

### 8.4 Python-Abhängigkeiten

- `numpy` - Array-Operationen
- `rasterio` - GeoTIFF I/O
- `geopandas` - Stadtgrenzen laden
- `pandas` - Statistiken

### 8.5 Nächste Schritte (Notebooks)

Nach dieser Phase werden die gefilterten CHM 1m-Daten in den Notebooks weiterverarbeitet:

- CHM-Resampling zu 10m (mean, max, std)
- Sentinel-2 Datenverarbeitung
- Feature-Extraction pro Baum
- Modelltraining (Random Forest, 1D-CNN)

---

## 9. Changelog

| Datum      | Änderung                                |
| ---------- | --------------------------------------- |
| 2025-12-09 | Initial: Methodik-Dokumentation         |
| 2026-01-06 | Update: Phase 4 zu Notebooks verschoben |

---

**Dokument-Status:** Aktuell (Scripts-Phase abgeschlossen)  
**Letzte Aktualisierung:** 6. Januar 2026

- Grid-Alignment mit Sentinel-2: Transform ist exakt identisch
- NoData-Behandlung: Nur Pixel mit gültigen Werten aggregieren
- Alle drei Varianten nutzen das gleiche 10m × 10m Sentinel-2 Grid

### 6.4 Ausgabedateien Phase 4
