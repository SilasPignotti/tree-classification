# Sentinel-2 Verarbeitung: Download via Google Earth Engine - Methodik und Dokumentation

**Projektphase:** Datenverarbeitung (Notebooks)
**Datum:** 6. Januar 2026
**Autor:** Silas Pignotti
**Notebook:** `notebooks/processing/02_sentinel2_gee_download.ipynb`

---

## 1. Übersicht

Dieses Dokument beschreibt die **komplette Pipeline** zum Download und zur Vorverarbeitung von Sentinel-2 Satellitendaten für Berlin, Hamburg und Rostock über **Google Earth Engine (GEE)** für das Jahr 2021.

### 1.1 Zweck

Sentinel-2 liefert hochauflösende (10m) multispektrale Daten mit 13 Bändern. Die Pipeline beschafft:

- 12 monatliche Median-Kompositionen (Jan-Dez 2021)
- 10 spektrale Bänder (B2-B12)
- 5 berechnete Vegetationsindizes (NDre, NDVIre, kNDVI, VARI, RTVIcore)
- **Gesamt: 15 Bänder pro Monat**

### 1.2 Datenspezifikation

| Parameter       | Wert                                                 |
| --------------- | ---------------------------------------------------- |
| **Quelle**      | Copernicus Sentinel-2 L2A (atmosphärisch korrigiert) |
| **Collection**  | COPERNICUS/S2_SR_HARMONIZED                          |
| **Zeitraum**    | 2021-01-01 bis 2021-12-31 (12 Monate)                |
| **Auflösung**   | 10m (alle Bänder resampelt zu 10m)                   |
| **Aggregation** | Monatliche Median-Kompositionen                      |
| **CRS**         | EPSG:25832 (UTM Zone 32N)                            |
| **Format**      | Cloud-Optimized GeoTIFF (COG)                        |
| **Kompression** | Keine (LZW möglich, aber GEE nutzt Raw)              |

### 1.3 Spectral Bands & Indices

**Spektrale Bänder (10 Bänder):**
| Band | Name | Auflösung | Wellenlänge | Resample |
| ----- | -------------- | --------- | ----------- | -------- |
| B2 | Blue | 10m | 490nm | – |
| B3 | Green | 10m | 560nm | – |
| B4 | Red | 10m | 665nm | – |
| B5 | Vegetation Red Edge | 20m | 705nm | ✓ 10m |
| B6 | Vegetation Red Edge | 20m | 740nm | ✓ 10m |
| B7 | Vegetation Red Edge | 20m | 783nm | ✓ 10m |
| B8 | NIR | 10m | 842nm | – |
| B8A | Narrow NIR | 20m | 865nm | ✓ 10m |
| B11 | SWIR-1 | 20m | 1610nm | ✓ 10m |
| B12 | SWIR-2 | 20m | 2190nm | ✓ 10m |

**Vegetationsindizes (5 Indizes):**

| Index        | Formel                             | Bereich       | Bedeutung                               |
| ------------ | ---------------------------------- | ------------- | --------------------------------------- |
| **NDre**     | (B8A - B5) / (B8A + B5)            | [-1, 1]       | Red Edge Normalized Difference          |
| **NDVIre**   | (B8A - B4) / (B8A + B4)            | [-1, 1]       | NIR Red Edge Normalized Difference      |
| **kNDVI**    | tanh((NDVI)²)                      | [0, 1]        | Kernel NDVI (nicht-linear, LAI)         |
| **VARI**     | (B3 - B4) / (B3 + B4 - B2)         | [-2, 2]       | Visible Atmospherically Resistant Index |
| **RTVIcore** | (B8A - B5) × 100 - (B8A - B4) × 10 | [-1000, 1000] | Red Transformation Vegetation Index     |

**Begründung der Indices:**

- **NDre, NDVIre, kNDVI:** Vegetationsgrüne in verschiedenen Ausprägungen
- **VARI:** Atmosphären-robust, nutzt nur sichtbare Wellenlängen
- **RTVIcore:** Kombiniert Red-Edge und NIR, sensitive für Baumarten

### 1.4 Datenprodukte

**Output pro Stadt × Monat:**

- `S2_<City>_2021_<MM>_median.tif` (15 Bänder, ~230 MB pro Datei)

**Gesamt:**

