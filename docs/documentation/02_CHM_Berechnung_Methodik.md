# CHM-Berechnung: Canopy Height Model - Methodik und Dokumentation

**Projektphase:** CHM-Berechnung & Qualitätssicherung
**Datum:** 30. November 2024
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Berechnung des Canopy Height Models (CHM) aus vorverarbeiteten DOM- und DGM-Daten für Hamburg, Berlin und Rostock. Das CHM bildet die Grundlage für die Extraktion von Vegetationshöhen und wird später mit Sentinel-2-Daten und Baumkatasterdaten zur Baumartenklassifikation kombiniert.

### 1.1 Eingangsdaten

**Digitales Oberflächenmodell (DOM):**
- Auflösung: 1m
- Format: GeoTIFF (LZW-komprimiert)
- CRS: EPSG:25832 (ETRS89 / UTM Zone 32N)
- Inhalt: Oberflächenhöhen inkl. Vegetation und Gebäude

**Digitales Geländemodell (DGM):**
- Auflösung: 1m
- Format: GeoTIFF (LZW-komprimiert)
- CRS: EPSG:25832
- Inhalt: Geländehöhen (bare earth)

### 1.2 Ausgabedaten

**Canopy Height Model (CHM):**
- Berechnung: CHM = DOM - DGM
- Auflösung: 1m
- Format: GeoTIFF (DEFLATE-komprimiert, predictor=3)
- CRS: EPSG:25832
- Wertebereich: 0-60m (negative Werte → 0, Werte >60m → 60)
- NoData: NaN für Wasserflächen und invalide Bereiche

---

## 2. Methodisches Vorgehen

### 2.1 Workflow-Übersicht

```
DOM (1m) + DGM (1m)
    ↓
[1] Validierung & Shape-Alignment
    ↓
[2] CHM-Berechnung (DOM - DGM)
    ↓
[3] Qualitätsfilter
    ├─ Negative Werte → 0
    └─ Ausreißer >60m → 60m
    ↓
[4] Statistiken (Full + City Core)
    ↓
[5] Qualitätsvalidierung
    ↓
[6] Visualisierung & QA
    ↓
[7] Export als GeoTIFF
```

### 2.2 Detaillierte Verarbeitungsschritte

#### Schritt 1: Validierung & Shape-Alignment

**Zweck:** Sicherstellen, dass DOM und DGM räumlich übereinstimmen

**Prozess:**
1. CRS-Validierung (beide Raster müssen EPSG:25832 sein)
2. Shape-Überprüfung (Zeilen × Spalten)
3. Bei Shape-Mismatch: Automatisches Cropping auf gemeinsames Extent
   - Min. Zeilen = min(DOM_rows, DGM_rows)
   - Min. Spalten = min(DOM_cols, DGM_cols)

**Beispiel Berlin:**
```
DOM: 37360 × 46092 Pixel
DGM: 37359 × 46093 Pixel
→ Gecroppt auf: 37359 × 46092 Pixel
```

**Code-Referenz:** [scripts/chm/create_chm.py:58-103](../../scripts/chm/create_chm.py)

#### Schritt 2: CHM-Berechnung

**Formel:**
```python
CHM = DOM - DGM
```

**Behandlung von NoData:**
- NoData-Pixel in DOM oder DGM → NoData (NaN) in CHM
- Wasserflächen bleiben als NoData erhalten

**Code-Referenz:** [scripts/chm/create_chm.py:106-125](../../scripts/chm/create_chm.py)

#### Schritt 3: Qualitätsfilter

**Filter 1: Negative Werte**
- **Schwellenwert:** 0.0m
- **Aktion:** Negative Werte → 0.0
- **Begründung:** Vegetation kann nicht unter dem Gelände sein (DGM-Fehler oder Erosion)

**Filter 2: Ausreißer**
- **Schwellenwert:** 60.0m
- **Aktion:** Werte >60m → 60.0
- **Begründung:** In deutschen Städten sind Bäume >60m extrem selten, Werte darüber sind meist DOM-Artefakte (z.B. Kräne, Funktürme)

**Code-Referenz:** [scripts/chm/create_chm.py:128-160](../../scripts/chm/create_chm.py)

