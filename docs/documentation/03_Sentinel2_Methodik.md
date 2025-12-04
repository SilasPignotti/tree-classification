# Datenakquise: Sentinel-2 - Methodik und Dokumentation

**Projektphase:** Datenakquise
**Datum:** 4. Dezember 2025
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung und Verarbeitung von Sentinel-2 Satellitendaten für drei deutsche Städte: Hamburg, Berlin und Rostock. Diese Daten bilden die Grundlage für die spektrale Charakterisierung von Bäumen und deren Umgebung und dienen als Input für maschinelle Lernmodelle zur Baumklassifikation.

### 1.1 Zieldaten

**Sentinel-2 Monatskompositionen:**

- Format: GeoTIFF (Cloud-optimiertes Format)
- Koordinatensystem: EPSG:25832 (ETRS89 / UTM Zone 32N)
- Auflösung: 10m × 10m
- Zeitraum: Monatliche Median-Kompositionen für 2021
- Bänder: 10 Spektralbänder + 5 Vegetationsindizes

**Spektralbänder:**

- B02 (Blue), B03 (Green), B04 (Red) - 10m native
- B05-B07 (Red Edge 1-3) - 20m → 10m resampled
- B08 (NIR), B8A (Narrow NIR) - 10m/20m → 10m resampled
- B11-B12 (SWIR 1-2) - 20m → 10m resampled

**Vegetationsindizes:**

- NDre: (B8A - B05) / (B8A + B05)
- NDVIre: (B8A - B04) / (B8A + B04)
- kNDVI: tanh((B08 - B04)² / (B08 + B04)²)
- VARI: (B03 - B04) / (B03 + B04 - B02)
- RTVIcore: 100×(B8A - B05) - 10×(B8A - B04)

### 1.2 Zielstädte

1. **Hamburg** - Trainingsdaten (gesamte Stadt + 500m Buffer)
2. **Berlin** - Trainingsdaten (gesamte Stadt + 500m Buffer)
3. **Rostock** - Testdaten als Proxy für Wismar (gesamte Stadt + 500m Buffer)

### 1.3 Pipeline-Übersicht

Die Sentinel-2 Pipeline besteht aus drei Hauptschritten:

1. **Cloud-Verarbeitung** - openEO-basierte Datenverarbeitung
2. **Lokale Verarbeitung** - Reprojektion und Indexberechnung
3. **Validierung** - Qualitätskontrolle und Coverage-Analyse

---

## 2. Datenquellen

### 2.1 Copernicus Data Space Ecosystem

**Quelle:** Copernicus Data Space Ecosystem (CDSE)
**Service:** openEO API
**Backend:** https://openeo.dataspace.copernicus.eu
**Datensatz:** SENTINEL2_L2A

**Datensatz-Details:**

- **Aktualität:** Laufend aktualisiert (L2A Produkte)
- **Auflösung:** 10m (B02-B04, B08), 20m (B05-B07, B8A, B11-B12)
- **Spektralbänder:** Alle 13 Bänder verfügbar
- **Zusatzbänder:** SCL (Scene Classification), CLD (Cloud Probability)
- **Abdeckung:** Global, kostenlos

**Vorteile dieser Datenquelle:**

- Cloud-native Verarbeitung (kein lokaler Download großer Datenmengen)
- Automatische atmosphärische Korrektur (L2A)
- Standardisierte APIs und Prozesse
- Kostenlos und frei verfügbar

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. Stadtgrenzen laden (500m Buffer für Kontext)
2. Bounding Box berechnen (WGS84 für openEO)
3. openEO Job erstellen:
   ├── Sentinel-2 L2A Collection laden
   ├── Räumliche und zeitliche Filterung
   ├── Cloud-Masking mit SCL-Band
   ├── Band-Auswahl und Resampling (20m → 10m)
   ├── Temporale Median-Aggregation
4. Batch-Job ausführen (asynchron)
5. Lokale Nachverarbeitung:
   ├── Reprojektion zu EPSG:25832
   ├── Vegetationsindizes berechnen
   ├── GeoTIFF speichern (LZW-Kompression)
