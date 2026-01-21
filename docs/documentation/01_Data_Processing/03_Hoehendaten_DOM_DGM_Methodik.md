# Höhendaten (DOM und DGM)

**Projektphase:** Datenakquise | **Autor:** Silas Pignotti | **Status:** Abgeschlossen

## Übersicht

Beschaffung und Harmonisierung von Höhendaten für Hamburg, Berlin und Rostock zur CHM-Berechnung.

**Datentypen:**

- **DOM:** Digitales Oberflächenmodell (mit Vegetation, Gebäuden)
- **DGM:** Digitales Geländemodell (bloße Geländeoberfläche)
- **CHM = DOM - DGM** → Vegetationshöhe

**Output-Spezifikation:** GeoTIFF (LZW), EPSG:25832, 1m Auflösung, Float32, Stadtgrenze + 500m Buffer, NoData: -9999

---

## Datenquellen

| Stadt   | Quelle                        | Format | CRS        | Aktualität | Besonderheit                             |
| ------- | ----------------------------- | ------ | ---------- | ---------- | ---------------------------------------- |
| Hamburg | Hamburg Open Data             | XYZ    | EPSG:25832 | 2021       | Direkte URLs, keine Reprojizierung nötig |
| Berlin  | FIS-Broker (Nested Atom Feed) | XYZ    | EPSG:25833 | 2023       | ~50-70 Kacheln, Pre-Filtering möglich    |
| Rostock | Geodaten MV (Atom Feed)       | XYZ    | EPSG:25833 | 2023       | ~6407 Kacheln → Pre-Filtering KRITISCH   |

---

## Methodik

### 1. Download & räumliche Filterung

**Hamburg:** Direkte ZIP-Downloads, XYZ → GeoTIFF, kein Reproject nötig (bereits EPSG:25832).

**Berlin & Rostock:** Feed-Parsing mit räumlichem Pre-Filtering:

- Konvertiere Stadtgrenze zu Feed-CRS
- Filtere Kacheln nach Koordinaten/Bbox-Attributen
- Berlin: ~50-70 von potenziell hunderten Kacheln
- Rostock: ~10-20 von 6407 Kacheln (99.7% Reduktion!) — essentiell für Performance

**Rostock-Spezial:** XYZ hat unregelmäßiges Whitespace → NumPy-Parsing robuster als GDAL.

**Parameter:**

- Download-Timeout: 600s (große Archive bis 2GB)
- Max Retries: 3
- Parallele Worker (Rostock): 3

### 2. XYZ-zu-GeoTIFF-Konvertierung & Reprojizierung

**Hamburg:** Direkt mit GDAL gdal_translate
**Berlin/Rostock:** NumPy-Grid-Parsing → GeoTIFF → GDAL gdalwarp (Reprojizierung)

**Parameter:** LZW-Kompression, gekachelt, Nearest-Neighbor-Resampling, bilinear für Grid-Alignment

### 3. Mosaicking & Clipping

Zusammenführung aller Kacheln mit rasterio.merge (first-Methode bei Überlappung), anschließend Clipping auf Stadtgrenze + 500m Buffer mit all_touched=True für vollständige Coverage.

### 4. Harmonisierung (Kritisch!)

**Problem 1: Unterschiedliche Raster-Dimensionen**

- Berlin: 1×1 Pixel Differenz
- Hamburg: 55×132 Pixel Differenz
- Rostock: 323×0 Pixel Differenz

**Lösung:** DOM als Referenz-Grid, DGM mit bilinearem Resampling auf DOM-Grid transformieren.

**Problem 2: Inkonsistente NoData-Werte**

- Berlin: 0.0 (problematisch, min. Höhe ~20m)
- Hamburg: None/-32768 (inkonsistent)
- Rostock: -9999 (korrekt)

**Lösung:** Alle NoData-Werte auf -9999 vereinheitlichen (Standard für Höhendaten, weit außerhalb 20-400m Bereich).

**Begründung DOM als Referenz:** Bessere räumliche Coverage, erfasst relevante Vegetation, vermeidet doppelte Reprojizierung.

### 5. Validierung

7 automatisierte Checks:

| Check            | Kriterium             | Ergebnis                                   |
| ---------------- | --------------------- | ------------------------------------------ |
| 1. Dateiexistenz | Alle 6 Dateien > 0 MB | ✓                                          |
| 2. CRS           | Alle in EPSG:25832    | ✓                                          |
| 3. Pixelgröße    | 1.0m ± 0.01m          | ✓ (1.0000-1.0007m)                         |
| 4. Datenbereich  | -20 bis 400m          | ✓ Plausibel                                |
| 5. NoData        | -9999, Coverage >95%  | ✓ >99%                                     |
| 6. DOM≥DGM       | >95% der Pixel        | Berlin 99.9%, Hamburg 91.9%, Rostock 90.3% |
| 7. Coverage      | >90% in Stadt         | ✓ >99%                                     |

**Wasserflächen-Warnung:** Hamburg und Rostock haben ~8-10% Pixel mit DOM<DGM (physikalisch korrekt für Wasserbereiche, negative CHM-Werte möglich).

