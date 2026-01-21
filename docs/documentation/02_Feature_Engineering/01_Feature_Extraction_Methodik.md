# Feature Extraction: Multi-temporale Remote-Sensing Features für Baumklassifikation

**Projektphase:** Feature Engineering  
**Datum:** 10. Januar 2026  
**Autor:** Silas Pignotti  
**Notebook:** [`notebooks/02_feature_engineering/01_feature_extraction.ipynb`](../../../notebooks/02_feature_engineering/01_feature_extraction.ipynb)

---

## 1. Übersicht

### 1.1 Zweck

Dieses Dokument beschreibt die **komplette Pipeline** zur Extraktion von **multi-temporalen Remote-Sensing Features** für urbane Bäume in Berlin, Hamburg und Rostock. Für jeden Baum werden **280 Features** extrahiert und in standardisierten GeoPackages bereitgestellt:

- **CHM-Features (4):** Baumhöhe (aus Kataster), CHM-Mittelwert, CHM-Maximum, CHM-Standardabweichung
- **Sentinel-2 Zeit-Serie (276):** 10 spektrale Bänder + 13 Vegetationsindizes × 12 Monate (Jahr 2021)

**Ziel:** Erstellung eines standardisierten Feature-Sets für nachgelagerte Machine-Learning-Experimente zur automatisierten Baumarten-Klassifikation.

### 1.2 Zieldaten / Output

**GeoPackages (3 Städte × 2 Varianten = 6 Dateien):**

| Datei                                     | Bäume     | Features | Format | Verwendung                      |
| ----------------------------------------- | --------- | -------- | ------ | ------------------------------- |
| `trees_with_features_Berlin.gpkg`         | 842k      | 284      | GPKG   | ML-Training                     |
| `trees_with_features_Hamburg.gpkg`        | 178k      | 284      | GPKG   | ML-Training                     |
| `trees_with_features_Rostock.gpkg`        | 62k       | 284      | GPKG   | ML-Validierung/Test             |
| `trees_with_features_edge_filtered_20m_*` | reduziert | 284      | GPKG   | Robustness-Check (Kantenpunkte) |

**Metadata:**

- **Format:** GeoPackage (GPKG), WGS84/Web Mercator für Geometrie
- **CRS:** EPSG:25832 (ETRS89 / UTM zone 32N)
- **Koordinatensystem:** Punkte (Tree Point Locations)
- **Datentypen:** Float32 für spektrale Features, Integer/Text für Metadaten
- **NoData-Handling:** Fehlende Werte werden als `NaN` bewahrt (nicht interpoliert)
- **Attribute pro Baum:** `tree_id`, `city`, `tree_type`, `genus_latin`, `species_latin`, `height_m`, `geometry` + 280 Features

### 1.3 Untersuchungsgebiete / Zielstädte

1. **Berlin** – Trainingsdaten (~842k Bäume)
2. **Hamburg** – Trainingsdaten (~178k Bäume)
3. **Rostock** – Test/Validierungsdaten (~62k Bäume)

### 1.4 Workflow-Übersicht

**Pipeline-Phasen:**

1. **Datenladen:** Alle Baumkataster validieren → 1.08M+ Bäume
2. **CHM-Extraktion:** Baumhöhe + CHM-Statistiken (4 Features)
3. **Sentinel-2-Extraktion:** Monatliche Spektralbänder + Indizes (276 Features, 12 Monate)
4. **Qualitätskontrolle:** Feature-Vollständigkeit, NoData-Statistiken
5. **Output:** 6 GeoPackages (3 Städte × 2 Varianten) + Metadaten

---

## 2. Theoretische Grundlagen

### 2.1 Punkt-basierte Raster-Extraktion

Feature-Extraktion durch Sampling von Raster-Werten an exakten Baum-Positionen (Punkt-Geometrien):

$$\text{feature}_{tree_i} = \text{raster}(x_i, y_i)$$

**Methode:** Der Pixel-Wert wird verwendet, in dessen Zelle der Punkt fällt (keine Interpolation).

**NoData-Handling:** Werte außerhalb gültiger Rasterdaten → `NaN` (nicht interpoliert, für Downstream-Analysen verfügbar).

