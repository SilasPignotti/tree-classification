# Scripts Directory

Dieses Verzeichnis enthält alle Datenverarbeitungs-Skripte für das Projekt.

## Struktur

```
scripts/
├── boundaries/
│   └── download_city_boundaries.py    # Stadtgrenzen herunterladen
└── elevation/
    ├── hamburg/
    │   └── download_elevation.py      # Hamburg DOM/DGM
    ├── berlin/
    │   └── download_elevation.py      # Berlin DOM/DGM
    └── rostock/
        └── download_elevation.py      # Rostock DOM/DGM
```

## Ausführungsreihenfolge

### 1. Stadtgrenzen herunterladen

```bash
uv run python scripts/boundaries/download_city_boundaries.py
```

**Output:**
- `data/boundaries/city_boundaries.gpkg` - Original-Stadtgrenzen
- `data/boundaries/city_boundaries_500m_buffer.gpkg` - Mit 500m Buffer
- `data/boundaries/city_boundaries_visualization.png` - Visualisierung

**Features:**
- Lädt Grenzen für Hamburg, Berlin, Rostock vom BKG WFS-Dienst
- Filtert nur Hauptland-Polygon (entfernt kleine Inseln)
- Erstellt 500m Buffer für Elevation-Clipping

### 2. Höhendaten herunterladen (pro Stadt)

#### Hamburg

```bash
uv run python scripts/elevation/hamburg/download_elevation.py
```

**Datenquellen:**
- DOM: XYZ ASCII Format von Hamburg Open Data
- DGM: XYZ ASCII Format von Hamburg Open Data

**Besonderheiten:**
- Konvertiert XYZ → GeoTIFF mit GDAL
- Erfordert `gdal_translate` im PATH

**Output:**
- `data/raw/hamburg/dom_1m.tif`
- `data/raw/hamburg/dgm_1m.tif`

#### Berlin

```bash
uv run python scripts/elevation/berlin/download_elevation.py
```

**Datenquellen:**
- DOM: FIS-Broker Atom Feed (XYZ ASCII in ZIP)
- DGM: Berlin GDI Atom Feed (XYZ ASCII in ZIP)

**Besonderheiten:**
- Parst nested Atom Feed Structure
- Filtert Kacheln nach Koordinaten im Dateinamen
- Konvertiert XYZ → GeoTIFF mit GDAL (`gdal_translate`)
- Erstellt Mosaik aus mehreren Kacheln

**Output:**
- `data/raw/berlin/dom_1m.tif`
- `data/raw/berlin/dgm_1m.tif`

#### Rostock

```bash
uv run python scripts/elevation/rostock/download_elevation.py
```

**Datenquellen:**
- DOM: Geodaten MV Atom Feed (XYZ ASCII in ZIP, ganz MV = 6407 Kacheln!)
- DGM: Geodaten MV Atom Feed (XYZ ASCII in ZIP, ganz MV = 6407 Kacheln!)

**Besonderheiten:**
- **KRITISCH:** Räumliche Filterung via bbox-Attribute im Feed
  - Vermeidet Download von 6407 Kacheln für ganz MV
  - Nur ~3-10 Kacheln für Rostock relevant
- Konvertiert XYZ → GeoTIFF mit GDAL (`gdal_translate` + `gdalwarp`)
- Reprojiziert von EPSG:25833 → EPSG:25832
- Erstellt Mosaik aus mehreren Kacheln

**Output:**
- `data/raw/rostock/dom_1m.tif`
- `data/raw/rostock/dgm_1m.tif`

## Gemeinsame Features

Alle Elevation-Skripte enthalten:

- ✅ **Idempotenz:** Überspringt bereits heruntergeladene, valide Dateien
- ✅ **Retry-Logik:** Max. 3 Versuche bei Netzwerkfehlern
- ✅ **Progress Bars:** `tqdm` für Downloads
- ✅ **Logging:** INFO-Level Ausgaben
- ✅ **Validierung:** Prüft Output-GeoTIFFs mit rasterio
- ✅ **Clipping:** Schneidet auf Stadtgrenze mit 500m Buffer
- ✅ **CRS:** Einheitlich EPSG:25832
- ✅ **Kompression:** LZW-komprimierte GeoTIFFs

## Datenfluss

```
1. Stadtgrenzen
   ↓
   BKG WFS → GeoPackage (EPSG:25832)

2. Elevation (pro Stadt)
   ↓
   Atom Feed/ZIP → Download → (Mosaic) → Clip → GeoTIFF (1m, EPSG:25832)
```

## Voraussetzungen

### Software

- Python 3.12+
- GDAL (für XYZ-Konvertierung in allen Städten)
  - `gdal_translate` (XYZ → GeoTIFF)
  - `gdalwarp` (Reprojection für Rostock)

### Python-Pakete

```bash
uv add geopandas requests matplotlib rasterio feedparser tqdm
```

### Festplattenspeicher

- Hamburg: ~1-2 GB
- Berlin: ~2-3 GB
- Rostock: ~1-2 GB
- **Gesamt:** ~5-7 GB für alle drei Städte

## Fehlerbehebung

### GDAL-Fehler (alle Städte)

```bash
# macOS (Homebrew)
brew install gdal

# Ubuntu/Debian
sudo apt-get install gdal-bin

# Conda
conda install -c conda-forge gdal
```

### Atom Feed Parsing-Fehler

- Prüfe Internetverbindung
- Manche Feeds erfordern evtl. VPN/Authentifizierung
- Retry-Logik sollte temporäre Fehler abfangen

### Zu wenig Speicherplatz

- Skripte löschen temporäre Dateien nach Verarbeitung
- Manuelle Bereinigung: `rm -rf data/raw/*/temp`

## Entwicklung

### Neue Stadt hinzufügen

1. Erstelle `scripts/elevation/{stadt}/download_elevation.py`
2. Implementiere `process_elevation_data()` für Datenquelle
3. Füge Stadt zu Boundaries-Skript hinzu
4. Aktualisiere diese README

### Tests

Skripte sind idempotent → einfach erneut ausführen zum Testen.

Validierung:

```python
import rasterio
with rasterio.open("data/raw/hamburg/dom_1m.tif") as src:
    print(f"CRS: {src.crs}")
    print(f"Bounds: {src.bounds}")
    print(f"Shape: {src.shape}")
```
