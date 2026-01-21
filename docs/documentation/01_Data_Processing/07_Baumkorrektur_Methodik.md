# Baumkorrektur: CHM-basierte Positions- & Höhenkorrektur

**Projektphase:** Datenverarbeitung | **Autor:** Silas Pignotti | **Notebook:** `notebooks/01_processing/01_tree_correction.ipynb` | **Version:** 2.0

## Übersicht

CHM-basierte Korrektur von Baumkataster-Fehlern: Positionen via Snap-to-Peak, Höhen direkt aus CHM extrahiert.

**Fehler im Original-Kataster:**
| Fehlertyp | Ursache | Auswirkung |
|-----------|--------|-----------|
| Position | GPS-Drift, Digitalisierung | ±5-10m horizontal |
| Höhe | Alte/manuelle Messungen | ±2-5m oder fehlend |
| Bias | Stadtgebiet-abhängig | Besser in Parks, schlechter in Straßen |

**Output:** 766k korrigierte Bäume, 598k für Training (mit Edge-Filtering)

---

## Datenquellen

| Input                   | Format     | Größe                                                                    |
| ----------------------- | ---------- | ------------------------------------------------------------------------ |
| Gefilterte Baumkataster | GeoPackage | Berlin: 862k, Hamburg: 216k, Rostock: 62k                                |
| CHM 1m Auflösung        | GeoTIFF    | Berlin: 37360×46092 px, Hamburg: 39000×40363 px, Rostock: 22953×19822 px |
| CRS                     | —          | EPSG:25832                                                               |

---

## Methodik

### 1. Pre-Validierung (stratifiziertes Sampling)

**Stratifizierung:** Gattung (8 häufigste) × Raum (4×4 Grid) = bis zu 144 Strata

**Sample:** 5000 Bäume pro Stadt → Korrelation Kataster-Höhe vs. CHM:

- Berlin: r=0.676 (gute Korrelation)
- Hamburg: r=0.665 (gute Korrelation)
- Rostock: r=0.657 (moderate Korrelation)

**Interpretation:** Kataster unterschätzt systematisch (+0.7-1.5m), CHM-Korrektur essentiell.

### 2. Dynamic Search Radius

Berechnet aus Pre-Validation (p75 von Peak-Offsets):

- Berlin: 2m
- Hamburg: 2m
- Rostock: 3m

**Rationale:** 75% der Bäume sind näher als diese Distanz am Peak → konservativer Buffer.

### 3. Snap-to-Peak Algorithmus (v2.0 optimiert)

**Schritte:**

1. **Tiled Processing:** CHM in 4096×4096 px Chunks laden (RAM-effizient, 200MB vs. 1.7GB)
2. **Local Maxima Detection:** scipy.ndimage.maximum_filter (3×3 footprint)
3. **Peak Selection (NEW):** Height-Weighted Distance: `score = distance / (height + 1)`
4. **Height Extraction:** CHM im 1m Buffer um gesnappt Position

**Height-Weighted Distance Logik:**

```
Peak 1: distance=0.5m, height=18m → score = 0.026 ← Select
Peak 2: distance=1.2m, height=15m → score = 0.075
Peak 3: distance=0.3m, height=2m  → score = 0.100 (Artifact!)
```

**Vorteil gegenüber v1.0:** Reduziert Artefakt-Rate von 8% auf 2% (bevorzugt hohe Peaks).

### 4. Tiled Processing Details

**Warum Chunks?** CHM Berlin 1.7GB unkomprimiert → zu viel RAM.

**Implementation:**

- CHUNK_SIZE: 4096 px (~4km × 4km at 1m)
- Padding: dynamic_radius + 2m (verhindert Edge-Artefakte)
- Memory: 200MB total (vs. 1.7GB full CHM) = 8-9x Ersparnis

### 5. Post-Snap Quality Checks

**Filter:**

- Height Plausibility: 3-50m
- Snap Success: Erfolgreich gesnapped (87% median)

**Failure Modes:**

- Kleine Bäume (<3m): Ausgeklappt oder original behalten
- Wasserflächen/NoData: Original behalten
- Keine Peak gefunden: Original behalten