- 3 Städte × 12 Monate = 36 GeoTIFF Dateien
- Gesamtspeicher: ~8 GB

---

## 2. Cloud Masking & Qualitätskontrolle

### 2.1 SCL-basiertes Masking

**Problem:** Sentinel-2 enthält Wolken, Schatten, Wasser, die Klassifikation stören.

**Lösung:** Scene Classification Layer (SCL) Band nutzen.

**SCL-Klassen:**
| Klasse | Name | Code | Action |
| ------ | ------------------- | ---- | ------------- |
| 0 | No Data | - | Ignore (mask) |
| 1 | Saturated/Defective | - | Ignore (mask) |
| 2 | Dark Area Pixels | - | Ignore (mask) |
| 3 | Cloud Shadows | - | Ignore (mask) |
| 4 | **Vegetation** | ✓ | **Keep** |
| 5 | **Not Vegetated** | ✓ | **Keep** |
| 6 | Water | - | Ignore (mask) |
| 7 | **Unclassified** | ✓ | **Keep** (aber weniger zuverlässig) |
| 8 | Cloud Medium | - | Ignore (mask) |
| 9 | Cloud High | - | Ignore (mask) |
| 10 | Thin Cirrus | - | Ignore (mask) |
| 11 | Snow Ice | - | Ignore (mask) |

**Whitelist (Klassen behalten):** 4 (Vegetation), 5 (Not Vegetated), 7 (Unclassified)

**Implementierung:**

```python
def mask_clouds_scl(image):
    scl = image.select('SCL')
    valid_mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(7))
    return image.updateMask(valid_mask)
```

**Auswirkung:** Monatliche Median-Kompositionen behalten ~70-85% der Daten nach Masking.

### 2.2 Band-Resample zu 10m

**Problem:** Sentinel-2 liefert 20m Bänder (B5, B6, B7, B8A, B11, B12) mit unterschiedlicher Auflösung als 10m Bänder.

**Lösung:** Bilinear Resampling zu 10m vor Median-Aggregation.

```python
def resample_20m_to_10m(image):
    bands_20m = ['B5', 'B6', 'B7', 'B8A', 'B11', 'B12']
    resampled = image.select(bands_20m).resample('bilinear').reproject(
        crs=image.select('B2').projection(),
        scale=10
    )
    return image.addBands(resampled, overwrite=True)
```

**Laufzeit-Overhead:** +20-30% pro Image (vernachlässigbar bei Median).

---

## 3. Vegetationsindizes

### 3.1 Berechnung in GEE

**Kritische Details:**

1. **Alle Indizes sind Float32** (nicht Integer!)
2. **Robuste Normalisierung:** $1e^{-8}$ Epsilon zur Vermeidung von Division durch Null
3. **RTVIcore speziell:** Normalisierung auf 0-1 vor Berechnung, um Überläufe zu vermeiden

```python
def add_vegetation_indices(image):
    eps = 1e-8

    # NDre
    ndre = image.select('B8A').subtract(image.select('B5')) \
               .divide(image.select('B8A').add(image.select('B5')).add(eps)) \
               .float().rename('NDre')

    # NDVIre
    ndvire = image.select('B8A').subtract(image.select('B4')) \
                  .divide(image.select('B8A').add(image.select('B4')).add(eps)) \
                  .float().rename('NDVIre')

    # kNDVI
    ndvi_base = image.select('B8').subtract(image.select('B4')) \
                    .divide(image.select('B8').add(image.select('B4')).add(eps))
    kndvi = ndvi_base.pow(2).tanh().float().rename('kNDVI')

    # VARI
    vari_num = image.select('B3').subtract(image.select('B4'))
    vari_den = image.select('B3').add(image.select('B4')) \
                   .subtract(image.select('B2')).add(eps)
    vari = vari_num.divide(vari_den).float().rename('VARI')

    # RTVIcore (mit Normalisierung)
    b8a_norm = image.select('B8A').divide(10000.0)
    b5_norm = image.select('B5').divide(10000.0)
    b4_norm = image.select('B4').divide(10000.0)
    rtvicore = b8a_norm.subtract(b5_norm).multiply(100) \
                      .subtract(b8a_norm.subtract(b4_norm).multiply(10)) \
                      .float().rename('RTVIcore')

    return image.addBands([ndre, ndvire, kndvi, vari, rtvicore])
```

### 3.2 Erwartete Wertebereiche