### 2.2 Zeitliche Konsistenz

Sentine-2 Extraktion nutzt **monatliche Median-Kompositionen für 2021** (Jan–Dez):

- Aggregation: Median über wolkenfreie Pixel (nach SCL-Masking)
- Garantiert Vergleichbarkeit zwischen Städten und phänologische Konsistenz

### 2.3 Feature-Dimensionalität

$$\text{Total} = 4 \text{ CHM} + (10 \text{ Bänder} + 13 \text{ Indizes}) \times 12 \text{ Monate} = 280 \text{ Features}$$

## 3. Datenquellen

### 3.1 Baumkataster (Input)

**Quelle:** Harmonisierte, korrigierte Kataster (siehe [02_Baumkataster_Methodik.md](02_Baumkataster_Methodik.md), [07_Baumkorrektur_Methodik.md](07_Baumkorrektur_Methodik.md))

**Erforderliche Spalten:** `tree_id`, `city`, `tree_type`, `genus_latin`, `species_latin`, `height_m`, `geometry` (Point)

**Dateien:**

- Standard: `trees_corrected_{Berlin,Hamburg,Rostock}.gpkg`
- Edge-gefiltert (20m Buffer): `trees_corrected_edge_filtered_20m_{city}.gpkg`

### 3.2 CHM Raster (10m Auflösung)

**Quelle:** Resampled Canopy Height Models (siehe [05_CHM_Resampling_Methodik.md](05_CHM_Resampling_Methodik.md))

**Dateien:** `CHM_10m_{mean,max,std}_{city}.tif` (je Stadt 3 Varianten)

**Spezifikation:** 10m × 10m, Float32, EPSG:25832, Wertebereich 0–50m

### 3.3 Sentinel-2 Monatliche Kompositionen (2021)

**Quelle:** Google Earth Engine (Copernicus Sentinel-2 L2A), monatliche Median-Aggregate

**Dateien:** `S2_{city}_2021_{month:02d}_median.tif` (36 Dateien: 3 Städte × 12 Monate)

**Inhalt pro Datei:** 10 Spektralbänder (B2–B12) + 13 Vegetationsindizes (NDVI, GNDVI, EVI, VARI, NDre1, NDVIre, CIre, IRECI, RTVIcore, NDWI, MSI, NDII, kNDVI)

---

## 4. Methodisches Vorgehen

### 4.1 Phase 1: Datenladen und Validierung

**Zweck:** Laden aller Eingabe-Baumkataster und Validierung der Datenintegrität

**Methode:**

```python
import geopandas as gpd
from pathlib import Path

CADASTRE_DIR = Path("data/02_pipeline/01_corrected/data")

DATASET_VARIANTS = {
    'standard': "trees_corrected_{city}.gpkg",
    'edge_20m': "trees_corrected_edge_filtered_20m_{city}.gpkg"
}

all_trees = []

for city in ['Berlin', 'Hamburg', 'Rostock']:
    for variant_name, filename_pattern in DATASET_VARIANTS.items():
        filename = filename_pattern.format(city=city)
        cadastre_path = CADASTRE_DIR / filename

        if cadastre_path.exists():
            trees_gdf = gpd.read_file(cadastre_path)
            trees_gdf['city'] = city
            trees_gdf['dataset_variant'] = variant_name
            all_trees.append(trees_gdf)

trees_gdf = pd.concat(all_trees, ignore_index=True)
```

**Validierungsschritte:**

| Check                 | Beschreibung                            | Aktion bei Fehler         |
| --------------------- | --------------------------------------- | ------------------------- |
| Erforderliche Spalten | Prüfe `tree_id`, `height_m`, `geometry` | Fehler werfen             |
| Geometrie-Validität   | Prüfe auf `geom.is_valid()`             | Ungültige Geom. entfernen |
| Duplikate             | Prüfe auf doppelte `tree_id`            | Warnung loggen            |
| CRS-Konsistenz        | Alle Geometrien im gleichen CRS         | Neuprojizieren            |

**Output:** Unified GeoDataFrame mit ~1.08M Bäumen (alle Varianten kombiniert)

### 4.2 Phase 2: CHM-Feature Extraktion

**4 Features pro Baum:**

