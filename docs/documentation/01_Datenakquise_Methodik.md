# Datenakquise: Höhendaten (DOM/DGM) - Methodik und Dokumentation

**Projektphase:** Datenakquise
**Datum:** 24. November 2024
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung und Vorverarbeitung von Höhendaten (DOM und DGM) für drei deutsche Städte: Hamburg, Berlin und Rostock. Diese Daten bilden die Grundlage für die Berechnung des Canopy Height Models (CHM), welches zur Klassifikation von Baumarten verwendet wird.

### 1.1 Zieldaten

**Digitales Oberflächenmodell (DOM):**
- Erfasst die Oberfläche inklusive Vegetation und Gebäude
- Auflösung: 1m
- Format: GeoTIFF

**Digitales Geländemodell (DGM):**
- Erfasst die Geländeoberfläche ohne Vegetation/Gebäude
- Auflösung: 1m
- Format: GeoTIFF

**Canopy Height Model (CHM):**
- Berechnet als: CHM = DOM - DGM
- Ergibt Vegetationshöhe (inkl. Baumhöhen)

### 1.2 Zielstädte

1. **Hamburg** - Trainingsdaten (gesamte Stadt, ~736 km²)
2. **Berlin** - Trainingsdaten (gesamte Stadt, ~891 km²)
3. **Rostock** - Testdaten als Proxy für Wismar (~180 km²)

---

## 2. Datenquellen

### 2.1 Hamburg

**Quelle:** Transparenzportal Hamburg (Hamburg Open Data Portal)
**URL:** https://daten-hamburg.de/
**Datenformat:** XYZ ASCII in ZIP-Archiven (kachelbasiert)
**CRS:** EPSG:25832
**Besonderheiten:**
- Kachelbasierte Abdeckung (~850+ Kacheln für Stadtgebiet)
- 2km × 2km Kacheln
- Direkte URLs (kein komplexes Feed-Parsing)
- Gemischte Raster-Orientierungen (upside-down tiles)

### 2.2 Berlin

**Quelle:** Senatsverwaltung für Stadtentwicklung Berlin
**URL:** https://fbinter.stadt-berlin.de/fb/atom/
**Datenformat:** XYZ ASCII in ZIP-Archiven
**CRS:** EPSG:25832
**Besonderheiten:**
- Atom Feed mit verschachtelter Struktur
- Kachelbasiert (2km × 2km Kacheln)
- Filterung nach Koordinaten erforderlich (XX_YYY Format)
- Großes Stadtgebiet (~891 km²)

### 2.3 Rostock

