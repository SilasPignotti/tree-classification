# Datenakquise: Sentinel-2 Multispektraldaten - Methodik und Dokumentation

**Projektphase:** Datenakquise  
**Datum:** 29. November 2024  
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung und Vorverarbeitung von Sentinel-2 L2A Multispektraldaten für drei deutsche Städte: Hamburg, Berlin und Rostock. Diese Daten bilden zusammen mit dem CHM die Grundlage für die spektrale und strukturelle Klassifikation von Baumarten.

### 1.1 Zieldaten

**Sentinel-2 Level-2A (L2A):**

- Atmosphärisch korrigierte Oberflächenreflektanz (Bottom of Atmosphere, BOA)
- Auflösung: 10m (native Bänder), 20m Bänder auf 10m resampelt
- Format: GeoTIFF (Cloud-Optimized)

**Monatliche Median-Komposite:**

- Zeitraum: Januar - Dezember 2024 (12 Monate)
- Aggregation: Median über alle wolkenfreien Beobachtungen pro Monat
- Begründung: Robuste Statistik gegen Ausreißer, phänologische Variation erfasst

### 1.2 Spektrale Bänder

| Band | Name       | Wellenlänge (nm) | Native Auflösung | Anwendung               |
| ---- | ---------- | ---------------- | ---------------- | ----------------------- |
| B02  | Blue       | 490              | 10m              | Vegetation, Wasser      |
| B03  | Green      | 560              | 10m              | Vegetation (Grünpeak)   |
| B04  | Red        | 665              | 10m              | Chlorophyll-Absorption  |
| B05  | Red Edge 1 | 705              | 20m → 10m        | Vegetationsstress       |
| B06  | Red Edge 2 | 740              | 20m → 10m        | Blattstruktur           |
| B07  | Red Edge 3 | 783              | 20m → 10m        | LAI-Schätzung           |
| B08  | NIR        | 842              | 10m              | Biomasse, Struktur      |
| B8A  | Narrow NIR | 865              | 20m → 10m        | Wasserdampf, Vegetation |
| B11  | SWIR 1     | 1610             | 20m → 10m        | Feuchtigkeit, Boden     |
| B12  | SWIR 2     | 2190             | 20m → 10m        | Lignin, Zellulose       |

**Nicht verwendete Bänder:**

- B01 (Coastal Aerosol, 60m) - zu grob
- B09 (Water Vapour, 60m) - atmosphärische Korrektur
- B10 (Cirrus, 60m) - Cloud Detection

### 1.3 Zielstädte

1. **Hamburg** - Trainingsdaten (maritime Klima)
2. **Berlin** - Trainingsdaten (kontinentales Klima)
3. **Rostock** - Testdaten als Proxy für Wismar (Ostseeküste)

---

## 2. Datenquelle und Plattform

### 2.1 openEO und Copernicus Data Space Ecosystem