1. `height_m` – direkt aus Kataster kopieren
2. `CHM_mean` – Punkt-Sampling aus 10m CHM-Raster
3. `CHM_max` – Punkt-Sampling aus 10m CHM-Raster
4. `CHM_std` – Punkt-Sampling aus 10m CHM-Raster

**NoData-Rate (typisch):**

- Berlin: ~1.8% (Grenzpunkte außerhalb Raster)
- Hamburg: ~4.2% (mehr Grenzregionen)
- Rostock: ~0.9% (gute Abdeckung)

### 4.3 Phase 3: Sentinel-2 Feature Extraction (Batch-Processing)

### 4.3 Phase 3: Sentinel-2 Extraktion (Batch-Processing)

**Challenge:** ~1M Bäume × 36 Raster-Dateien → Speicherüberlauf ohne Batching

**Lösung:**

- Batch-weise Verarbeitung (`BATCH_SIZE = 50,000`)
- Iteratives Sampling je Monat/Stadt
- NoData-Tracking pro Baum
- RAM-Bedarf: ~8 GB

**Output:** 276 Spalten (10 Bänder + 13 Indizes × 12 Monate)

**Performance:**

- Berlin (842k): ~4 Std | Hamburg (178k): ~50 Min | Rostock (62k): ~18 Min
- **Gesamt:** ~5-6 Stunden

### 4.4 Phase 4: Qualitätskontrolle

- Prüfe Feature-Vollständigkeit (Anteil gültiger Werte)
- Validiere NoData-Verteilung
- Erzeuge Statistik-Report (JSON)

---

## 5. Datenqualität & Validierung

### 5.1 Qualitätsprüfungen

| Prüfung                    | Methode                             | Kriterium                           | Ergebnis                                   |
| -------------------------- | ----------------------------------- | ----------------------------------- | ------------------------------------------ |
| Input-Datensatz-Integrität | Erwartete vs. tatsächliche Baumzahl | ±5% akzeptabel                      | ✅ Berlin 842k, Hamburg 178k, Rostock 62k  |
| Geometrie-Validität        | `geom.is_valid()`                   | 100% gültig                         | ✅ 0 ungültige Punkte                      |
| CHM-Extraktion             | NoData-Rate                         | <5% akzeptabel                      | ✅ Berlin 1.8%, Hamburg 4.2%, Rostock 0.9% |
| S2 Monatliche Abdeckung    | Alle 12 Monate verfügbar            | 12 × 23 Bänder                      | ✅ Vollständiger Jahrzyklus 2021           |
| Feature-Wertebereich       | Vergleich mit Erwartung             | CHM 0-50m, NDVI [-1,1], kNDVI [0,1] | ✅ Bestanden                               |

### 5.2 Fehlerbehandlung

| Fehlertyp               | Problem                        | Häufigkeit       | Lösung                                |
| ----------------------- | ------------------------------ | ---------------- | ------------------------------------- |
| Raster-Datei fehlt      | CHM/S2-Dateien nicht vorhanden | Selten           | Warnung loggen, Spalte bleibt NaN     |
| NoData außerhalb Raster | Baumpunkt außerhalb Bereich    | 1-5%             | Als NaN codiert, ML-Modelle behandeln |
| Speicherüberlauf        | Zu viele Bäume gleichzeitig    | >100k BATCH_SIZE | BATCH_SIZE=50k, ~8GB RAM              |

**Fazit:** Keine Filterungen – volle Datenintegrität bewahrt (NoData präserviert für Downstream-Analysen)

---

## 6. Ergebnisse & Statistiken

### 6.1 Output-Dateien

**GeoPackages (6 Varianten):**

- `trees_with_features_{Berlin,Hamburg,Rostock}.gpkg` (Standard)
- `trees_with_features_edge_filtered_20m_{city}.gpkg` (Grenzpunkte entfernt)

**Metadata:** `feature_extraction_summary.json`

**Dateigröße:** ~1.5 GB gesamt (~650 MB Berlin, ~140 MB Hamburg, ~50 MB Rostock)

### 6.2 Statistiken nach Stadt