**Quelle:** Geodateninfrastruktur Mecklenburg-Vorpommern
**URL:** https://www.geodaten-mv.de/
**Datenformat:** XYZ ASCII in ZIP-Archiven
**CRS:** EPSG:25833 (Quell-CRS, wird zu EPSG:25832 konvertiert)
**Besonderheiten:**
- Feed deckt gesamtes Bundesland MV ab (32.035 Kacheln!)
- Kritische räumliche Filterung erforderlich
- Irreguläre Whitespace-Delimiter in XYZ-Dateien
- Küstenstadt (Baltic Sea → NoData in Wasserflächen)

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. Stadtgrenzen laden (+ 500m Buffer)
2. Relevante Kacheln identifizieren (Spatial Filtering)
3. Kacheln herunterladen (parallel)
4. XYZ → GeoTIFF Konvertierung
5. CRS-Reprojektion (falls erforderlich)
6. Mosaik erstellen
7. Auf Stadtgrenze clippen
8. Validierung
```

### 3.2 Stadtgrenzen und Bufferzone

**Quelle:** Bundesamt für Kartographie und Geodäsie (BKG)
**Service:** WFS (Web Feature Service)
**Layer:** `vg250_gem` (Gemeindegrenzen)

**Verarbeitungsschritte:**
1. Download via WFS für Hamburg, Berlin, Rostock
2. Bereinigung: Duplikate entfernen, relevante Spalten auswählen
3. MultiPolygon-Filterung: Nur größtes Polygon (Festland) behalten
4. **Buffer: 500m um Stadtgrenzen**
   - Begründung: Erfassung von Randbereichen und Übergangszonen
   - Wichtig für vollständige Baumerfassung in Stadtrandgebieten

**Output:**
- `data/boundaries/city_boundaries.gpkg` (Originalgrenze)
- `data/boundaries/city_boundaries_500m_buffer.gpkg` (mit Buffer)

### 3.3 Stadt-spezifische Workflows

#### 3.3.1 Hamburg

**Script:** `scripts/elevation/hamburg/download_elevation.py`

**Ablauf:**
1. **Download:**
   - DOM URL: `dom1_xyz_HH_2021_04_30.zip`
   - DGM URL: `dgm1_2x2km_XYZ_hh_2021_04_01.zip`
2. **ZIP Extraktion:**
   - Extraktion aller XYZ-Dateien (~850+ Kacheln pro Typ)
3. **XYZ → GeoTIFF Konvertierung:**
   - `gdal_translate` für jede Kachel
   - Konvertierung ALLER Kacheln (nicht nur erste!)
4. **Mosaik-Erstellung:**
   - **DOM:** `rasterio.merge()` mit "first" Methode
   - **DGM:** `gdalwarp` direktes Merging (wegen mixed orientations)
   - Problem: Einige Kacheln haben negative Y-Pixelgröße ("upside down")
   - Lösung: Direktes `gdalwarp`-Merging ohne VRT (handhabt verschiedene Orientierungen)
5. **Clip auf Stadtgrenze:**
   - `rasterio.mask()` mit 500m Buffer
6. **Output:** `data/raw/hamburg/{dom,dgm}_1m.tif`

**Besonderheiten:**
- Großes Datenvolumen (DOM 2.3 GB, DGM 1.1 GB)
- Gemischte Raster-Orientierungen erfordern spezielle Behandlung
- ~850+ Kacheln müssen verarbeitet werden
- Direktes gdalwarp-Merging für robustes Mosaicking

#### 3.3.2 Berlin

**Script:** `scripts/elevation/berlin/download_elevation.py`

**Ablauf:**
1. **Atom Feed Parsing:**
   - Haupt-Feed → Dataset-Feed (verschachtelt)
   - Extraktion von Tile-URLs
2. **Spatial Filtering:**
   - Nur Kacheln mit Koordinaten in Stadtgrenzen
   - Pattern: `dgm_33_XXX_YYYY_2.zip` (XX=Easting, YYY=Northing)
3. **Parallel Processing:**
   - 3 Worker für Download + Konvertierung
   - `ThreadPoolExecutor` für I/O-bound Tasks
4. **XYZ → GeoTIFF:**
   - `gdal_translate` für Konvertierung
   - Bereits in EPSG:25832
5. **Mosaic + Clip:**
   - `rasterio.merge()` für Mosaik
   - `rasterio.mask()` für Clipping

**Besonderheiten:**
- Großes Datenvolumen (2.1 GB DOM, 1.7 GB DGM)
- Viele Kacheln (mehrere hundert)
- 54.89% Pixelabdeckung (irreguläre Stadtgrenze)

#### 3.3.3 Rostock

**Script:** `scripts/elevation/rostock/download_elevation.py`

**Ablauf:**
1. **Atom Feed Parsing + Critical Spatial Filtering:**
   - Feed hat 32.035 Kacheln für ganz MV!
   - Verwendung von `bbox`-Attributen im Feed
   - Spatial Intersection mit Rostock-Boundary (WGS84)
   - Reduzierung auf ~115 DOM / ~230 DGM Kacheln
2. **Parallel Processing:**
   - 3 Worker für Download + Konvertierung
3. **XYZ → GeoTIFF (Custom NumPy Gridding):**
   - Problem: Irreguläre Whitespace-Delimiter in XYZ
   - `gdal_grid` scheitert (VRT kann Datei nicht parsen)
   - **Lösung:** NumPy-basiertes Gridding
     ```python
     data = np.loadtxt(xyz_path)  # Robust gegen variable Whitespace
     x, y, z = data[:, 0], data[:, 1], data[:, 2]
     raster = np.full((height, width), nodata, dtype=np.float32)
     raster[y_indices, x_indices] = z_values
     ```
4. **CRS Reprojektion:**
   - Quell-CRS: EPSG:25833 (MV Standard)
   - Ziel-CRS: EPSG:25832 (Konsistenz mit anderen Städten)
   - Tool: `gdalwarp -s_srs EPSG:25833 -t_srs EPSG:25832`
5. **Mosaic + Clip:**
   - Gleich wie Berlin

**Besonderheiten:**
- Kritische Spatial Filtering (32.035 → ~230 Kacheln)
- Custom Gridding-Lösung erforderlich
- CRS-Konvertierung
- 48.18% Pixelabdeckung (Küstenstadt + irreguläre Grenze)

---

## 4. Herausforderungen und Lösungen

### 4.1 Hamburg: Gemischte Raster-Orientierungen

**Problem:**
DGM-Kacheln hatten inkonsistente Y-Achsen-Orientierungen ("upside down" rasters).

**Debugging-Schritte:**
1. Initialer Versuch: `gdalbuildvrt` → Fehler "does not support positive NS resolution"
2. Analyse einzelner Kacheln: `src.transform.e` zeigte negative/positive Werte gemischt
3. VRT kann keine gemischten Orientierungen verarbeiten

**Root Cause:**
- `gdal_translate` bei XYZ-Konvertierung erzeugt automatisch Orientierung basierend auf Datenreihenfolge
- Verschiedene XYZ-Dateien haben verschiedene Sortierungen
- Resultat: Mix aus "normalen" und "upside down" Kacheln

**Lösung:**
Direktes `gdalwarp`-Merging ohne VRT:
```bash
gdalwarp -te {bounds} tile1.tif tile2.tif ... tileN.tif output.tif
```

**Vorteile:**
- `gdalwarp` handhabt verschiedene Orientierungen automatisch
- Kein VRT-Zwischenschritt nötig
- Gleichzeitiges Merging und Clipping

**Ergebnis:** ✅ Erfolgreich, DGM 1.1GB (40.418 × 39.132 Pixel)

### 4.2 Rostock: Leere GeoTIFF-Ausgaben

**Problem:**
Nach initialer Implementierung hatten DOM und DGM 0 valide Pixel (nur NoData).

**Debugging-Schritte:**
1. Überprüfung der Quell-XYZ-Dateien → OK (Daten vorhanden)
2. Test von `gdal_grid` → 0 Pixel Output
3. VRT-Validierung mit `ogrinfo` → "Feature Count: 0"
4. Analyse des XYZ-Formats:
   ```
   # Erwartetes Format: Space-separated
   310000.000 5994269.000 37.954

   # Tatsächliches Format: Multiple spaces + Windows line endings
   310000.000           5994269.000                            37.954\r\n
   ```

**Root Cause:**
- XYZ-Dateien nutzen irreguläre Anzahl an Leerzeichen als Delimiter
- GDAL VRT kann die Datei nicht korrekt parsen
- `gdal_grid` arbeitet auf VRT → leerer Output

**Lösung:**
Implementierung eines NumPy-basierten Gridding-Ansatzes:
```python
# NumPy handhabt variable Whitespace automatisch
data = np.loadtxt(xyz_path)
x_coords, y_coords, z_values = data[:, 0], data[:, 1], data[:, 2]

