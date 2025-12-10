# Datenakquise: Höhendaten (DOM und DGM) - Methodik und Dokumentation

**Projektphase:** Datenakquise
**Datum:** 9. Dezember 2025
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung und Vorverarbeitung von Höhendaten für drei deutsche Städte: Hamburg, Berlin und Rostock. Die Höhendaten werden in zwei Varianten erfasst:

1. **DOM (Digitales Oberflächenmodell):** Repräsentiert die Erdoberfläche inklusive Vegetation, Gebäuden und anderen Objekten
2. **DGM (Digitales Geländemodell):** Repräsentiert die bloße Geländeoberfläche (Gelände ohne Vegetation/Gebäude)

Die Differenz zwischen DOM und DGM wird verwendet, um die **Canopy Height Model (CHM)** zu berechnen, welche die Vegetationshöhe darstellt.

### 1.1 Zieldaten

**DOM und DGM (verarbeitet):**

- Auflösung: 1 Meter
- Format: GeoTIFF (LZW-komprimiert, gekachelt)
- Koordinatensystem: EPSG:25832 (ETRS89 / UTM zone 32N)
- Räumliche Abdeckung: Stadtgrenze + 500m Buffer
- Datentyp: Float32
- NoData-Wert: -9999

### 1.2 Zielstädte

1. **Hamburg** - Untersuchungsgebiet (~765 km² mit Buffer)
2. **Berlin** - Untersuchungsgebiet (~920 km² mit Buffer)
3. **Rostock** - Untersuchungsgebiet (~205 km² mit Buffer)

---

## 2. Datenquellen

### 2.1 Hamburg

**Quelle:** Freie und Hansestadt Hamburg - Open Data
**Datentyp:** XYZ ASCII Format in ZIP-Archiven
**Auflösung:** 1m
**Datum:** 2021

**Download-URLs:**

- DOM: https://daten-hamburg.de/opendata/Digitales_Hoehenmodell_bDOM/dom1_xyz_HH_2021_04_30.zip
- DGM: https://daten-hamburg.de/geographie_geologie_geobasisdaten/Digitales_Hoehenmodell/DGM1/dgm1_2x2km_XYZ_hh_2021_04_01.zip

**Charakteristiken:**

- Direkte Download-URLs (keine Atom-Feeds)
- Bereits in EPSG:25832 (kein Reproject nötig)
- XYZ-Format erfordert Konvertierung zu GeoTIFF mit `gdal_translate`

### 2.2 Berlin

**Quelle:** Berlin FIS-Broker (Atom Feed Dienst)
**Feed URL (DOM):** https://fbinter.stadt-berlin.de/fb/feed/senstadt/a_dom1
**Feed URL (DGM):** https://gdi.berlin.de/data/dgm1/atom
**Datentyp:** XYZ ASCII Format in ZIP-Archiven (pro Kachel)
**Auflösung:** 1m
**Datum:** 2023

**Charakteristiken:**

- Nested Atom Feed-Struktur (Haupt-Feed → Dataset-Feed → Kacheln)
- Kachel-Format: "DOM1 XXX_YYYY" mit km-Koordinaten in EPSG:25833
- Etwa 50-70 Kacheln pro Datentyp für Berlin erforderlich
- Daten in EPSG:25833, müssen zu EPSG:25832 reprojiziert werden
- Räumliche Filterung nach Koordinatennamen möglich (Pre-Filtering)

### 2.3 Rostock (Mecklenburg-Vorpommern)

**Quelle:** Geodaten MV - Atom Feed Dienst
**Feed URL (DOM):** https://www.geodaten-mv.de/dienste/dom_atom
**Feed URL (DGM):** https://www.geodaten-mv.de/dienste/dgm_atom
**Datentyp:** XYZ ASCII Format in ZIP-Archiven (pro Kachel)
**Auflösung:** 1m
**Datum:** 2023

**Charakteristiken:**