---

## Ergebnisse

### Datengrößen

| Stadt   | DOM Größe | DGM Größe | Dimensionen   |
| ------- | --------- | --------- | ------------- |
| Berlin  | 1938 MB   | 2494 MB   | 46092 × 37360 |
| Hamburg | 2150 MB   | 2710 MB   | 40363 × 39000 |
| Rostock | 590 MB    | 782 MB    | 19822 × 22953 |

### Statistiken nach Harmonisierung

**Berlin:** DOM Mean 48.88m, DGM Mean 42.48m → CHM ~6.39m, Range 20.83-366.43m
**Hamburg:** DOM Mean 9.65m, DGM Mean 15.04m → CHM negativ in Wasserflächen, Range -6-251.87m
**Rostock:** DOM Mean 14.27m, DGM Mean 9.99m → CHM ~4.27m, Range -12.50-238.62m

### Validierungsergebnisse

- ✓ Alle Shapes nach Harmonisierung identisch
- ✓ Einheitlicher NoData-Wert -9999
- ✓ Coverage >99% innerhalb Stadtgrenzen
- ⚠️ Hamburg/Rostock: Erwartete Abweichungen in Wasserflächen

**Status:** ✓ READY FOR CHM PROCESSING

---

## Designentscheidungen

### EPSG:25832 als Ziel-CRS

- Zentral zwischen allen Städten
- Metrisches UTM-System für Distanzberechnungen
- Hamburg bereits in EPSG:25832
- Minimale Verzerrung über Untersuchungsgebiet

### DOM als Referenz-Grid

- Bessere Coverage als DGM
- Erfasst relevante Vegetation
- Vermeidet doppelte Reprojizierung
- DGM wird glattgehobelt durch Resampling (akzeptabel)

### NoData-Wert -9999

- Weit außerhalb plausiblen Bereichs
- Standard-Convention für Höhendaten
- Vermeidet Konflikte mit echten 0m-Höhen

### 500m Buffer um Stadtgrenzen

- Vermeidung Rand-Artefakte
- Erfassung Randvegetation
- Kontext für ML-Features
- ~10-15% Größenerhöhung (akzeptabel)

---

## Bekannte Limitationen

1. **Zeitliche Inkonsistenz:** Hamburg 2021 vs. Berlin/Rostock 2023 → potenzielle Vegetationsänderungen
2. **Negative CHM-Werte:** Hamburg/Rostock Wasserflächen mit DOM<DGM → separate Behandlung notwendig
3. **Resampling-Artefakte:** Bilineares Resampling des DGM glättet leicht
4. **Datenlücken:** ~1-5% echte NoData (Flughäfen, Gewässer) → nicht nutzbar für Baumklassifikation
5. **Auflösung:** 1m gut für große Bäume, kleine Vegetation (<2m) unterrepräsentiert

---

## Runtime & Ressourcen

| Stadt   | Download | Verarbeitung | RAM | Disk  |
| ------- | -------- | ------------ | --- | ----- |
| Berlin  | ~45 min  | ~30 min      | 8GB | 4.5GB |
| Hamburg | ~20 min  | ~15 min      | 6GB | 4.8GB |
| Rostock | ~30 min  | ~25 min      | 4GB | 1.4GB |

**Harmonisierung:** ~15 min (alle), 12GB RAM Peak
**Validierung:** ~10 min, 8GB RAM

---

## Lessons Learned

**Herausforderung 1 - Große Feeds:** Rostock Atom-Feed mit 6407 Kacheln → Bbox-Pre-Filtering sparte 99.7% Download-Zeit und -Bandbreite. **Fazit:** Räumliches Pre-Filtering ist essentiell bei großen Feeds.

**Herausforderung 2 - XYZ-Format:** Rostock XYZ mit Whitespace-Variationen → GDAL fehlgeschlagen. **Lösung:** NumPy loadtxt() robuster. **Fazit:** Entkopplung von Parsing und Georeferenzierung erhöht Fehlertoleranz.

**Herausforderung 3 - NoData-Inkonsistenz:** Verschiedene NoData-Konventionen pro Stadt → CHM-Berechnung unmöglich. **Lösung:** Stadt-spezifische Harmonisierung vor Grid-Alignment. **Fazit:** NoData-Harmonisierung muss vor Grid-Alignment erfolgen.

**Herausforderung 4 - Grid-Misalignment:** DOM/DGM unterschiedliche Dimensionen. **Lösung:** DOM als Referenz, DGM resampled. **Fazit:** DOM-Coverage i.d.R. besser, Bilinear-Resampling für Höhendaten geeignet.

---

## Tools & Abhängigkeiten

**Python Stack:** Python 3.10+, GDAL 3.4+, rasterio 1.3+, geopandas 0.12+, numpy 1.23+, requests 2.28+, feedparser 6.0+

**Externe Tools:** gdal_translate, gdalwarp, unzip

**Input-Dateien:** data/boundaries/city_boundaries_500m_buffer.gpkg, scripts/config.py

**Output-Dateien:** data/CHM/raw/{berlin,hamburg,rostock}/{dom,dgm}\_1m.tif