# Erstelle Grid
width = int(xmax - xmin)
height = int(ymax - ymin)
raster = np.full((height, width), -9999.0, dtype=np.float32)

# Fülle Grid (Nearest Neighbor)
x_indices = (x_coords - xmin).astype(int)
y_indices = (ymax - y_coords).astype(int)
raster[y_indices, x_indices] = z_values

# Speichere mit Rasterio
with rasterio.open(output_path, 'w', ...) as dst:
    dst.write(raster, 1)
```

**Ergebnis:** ✅ Erfolgreich, 100% Pixelabdeckung in Kacheln

### 4.3 Rostock: CRS-Inkonsistenz

**Problem:**
Mecklenburg-Vorpommern nutzt EPSG:25833, Rest des Projekts EPSG:25832.

**Lösung:**
Zweistufige Konvertierung:
1. NumPy-Gridding in EPSG:25833 (Quell-CRS)
2. `gdalwarp` Reprojektion zu EPSG:25832

**Vorteil:**
- Trennung von Gridding und Reprojektion
- Robuster als direkte CRS-Transformation während Gridding

### 4.4 Rostock: Disk Full während DGM Processing

**Problem:**
- Temp-Verzeichnis erreichte 36 GB
- Disk voll (100% Kapazität)
- "No space left on device" Error

**Lösung:**
1. Cleanup von Temp-Daten zwischen DOM und DGM
2. Nur finale GeoTIFFs behalten (DOM/DGM pro Stadt)
3. Entfernen von ZIPs, extrahierten XYZ, temporären GeoTIFFs

**Finales Datenvolumen:**
- Hamburg: DOM 2.3 GB, DGM 1.1 GB
- Berlin: DOM 2.1 GB, DGM 1.7 GB
- Rostock: DOM 657 MB, DGM 584 MB

### 4.5 Rostock: Hoher NoData-Anteil (~52%)

**Frage:** Warum haben Rostock DOM/DGM nur ~48% valide Pixel?

**Analyse:**
1. **Irreguläre Stadtgrenze (~50% Verlust):**
   - Raster ist rechteckig (20.145 × 22.953 Pixel)
   - Stadtgrenze (+ 500m Buffer) ist irregulär
   - Clipping → Alles außerhalb Boundary = NoData

2. **Wasserflächen (zusätzlicher Verlust):**
   - Rostock liegt an der Ostsee
   - LiDAR kann nicht durch Wasser messen
   - Flüsse (Warnow), Seen, Küstenbereiche = NoData

3. **Vergleich mit Berlin:**
   - Berlin: 54.89% valide Pixel
   - Rostock: 48.18% valide Pixel
   - Differenz (~7%) erklärbar durch Küstenlage

**Fazit:** ✅ 48% valide Pixel sind NORMAL und KORREKT.

---

## 5. Validierung

### 5.1 Validierungskriterien

**Checkliste:**
- [ ] Valide GeoTIFF-Dateien
- [ ] CRS ist EPSG:25832 für alle Dateien
- [ ] Raster sind auf Stadtgrenzen geclippt
- [ ] Dateigrößen plausibel (~500MB-2GB)
- [ ] Keine negativen Werte in DOM (außer Küstengebiete)
- [ ] DOM > DGM (Sanity Check für CHM)

### 5.2 Validierungsergebnisse

#### Hamburg
- ✅ DOM: 2.3 GB, 40.363 × 39.000 px, CRS: EPSG:25832
- ✅ DGM: 1.1 GB, 40.418 × 39.132 px, CRS: EPSG:25832
- ✅ Volle Stadtabdeckung (~736 km²)
- ✅ DOM: Min -6.00m, Max 251.87m, Mean 9.65m, StdDev 16.66m
- ✅ DGM: Min -12.22m, Max 116.28m, Mean 15.05m, StdDev 15.23m
- ⚠️ Negative Werte in Hafen/Elbe-Bereichen (unter Meeresspiegel)

#### Berlin
- ✅ DOM: 2.1 GB, 46.092 × 37.360 px, CRS: EPSG:25832
- ✅ DGM: 1.7 GB, 46.093 × 37.359 px, CRS: EPSG:25832
- ✅ 54.89% valide Pixel (irreguläre Stadtgrenze)
- ✅ DOM: Min 20.83m, Max 366.43m
- ✅ DGM: Min 19.09m, Max 122.34m

#### Rostock
- ✅ DOM: 657 MB, 19.822 × 22.953 px, CRS: EPSG:25832
- ✅ DGM: 584 MB, 20.145 × 22.953 px, CRS: EPSG:25832
- ✅ 48.18% valide Pixel (Küstenstadt + irreguläre Grenze)
- ⚠️ DOM: Min **-12.50m**, Max 238.62m (neg. Werte → Ostsee)
- ⚠️ DGM: Min **-6.42m**, Max 54.86m (neg. Werte → Ostsee)
- ✅ DOM > DGM: 80.6% der Pixel (Sample 1.000 × 1.000)
- ✅ Mittlere Differenz: 2.37m

**Interpretation negativer Werte (Rostock):**
- Rostock liegt an der Ostsee (Meeresspiegel ~0m)
- Negative Werte in Küstenbereichen/Gewässern sind ERWARTET
- DOM: 8.230.917 negative Pixel (37.5% der validen Pixel)
- DGM: 2.221.555 negative Pixel (10% der validen Pixel)

---

## 6. Outputs

### 6.1 Finale Datenprodukte

**Struktur:**
```
data/
├── boundaries/
│   ├── city_boundaries.gpkg                 # Originalgrenze
│   ├── city_boundaries_500m_buffer.gpkg     # Mit 500m Buffer
│   └── city_boundaries_visualization.png    # Visualisierung
└── raw/
    ├── hamburg/
    │   ├── dom_1m.tif                       # 2.3 GB
    │   └── dgm_1m.tif                       # 1.1 GB
    ├── berlin/
    │   ├── dom_1m.tif                       # 2.1 GB
    │   └── dgm_1m.tif                       # 1.7 GB
    └── rostock/
        ├── dom_1m.tif                       # 657 MB
        └── dgm_1m.tif                       # 584 MB