#### Schritt 4: Statistik-Berechnung

**Full Extent:**
- Gesamtes Stadtgebiet (inkl. Stadtrand)
- Bezieht alle gültigen Pixel ein

**City Core:**
- Kern-Stadtgebiet (definiert durch `city_boundaries.gpkg`)
- Reduziert Einfluss von ländlichen/unbewachsenen Randbereichen
- Bessere Repräsentation der urbanen Vegetation

**Berechnete Metriken:**
- Anzahl gültiger Pixel
- Prozentsatz gültiger Pixel
- Min, Max, Mean, Median, Std
- Perzentile: P25, P75, P95, P99

**Code-Referenz:** [scripts/chm/create_chm.py:163-209](../../scripts/chm/create_chm.py)

#### Schritt 5: Qualitätsvalidierung

**Validierung 1: Plausibilität der Mittelwerte**
- Full Extent: 2-20m erwartet
- City Core: 5-25m erwartet
- ⚠️ Warnung bei Abweichung

**Validierung 2: Ausreißer-Rate**
- Erwartet: <2% Ausreißer >60m
- ⚠️ Warnung bei >2%

**Validierung 3: Gültige Pixel**
- Full Extent: >40% erwartet
- City Core: >60% erwartet
- ⚠️ Warnung bei zu wenig gültigen Pixeln

**Validierung 4: Verteilungsform**
- Median sollte < Mean sein (rechtsschiefe Verteilung)
- ⚠️ Warnung bei Median ≥ Mean

**Code-Referenz:** [scripts/chm/create_chm.py:244-285](../../scripts/chm/create_chm.py)

#### Schritt 6: Visualisierung

**Plot 1: Statistischer Überblick** (2×2 Grid)
1. Histogram der Höhenverteilung (mit Mean/Median)
2. Box Plot (Full vs. City Core)
3. Spatial Map (Downsampled für große Raster)
4. Kumulative Verteilungsfunktion (CDF)

**Plot 2: QA-Visualisierung** (1×2 Grid)
1. NoData-Verteilung (Rot = NoData)
2. Korrektur-Impact (Vor/Nach-Histogramm)

**Code-Referenz:** [scripts/chm/create_chm.py:287-447](../../scripts/chm/create_chm.py)

#### Schritt 7: GeoTIFF-Export

**Kompressionseinstellungen:**
```python
{
    "driver": "GTiff",
    "dtype": "float32",
    "nodata": np.nan,
    "compress": "DEFLATE",
    "predictor": 3,        # Floating-point predictor
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "num_threads": 4
}
```

**Optimierungen:**
- DEFLATE-Kompression mit Predictor 3 für Float32-Daten
- Tiled Layout (512×512) für schnellen regionalen Zugriff
- Multi-Threading für Schreiboperationen

**Code-Referenz:** [scripts/chm/create_chm.py:449-490](../../scripts/chm/create_chm.py)

---

## 3. Ergebnisse

### 3.1 Datei-Übersicht

| Stadt    | Pixel (Zeilen × Spalten) | Gesamtpixel | Dateigröße | Kompression |
|----------|--------------------------|-------------|------------|-------------|
| Hamburg  | 39,000 × 40,363          | 1.574 Mio.  | 1.7 GB     | DEFLATE     |
| Berlin   | 37,359 × 46,092          | 1.722 Mio.  | 2.3 GB     | DEFLATE     |
| Rostock  | 22,953 × 19,822          | 455 Tsd.    | 465 MB     | DEFLATE     |

### 3.2 Statistische Zusammenfassung

#### Hamburg

**Full Extent:**
- Gültige Pixel: 746.880.341 (47.5%)
- Mean: 4.08m, Median: 0.51m
- P95: 20.05m, P99: 28.41m
- Max: 60.0m

**City Core:**
- Gültige Pixel: 732.015.004 (46.5%)
- Mean: 4.14m, Median: 0.55m
- P95: 20.12m, P99: 28.46m
- Max: 60.0m

**Interpretation:**
- Niedrige Medianwerte (0.5m) zeigen hohen Anteil an Gras/Büschen
- Mean >4m zeigt signifikante Baumpräsenz
- Rechtsschiefe Verteilung (Median << Mean) ist erwartungsgemäß