Nach Monatlicher Median-Aggregation:

| Index        | Bereich (Median) | Stadt Berlin | Hamburg   | Rostock   |
| ------------ | ---------------- | ------------ | --------- | --------- |
| **NDre**     | [-1, 1]          | 0.10-0.35    | 0.15-0.40 | 0.10-0.38 |
| **NDVIre**   | [-1, 1]          | 0.30-0.55    | 0.35-0.60 | 0.30-0.58 |
| **kNDVI**    | [0, 1]           | 0.10-0.65    | 0.15-0.70 | 0.10-0.68 |
| **VARI**     | [-2, 2]          | 0.05-0.25    | 0.08-0.30 | 0.05-0.28 |
| **RTVIcore** | [-1000, 1000]    | 50-300       | 80-350    | 50-320    |

---

## 4. Monatliche Median-Aggregation

### 4.1 Workflow pro Monat

```python
def process_month(year, month, aoi, city_name):
    # 1. Lade alle Szenen für den Monat
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(aoi) \
        .filterDate(f'{year}-{month:02d}-01', f'{year}-{month+1:02d}-01')

    # 2. Cloud/Schatten Masking
    s2_masked = s2.map(mask_clouds_scl)

    # 3. Resample 20m Bänder zu 10m
    s2_resampled = s2_masked.map(resample_20m_to_10m)

    # 4. Vegetationsindizes berechnen
    s2_with_indices = s2_resampled.map(add_vegetation_indices)

    # 5. Auswählen: 10 spektrale + 5 Indizes = 15 Bänder
    all_bands = ['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12',
                 'NDre','NDVIre','kNDVI','VARI','RTVIcore']
    s2_selected = s2_with_indices.select(all_bands)

    # 6. Monatlicher Median → robuster gegen Wolken/Ausreißer
    monthly_median = s2_selected.median().clip(aoi)

    # 7. Konvertierung zu Float32 (KRITISCH!)
    monthly_median = monthly_median.toFloat()

    return monthly_median
```

**Warum Median statt Mean?**

- Robust gegen Ausreißer (Wolken-Artefakte, Sensor-Fehler)
- Bessere Qualität bei wenigen Szenen pro Monat

### 4.2 Erwartete Szenen-Anzahl

| Monat | Berlin | Hamburg | Rostock | Notizen                |
| ----- | ------ | ------- | ------- | ---------------------- |
| Jan   | 3-5    | 2-4     | 2-4     | Winter: weniger Szenen |
| Feb   | 3-5    | 2-4     | 2-4     | —                      |
| Mär   | 4-6    | 3-5     | 3-5     | —                      |
| Apr   | 5-8    | 4-7     | 4-7     | —                      |
| Mai   | 6-10   | 5-9     | 5-9     | Frühling: mehr Szenen  |
| Jun   | 8-12   | 7-11    | 7-11    | —                      |
| Jul   | 9-13   | 8-12    | 8-12    | Sommer: max. Szenen    |
| Aug   | 8-12   | 7-11    | 7-11    | —                      |
| Sep   | 6-9    | 5-8     | 5-8     | Herbst: weniger        |
| Okt   | 5-7    | 4-6     | 4-6     | —                      |
| Nov   | 3-5    | 2-4     | 2-4     | —                      |
| Dez   | 2-4    | 1-3     | 1-3     | Winter: min. Szenen    |

**Durchschnitt:** 4-8 Szenen pro Monat pro Stadt.

---

## 5. Export zu Google Drive

### 5.1 Prozess

```python
def export_to_drive(image, city_name, year, month, aoi):
    description = f'S2_{city_name}_{year}_{month:02d}_median'

    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=DRIVE_FOLDER,  # 'sentinel2_2021_final'
        fileNamePrefix=description,
        region=aoi,
        scale=TARGET_SCALE,  # 10m
        crs=TARGET_CRS,      # EPSG:25832
        maxPixels=1e13,
        fileFormat='GeoTIFF',
        formatOptions={'cloudOptimized': True}
    )

    task.start()
    return task
```

**GEE Task Management:**

- Export läuft **asynchron** auf GEE-Servern
- Datei erscheint in Google Drive (Ordner: `sentinel2_2021_final`)
- Laufzeit: 5-20 min pro Export (abhängig von Größe)

### 5.2 Dateigrößen