| Metrik                  | Berlin   | Hamburg  | Rostock          |
| ----------------------- | -------- | -------- | ---------------- |
| Anzahl Bäume            | 842,068  | 177,845  | 61,802           |
| Durchschnitt Baumhöhe   | 14.2 m   | 13.5 m   | 11.6 m           |
| Std.abw. Baumhöhe       | 5.8 m    | 5.6 m    | 6.4 m            |
| Feature-Vollständigkeit | 83%      | 67%      | 86%              |
| Rolle                   | Training | Training | Test/Validierung |

### 6.3 Standard vs. Edge-Filtered

| Stadt   | Standard | Edge-gefiltert | Reduktion |
| ------- | -------- | -------------- | --------- |
| Berlin  | 842k     | ~720k          | 14%       |
| Hamburg | 178k     | ~150k          | 15%       |
| Rostock | 62k      | ~52k           | 16%       |

Edge-Filtered Varianten: Grenzpunkte (20m Buffer) entfernt für robusteres Transfer Learning

---

## 7. Herausforderungen & Lösungen

| Herausforderung         | Problem                                    | Kontext                             | Lösung                                                                              |
| ----------------------- | ------------------------------------------ | ----------------------------------- | ----------------------------------------------------------------------------------- |
| **Speicherüberlauf**    | ~1M Bäume × 36 Raster → unkomprimiert 15GB | Naives Point-Sampling               | Batch-weise Verarbeitung (50k Bäume), direkte Column-Befüllung statt temp. Arrays   |
| **Zeitliche Lücken S2** | >40% NoData in Hamburg Winter              | Bewölkung in Monaten 12-02          | SCL-Masking (Klassen 4+5), Median-Aggregation statt Mean, NoData-Tracking pro Monat |
| **CRS-Missmatch**       | Baumkataster WGS84 vs. Raster EPSG:25832   | Unterschiedliche Koordinatensysteme | Explizite Reprojizierung vor Sampling zu EPSG:25832                                 |

**Lektionen:** Batch-Processing ist nicht optional sondern essenziell für große räumliche Datensätze. CRS-Konsistenz kritisch.

**Resultat:** Mit Whitelist 4+5 wurden 20-55% der Pixel bewahrt (konservativer, aber robust).

### 7.3 Herausforderung 3: CRS-Missmatch zwischen Eingabedaten

**Problem:** Baumkataster und Raster-Dateien hatten leicht unterschiedliche CRS-Definitionen.

**Kontext:** Baumkataster in WGS84, CHM/S2 in EPSG:25832 (UTM).

**Lösung:**

1. Standardisiere alle Eingaben auf EPSG:25832
2. Explizite Reprojizierung vor Sampling:

```python
if trees_gdf.crs != 'EPSG:25832':
    trees_gdf = trees_gdf.to_crs('EPSG:25832')
```

**Lessons Learned:** CRS-Konsistenz ist kritisch für räumliche Operationen – immer explizit prüfen.

---

## 8. Designentscheidungen & Begründungen

### 8.1 Entscheidung 1: Punkt-Extraktion statt Pixelblock-Aggregation

**Entscheidung:** Nutze exakte Baum-Koordinaten (Point-Sampling), nicht aggregierte 10m-Pixel-Blöcke.

**Alternativen:**

1. **Point-Sampling (gewählt):** Extract Raster-Wert an exakter Baum-Position
2. **Pixel-Block:** Aggregiere alle Pixel in 10m Umkreis um Baum
3. **Buffer-Aggregation:** Aggregiere Pixel in 20m Buffer

**Begründung:**

- **Konsistenz:** Exakte räumliche Auflösung über alle Features
- **Robustheit:** Keine Überinterpolation oder Glättung
- **Reproduzierbarkeit:** Deterministische Mapping Baum → Pixel

**Implikationen:**

- NoData bei Grenzpunkten (1-5%, akzeptabel)
- Keine zusätzliche räumliche Aggregation nötig
- Direkte Kompatibilität mit ML-Modellen

### 8.2 Entscheidung 2: 23 Sentinel-2 Features (Bands + Indices)

**Entscheidung:** Nutze 10 spektrale Bänder **+ 13 Vegetationsindizes**, nicht nur Rohdaten.

**Alternativen:**