### 6. Edge-Filtering (20m Isolation)

**Zweck:** Separate Datasets für Training (spektrale Reinheit).

**Logik:** Bäume mit >20m Abstand zu nächster anderer Gattung.

**Impact:**
| Stadt | Standard | Edge-Filtered | Reduktion |
|-------|----------|---------------|-----------|
| Berlin | 609k | 480k | 21% |
| Hamburg | 113k | 85k | 25% |
| Rostock | 44k | 33k | 25% |

---

## Ergebnisse

### Aggregierte Statistiken (v2.0)

| Metrik                   | Berlin       | Hamburg      | Rostock     | Total        |
| ------------------------ | ------------ | ------------ | ----------- | ------------ |
| **Input (gefiltert)**    | 862k         | 216k         | 62k         | 1.14M        |
| **Snap Success**         | 753k (87.4%) | 177k (82.1%) | 52k (84.0%) | 983k (86.2%) |
| **Final Output**         | 609k (70.7%) | 113k (52.3%) | 44k (70.8%) | 766k (67.2%) |
| **Edge-Filtered**        | 480k         | 85k          | 33k         | 598k         |
| **Excluded**             | 253k (29.3%) | 103k (47.7%) | 18k (29.2%) | 374k (32.8%) |
| **Median Snap Distance** | 1.42m        | 1.00m        | 2.00m       | 1.35m        |
| **Median Height**        | 14.4m        | 14.0m        | 11.4m       | 13.9m        |
| **Height Range**         | 3.0-48.5m    | 3.0-45.2m    | 3.0-38.1m   | 3.0-48.5m    |

**Key Findings:**

- 766k Bäume korrigiert (67.2% Retention)
- Snap-Distanz: Median 1.35m → sehr genau!
- v2.0 ist strenger (67% vs. 85% in v1.0) aber genauer

### Städtespezifische Ergebnisse

**Berlin (Beste Qualität):**

- Snap 87.4%: Dicht bebaute Stadt mit vielen Peaks
- Median Snap 1.42m: Sehr genau
- 70.7% Retention: Height-Filter konservativ (3-50m Bereich)

**Hamburg (Herausfordern):**

- Snap 82.1%: Wasserflächen/NoData reduzieren Quote
- Nur 52.3% Retention: Höchste Ausschlussquote!
- Median Snap 1.00m: Wenn gesnapped, sehr präzise
- Hypothese: Ältere Katasterdaten + Wasserflächen

**Rostock (Optimal Balance):**

- Snap 84.0%: Ländliche Bereiche, aber stabil
- 70.8% Retention: Ähnlich Berlin
- Median Snap 2.00m: Höher aber akzeptabel
- Best Balance zwischen Snap & Retention

---

## Designentscheidungen

### Height-Weighted Distance (v2.0)

Bevorzuge hohe Peaks über kleine Artefakte.
**Formel:** `score = distance / (height + 1)`
**Vorteil:** Vermeidet Snapping zu Zäunen/Sträuchern, Artefakt-Rate -75%.

### Tiled Processing

4096×4096 Chunks mit Padding statt Global-Processing.
**Vorteil:** 8-9x Speicherersparnis, enables Google Colab Free, keine Qualitäts-Einbußen.

### Dynamic Search Radius

p75 von Pre-Validation Offsets (stadt-spezifisch).
**Vorteil:** Besser als Fixed 5m, verbessert Snap-Success um 5-8%.

### 20m Edge-Filtering

Separates Training-Dataset mit spektraler Reinheit.
**Vorteil:** Reduziert Cross-Gattungs-Konfusion, 20-25% Reduktion für bessere Modell-Qualität.

---

## Bekannte Limitationen

1. **Wintermonate-Bias:** Hamburg zeigt höhere Snap-Fehler (Wasserflächen-Maskierung in CHM)
2. **Räumliche Auflösung:** 1m Pixel kann mehrere kleine Bäume enthalten
3. **Höhen-Unsicherheit:** ±2-3m total (CHM ±0.5m + Vertex ±1m + Definition ±1-2m)
4. **Systematische Bias pro Stadt:** Rostock +1.5m, Hamburg +1.2m, Berlin +0.7m
5. **Mixed-Pixel-Effekte:** Waldränder & urbane Szenen können Artefakte zeigen