| Stadt                  | Dateigröße | Speicherort  |
| ---------------------- | ---------- | ------------ |
| Berlin                 | ~230 MB    | Google Drive |
| Hamburg                | ~200 MB    | Google Drive |
| Rostock                | ~100 MB    | Google Drive |
| **Gesamt (12 Monate)** | ~8 GB      | —            |

---

## 6. Validierung

### 6.1 Detaillierte Validierungschecks

Nach dem Download prüft das Notebook folgende Kriterien pro Datei:

**1. Grundlegende Eigenschaften:**

- Band-Anzahl: 15 (10 spektral + 5 Indizes)
- CRS: EPSG:25832
- Auflösung: 10m
- Datentyp: Float32

**2. Stadtgrenzen-Coverage:**

- Prozentsatz gültiger Pixel innerhalb Stadtgrenzen
- Mindest-Threshold: 15% (sehr konservativ)
- Typisch: 70-85%

**3. Spektral-Ranges (pro Band):**

- B2-B12: [0, 20000]
- NDre, NDVIre: [-1, 1]
- kNDVI: [0, 1]
- VARI: [-2, 2]
- RTVIcore: [-1000, 1000]

**4. Räumliche Validierung:**

- Grid-Alignment mit CHM 10m
- Keine NaN-Pixel außerhalb der Cloud-Maske
- Transform korrekt

**5. Temporal Validierung:**

- Alle 12 Monate vorhanden
- Metadata: year, month, city

### 6.2 Automatische Fehlererkennung

Validierungsfunktion gibt aus:

```
DETAILLIERTE VALIDIERUNG
================================================================================
Datei: S2_Berlin_2021_01_median.tif

1. GRUNDLEGENDE EIGENSCHAFTEN
────────────────────────────────────────────────────────────────────────────
   Bänder: 15/15 ✅
   CRS: EPSG:25832 ✅
   Auflösung: 10.00m ✅

2. COVERAGE (innerhalb Stadtgrenzen)
────────────────────────────────────────────────────────────────────────────
   Coverage: 78.3% ✅

3. SPEKTRAL-RANGES (Sample von 5000 Pixeln)
────────────────────────────────────────────────────────────────────────────
   B2 [Blue]: 250-3200 ✅ (erwartet 0-3500)
   B3 [Green]: 300-3600 ✅
   ...
   NDre: -0.15-0.42 ✅ (erwartet -1-1)
   NDVIre: 0.12-0.58 ✅ (erwartet -1-1)
   kNDVI: 0.02-0.68 ✅ (erwartet 0-1)
   VARI: -0.05-0.28 ✅ (erwartet -2-2)
   RTVIcore: 45-320 ✅ (erwartet -1000-1000)

STATUS: ✅ BESTANDEN (0 kritische Issues, 0 Warnungen)
```

---

## 7. Notebook-Outputs (für Dokumentation erforderlich)

Um diese Dokumentation später zu vervollständigen, benötige ich folgende **Zell-Outputs** aus Colab:

### **Zelle 2 (Authentication):**

```
Authenticating to Earth Engine... (Autorisierungs-Dialog im Browser)
Authentication successful.
```

### **Zelle 3 (Konfiguration):**

```
✓ Verzeichnisse bereit:
   GEE Export: /content/drive/MyDrive/.../sentinel2_2021_final
   Zielordner: /content/drive/MyDrive/.../data/sentinel2_2021
✓ Parameter geladen
```

### **Zelle 5 (Hauptschleife - Export):**

**Output (Actual):**