1. **Rohdaten-only:** Nur 10 spektrale Bänder (minimalistisch)
2. **Standardindizes:** NDVI + NDWI + EVI (subset, schnell)
3. **Full Stack (gewählt):** 10 Bänder + 13 Indizes = 23 Features

**Begründung:**

- **Redundanz:** Indizes entfernen Redundanz aus Rohdaten (z.B. NDVI = normalized ratio)
- **Domain Knowledge:** Vegetationsindizes sind empirisch für Baumarten-Klassifikation etabliert
- **ML-Effizienz:** Feature-Set orientiert an Standard-Praxis (NDVI, NDre1, CIre, kNDVI zeigen Baumarten-Unterschiede)

**Implikationen:**

- 284 Features pro Baum, Overfitting-Risiko (Regularisierung nötig)
- 67-86% Feature-Vollständigkeit (stadt-abhängig)

---

## 9. Tools & Umgebung

**Stack:** Python 3.10, GeoPandas 0.13+, Rasterio 1.3+ (Point-Sampling), NumPy, Pandas, tqdm

**Runtime:** ~5-6 Stunden (3 Städte), ~8-12 GB RAM (Batching erforderlich), I/O-bound (nicht CPU-intensive)

### 10.2 Runtime & Ressourcen

| Parameter           | Wert        | Anmerkung                             |
| ------------------- | ----------- | ------------------------------------- |
| Geschätzte Laufzeit | 5-6 Stunden | Mit allen 3 Städten, GPU optional     |
| RAM-Bedarf          | 8-12 GB     | Peak während Batch-Processing         |
| CPU-Auslastung      | 2-4 Cores   | I/O-bound (Rasterio), nicht CPU-heavy |
| Disk Space Output   | ~1.5 GB     | 6 GeoPackages + Metadata              |

---

## 10. Limitationen & Offene Fragen

### Bekannte Limitationen

1. **Räumliche Auflösungs-Heterogenität:** 20m S2-Bänder → 10m resampled (Subpixel-Heterogenität bleibt)
2. **Zeitliche Lücken S2:** >40% NoData Hamburg-Winter → ML benötigt Imputation oder Masking
3. **Baumhöhe:** Nur Kataster (alte Messungen), keine CHM-Validierung
4. **Edge-Effekte:** Grenzpunkte (20m Buffer) mit höheren NoData-Raten (Edge-Varianten verfügbar)
5. **Phänologie:** Monatliche Aggregation maskiert saisonale Variation (April/Oktober Laubwechsel)

### Offene Fragen

- **Imputation optimal?** Temporal-Spline vs. ML-seitiges NaN-Handling
- **Feature-Reduktion:** Welche 10-15 Best-Features via Feature Selection?
- **Transfer Learning:** Stadt-übergreifend trainierbar oder Stadt-spezifische Modelle?
- **Winter-Robustheit:** Benötigen stratifizierte CV-Splits für S2 Monate 12-02?
- **Gattungs-Spezifik:** RTVIcore für Laubbäume, andere Indizes für Nadelgehölze optimal?

---

## Anhang

### A. GeoPackage Struktur

```
trees_with_features_Berlin.gpkg
│
├─ Feature Table: "trees_with_features_Berlin"
│  ├─ tree_id (INTEGER, PK)
│  ├─ city (TEXT)
│  ├─ tree_type (TEXT)
│  ├─ genus_latin (TEXT)
│  ├─ species_latin (TEXT)
│  ├─ height_m (REAL)
│  ├─ geometry (POINT, SRID=25832)
│  ├─ CHM_mean (REAL)
│  ├─ CHM_max (REAL)
│  ├─ CHM_std (REAL)
│  ├─ B2_01, B2_02, ..., B2_12 (REAL each)
│  ├─ ... (weitere 10 Bänder)
│  ├─ NDVI_01, NDVI_02, ..., NDVI_12 (REAL each)
│  ├─ ... (weitere 12 Indizes)
│  └─ nodata_months (INTEGER, Tracking)
│
└─ Metadata (optional)
   ├─ Spatial Index auf geometry
   └─ Creation Timestamp
```

---

**Dokumentversion:** 1.1
**Letzte Aktualisierung:** 21. Januar 2026
**Status:** ✅ Abgeschlossen