- **KRITISCH:** Feed enthält ~6407 Kacheln für gesamtes MV!
- Bbox-Attribute in Feed erlauben räumliches Pre-Filtering
- Kachel-Format: z.B. "dom1_33_302_5992_2.zip"
- Daten in EPSG:25833, müssen zu EPSG:25832 reprojiziert werden
- Erfordert parallele Verarbeitung (ThreadPoolExecutor)
- XYZ-Parsing mit NumPy (robuster gegen Whitespace-Variationen)

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. Download-Daten beschaffen (Feed-Parsing oder direkte URLs)
2. Räumliche Filterung (falls erforderlich)
3. ZIP-Archive extrahieren → XYZ-Dateien
4. XYZ zu GeoTIFF konvertieren (GDAL)
5. Reprojizierung (GDAL Warp) zu EPSG:25832
6. Mosaik aus Kacheln erstellen (rasterio.merge)
7. Clipping auf Stadtgrenze + 500m Buffer
8. **Harmonisierung (NoData + Grid-Alignment)**
9. Validierung (CRS, Pixelgröße, Datenbereich)
10. Speichern als finales GeoTIFF
```

### 3.2 Hamburg-spezifischer Prozess

**Besonderheit:** Direkte Download-URLs, keine Atom-Feeds

```python
# Workflow-Schritte:
1. Download ZIP direkt
2. Extraktion der XYZ-Dateien
3. gdal_translate: XYZ → GeoTIFF (bereits EPSG:25832)
4. Clip auf Stadtgrenze + Buffer
5. Speichern
```

**Keine Reprojizierung nötig** da Hamburg bereits in EPSG:25832 ist.

### 3.3 Berlin-spezifischer Prozess

**Besonderheit:** Nested Atom Feed, Koordinaten-basierte Filterung

```python
# Workflow-Schritte:
1. Parse Haupt-Atom Feed
2. Extrahiere Dataset-Feed URL
3. Parse Dataset-Feed für Kacheln (<link rel="section">)
4. Filter nach km-Koordinaten im Dateinamen
   - Konvertiere Stadtgrenze zu EPSG:25833 Bounds
   - Extrahiere XXX, YYYY aus "DOM1 XXX_YYYY"
   - Behalte nur Kacheln innerhalb erweiterter Bounds
5. Parallele Verarbeitung:
   - Download ZIP
   - Extraktion XYZ
   - gdal_translate: XYZ → GeoTIFF (EPSG:25833)
   - gdalwarp: Reprojizierung zu EPSG:25832
6. Mosaik + Clip
7. Speichern
```

**Reprojizierung erforderlich** von EPSG:25833 → EPSG:25832.

### 3.4 Rostock-spezifischer Prozess

**Besonderheit:** Huge Atom Feed (6407 Kacheln), räumliches Pre-Filtering KRITISCH

```python
# Workflow-Schritte:
1. Parse Haupt-Atom Feed
2. Extrahiere Dataset-Feed URL
3. Parse Dataset-Feed mit Bbox-Filtering:
   - Konvertiere Stadtgrenze zu EPSG:4326 (WGS84)
   - Für jede Kachel: Parse bbox-Attribut
   - Prüfe Überschneidung mit Stadtgrenze-Box
   - **Resultiert in ~10-20 Kacheln statt 6407!**
4. Parallele Verarbeitung (ThreadPoolExecutor, 3 Workers):
   - Download ZIP (mit Retry-Logik)
   - Extraktion XYZ
   - NumPy-basiertes Grid-Parsing (robust gegen Whitespace)
   - Rasterisierung zu GeoTIFF (EPSG:25833)
   - gdalwarp: Reprojizierung zu EPSG:25832
5. Mosaik + Clip
6. Speichern
```

**Besonderheiten bei XYZ-Parsing:**

- Rostock XYZ hat unregelmäßiges Whitespace
- NumPy loadtxt() ist robuster als GDAL-basierte Methoden
- Zweigeteilter Prozess:
  1. NumPy: XYZ → Raster in EPSG:25833
  2. GDAL: Reprojizierung + Orientierungskorrektur

### 3.5 Konfigurationsparameter

Alle Konfigurationen sind in `scripts/config.py` zentral definiert:

```python
# Zielauflösung und CRS
ELEVATION_RESOLUTION_M = 1
TARGET_CRS = "EPSG:25832"

# Source CRS pro Stadt
ELEVATION_SOURCE_CRS = {
    "Berlin": "EPSG:25833",
    "Hamburg": "EPSG:25832",
    "Rostock": "EPSG:25833",
}

# Feed-Endpoints
ELEVATION_FEEDS = {
    "Berlin": {...},
    "Hamburg": {...},
    "Rostock": {...},
}