```

### 6.2 Scripts

```
scripts/
├── boundaries/
│   └── download_city_boundaries.py          # Stadtgrenzen + Buffer
└── elevation/
    ├── hamburg/
    │   └── download_elevation.py            # Hamburg DOM/DGM
    ├── berlin/
    │   └── download_elevation.py            # Berlin DOM/DGM
    └── rostock/
        └── download_elevation.py            # Rostock DOM/DGM
```

---

## 7. Technische Details

### 7.1 Verwendete Bibliotheken

**Python-Packages:**
- `geopandas` - Vektor-Geodaten (Boundaries)
- `rasterio` - Raster-Geodaten (GeoTIFF I/O)
- `numpy` - Numerische Arrays (Custom Gridding)
- `requests` - HTTP Downloads
- `feedparser` - Atom Feed Parsing (Berlin, Rostock)
- `tqdm` - Progress Bars
- `matplotlib` - Visualisierung

**GDAL Tools:**
- `gdal_translate` - XYZ → GeoTIFF (Hamburg, Berlin)
- `gdalwarp` - CRS Reprojektion (Rostock)
- `gdal_grid` - Gridding (versuchter Ansatz, gescheitert)

### 7.2 Performance-Optimierungen

**Parallel Processing:**
- `ThreadPoolExecutor` mit 3 Workers
- Anwendung: Berlin und Rostock Tile-Verarbeitung
- Begründung: I/O-bound (Download + Disk Write)

**Memory Management:**
- Streaming von Raster-Daten (nicht gesamtes Raster im RAM)
- Window-basiertes Lesen bei großen Files

### 7.3 Environment Setup

**UV Package Manager:**
```bash
uv venv                    # Create virtual environment
uv sync                    # Install dependencies
uv run python script.py    # Run with managed environment
```

**Dependencies in `pyproject.toml`:**
```toml
dependencies = [
    "geopandas>=1.0.1",
    "rasterio>=1.4.3",
    "requests>=2.32.3",
    "matplotlib>=3.10.0",
    "feedparser>=6.0.11",
    "tqdm>=4.67.1",
    "numpy>=2.2.0",
]
```

---

## 8. Lessons Learned

### 8.1 Technische Erkenntnisse

1. **GDAL ist nicht immer die Lösung:**
   - Bei unregelmäßigen Datenformaten kann NumPy robuster sein
   - VRT-basierte Workflows können bei Edge Cases scheitern

2. **Spatial Filtering ist kritisch:**
   - Rostock: 32.035 → 230 Kacheln (99.3% Reduktion)
   - Ohne Filtering: >1 TB Download, Stunden/Tage Laufzeit

3. **CRS-Konsistenz planen:**
   - Früh im Projekt CRS festlegen (EPSG:25832)
   - Reprojektion separat von Datenverarbeitung

4. **Disk Space Management:**
   - Bei großen Datenmengen Cleanup zwischen Schritten
   - Temp-Verzeichnisse regelmäßig leeren

### 8.2 Methodische Erkenntnisse

1. **Stadtgrenze-Buffer ist wichtig:**
   - 500m Buffer erfasst Randgebiete
   - Wichtig für vollständige Baumkartierung

2. **NoData ist normal:**
   - Bei geclippten Daten 50% NoData erwartbar
   - Küstenstädte: zusätzlicher NoData-Anteil durch Wasser

3. **Validierung frühzeitig:**
   - Pixel-Counts, Wertebereiche, CRS prüfen
   - Verhindert späte Fehlerentdeckung

### 8.3 Prozess-Optimierungen

1. **Modulare Scripts:**
   - Stadt-spezifische Scripts statt Monolith
   - Einfacher zu debuggen und anzupassen

2. **Parallel Processing lohnt sich:**
   - 3x Speedup bei Tile-Verarbeitung
   - Kritisch bei hunderten Kacheln

3. **Logging ist essentiell:**
   - Progress Tracking bei langen Downloads
   - Error Messages für Debugging

---

## 9. Nächste Schritte

### 9.1 Sofortige nächste Schritte

1. ✅ **CHM Berechnung:** CHM = DOM - DGM
2. **Sentinel-2 Integration:** Multispektrale Daten herunterladen
3. **Baumkataster-Daten:** Ground Truth für Training

### 9.2 Zukünftige Erweiterungen

1. **Automatisierung:**
   - Scheduled Updates für neue LiDAR-Daten
   - CI/CD Pipeline für Datenverarbeitung

2. **Qualitätskontrolle:**
   - Automatisierte Validierung
   - Outlier-Detection in Höhendaten

3. **Wismar Integration:**
   - Finales Testgebiet (aktuell: Rostock als Proxy)
   - Transfer Learning Evaluation

---

## 10. Referenzen

### 10.1 Datenquellen

- **Hamburg Transparenzportal:** https://transparenz.hamburg.de/
- **Berlin FIS-Broker:** https://fbinter.stadt-berlin.de/
- **Geodaten MV:** https://www.geodaten-mv.de/
- **BKG VG250:** https://gdz.bkg.bund.de/

### 10.2 Technische Dokumentation

- **GDAL Documentation:** https://gdal.org/
- **Rasterio Documentation:** https://rasterio.readthedocs.io/
- **GeoPandas Documentation:** https://geopandas.org/

### 10.3 CRS-Informationen

- **EPSG:25832:** ETRS89 / UTM zone 32N
- **EPSG:25833:** ETRS89 / UTM zone 33N

---

## Anhang: Reproduzierbarkeit

### A.1 Vollständiger Workflow

```bash
# 1. Environment Setup
uv venv
uv sync

# 2. Stadtgrenzen downloaden
uv run python scripts/boundaries/download_city_boundaries.py

# 3. Höhendaten downloaden (pro Stadt)
uv run python scripts/elevation/hamburg/download_elevation.py
uv run python scripts/elevation/berlin/download_elevation.py
uv run python scripts/elevation/rostock/download_elevation.py

# 4. Validierung
uv run python scripts/validate_elevation.py
```

### A.2 Laufzeiten (Approximate)

- **Hamburg:** ~2-3 Stunden (850+ Kacheln, abhängig von Netzwerk)
- **Berlin:** ~30-45 Minuten (abhängig von Netzwerk)
- **Rostock:** ~45-60 Minuten (abhängig von Netzwerk)

### A.3 System Requirements

- **Disk Space:** Mindestens 30 GB frei (20 GB für Hamburg temp data + finals)
- **RAM:** Mindestens 8 GB empfohlen (16 GB für Hamburg mosaicking)
- **Netzwerk:** Stabile Internetverbindung (mehrere GB Download pro Stadt)
- **Software:** Python 3.12+, GDAL 3.x

---

**Dokument-Ende**