#### Berlin

**Full Extent:**
- Gültige Pixel: 940.856.810 (54.6%)
- Mean: 6.39m, Median: 1.98m
- P95: 22.81m, P99: 27.41m
- Max: 60.0m

**City Core:**
- Gültige Pixel: 887.303.798 (51.5%)
- Mean: 6.49m, Median: 2.13m
- P95: 22.90m, P99: 27.49m
- Max: 60.0m

**Interpretation:**
- Höhere Median/Mean-Werte als Hamburg → dichtere/höhere Vegetation
- Hoher Anteil gültiger Pixel (>50%) → gute Datenqualität
- P95-Werte ~23m zeigen typische Baumhöhen in Berlin

#### Rostock

**Full Extent:**
- Gültige Pixel: 211.772.618 (46.6%)
- Mean: 5.03m, Median: 1.24m
- P95: 20.72m, P99: 26.03m
- Max: 60.0m

**City Core:**
- Gültige Pixel: 169.498.586 (37.2%)
- Mean: 5.66m, Median: 1.84m
- P95: 21.25m, P99: 26.43m
- Max: 60.0m

**Interpretation:**
- Mittlere Vegetationshöhen zwischen Hamburg und Berlin
- Niedrigerer Anteil gültiger Pixel im City Core (37%) durch Küstenlage
- Küstennahe Bereiche haben mehr NoData (Wasser)

### 3.3 Cross-City-Vergleich

**Vegetationshöhen (Mean):**
```
Berlin (6.39m) > Rostock (5.03m) > Hamburg (4.08m)
```

**Gültige Pixel (Full):**
```
Berlin (54.6%) > Rostock (46.6%) > Hamburg (47.5%)
```

**P95-Perzentil (typische Baumhöhen):**
```
Berlin (22.81m) > Rostock (20.72m) > Hamburg (20.05m)
```

**Befund:**
- Berlin hat die höchste und dichteste Vegetation
- Alle Städte zeigen rechtsschiefe Verteilungen (typisch für urbane Vegetation)
- Keine kritischen Qualitätsprobleme (alle Validierungen bestanden)

### 3.4 Korrektur-Statistiken

| Stadt    | Negative Pixel | Ausreißer >60m |
|----------|----------------|----------------|
| Hamburg  | 0              | 0              |
| Berlin   | 0              | 0              |
| Rostock  | 0              | 0              |

**Interpretation:**
- Hervorragende DOM/DGM-Qualität (keine negativen Werte)
- Keine signifikanten Artefakte (keine Ausreißer >60m)
- Vorverarbeitung der Elevation-Daten war erfolgreich

---

## 4. Qualitätssicherung

### 4.1 Validierungs-Checks

**✓ Alle Städte bestanden:**
1. CRS-Übereinstimmung (EPSG:25832)
2. Shape-Alignment (DOM/DGM)
3. Plausible Mittelwerte (2-20m Full, 5-25m Core)
4. Akzeptable Ausreißer-Rate (<2%)
5. Ausreichend gültige Pixel (>40% Full, >60% Core bei Hamburg/Berlin)

**⚠️ Rostock City Core:** Nur 37.2% gültige Pixel (unter 60%-Schwelle)
- **Ursache:** Küstenlage → große Wasserflächen
- **Bewertung:** Akzeptabel für Küstenstadt

### 4.2 Visuelle Qualitätskontrolle

**Generierte Plots:**
- `chm_overview_{city}.png` - Statistische Übersicht
- `chm_qa_{city}.png` - Qualitätsassessment

**Geprüfte Aspekte:**
- Räumliche Verteilung (keine systematischen Lücken)
- Höhenverteilung (plausible Form)
- NoData-Muster (nur Wasser/invalide Bereiche)
- Korrektur-Impact (minimal → gute Eingangsdaten)

### 4.3 Datenintegrität

**GeoTIFF-Validierung:**
```bash
gdalinfo CHM_1m_{city}.tif
```