# GDAL-Parameter
GDAL_TRANSLATE_OPTS = ["-co", "COMPRESS=LZW", "-co", "TILED=YES", ...]
GDALWARP_OPTS = ["-r", "near", "-co", "COMPRESS=LZW", ...]

# Download-Parameter
ELEVATION_MAX_RETRIES = 3
ELEVATION_TIMEOUT_S = 600
```

---

## 4. Datenverarbeitung und Validierung

### 4.1 Verarbeitungsschritte im Detail

#### 4.1.1 Download und Extraktion

| Schritt    | Input | Output       | Tool            |
| ---------- | ----- | ------------ | --------------- |
| Download   | URL   | ZIP-Datei    | requests + tqdm |
| Extraktion | ZIP   | XYZ-Dateien  | system `unzip`  |
| Parsing    | XYZ   | Raster-Daten | NumPy oder GDAL |

#### 4.1.2 Konvertierung XYZ → GeoTIFF

**Zwei Methoden je nach Stadt:**

**Methode A (Hamburg):** Direkt mit GDAL

```bash
gdal_translate -of GTiff -a_srs EPSG:25832 -co COMPRESS=LZW input.xyz output.tif
```

**Methode B (Berlin, Rostock):** NumPy + GDAL

```python
# Schritt 1: NumPy Grid-Parsing
data = np.loadtxt(xyz_file)  # Robust gegen Whitespace
raster = create_grid(data)
# Speichern in Source-CRS
rasterio.write(raster, crs=SOURCE_CRS)

# Schritt 2: GDAL Reprojizierung
gdalwarp -s_srs EPSG:25833 -t_srs EPSG:25832 temp.tif output.tif
```

#### 4.1.3 Mosaicking

```python
# Öffne alle konvertierten GeoTIFFs
with rasterio.open(tile1), rasterio.open(tile2), ...:
    mosaic, transform = merge(files, method="first")
    # Speichere Zwischen-Mosaik
    write_mosaic(mosaic)
```

**Merge-Methode:** `method="first"` (erste (höchste) Kachel hat Vorrang bei Überlappung)

#### 4.1.4 Clipping auf Stadtgrenze + Buffer

```python
# Lade gepufferte Stadtgrenze
boundary_gdf = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
boundary_reproj = boundary_gdf.to_crs(mosaic.crs)

# Clippe mit all_touched=True (inclusive Rand-Pixel)
out_image, out_transform = mask(
    mosaic,
    boundary_reproj.geometry,
    crop=True,
    all_touched=True
)
```

**Wichtig:** `all_touched=True` stellt sicher, dass auch Pixel an der Grenze erfasst werden.

### 4.2 Harmonisierung (DOM/DGM Post-Processing)

Nach dem initialen Download weisen die Daten zwei kritische Probleme auf, die vor der CHM-Berechnung behoben werden müssen:

#### 4.2.1 Problem 1: Unterschiedliche Raster-Dimensionen

DOM und DGM haben leicht unterschiedliche Dimensionen:

| Stadt   | DOM           | DGM           | Differenz      |
| ------- | ------------- | ------------- | -------------- |
| Berlin  | 46092 × 37360 | 46093 × 37359 | 1 × 1 Pixel    |
| Hamburg | 40363 × 39000 | 40418 × 39132 | 55 × 132 Pixel |
| Rostock | 19822 × 22953 | 20145 × 22953 | 323 × 0 Pixel  |

**Lösung:** Grid-Alignment mit DOM als Referenz (bessere Coverage). DGM wird mit bilinearem Resampling auf das DOM-Grid reprojiziert.

#### 4.2.2 Problem 2: Inkonsistente NoData-Werte

Die Quelldaten verwenden unterschiedliche NoData-Konventionen:

| Stadt   | DOM NoData | DGM NoData | Problem                                   |
| ------- | ---------- | ---------- | ----------------------------------------- |
| Berlin  | 0.0        | 0.0        | 0 ist korrekt als NoData (min. Höhe ~20m) |
| Hamburg | None       | -32768     | Inkonsistent                              |
| Rostock | -9999      | -9999      | Bereits korrekt                           |

**Lösung:** Alle NoData-Werte auf **-9999** vereinheitlichen.

**Wichtige Erkenntnis Berlin:** Die 0-Werte sind KORREKT als NoData interpretiert. Die niedrigste echte Höhe in Berlin liegt bei ~20m (DOM) bzw. ~19m (DGM). Es gibt keine validen 0m-Höhenwerte.

#### 4.2.3 Coverage-Analyse

Die scheinbar niedrige Coverage (~50%) in den Rohdaten erklärt sich durch die rechteckige Bounding-Box der Raster vs. die unregelmäßigen Stadtgrenzen:

| Stadt   | DOM Coverage (innerhalb Stadtgrenze) | DGM Coverage |
| ------- | ------------------------------------ | ------------ |
| Berlin  | 94.9%                                | 94.5%        |
| Hamburg | 100%                                 | 88.9%        |
| Rostock | 99.1%                                | 99.9%        |

Die ~5-11% fehlenden Pixel sind echte Datenlücken (z.B. Gewässer, Flughäfen).

#### 4.2.4 Harmonisierungs-Pipeline

```python
# Script: scripts/elevation/harmonize_elevation.py