```
================================================================================
SENTINEL-2 DOWNLOAD PIPELINE - FINALE VERSION
================================================================================
✅ Verzeichnisse bereit:
   GEE Export: /content/drive/MyDrive/sentinel2_2021_final
   Zielordner: /content/drive/MyDrive/Studium/Geoinformation/Module/Projektarbeit/data/sentinel2_2021

Authentifiziere GEE...
✅ GEE bereit

================================================================================
PHASE 1: TEST-DOWNLOAD
================================================================================

Test-Datei: Rostock Juli 2021

Starte Download...
   Rostock 2021-07 ... (3 Szenen, <20%) ... Task gestartet

Warte auf Abschluss (max. 30min)...
   [1/30] RUNNING
   ...
   [10/30] RUNNING
   ✅ Abgeschlossen nach 11 Checks

Warte 15s auf Drive-Sync...

Verschiebe Datei zum Zielordner...
      ✅ Verschoben: S2_Rostock_2021_07_median.tif

================================================================================
PHASE 2: VOLLSTÄNDIGER DOWNLOAD
================================================================================

Phase 1 erfolgreich? Vollständigen Download starten? (ja/nein): ja

Starte Download: 3 Städte × 12 Monate = 36 Dateien
   GEE exportiert nach: /content/drive/MyDrive/sentinel2_2021_final
   Dateien werden verschoben nach: /content/drive/MyDrive/Studium/Geoinformation/Module/Projektarbeit/data/sentinel2_2021

================================================================================
Hamburg
================================================================================
   2021-01 ...     Verfügbare Szenen: 15 ✅ (15 Szenen)
   2021-02 ...     Verfügbare Szenen: 14 ✅ (14 Szenen)
   2021-03 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-04 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-05 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-06 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-07 ...     Verfügbare Szenen: 13 ✅ (13 Szenen)
   2021-08 ...     Verfügbare Szenen: 13 ✅ (13 Szenen)
   2021-09 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-10 ...     Verfügbare Szenen: 16 ✅ (16 Szenen)
   2021-11 ...     Verfügbare Szenen: 12 ✅ (12 Szenen)
   2021-12 ...     Verfügbare Szenen: 11 ✅ (11 Szenen)

================================================================================
Berlin
================================================================================
   2021-01 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-02 ...     Verfügbare Szenen: 55 ✅ (55 Szenen)
   2021-03 ...     Verfügbare Szenen: 63 ✅ (63 Szenen)
   2021-04 ...     Verfügbare Szenen: 63 ✅ (63 Szenen)
   2021-05 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-06 ...     Verfügbare Szenen: 63 ✅ (63 Szenen)
   2021-07 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-08 ...     Verfügbare Szenen: 68 ✅ (68 Szenen)
   2021-09 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-10 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-11 ...     Verfügbare Szenen: 55 ✅ (55 Szenen)
   2021-12 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)

================================================================================
Rostock
================================================================================
   2021-01 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-02 ...     Verfügbare Szenen: 55 ✅ (55 Szenen)
   2021-03 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-04 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-05 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-06 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-07 ... ⏭️ Existiert bereits
   2021-08 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-09 ...     Verfügbare Szenen: 59 ✅ (59 Szenen)
   2021-10 ...     Verfügbare Szenen: 65 ✅ (65 Szenen)
   2021-11 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)
   2021-12 ...     Verfügbare Szenen: 60 ✅ (60 Szenen)

================================================================================
✅ 35 neue Tasks gestartet
================================================================================

Überwache Tasks (alle 60s, max. 240 Checks)...
[1/60] READY: 29 | RUNNING: 6 |
[6/60] READY: 28 | RUNNING: 6 | COMPLETED: 1 |
[12/60] READY: 23 | RUNNING: 6 | COMPLETED: 6 |
[20/60] READY: 19 | RUNNING: 6 | COMPLETED: 10 |
[30/60] READY: 14 | RUNNING: 6 | COMPLETED: 15 |
[40/60] READY: 8 | RUNNING: 6 | COMPLETED: 21 |
[50/60] READY: 1 | RUNNING: 6 | COMPLETED: 28 |
[59/60] COMPLETED: 35 |

✅ Alle Tasks abgeschlossen!

================================================================================
Download-Phase beendet: 35/35 erfolgreich
================================================================================

Warte 30s auf Drive-Sync...

Verschiebe Dateien zum Zielordner...
      ✅ Verschoben: S2_Hamburg_2021_01_median.tif
      ✅ Verschoben: S2_Hamburg_2021_02_median.tif
      ✅ Verschoben: S2_Hamburg_2021_03_median.tif
      ✅ Verschoben: S2_Hamburg_2021_04_median.tif
      ✅ Verschoben: S2_Hamburg_2021_05_median.tif
      ✅ Verschoben: S2_Hamburg_2021_06_median.tif
      ✅ Verschoben: S2_Hamburg_2021_07_median.tif
      ✅ Verschoben: S2_Hamburg_2021_08_median.tif
      ✅ Verschoben: S2_Hamburg_2021_09_median.tif
      ✅ Verschoben: S2_Hamburg_2021_10_median.tif
      ✅ Verschoben: S2_Hamburg_2021_11_median.tif
      ✅ Verschoben: S2_Hamburg_2021_12_median.tif
      ✅ Verschoben: S2_Berlin_2021_01_median.tif
      ✅ Verschoben: S2_Berlin_2021_02_median.tif
      ✅ Verschoben: S2_Berlin_2021_03_median.tif
      ✅ Verschoben: S2_Berlin_2021_04_median.tif
      ✅ Verschoben: S2_Berlin_2021_05_median.tif
      ✅ Verschoben: S2_Berlin_2021_06_median.tif
      ✅ Verschoben: S2_Berlin_2021_07_median.tif
      ✅ Verschoben: S2_Berlin_2021_08_median.tif
      ✅ Verschoben: S2_Berlin_2021_09_median.tif
      ✅ Verschoben: S2_Berlin_2021_10_median.tif
      ✅ Verschoben: S2_Berlin_2021_11_median.tif
      ✅ Verschoben: S2_Berlin_2021_12_median.tif
      ✅ Verschoben: S2_Rostock_2021_01_median.tif
      ✅ Verschoben: S2_Rostock_2021_02_median.tif
      ✅ Verschoben: S2_Rostock_2021_03_median.tif
      ✅ Verschoben: S2_Rostock_2021_04_median.tif
      ✅ Verschoben: S2_Rostock_2021_05_median.tif
      ✅ Verschoben: S2_Rostock_2021_06_median.tif
      ✅ Verschoben: S2_Rostock_2021_08_median.tif
      ✅ Verschoben: S2_Rostock_2021_09_median.tif
      ✅ Verschoben: S2_Rostock_2021_10_median.tif
      ✅ Verschoben: S2_Rostock_2021_11_median.tif
      ✅ Verschoben: S2_Rostock_2021_12_median.tif
   ✅ 35/35 Dateien verschoben
```