---

## Failure Analysis

**Ausschlussgründe (Hamburg-Beispiel):**

- No CHM Data (40%): Wasserflächen, Lücken
- No Peak (25%): Baum isoliert, flacher als Umgebung
- Height Too Low (20%): Sträucher/Jungbäume
- Height Too High (10%): Rare Ausreißer
- Other (5%): CRS-Fehler, Geometrie

---

## Runtime & Ressourcen

| Phase                 | Dauer                             |
| --------------------- | --------------------------------- |
| GEE Processing        | 10-15 min                         |
| Snap-to-Peak + Height | 1-3h pro Stadt                    |
| Validation & Export   | 30 min                            |
| **Gesamt**            | **6-10h** (Google Colab Standard) |

**Memory Profile:**

- Working Memory: 200MB (Tiled)
- Full CHM (ungekürzt): 1.7GB
- Gain: 8-9x Reduktion

---

## Output-Schema

**Outputs pro Stadt:**

```
data/02_pipeline/01_corrected/data/
├── trees_corrected_<City>.gpkg (Standard Dataset)
├── trees_corrected_edge_filtered_20m_<City>.gpkg (Training-Ready)
└── trees_excluded_<City>.gpkg (QA/QC Failures)

metadata/
├── stats_before_<City>.json (Pre-validation)
├── stats_after_<City>.json (Post-processing)
└── summary_all_cities.csv (Cross-city)

plots/
├── validation_before_<City>.png
└── validation_after_<City>.png
```

**GeoPackage Attribute:**

- tree_id, city, genus_latin, species_latin, plant_year
- **height_m** (korrigiert aus CHM)
- **geometry** (korrigiert via Snap-to-Peak)
- snap_distance_m, snap_success, height_plausible

---

## Tools & Abhängigkeiten

**Python Stack:**

- numpy, pandas, geopandas 0.10+
- rasterio 1.3+, scipy 1.7+, shapely 1.8+
- scikit-image (optional), matplotlib, seaborn

**Externe Tools:** Google Earth Engine (für CHM), GeoPackage support

---

## Lessons Learned

**Challenge 1 - Speicher-Overhead:** CHM 1.7GB zu groß. **Lösung:** Tiled Processing (4096 Chunks) → 200MB. **Fazit:** Chunk-Ansatz essentiell für Standard-Hardware.

**Challenge 2 - Artefakt-Snapping:** v1.0 snappte zu Zäunen/Sträuchern. **Lösung:** Height-Weighted Distance. **Fazit:** Bevorzuge hohe Peaks reduziert Fehler -75%.

**Challenge 3 - Hamburg-Coverage:** 47.7% Ausschlussquote (vs. 29% Berlin/Rostock). **Grund:** Wasserflächen, NoData in CHM. **Fazit:** Stadt-spezifische Analyse nötig.

**Challenge 4 - Höhen-Bias:** +0.7-1.5m systematische Unterschätzung in Originals. **Fazit:** CHM-Korrektur nicht optional, essentiell für Qualität.

---

## Empfehlungen für Feature Engineering

1. **Nutze Edge-Filtered Dataset:** 598k Bäume mit Spectral Purity für Single-Tree Classification
2. **Standard Dataset für räumliche Features:** 766k Bäume für Kontextfeatures
3. **Höhen-Toleranz:** ±2m akzeptabel bei Vergleichen
4. **Winter-Vorsicht:** Hamburg/Rostock Winter-Daten weniger zuverlässig
5. **Genus-Spezifische Features:** Red-Edge Indizes sensibel für Baumarten

---

## Version History

**v1.0:** Nearest-peak only, Global Processing (1.7GB RAM), Fixed 5m Radius

- Retention: 85%, Snap Distance: 1.8m, Artefakte: ~8%

**v2.0:** Height-weighted distance, Tiled Processing (200MB RAM), Dynamic Radius

- Retention: 67%, Snap Distance: 1.35m, Artefakte: ~2%
- Trade-off: Strenger aber deutlich genauer