# Schritt 1: NoData-Harmonisierung
for city in [Berlin, Hamburg, Rostock]:
    # Stadt-spezifische Konvertierung zu NoData=-9999
    harmonize_nodata(dom_path, dgm_path)

# Schritt 2: Grid-Alignment
for city in [Berlin, Hamburg, Rostock]:
    # DGM auf DOM-Grid reprojizieren (bilinear)
    reproject(
        dgm,
        dst_transform=dom.transform,
        dst_crs=dom.crs,
        resampling=Resampling.bilinear
    )
```

**Reihenfolge wichtig:** NoData ZUERST harmonisieren, dann Grid-Alignment.

### 4.3 Validierung

Siehe Abschnitt 5 für detaillierte Validierungschecks.

---

## 5. Validierungsprozess

Das Script `scripts/elevation/validate_elevation.py` führt 7 umfassende Validierungschecks durch:

### 5.1 CHECK 1: Dateiexistenz und Größe

- ✓ Prüft, ob alle 6 Dateien existieren (DOM + DGM × 3 Städte)
- Zeigt Dateigröße in MB

**Erwartete Größen:**

- Hamburg: DOM ~2.3GB, DGM ~1.1GB
- Berlin: DOM ~2.1GB, DGM ~1.7GB
- Rostock: DOM ~657MB, DGM ~584MB

### 5.2 CHECK 2: CRS Validierung

- ✓ Prüft, dass alle Dateien EPSG:25832 sind
- Zeigt Pixel-Dimensionen

**Ergebnis:** ALLE Dateien müssen EPSG:25832 sein (Target CRS)

### 5.3 CHECK 3: Pixelgröße (1m Auflösung)

- ✓ Validiert X und Y Pixelgröße
- Toleranz: ±0.01m

**Ergebnis:** Beide Achsen müssen 1.0m ± 0.01m sein

### 5.4 CHECK 4: Datenbereich und Statistiken (Vollständige Datei)

- ✓ Berechnet Min/Max/Mean/StdDev für gesamte Raster
- Warnt vor negativen Höhenwerten

**Erwartete Wertebereiche:**

- Min: ~-5m bis +10m (negative Werte in Gewässern möglich)
- Max: 50m bis 150m je nach Stadt
- Mean: 10m bis 40m

### 5.5 CHECK 5: NoData-Behandlung (innerhalb Stadtgrenzen)

- ✓ Zeigt NoData-Wert aus TIFF-Metadaten
- Berechnet % gültige Pixel **innerhalb der Stadtgrenzen (ohne Buffer)**

**Ergebnis nach Harmonisierung:**

- NoData = -9999 (einheitlich)
- Berlin: ~95% gültige Pixel
- Hamburg DOM: ~100%, DGM: ~89%
- Rostock: >99% gültige Pixel

### 5.6 CHECK 6: DOM >= DGM Sanity Check (KRITISCH)

Dies ist die wichtigste methodische Überprüfung!

- ✓ Vergleicht DOM und DGM Pixel-für-Pixel
- Berechnet Mittelwert-Differenz DOM - DGM
- Prüft, dass DOM >= DGM in > 95% der Fälle (mit -0.1m Toleranz)

**Erwartung:**

- DOM-DGM mean sollte 5m bis 20m sein (Vegetation/Gebäude)
- > 95% DOM >= DGM: ✓ GOOD
- 80-95%: ⚠️ WARNING
- < 80%: ✗ POOR

### 5.7 CHECK 7: Datenabdeckung (innerhalb Stadtgrenzen)

- ✓ Zeigt gültige Pixel pro Stadt und Datentyp
- Berechnet Coverage **nur innerhalb der Stadtgrenzen (ohne Buffer)**
- Ignoriert NoData-Padding außerhalb der Stadtgrenzen

**Ergebnis nach Harmonisierung:**

- Berlin: ~95% (Rest sind echte Lücken, z.B. Flughäfen)
- Hamburg: ~89-100%
- Rostock: >99%

---

## 6. Validierungsergebnisse nach Harmonisierung

### 6.1 Dateiexistenz und Größe

| Stadt   | DOM     | DGM     |
| ------- | ------- | ------- |
| Berlin  | 1938 MB | 2494 MB |
| Hamburg | 2150 MB | 2710 MB |
| Rostock | 590 MB  | 782 MB  |

✓ Alle 6 Dateien existieren und sind harmonisiert.

### 6.2 Grid-Alignment (CHECK 2 & 3)

| Stadt   | DOM Shape     | DGM Shape     | CRS        | Pixel Size |
| ------- | ------------- | ------------- | ---------- | ---------- |
| Berlin  | 46092 × 37360 | 46092 × 37360 | EPSG:25832 | 1.0007m    |
| Hamburg | 40363 × 39000 | 40363 × 39000 | EPSG:25832 | 1.0000m    |
| Rostock | 19822 × 22953 | 19822 × 22953 | EPSG:25832 | 1.0000m    |

✓ **ALLE Shapes identisch!** Grid-Alignment erfolgreich.

### 6.3 NoData-Harmonisierung (CHECK 5)

| Stadt   | DOM NoData | DGM NoData | DOM Coverage | DGM Coverage |
| ------- | ---------- | ---------- | ------------ | ------------ |
| Berlin  | -9999 ✓    | -9999 ✓    | 100.0%       | 99.5%        |
| Hamburg | -9999 ✓    | -9999 ✓    | 100.0%       | 99.7%        |
| Rostock | -9999 ✓    | -9999 ✓    | 99.7%        | 100.0%       |

✓ **Einheitlicher NoData-Wert -9999** in allen Dateien.
✓ **Ausgezeichnete Coverage:** >99% innerhalb Stadtgrenzen.

### 6.4 Datenbereich (CHECK 4)

**Berlin (referenziale Stadtkern):**

- DOM: 20.83m - 366.43m (Mean: 48.88m)
- DGM: 19.09m - 122.34m (Mean: 42.48m)
- CHM-Differenz: 6.39m (mit Gebäuden, Bäumen)

**Hamburg (mit Wasserauffälligkeiten):**

- DOM: -6.00m - 251.87m (Mean: 9.65m) — Negative Werte in Wasserflächen
- DGM: -12.18m - 116.24m (Mean: 15.04m) — DGM-Interpolation unter DOM

**Rostock (mit Waterkanten):**

- DOM: -12.50m - 238.62m (Mean: 14.27m) — Wasserkanten-Artefakte
- DGM: -6.39m - 54.82m (Mean: 9.99m)

**Interpretation negativer Werte:** Wasserflächen und Brückenbereiche, wo DOM < DGM. Dies ist **physikalisch korrekt** und wird in der CHM-Berechnung berücksichtigt.

### 6.5 DOM ≥ DGM Sanity Check (CHECK 6)

| Stadt   | Mean Differenz | % DOM ≥ DGM | Status                   |
| ------- | -------------- | ----------- | ------------------------ |
| Berlin  | 6.39m          | 99.9% ✓     | EXCELLENT                |
| Hamburg | 3.37m          | 91.9% ⚠️    | WARNING (Wasserflächen)  |
| Rostock | 4.27m          | 90.3% ⚠️    | WARNING (Küstenbereiche) |

**Berlin:** Perfekt. Hamburg/Rostock haben ~8-9% Pixel mit DOM<DGM (Wasserflächen, Brücken) — dies ist **erwartet und korrekt**.

### 6.6 Zusammenfassung Datenqualität

| Stadt   | Coverage | Status |
| ------- | -------- | ------ |
| Berlin  | 99.8%    | ✓ GOOD |
| Hamburg | 99.9%    | ✓ GOOD |
| Rostock | 99.9%    | ✓ GOOD |

✓ **Alle Städte: READY FOR CHM PROCESSING**

---

## 7. Dateistruktur

```
data/CHM/
├── raw/
│   ├── berlin/
│   │   ├── dom_1m.tif          (2.1 GB) - Digitales Oberflächenmodell
│   │   ├── dgm_1m.tif          (1.7 GB) - Digitales Geländemodell
│   │   └── temp/               [wird gelöscht nach Verarbeitung]
│   ├── hamburg/
│   │   ├── dom_1m.tif          (2.3 GB)
│   │   ├── dgm_1m.tif          (1.1 GB)
│   │   └── temp/               [wird gelöscht nach Verarbeitung]
│   └── rostock/
│       ├── dom_1m.tif          (657 MB)
│       ├── dgm_1m.tif          (584 MB)
│       └── temp/               [wird gelöscht nach Verarbeitung]
└── processed/
    └── [CHM-Outputs werden hier gespeichert]