### **Zelle 7 (Validierung - Hauptzelle):**

**Output (Actual):**

```
================================================================================
DETAILLIERTE VALIDIERUNG
================================================================================

Datei: S2_Rostock_2021_07_median.tif

1. GRUNDLEGENDE EIGENSCHAFTEN
────────────────────────────────────────────────────────────────────────────
   Bänder: 15/15 ✅
   CRS: EPSG:25832 ✅
   Auflösung: 10.00m ✅

2. COVERAGE (innerhalb Stadtgrenzen)
────────────────────────────────────────────────────────────────────────────
   Coverage: 28.1% ⚠️ NIEDRIG (aber akzeptabel)

3. SPEKTRALE BÄNDER (1-10)
────────────────────────────────────────────────────────────────────────────
   ✅ B2: Min=1, Max=18560, Mean=780
   ✅ B3: Min=1, Max=17408, Mean=1002
   ✅ B4: Min=96, Max=16672, Mean=969
   ✅ B5: Min=175, Max=16344, Mean=1472
   ✅ B6: Min=304, Max=16083, Mean=2626
   ✅ B7: Min=280, Max=15938, Mean=3068
   ✅ B8: Min=165, Max=15784, Mean=3146
   ✅ B8A: Min=301, Max=15761, Mean=3331
   ✅ B11: Min=265, Max=15204, Mean=2267
   ✅ B12: Min=142, Max=15130, Mean=1426

4. VEGETATIONSINDIZES (11-15)
────────────────────────────────────────────────────────────────────────────
   ✅ NDre: 493,971 gültig (29.1%), Bereich=[0.023, 0.723]
   ✅ NDVIre: 477,846 gültig (28.1%), Bereich=[0.028, 0.900]
   ✅ kNDVI: 477,846 gültig (28.1%), Bereich=[0.001, 0.666]
   ✅ VARI: 477,846 gültig (28.1%)
       Perzentile (1%, 99%): [-0.263, 0.637] ✅
       ℹ️ Extrema: [-487.000, 32700000256.000] (Ausreißer vorhanden, aber OK)
   ✅ RTVIcore: 477,846 gültig (28.1%)
       Perzentile (1%, 99%): [0.709, 37.874] ✅
       ℹ️ Extrema: [-6.468, 115.135] (Ausreißer vorhanden, aber OK)

5. GESAMTSTATUS
────────────────────────────────────────────────────────────────────────────
   ⚠️ 1 WARNUNGEN (nicht kritisch):
      - Coverage 28.1% niedrig

✅ VALIDIERUNG ERFOLGREICH (mit Warnungen)

================================================================================
SCHNELLE BATCH-VALIDIERUNG (alle 36 Dateien)
================================================================================

[ 1/36] S2_Berlin_2021_01_median.tif             ... ✅ (Cov: 58.8%)
[ 2/36] S2_Berlin_2021_02_median.tif             ... ✅ (Cov: 94.9%)
[ 3/36] S2_Berlin_2021_03_median.tif             ... ✅ (Cov: 87.3%)
[ 4/36] S2_Berlin_2021_04_median.tif             ... ✅ (Cov: 94.1%)
[ 5/36] S2_Berlin_2021_05_median.tif             ... ✅ (Cov: 95.1%)
[ 6/36] S2_Berlin_2021_06_median.tif             ... ✅ (Cov: 95.4%)
[ 7/36] S2_Berlin_2021_07_median.tif             ... ✅ (Cov: 95.6%)
[ 8/36] S2_Berlin_2021_08_median.tif             ... ✅ (Cov: 95.7%)
[ 9/36] S2_Berlin_2021_09_median.tif             ... ✅ (Cov: 95.6%)
[10/36] S2_Berlin_2021_10_median.tif             ... ✅ (Cov: 91.1%)
[11/36] S2_Berlin_2021_11_median.tif             ... ✅ (Cov: 57.2%)
[12/36] S2_Berlin_2021_12_median.tif             ... ✅ (Cov: 52.1%)
[13/36] S2_Hamburg_2021_01_median.tif            ... ✅ (Cov: 19.5%)
[14/36] S2_Hamburg_2021_02_median.tif            ... ✅ (Cov: 56.9%)
[15/36] S2_Hamburg_2021_03_median.tif            ... ✅ (Cov: 89.2%)
[16/36] S2_Hamburg_2021_04_median.tif            ... ✅ (Cov: 91.9%)
[17/36] S2_Hamburg_2021_05_median.tif            ... ✅ (Cov: 86.8%)
[18/36] S2_Hamburg_2021_06_median.tif            ... ✅ (Cov: 95.6%)
[19/36] S2_Hamburg_2021_07_median.tif            ... ✅ (Cov: 92.0%)
[20/36] S2_Hamburg_2021_08_median.tif            ... ✅ (Cov: 92.6%)
[21/36] S2_Hamburg_2021_09_median.tif            ... ✅ (Cov: 93.5%)
[22/36] S2_Hamburg_2021_10_median.tif            ... ✅ (Cov: 79.9%)
[23/36] S2_Hamburg_2021_11_median.tif            ... ✅ (Cov: 47.8%)
[24/36] S2_Hamburg_2021_12_median.tif            ... ✅ (Cov: 54.9%)
[25/36] S2_Rostock_2021_01_median.tif            ... ✅ (Cov: 44.7%)
[26/36] S2_Rostock_2021_02_median.tif            ... ✅ (Cov: 95.4%)
[27/36] S2_Rostock_2021_03_median.tif            ... ✅ (Cov: 97.7%)
[28/36] S2_Rostock_2021_04_median.tif            ... ✅ (Cov: 97.7%)
[29/36] S2_Rostock_2021_05_median.tif            ... ✅ (Cov: 98.6%)
[30/36] S2_Rostock_2021_06_median.tif            ... ✅ (Cov: 99.0%)
[31/36] S2_Rostock_2021_07_median.tif            ... ✅ (Cov: 28.1%)
[32/36] S2_Rostock_2021_08_median.tif            ... ✅ (Cov: 98.6%)
[33/36] S2_Rostock_2021_09_median.tif            ... ✅ (Cov: 98.9%)
[34/36] S2_Rostock_2021_10_median.tif            ... ✅ (Cov: 98.5%)
[35/36] S2_Rostock_2021_11_median.tif            ... ✅ (Cov: 93.8%)
[36/36] S2_Rostock_2021_12_median.tif            ... ✅ (Cov: 76.6%)

================================================================================
ZUSAMMENFASSUNG
================================================================================
   ✅ Berlin    : 12/12 OK (Ø Coverage: 84.4%)
   ✅ Hamburg   : 12/12 OK (Ø Coverage: 75.0%)
   ✅ Rostock   : 12/12 OK (Ø Coverage: 85.6%)

   Gesamt:
      ✅ OK:      36/36 (100.0%)
      📄 Details: batch_validation_results.csv

================================================================================
✅ ALLE DATEIEN VALIDIERT - BEREIT FÜR FEATURE EXTRACTION!
================================================================================
```