6. Validierung und Coverage-Report
```

### 3.2 Cloud-Verarbeitung (openEO)

**Datenauswahl:**

```python
s2_cube = connection.load_collection(
    "SENTINEL2_L2A",
    spatial_extent=bbox,  # WGS84 Bounding Box
    temporal_extent=[start_date, end_date],  # Monatsbereich
    bands=SPECTRAL_BANDS + ["SCL"]
)
```

**Cloud-Masking:**

```python
# SCL-Werte: 3=Cloud shadows, 8=Cloud medium, 9=Cloud high, 10=Thin cirrus
scl = s2_cube.band("SCL")
mask = scl.isin([3, 8, 9, 10]).logical_not()
s2_masked = s2_cube.mask(~mask)
```

**Temporale Aggregation:**

```python
s2_monthly = (
    s2_masked
    .filter_bands(SPECTRAL_BANDS)
    .resample_spatial(resolution=10, method="bilinear")
    .reduce_dimension(dimension="t", reducer="median")
)
```

**Batch-Ausführung:**

```python
job = s2_monthly.execute_batch(
    out_format="GTiff",
    title=f"S2_{city_name}_{year}_{month:02d}",
    outputfile=output_path,
    job_options={"driver-memory": "4g", "executor-memory": "4g"}
)
```

### 3.3 Lokale Nachverarbeitung

**Reprojektion:**

```python
dst_crs = CRS.from_string("EPSG:25832")
transform, width, height = calculate_default_transform(
    src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=10
)
```

**Vegetationsindizes-Berechnung:**

```python
indices = {
    "NDre": (b8a - b05) / (b8a + b05 + eps),
    "NDVIre": (b8a - b04) / (b8a + b04 + eps),
    "kNDVI": np.tanh(((b08 - b04) / (b08 + b04 + eps)) ** 2),
    "VARI": (b03 - b04) / (b03 + b04 - b02 + eps),
    "RTVIcore": 100 * (b8a - b05) - 10 * (b8a - b04),
}
```

**GeoTIFF-Optimierung:**

```python
dst_meta.update({
    "crs": dst_crs,
    "transform": transform,
    "count": 15,  # 10 Spektral + 5 Indizes
    "dtype": "float32",
    "compress": "lzw",
    "predictor": 2,
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
})
```

### 3.4 Validierung

**Coverage-Berechnung:**

```python
city_mask = geometry_mask(
    city_geometry.geometry,
    out_shape=(src.height, src.width),
    transform=src.transform,
    invert=True
)
pixels_with_data_in_city = np.sum(valid_mask & city_mask)
coverage_percent = 100 * pixels_with_data_in_city / pixels_in_city
```

---

## 4. Herausforderungen und Lösungen

### 4.1 Cloud-Verarbeitung

**Problem:** Komplexe openEO-API und asynchrone Job-Verarbeitung.

**Lösung:** Robuste Fehlerbehandlung und Job-Monitoring mit automatischen Retries.

### 4.2 Speicheroptimierung

**Problem:** Große Raster-Dateien (100-160 MB pro Monat/Stadt).

**Lösung:** LZW-Kompression, Tiling (512×512), Predictor 2 für Float32-Daten.

### 4.3 CRS-Konsistenz

**Problem:** openEO verwendet WGS84, Zielsystem ist UTM.

**Lösung:** Automatische Reprojektion mit bilinearer Interpolation.

### 4.4 Cloud-Masking

**Problem:** Balance zwischen zu aggressivem und zu permissivem Cloud-Masking.

**Lösung:** SCL-basierte Maskierung der problematischsten Klassen (Shadows, Medium/High Clouds, Cirrus).

---

## 5. Validierung

### 5.1 Validierungskriterien

**Download-Validierung:**

- [ ] 15 Bänder (10 Spektral + 5 Indizes)
- [ ] EPSG:25832 Koordinatensystem
- [ ] 10m × 10m Auflösung
- [ ] Float32 Datentyp
- [ ] Keine NoData-Werte außerhalb Stadtgebiet

**Coverage-Validierung:**

- [ ] Mindestens 50% Coverage innerhalb Stadtgrenzen
- [ ] Realistische Wertebereiche pro Band
- [ ] Keine systematischen Artefakte

### 5.2 Validierungsergebnisse

**Coverage-Statistiken (2021):**

| Stadt   | Durchschnitt Coverage | Min Coverage | Max Coverage | Bemerkung                             |
| ------- | --------------------- | ------------ | ------------ | ------------------------------------- |
| Berlin  | 98.1%                 | 89.7% (01)   | 100%         | Durchgehend exzellent                 |
| Hamburg | 84.6%                 | 44.7% (11)   | 100%         | November kritisch, aber meistens gut  |
| Rostock | 91.2%                 | 5.9% (01)    | 100%         | Januar problematisch (nördl., Winter) |

**Dateigrößen (tatsächlich):**

- Berlin: 1.76-1.94 GB pro Monat (durchschnittlich 1.91 GB)
- Hamburg: 0.52-1.09 GB pro Monat (durchschnittlich 0.89 GB)
- Rostock: 0.068-0.305 GB pro Monat (durchschnittlich 0.29 GB)

**Band-Statistiken (Beispiel Berlin Januar 2021):**

| Band   | Min     | Max     | Mean      | Bemerkung        |
| ------ | ------- | ------- | --------- | ---------------- |
| B02    | -594.23 | 19400.0 | 478.57    | Blue             |
| B04    | -594.23 | 19400.0 | 478.57    | Red              |
| B08    | -594.23 | 19400.0 | 478.57    | NIR              |
| NDVIre | -1.0    | 1.0     | 0.24-0.27 | Vegetation Index |

---

## 6. Outputs

### 6.1 Finale Datenprodukte

**Dateistruktur:**

```
data/sentinel2/
├── berlin/
│   ├── S2_2021_01_median.tif ... S2_2021_12_median.tif (12 Dateien, ✓ 100% vollständig)
├── hamburg/
│   ├── S2_2021_01_median.tif ... S2_2021_12_median.tif (12 Dateien, ✓ 100% vollständig)
├── rostock/
│   ├── S2_2021_01_median.tif ... S2_2021_12_median.tif (12 Dateien, ✓ 100% vollständig)
└── coverage_report.csv (Validierungsbericht mit allen Metriken)
```

**GeoTIFF-Spezifikation:**

| Eigenschaft | Wert                         |
| ----------- | ---------------------------- |
| Format      | GeoTIFF                      |
| Bänder      | 15 (10 Spektral + 5 Indizes) |
| Datentyp    | Float32                      |
| NoData      | -32768.0 (Standard float32)  |
| Kompression | LZW                          |
| CRS         | EPSG:25832                   |
| Auflösung   | 10m × 10m                    |

### 6.2 Scripts

**Hauptscripts:**

- `scripts/sentinel2/download_sentinel2.py` - Download und Verarbeitung
- `scripts/sentinel2/validate_coverage.py` - Coverage-Analyse

**Konfiguration:** `scripts/config.py`

---

## 7. Technische Details

### 7.1 Verwendete Bibliotheken

**Python-Packages:**

- `openeo>=0.29.0` - openEO Client für Copernicus Data Space
- `geopandas>=1.0.1` - Geodaten-Verarbeitung
- `rasterio>=1.3.0` - Raster-Verarbeitung
- `numpy>=1.24.0` - Numerische Berechnungen

**openEO-Prozesse:**

- `load_collection` - Datensatz laden
- `mask` - Cloud-Masking
- `resample_spatial` - Auflösung angleichen
- `reduce_dimension` - Temporale Aggregation
- `execute_batch` - Asynchrone Verarbeitung

---

## 8. Referenzen

### 8.1 Datenquellen

- **Copernicus Data Space:** https://dataspace.copernicus.eu/
- **openEO:** https://openeo.org/
- **Sentinel-2 L2A:** https://sentinel.esa.int/web/sentinel/missions/sentinel-2

---

## 9. Anhang

### 9.1 Beispiel-Output (Berlin Januar 2021)

**Datei:** `data/sentinel2/berlin/S2_2021_01_median.tif`  
**Größe:** 1.76 GB  
**Coverage:** 89.7% (Januar 2021 war wolkenreich, ab März >99%)  
**Qualität:** ✓ 15 Bänder, 5063×4337 Pixel, EPSG:25832, Float32

**Band-Beschreibungen:**

1. B02 - Blue (490nm)
2. B03 - Green (560nm)
3. B04 - Red (665nm)
4. B05 - Red Edge 1 (705nm)
5. B06 - Red Edge 2 (740nm)
6. B07 - Red Edge 3 (783nm)
7. B08 - NIR (842nm)
8. B8A - Narrow NIR (865nm)
9. B11 - SWIR 1 (1610nm)
10. B12 - SWIR 2 (2190nm)
11. NDre - Normalized Difference Red Edge
12. NDVIre - Red Edge NDVI
13. kNDVI - Kernel NDVI
14. VARI - Visible Atmospherically Resistant Index
15. RTVIcore - Red Edge Triangle Vegetation Index

---

**Dokument-Ende**