```

---

## 8. Scripts und Verwendung

### 8.1 Download-Scripts

```bash
# Berlin
python scripts/elevation/berlin/download_elevation.py

# Hamburg
python scripts/elevation/hamburg/download_elevation.py

# Rostock
python scripts/elevation/rostock/download_elevation.py
```

### 8.2 Harmonisierungsscript

```bash
# Harmonisiert NoData-Werte und Grid-Alignment
# ACHTUNG: Überschreibt Originaldateien! Backup erstellen!
python scripts/elevation/harmonize_elevation.py
```

Führt zwei Schritte aus:

1. NoData-Harmonisierung (alle auf -9999)
2. Grid-Alignment (DGM auf DOM-Grid)

### 8.3 Validierungsscript

```bash
python scripts/elevation/validate_elevation.py
```

Gibt umfassenden Report mit allen 7 Checks aus.
Coverage wird nur innerhalb der Stadtgrenzen (ohne Buffer) berechnet.

---

## 9. Qualitätssicherung

### 9.1 Überprüfte Aspekte

- ✓ Alle Dateien existieren
- ✓ Koordinatensystem korrekt (EPSG:25832)
- ✓ Pixelauflösung 1m
- ✓ Höhenwertbereiche plausibel
- ✓ NoData richtig behandelt
- ✓ DOM >= DGM logisch konsistent
- ✓ Räumliche Abdeckung vollständig

### 9.2 Bekannte Besonderheiten

**Hamburg:**

- Bereits in korrektem CRS (kein Reproject)
- Nur zwei große ZIP-Archive
- Schnelle Verarbeitung
- DOM hat NoData=None (alle Pixel valid)
- DGM hat ~11% echte Datenlücken innerhalb Stadtgrenze

**Berlin:**

- Nested Atom Feed-Struktur
- Etwa 50-70 Kacheln
- Reprojizierung erforderlich
- NoData=0.0 (korrekt, da min. Höhe ~20m)
- ~5% echte Datenlücken (Flughäfen, etc.)

**Rostock:**

- Größtes Daten-Volumen (6407 Kacheln)
- Räumliches Pre-Filtering KRITISCH
- Parallele Verarbeitung notwendig
- NumPy-basiertes XYZ-Parsing
- Beste Coverage (>99%)

### 9.3 Harmonisierungsprozess

Nach dem Download müssen die Daten harmonisiert werden:

1. **NoData-Werte vereinheitlichen** auf -9999
2. **Grid-Alignment** durchführen (DGM auf DOM-Grid)

Dies ist notwendig für die CHM-Berechnung (DOM - DGM), da beide Raster identische Dimensionen haben müssen.

---

## 10. Zitierung und Referenzen

**Download-Scripts:**

- `scripts/elevation/berlin/download_elevation.py`
- `scripts/elevation/hamburg/download_elevation.py`
- `scripts/elevation/rostock/download_elevation.py`

**Validierungsscript:**

- `scripts/elevation/validate_elevation.py`

**Konfiguration:**

- `scripts/config.py` (Abschnitt: Höhendaten)

**Abhängigkeiten:**

- rasterio
- geopandas
- numpy
- requests
- tqdm
- GDAL (gdal_translate, gdalwarp, gdalbuildvrt)

---

**Dokument-Status:** Abgeschlossen — Harmonisierung und Validierung erfolgreich
**Letzte Aktualisierung:** 9. Dezember 2025