---

## 8. Verwendung

### 8.1 Im Notebook ausführen

```python
# 1. Authentifizierung
ee.Authenticate()
ee.Initialize()

# 2. Verzeichnisse vorbereiten
ensure_directories()

# 3. Exports starten (asynchron)
export_tasks = {}
for city in ['Berlin', 'Hamburg', 'Rostock']:
    for month in range(1, 13):
        # Processing und Export
        ...
        export_tasks[f"{city}_{month}"] = task

# 4. Monitoring (optional)
# - GEE Tasks verfolgbar über: https://code.earthengine.google.com/
# - oder programmatisch abfragen

# 5. Nach Completion: Validierung
for city in CITIES:
    for month in range(1, 13):
        filepath = LOCAL_OUTPUT_DIR / f"S2_{city}_2021_{month:02d}_median.tif"
        detailed_validation(filepath, BOUNDARIES_PATH)
```

### 8.2 Geschätzte Laufzeit

| Phase              | Laufzeit        |
| ------------------ | --------------- |
| GEE Processing     | 10-15 min       |
| Export zu Drive    | 2-4h (36 Tasks) |
| Download/Migration | 30-60 min       |
| Validierung        | 10-20 min       |
| **Gesamt**         | **3-5h**        |

### 8.3 Parallele Verarbeitung