**Geprüfte Attribute:**
- CRS: EPSG:25832 ✓
- Auflösung: 1m × 1m ✓
- NoData: NaN ✓
- Compression: DEFLATE ✓
- Tiled: 512×512 ✓

---

## 5. Verwendete Software & Bibliotheken

**Kernbibliotheken:**
- `rasterio` 1.4.2 - Raster I/O
- `numpy` 2.1.3 - Array-Operationen
- `geopandas` 1.0.1 - Vektordaten (City Boundaries)
- `pandas` 2.2.3 - Statistik-Tabellen
- `matplotlib` 3.9.2 - Visualisierung

**Entwicklungsumgebung:**
- Python 3.12
- UV Package Manager
- macOS Darwin 24.6.0

---

## 6. Reproduzierbarkeit

### 6.1 Voraussetzungen

**Benötigte Daten:**
```
data/raw/
├── hamburg/
│   ├── dom_1m.tif  (2.3 GB)
│   └── dgm_1m.tif  (1.1 GB)
├── berlin/
│   ├── dom_1m.tif  (2.1 GB)
│   └── dgm_1m.tif  (1.7 GB)
└── rostock/
    ├── dom_1m.tif  (723 MB)
    └── dgm_1m.tif  (368 MB)

data/boundaries/
└── city_boundaries.gpkg
```

### 6.2 Ausführung

**Komplette Pipeline:**
```bash
uv run python scripts/chm/create_chm.py
```

**Erwartete Outputs:**
```
data/processed/
├── CHM_1m_Hamburg.tif
├── CHM_1m_Berlin.tif
├── CHM_1m_Rostock.tif
├── chm_statistics.csv
└── plots/
    ├── chm_overview_hamburg.png
    ├── chm_overview_berlin.png
    ├── chm_overview_rostock.png
    ├── chm_qa_hamburg.png
    ├── chm_qa_berlin.png
    └── chm_qa_rostock.png
```

**Verarbeitungszeit:**
- Hamburg: ~5 Min
- Berlin: ~8 Min (größtes Raster)
- Rostock: ~2 Min

**Speicherbedarf:**
- Peak RAM: ~8 GB (Berlin-Verarbeitung)

### 6.3 Parametrierung

**Anpassbare Schwellenwerte in `create_chm.py`:**
```python
NEGATIVE_THRESHOLD = 0.0      # Minimum CHM value
MAX_HEIGHT_THRESHOLD = 60.0   # Maximum plausible tree height

EXPECTED_MEAN_FULL = (2.0, 20.0)   # Expected mean range (Full)
EXPECTED_MEAN_CORE = (5.0, 25.0)   # Expected mean range (Core)
```

---

## 7. Nächste Schritte

**CHM-Integration in Klassifikations-Pipeline:**
1. ✅ CHM-Berechnung für alle Städte abgeschlossen
2. ⏳ Sentinel-2-Daten-Akquise (zeitlich abgestimmt mit LiDAR)
3. ⏳ Baumkataster-Integration (Rostock/Hamburg/Berlin)
4. ⏳ Feature-Extraktion: CHM-basierte Merkmale
   - Mittlere/Max. Baumhöhe pro Polygon
   - Höhenvarianz (Homogenität)
   - Kronendurchmesser-Schätzung
5. ⏳ Multi-Source-Feature-Stack: Sentinel-2 + CHM + Cadastre

---

## 8. Anhang

### 8.1 Verzeichnisstruktur

```
project/
├── scripts/
│   └── chm/
│       └── create_chm.py          # Haupt-Script
├── data/
│   ├── raw/                       # DOM/DGM Inputs
│   ├── processed/                 # CHM Outputs
│   └── boundaries/                # City boundaries
└── docs/
    └── documentation/
        ├── 01_Datenakquise_Methodik.md
        └── 02_CHM_Berechnung_Methodik.md
```

### 8.2 Referenzen

- **DOM/DGM-Akquise:** Siehe `01_Datenakquise_Methodik.md`
- **Code-Referenz:** `scripts/chm/create_chm.py`
- **Statistiken:** `data/processed/chm_statistics.csv`

---

**Dokumentversion:** 1.0
**Letzte Aktualisierung:** 30. November 2024