**Plattform:** openEO (https://openeo.dataspace.copernicus.eu)  
**Backend:** Copernicus Data Space Ecosystem (CDSE)  
**Authentifizierung:** OIDC (Device Code Flow)

**Vorteile von openEO:**

- **Cloud-native Processing:** Verarbeitung auf dem Server, kein lokaler Download von Rohdaten
- **Skalierbarkeit:** Automatische Ressourcenverwaltung für große Gebiete
- **Integrierte Cloud-Maskierung:** SCL-Band direkt verfügbar
- **Temporale Aggregation:** Server-seitige Median-Berechnung
- **Europäische Datenhoheit:** CDSE unterliegt europäischen Datenschutzrichtlinien

**Kostenstruktur:**

- Free Tier: ~100 Processing Units/Monat
- Pro Monatskompositum: ~2-5 Units
- Ausreichend für gesamtes Projekt

### 2.2 Sentinel-2 Produkt

**Collection:** `SENTINEL2_L2A`  
**Prozessierungsgrad:** Level-2A (atmosphärisch korrigiert)  
**Sensor:** MSI (MultiSpectral Instrument)  
**Revisit-Zeit:** 5 Tage (2 Satelliten: S2A + S2B)  
**Orbit:** Sun-synchronous, 786 km Höhe

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. Stadtgrenzen laden (+ 500m Buffer, WGS84)
2. openEO-Verbindung herstellen (OIDC Auth)
3. Pro Stadt, pro Monat:
   a. Sentinel-2 Collection laden (spatial + temporal extent)
   b. Cloud-Masking mit SCL-Band
   c. 20m Bänder auf 10m resamplen (bilinear)
   d. Temporaler Median berechnen
   e. Batch Job starten und warten
   f. Ergebnis herunterladen
   g. Validierung
4. Checkpointing (Resume bei Unterbrechung)
```

### 3.2 Räumliche Ausdehnung

**Quelle:** `data/boundaries/city_boundaries_500m_buffer.gpkg`

**Transformation:**

- Quell-CRS: EPSG:25832 (UTM 32N)
- openEO erwartet: EPSG:4326 (WGS84 lat/lon)
- Reprojektion mit GeoPandas vor API-Aufruf

**Bounding Boxes (WGS84):**
| Stadt | West | South | East | North |
|-------|------|-------|------|-------|
| Hamburg | 9.7268° | 53.3906° | 10.3335° | 53.7430° |
| Berlin | 13.0810° | 52.3338° | 13.7678° | 52.6799° |
| Rostock | 11.9908° | 54.0461° | 12.3013° | 54.2492° |

### 3.3 Temporale Ausdehnung

**Jahr:** 2024  
**Monate:** Januar - Dezember (12 Monate)

**Begründung für 12 Monate:**

- Projektdesign spezifiziert April-Oktober (7 Monate) als primär
- Download aller 12 Monate für Flexibilität bei Ablationsstudien (Exp 4)
- Marginale Zusatzkosten (~40% mehr Daten)
- Ermöglicht Test der temporalen Suffizienzhypothese

**Monatsbereich-Berechnung:**

```python
from calendar import monthrange
_, last_day = monthrange(2024, month)
start = f"2024-{month:02d}-01"
end = f"2024-{month:02d}-{last_day:02d}"
```

### 3.4 Cloud-Masking

**Methode:** Scene Classification Layer (SCL)

**Maskierte Klassen:**
| SCL-Wert | Klasse | Beschreibung |
|----------|--------|--------------|
| 3 | Cloud Shadows | Wolkenschatten |
| 8 | Cloud Medium Probability | Mittlere Wolkenwahrscheinlichkeit |
| 9 | Cloud High Probability | Hohe Wolkenwahrscheinlichkeit |
| 10 | Thin Cirrus | Dünne Zirruswolken |

**openEO-Implementierung:**

```python
scl = s2_cube.band("SCL")
mask = (scl != 3) & (scl != 8) & (scl != 9) & (scl != 10)
s2_masked = s2_cube.mask(~mask)
```

**Erwartete Beobachtungen:**

- Sentinel-2 Revisit: 2-3 Überflüge pro 5 Tage
- Pro Monat: 8-12 Szenen
- Nach Cloud-Masking: ≥5 valide Beobachtungen (typisch)

### 3.5 Resampling

**Ziel:** Einheitliche 10m Auflösung für alle Bänder

**Betroffene Bänder:**

- B05, B06, B07 (Red Edge): 20m → 10m
- B8A (Narrow NIR): 20m → 10m
- B11, B12 (SWIR): 20m → 10m

**Methode:** Bilinear Interpolation

- Standard für kontinuierliche Reflektanzdaten
- Glättet Treppeneffekte
- Erhält radiometrische Integrität

**openEO-Implementierung:**

```python
s2_resampled = s2_masked.resample_spatial(
    resolution=10,
    method="bilinear"
)
```

### 3.6 Temporale Aggregation

**Methode:** Median

**Vorteile:**

- Robust gegen Ausreißer (verbleibende Wolken, Schatten)
- Standard für optische Zeitreihen-Komposites
- Erhält spektrale Charakteristik besser als Mittelwert

**openEO-Implementierung:**

```python
s2_monthly = s2_resampled.reduce_dimension(
    dimension="t",
    reducer="median"
)
```

### 3.7 Batch Processing

**Job-Konfiguration:**

```python
job = s2_monthly.execute_batch(
    out_format="GTiff",
    title=f"S2_{city}_{year}_{month:02d}",
    job_options={
        "driver-memory": "4g",
        "executor-memory": "4g",
    }
)
```

**Workflow:**

1. Job wird auf CDSE-Server erstellt
2. Status-Polling alle 10-30 Sekunden
3. Typische Laufzeit: 3-10 Minuten pro Monat
4. Download nach Abschluss (HTTP GET)

---

## 4. Implementierung

### 4.1 Script-Struktur

**Script:** `scripts/sentinel2/download_sentinel2.py`

**Hauptkomponenten:**

```python
# Konstanten
CITIES = ["Hamburg", "Berlin", "Rostock"]
SPECTRAL_BANDS = ["B02", "B03", ..., "B12"]
CLOUD_MASK_VALUES = [3, 8, 9, 10]
OPENEO_BACKEND = "openeo.dataspace.copernicus.eu"

# Funktionen
def connect_openeo() -> openeo.Connection
def load_city_bounds(city_name: str) -> dict
def process_monthly_composite(...) -> None
def validate_output(file_path: Path) -> bool
def download_sentinel2(...) -> None
```

### 4.2 CLI Interface

```bash
python scripts/sentinel2/download_sentinel2.py \
    --cities Hamburg Berlin Rostock \
    --year 2024 \
    --months 1-12 \
    --output data/sentinel2 \
    [--no-resume]
```

**Parameter:**
| Argument | Default | Beschreibung |
|----------|---------|--------------|
| `--cities` | Alle 3 | Space-separated Stadtliste |
| `--year` | 2024 | Ziel-Jahr |
| `--months` | 1-12 | Monatsbereich (z.B. "4-10") |
| `--output` | data/sentinel2 | Ausgabeverzeichnis |
| `--no-resume` | False | Existierende Dateien überschreiben |

### 4.3 Authentifizierung

**Methode:** OIDC Device Code Flow

**Ablauf:**

1. Script generiert Device Code
2. URL und Code werden im Terminal angezeigt
3. Nutzer öffnet URL im Browser
4. Nutzer meldet sich mit CDSE-Account an
5. Script erhält Access Token
6. Refresh Token wird lokal gespeichert (~/.config/openeo-python-client/)

**Implementierung:**

```python
def show_device_code(message: str) -> None:
    """Zeigt Device Code URL und Code an."""
    print("\n" + "=" * 60)
    print("AUTHENTICATION REQUIRED")
    print("=" * 60)
    print(message)
    print("=" * 60 + "\n")

connection.authenticate_oidc_device(
    provider_id="CDSE",
    display=show_device_code
)
```

### 4.4 Checkpointing

**Strategie:** Überspringe valide existierende Dateien

```python
if resume and output_path.exists():
    if validate_output(output_path):
        logger.info(f"Skipping {output_path.name} (already exists and valid)")
        continue
    else:
        logger.info(f"Re-downloading invalid file: {output_path.name}")
```

**Vorteile:**

- Robustheit gegen Netzwerkunterbrechungen
- Ermöglicht schrittweise Verarbeitung
- Keine doppelte Arbeit bei Neustart

---

## 5. Validierung

### 5.1 Validierungskriterien

**Checkliste pro Datei:**

- [ ] 10 spektrale Bänder vorhanden
- [ ] CRS definiert (EPSG:32632 oder EPSG:4326)
- [ ] Auflösung ~10m (oder ~0.0001° bei WGS84)
- [ ] Valide Pixel > 30%
- [ ] Reflektanzwerte im Bereich 0-10000

### 5.2 Validierungsfunktion

```python
def validate_output(file_path: Path) -> bool:
    with rasterio.open(file_path) as src:
        # Check 1: Bandanzahl
        assert src.count == 10

        # Check 2: CRS vorhanden
        assert src.crs is not None

        # Check 3: Auflösung
        # Bei UTM: 5-15m, bei WGS84: 0.00005-0.0002°

        # Check 4: Valid Pixel Anteil
        data = src.read(1)
        valid_mask = (data > 0) & (data <= 10000)
        valid_pct = np.sum(valid_mask) / data.size
        assert valid_pct > 0.30

        # Check 5: Wertebereich
        max_val = data[valid_mask].max()
        assert max_val <= 10000
```

### 5.3 Validierungsergebnis (Testlauf)

**Hamburg Januar 2024:**

```
Dimensions: 4075 × 3979 pixels
Bands: 10
CRS: EPSG:32632
Resolution: 10.0 × 10.0 m
Data type: int16

Band Statistics:
B02 (Blue)      | Min:    55 | Max: 16775 | Mean:  3333.4
B03 (Green)     | Min:    28 | Max: 16232 | Mean:  3057.9
B04 (Red)       | Min:     5 | Max: 15840 | Mean:  3071.2
B05 (RE1)       | Min:     3 | Max: 15498 | Mean:  3354.1
B06 (RE2)       | Min:     1 | Max: 15457 | Mean:  3543.1
B07 (RE3)       | Min:     4 | Max: 15419 | Mean:  3575.2
B08 (NIR)       | Min:    25 | Max: 15496 | Mean:  3752.2
B8A (Narrow NIR)| Min:     1 | Max: 15349 | Mean:  3609.3
B11 (SWIR1)     | Min:     1 | Max: 15113 | Mean:   897.9
B12 (SWIR2)     | Min:     1 | Max: 15061 | Mean:   759.9

Valid pixels: 100.0%
```

**Interpretation:**

- ✅ Alle 10 Bänder vorhanden
- ✅ CRS korrekt (UTM 32N)
- ✅ 10m Auflösung
- ✅ 100% valide Pixel (Winter, wenig Wolken)
- ✅ Reflektanzwerte plausibel:
  - Blue/Green/Red ~3000 (Winter-Reflektanz)
  - NIR ~3700 (höher, typisch)
  - SWIR ~800-900 (niedriger, typisch für Winter)

---

## 6. Outputs

### 6.1 Finale Datenprodukte

**Struktur:**

```
data/sentinel2/
├── hamburg/
│   ├── S2_2024_01_median.tif
│   ├── S2_2024_02_median.tif
│   ├── ...
│   └── S2_2024_12_median.tif
├── berlin/
│   ├── S2_2024_01_median.tif
│   └── ...
└── rostock/
    ├── S2_2024_01_median.tif
    └── ...
```

**Pro Datei:**

- 10 Bänder (B02-B12, ohne B01/B09/B10)
- ~50-200 MB (abhängig von Stadtgröße)
- GeoTIFF mit LZW-Kompression

**Gesamt:**

- 36 Dateien (3 Städte × 12 Monate)
- ~2-7 GB Gesamtvolumen

### 6.2 Dateinamen-Konvention

```
S2_{YYYY}_{MM}_median.tif
```

| Komponente | Bedeutung                  |
| ---------- | -------------------------- |
| S2         | Sentinel-2                 |
| YYYY       | Jahr (2024)                |
| MM         | Monat (01-12, zero-padded) |
| median     | Aggregationsmethode        |

### 6.3 Band-Reihenfolge

| Index | Band | Wellenlänge         |
| ----- | ---- | ------------------- |
| 1     | B02  | 490 nm (Blue)       |
| 2     | B03  | 560 nm (Green)      |
| 3     | B04  | 665 nm (Red)        |
| 4     | B05  | 705 nm (Red Edge 1) |
| 5     | B06  | 740 nm (Red Edge 2) |
| 6     | B07  | 783 nm (Red Edge 3) |
| 7     | B08  | 842 nm (NIR)        |
| 8     | B8A  | 865 nm (Narrow NIR) |
| 9     | B11  | 1610 nm (SWIR 1)    |
| 10    | B12  | 2190 nm (SWIR 2)    |

---

## 7. Herausforderungen und Lösungen

### 7.1 Authentifizierung: Browser öffnet nicht

**Problem:**
OIDC Device Code Flow zeigt keine URL im Terminal an.

**Ursache:**
openEO-Bibliothek gibt URL über internen Logger aus, der nicht sichtbar ist.

**Lösung:**
Custom Display-Funktion für explizite URL-Ausgabe:

```python
def show_device_code(message: str) -> None:
    print("\n" + "=" * 60)
    print("AUTHENTICATION REQUIRED")
    print(message)
    print("=" * 60 + "\n")

connection.authenticate_oidc_device(display=show_device_code)
```

### 7.2 CRS-Diskrepanz

**Beobachtung:**
Output ist EPSG:32632 (WGS84 / UTM 32N), nicht EPSG:25832 (ETRS89 / UTM 32N).

**Erklärung:**

- openEO/CDSE nutzt WGS84-basiertes UTM
- EPSG:32632 und EPSG:25832 sind für Deutschland quasi identisch
- Differenz: ~0.5m (vernachlässigbar bei 10m Auflösung)

**Entscheidung:**

- Akzeptieren, keine Reprojektion erforderlich
- Bei Bedarf: Reprojektion zu EPSG:25832 mit `gdalwarp`

### 7.3 TIFF-Warnungen

**Warnung:**

```
TIFFReadDirectory: Sum of Photometric type-related color channels
and ExtraSamples doesn't match SamplesPerPixel.
```

**Erklärung:**

- Metadaten-Warnung von GDAL/libtiff
- openEO schreibt TIFF mit 10 Bändern ohne korrekte Photometric-Tags
- Daten selbst sind korrekt

**Lösung:**

- Warnung ignorieren (harmlos)
- Optional: GDAL-Warnungen unterdrücken

### 7.4 Lange Verarbeitungszeiten

**Beobachtung:**
~3-10 Minuten pro Monat, 2.5-3 Stunden für alle 36 Dateien.

**Faktoren:**

- Server-Last auf CDSE
- Stadtgröße (Berlin > Hamburg > Rostock)
- Monat (Sommer: mehr Wolken, mehr Daten)

**Empfehlung:**

- Overnight-Run für vollständigen Download
- Checkpointing ermöglicht Unterbrechung

---

## 8. Technische Details

### 8.1 Verwendete Bibliotheken

**Python-Packages:**

```toml
openeo>=0.46.0      # openEO Python Client
geopandas>=1.1.1    # Vektor-Geodaten (Boundaries)
rasterio>=1.4.3     # Raster-Geodaten (Validierung)
numpy>=1.24.0       # Numerische Arrays
```

### 8.2 openEO API-Aufrufe

**Wichtige Endpunkte:**

- `load_collection()` - Daten laden
- `band()` - Einzelnes Band extrahieren
- `mask()` - Pixelmaske anwenden
- `filter_bands()` - Bänder filtern
- `resample_spatial()` - Auflösung ändern
- `reduce_dimension()` - Temporale Aggregation
- `execute_batch()` - Batch Job starten

### 8.3 Datenfluss

```
┌─────────────────────────────────────────────────────────────┐
│                    CDSE Server                               │
│                                                              │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐            │
│  │ Sentinel-2│───▶│   Cloud   │───▶│ Resample  │            │
│  │ L2A Data  │    │  Masking  │    │  10m      │            │
│  └───────────┘    └───────────┘    └───────────┘            │
│                          │                 │                 │
│                          ▼                 ▼                 │
│                   ┌───────────┐    ┌───────────┐            │
│                   │  Temporal │───▶│  GeoTIFF  │            │
│                   │   Median  │    │  Output   │            │
│                   └───────────┘    └───────────┘            │
│                                           │                  │
└───────────────────────────────────────────│──────────────────┘
                                            │
                                            ▼ HTTP Download
┌─────────────────────────────────────────────────────────────┐
│                    Local Machine                             │
│                                                              │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐            │
│  │  Download │───▶│ Validate  │───▶│   Save    │            │
│  │  Result   │    │   Data    │    │  to Disk  │            │
│  └───────────┘    └───────────┘    └───────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Performance und Ressourcen

### 9.1 Laufzeiten

| Phase             | Dauer                  |
| ----------------- | ---------------------- |
| Authentifizierung | 1-2 Minuten (einmalig) |
| Pro Monat/Stadt   | 3-10 Minuten           |
| Alle 36 Dateien   | 2.5-3 Stunden          |

### 9.2 Datenvolumen

| Stadt      | Erwartete Größe | Pixel-Dimensionen |
| ---------- | --------------- | ----------------- |
| Hamburg    | ~1.5 GB         | ~4000 × 4000      |
| Berlin     | ~2.5 GB         | ~6000 × 4000      |
| Rostock    | ~1.0 GB         | ~3000 × 2500      |
| **Gesamt** | **~5 GB**       |                   |

### 9.3 Netzwerk-Anforderungen

- Stabile Internetverbindung für 2-3 Stunden
- Download-Volumen: ~5 GB
- Upload: Minimal (nur API-Requests)

---

## 10. Lessons Learned

### 10.1 Technische Erkenntnisse

1. **openEO ist produktionsreif:**

   - Stabile API, gute Dokumentation
   - Free Tier ausreichend für Forschungsprojekte
   - Batch Processing zuverlässig

2. **Cloud-Masking ist essentiell:**

   - SCL-basierte Maskierung effektiv
   - Median-Aggregation kompensiert verbleibende Artefakte

3. **Authentifizierung erfordert Aufmerksamkeit:**
   - Device Code Flow nicht immer intuitiv
   - Explizite URL-Ausgabe verbessert UX

### 10.2 Methodische Erkenntnisse

1. **12 Monate sind sinnvoll:**

   - Flexibilität für Ablationsstudien
   - Geringe Mehrkosten

2. **Bilineare Interpolation angemessen:**

   - Keine Artefakte bei 20m → 10m
   - Standard in der Fernerkundung

3. **Median robust:**
   - Weniger sensitiv gegenüber Ausreißern
   - Gut für operationelle Anwendung

---

## 11. Nächste Schritte

### 11.1 Sofortige nächste Schritte

1. ✅ **Vollständiger Download:** Alle 36 Dateien (Overnight-Run)
2. **Vegetation Indices:** NDVI, kNDVI, EVI berechnen
3. **Grid Alignment:** CHM (1m) auf S2-Grid (10m) aggregieren

### 11.2 Feature Engineering

**Geplante Indices:**

- NDVI = (B08 - B04) / (B08 + B04)
- kNDVI = tanh(NDVI²)
- EVI = 2.5 × (B08 - B04) / (B08 + 6×B04 - 7.5×B02 + 1)
- NDRE = (B08 - B05) / (B08 + B05)
- NDWI = (B08 - B11) / (B08 + B11)

### 11.3 Integration mit anderen Datenquellen

1. **CHM-Alignment:** Resampling CHM 1m → 10m (Mean/Max/Std)
2. **Baumkataster:** Spatial Join mit S2-Pixeln
3. **Feature Stack:** CHM + S2 + Indices pro Pixel

---

## 12. Referenzen

### 12.1 Datenquellen

- **Copernicus Data Space Ecosystem:** https://dataspace.copernicus.eu/
- **openEO Platform:** https://openeo.cloud/
- **Sentinel-2 User Handbook:** https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi

### 12.2 Technische Dokumentation

- **openEO Python Client:** https://open-eo.github.io/openeo-python-client/
- **openEO API:** https://api.openeo.org/
- **Rasterio Documentation:** https://rasterio.readthedocs.io/

### 12.3 Methodische Referenzen

- **Sen2Cor (L2A Processing):** https://step.esa.int/main/snap-supported-plugins/sen2cor/
- **SCL Classification:** ESA Sentinel-2 Algorithm Theoretical Basis Document

---

## Anhang: Reproduzierbarkeit

### A.1 Vollständiger Workflow

```bash
# 1. Environment Setup
uv venv
uv sync

# 2. Account erstellen (einmalig)
# https://identity.dataspace.copernicus.eu/

# 3. Sentinel-2 Download
# Test mit einem Monat
uv run python scripts/sentinel2/download_sentinel2.py \
    --cities Hamburg --months 1

# Vollständiger Download (overnight)
uv run python scripts/sentinel2/download_sentinel2.py
```

### A.2 Laufzeiten (Approximate)

- **Setup + Auth:** ~5 Minuten
- **Test (1 Monat):** ~5 Minuten
- **Vollständig (36 Monate):** ~2.5-3 Stunden

### A.3 System Requirements

- **Disk Space:** Mindestens 10 GB frei
- **RAM:** 4 GB ausreichend (Processing auf Server)
- **Netzwerk:** Stabile Verbindung, ~5 GB Download
- **Software:** Python 3.12+, CDSE Account

---

**Dokument-Ende**