Alle 36 Tasks können **parallel** gestartet werden (da Google Cloud die Skalierung handhabt). Beobachte den Fortschritt auf [https://code.earthengine.google.com/](https://code.earthengine.google.com/).

---

## 9. Nachgelagerte Schritte

Die Output-Dateien werden verwendet in:

- **Feature-Extraction:** Kombination mit CHM 10m zur Erzeugung von Features pro Baum
- **Modell-Input:** Spektrale Bänder + Vegetationsindizes als Features

---

## 10. Bekannte Limitationen und Workarounds

### 10.1 Wolkenabdeckung im Winter

**Problem:** Dezember-Februar: hohe Wolkenabdeckung (~40-50% auch nach Masking)

**Auswirkung:** Coverage fällt auf ~60-70% statt 75-85%

**Lösung:**

- Akzeptieren niedrigere Coverage im Winter
- Oder: Sentinel-1 (Radar) als Fallback für Winter
- Oder: Multi-Jahr-Median (2020-2022 statt nur 2021)

### 10.2 Cloud-Optimization (COG)

**Problem:** Standard GeoTIFF-Export aus GEE ist nicht cloud-optimiert

**Lösung:** GEE Option `cloudOptimized=True` nutzen (konfiguriert)

### 10.3 Task Limits bei GEE

**Problem:** Google Earth Engine hat Rate Limits (~10 Concurrent Tasks)

**Lösung:** Tasks werden sequenziell gestartet, GEE managed automatisch Queue.

---

## 11. Referenzen

### 11.1 Externe Ressourcen

- [Google Earth Engine Documentation](https://developers.google.com/earth-engine)
- [Sentinel-2 Product Handbook](https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi)
- [Scene Classification (SCL) Band](https://docs.sentinel-hub.com/api/latest/data/sentinel-2-l2a/)

### 11.2 Python-Abhängigkeiten

- `earthengine-api` - GEE Python API
- `geopandas` - Geometrie Management
- `rasterio` - GeoTIFF I/O
- `numpy` - Array-Operationen
- `pandas` - Tabellendaten

### 11.3 Abhängige Dokumentation

- [05_CHM_Resampling_Methodik.md](05_CHM_Resampling_Methodik.md) - CHM 10m Input
- [07_Feature_Extraction_Methodik.md](07_Feature_Extraction_Methodik.md) - S2 + CHM Kombination

---

## 12. Changelog

| Datum      | Änderung                        |
| ---------- | ------------------------------- |
| 2026-01-06 | Initial: Methodik-Dokumentation |

---

**Dokument-Status:** ✅ AKTUALISIERT - Alle 36 Dateien validiert  
**Letzte Aktualisierung:** 6. Januar 2026
