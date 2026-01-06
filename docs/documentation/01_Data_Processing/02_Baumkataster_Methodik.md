# Datenakquise: Baumkataster - Methodik und Dokumentation

**Projektphase:** Datenakquise
**Datum:** 3. Dezember 2025
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung, Harmonisierung und Filterung von Baumkataster-Daten für drei deutsche Städte: Hamburg, Berlin und Rostock. Diese Daten bilden die Grundlage für die Baumklassifikation basierend auf Fernerkundungsdaten (CHM und Sentinel-2) und dienen als Trainings- und Testdaten für maschinelle Lernmodelle.

### 1.1 Zieldaten

**Harmonisierte Baumkataster:**

- Einheitliches Schema für alle Städte
- Format: GeoPackage (GPKG)
- Koordinatensystem: EPSG:25832 (ETRS89 / UTM zone 32N)
- Attribute: tree_id, city, genus_latin, species_latin, plant_year, height_m, crown_diameter_m, stem_circumference_cm, source_layer, geometry

**Gefilterte Baumkataster:**

- Mehrere Varianten mit unterschiedlichen Qualitätsfiltern
- Räumliche Filterung (Kantenabstand, Stadtgrenzen-Clipping)
- Gattungs-Viabilitätsprüfung (≥500 Bäume pro Gattung in allen Städten)
- Temporale Filterung (Pflanzjahr ≤ 2021)

### 1.2 Zielstädte

1. **Hamburg** - Trainingsdaten (gesamte Stadt)
2. **Berlin** - Trainingsdaten (gesamte Stadt)
3. **Rostock** - Testdaten als Proxy für Wismar

### 1.3 Pipeline-Übersicht

Die Baumdatenpipeline besteht aus drei Hauptschritten:

1. **Download** - Beschaffung der Rohdaten aus verschiedenen Quellen
2. **Harmonisierung** - Normalisierung zu einheitlichem Schema
3. **Filterung** - Räumliche, temporale und gattungsbasierte Filterung

---

## 2. Datenquellen

### 2.1 Hamburg

**Quelle:** Freie und Hansestadt Hamburg - Geoportal
**Service:** OGC API Features (nicht WFS)
**URL:** https://geodienste.hamburg.de/HH_WFS_Baumkataster
**Datenformat:** GeoJSON
**CRS:** EPSG:25832

**Datensatz-Details:**

- **Aktualität:** Laufend aktualisiert
- **Geometrie-Typ:** Point
- **Schlüsselattribute:** baumid, gattung_latein, art_latein, pflanzjahr_portal, kronendurchmesser, stammumfang

### 2.2 Berlin

**Quelle:** Geoportal Berlin
**Service:** Web Feature Service (WFS) 2.0.0
**Layer:** Anlagenbäume, Straßenbäume
**URL:** https://fbinter.stadt-berlin.de/fb/wfs/data/senstadt/s_wfs_baumbestand
**Datenformat:** GML 3.2
**CRS:** EPSG:25832

**Datensatz-Details:**

- **Aktualität:** Laufend aktualisiert
- **Geometrie-Typ:** Point
- **Schlüsselattribute:** gisid, gattung, art_bot, pflanzjahr, baumhoehe, kronedurch, stammumfg

### 2.3 Rostock

**Quelle:** Hanse- und Universitätsstadt Rostock
**Service:** Web Feature Service (WFS) 2.0.0
**Layer:** Baumkataster
**URL:** https://www.geodaten-mv.de/dienste/baumkataster_rostock
**Datenformat:** GML 3.2
**CRS:** EPSG:25832

**Datensatz-Details:**

- **Aktualität:** Laufend aktualisiert
- **Geometrie-Typ:** Point
- **Schlüsselattribute:** uuid, gattung_botanisch, art_botanisch, hoehe, kronendurchmesser, stammumfang

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. Download der Rohdaten (pro Stadt)
   ├── Hamburg: OGC API Features
   ├── Berlin: WFS (2 Layer)
   └── Rostock: WFS (1 Layer)
2. Schema-Extraktion und Metadaten-Erstellung
3. Harmonisierung zu einheitlichem Schema
   ├── Normalisierung Gattung/Art
   ├── CRS-Reprojektion
   ├── Attribut-Mapping
4. Räumliche und temporale Filterung
5. Gattungs-Viabilitätsprüfung
6. Export mehrerer Datensatz-Varianten
```

### 3.2 Download-Phase

**Hamburg (OGC API Features):**

```python
# Pagination durch alle Features
while True:
    url = f"{base_url}?f=json&limit={limit}&offset={offset}&crs={crs_param}"
    response = requests.get(url, timeout=300)
    features = response.json().get("features", [])
    if not features:
        break
    all_features.extend(features)
    offset += limit
```

**Berlin (WFS):**

```python
wfs = WebFeatureService(url=wfs_url, version="2.0.0")
for layer_name in layers:
    response = wfs.getfeature(typename=layer_name, outputFormat="application/gml+xml; version=3.2")
    gdf = gpd.read_file(response)
```

**Rostock (WFS):**

- Ähnlich zu Berlin, aber einzelner Layer

### 3.3 Schema-Extraktion

Für jede Stadt wird ein vollständiges Schema extrahiert:

```python
schema = {
    "city": city_name,
    "total_records": len(gdf),
    "columns": [
        {
            "name": col,
            "dtype": str(gdf[col].dtype),
            "null_percentage": round(null_count / total_rows * 100, 2),
            "unique_count": unique_count,
            "sample_values": sample_values[:10]
        }
        for col in gdf.columns
    ]
}
```

### 3.4 Harmonisierung

**Normalisierung Gattung:**

```python
def normalize_genus(genus: str | None) -> str | None:
    if not genus or pd.isna(genus):
        return None
    return str(genus).strip().upper()
```

**Normalisierung Art:**

```python
def normalize_species(species: str | None) -> str | None:
    if not species or pd.isna(species):
        return None
    species_str = str(species).strip()
    parts = species_str.split()
    if len(parts) > 1 and parts[0][0].isupper():
        return " ".join(parts[1:]).lower()
    return species_str.lower()
```

**Stadt-spezifische Mapping:**

- **Berlin:** gisid → tree_id, gattung → genus_latin, art_bot → species_latin
- **Hamburg:** baumid → tree_id, gattung_latein → genus_latin, art_latein → species_latin
- **Rostock:** uuid → tree_id, gattung_botanisch → genus_latin, art_botanisch → species_latin

### 3.5 Filterung

**Temporale Filterung:**

```python
mask = gdf["plant_year"].isna() | (gdf["plant_year"] <= CHM_REFERENCE_YEAR)
```

**Räumliche Filterung (Stadtgrenzen-Clipping):**

```python
gdf_clipped = gpd.sjoin(
    gdf, boundaries[["geometry"]], how="inner", predicate="within"
)
```

**Kantenabstands-Berechnung:**

```python
for genus in genera_list:
    genus_trees = gdf_with_genus[gdf_with_genus["genus_latin"] == genus]
    other_trees = gdf_with_genus[gdf_with_genus["genus_latin"] != genus]
    coords_same = np.column_stack([genus_trees.geometry.x, genus_trees.geometry.y])
    coords_other = np.column_stack([other_trees.geometry.x, other_trees.geometry.y])
    tree = cKDTree(coords_other)
    distances, _ = tree.query(coords_same, k=1)
    gdf.loc[genus_indices, "min_dist_other_genus"] = distances
```

**Gattungs-Viabilität:**

```python
counts = gdf.groupby(["city", "genus_latin"]).size().unstack(fill_value=0).T
viable_mask = (counts[available_cities] >= min_samples).all(axis=1)
viable_genera = counts[viable_mask].index.tolist()
```

### 3.6 Datensatz-Varianten

**Erstellte Varianten:**

1. **no_edge** - Ohne Kantenfilterung (1,140,150 Bäume, 20 Genera)
2. **edge_15m** - ≥15m Abstand zu anderen Gattungen (363,571 Bäume, 8 Genera)
3. **edge_20m** - ≥20m Abstand zu anderen Gattungen (280,522 Bäume, 7 Genera)
4. **edge_30m** - ≥30m Abstand zu anderen Gattungen (195,117 Bäume, 6 Genera)

---

## 4. Herausforderungen und Lösungen

### 4.1 Heterogene Datenquellen

**Problem:** Unterschiedliche APIs, Schemas und Attribute pro Stadt.

**Lösung:** Stadt-spezifische Download- und Mapping-Funktionen mit einheitlichem Zielschema.

### 4.2 Gattungs-Normalisierung

**Problem:** Inkonsistente Schreibweisen und Formate.

**Lösung:** Uppercase für Gattungen, Lowercase für Arten, Entfernung von Gattungspräfixen.

### 4.3 Performance bei Kantenabstands-Berechnung

**Problem:** O(n²) Komplexität bei naiver Distanzberechnung.

**Lösung:** KD-Tree für O(n log n) Performance.

### 4.4 MultiPoint-Geometrien

**Problem:** Hamburg verwendet MultiPoint-Geometrien.

**Lösung:** Konvertierung zu Point-Geometrien (Extraktion erster Punkt).

---

## 5. Validierung

### 5.1 Validierungskriterien

**Download-Validierung:**

- [ ] Mindestens 10.000 Bäume pro Stadt
- [ ] Korrekte Geometrie-Typen (Point/MultiPoint)
- [ ] CRS EPSG:25832/25833

**Harmonisierung-Validierung:**

- [ ] Einheitliches Schema für alle Städte
- [ ] Keine Duplikate (city, tree_id)
- [ ] Normalisierte Gattungsnamen

**Filter-Validierung:**

- [ ] Temporale Filterung korrekt angewendet
- [ ] Räumliche Clipping innerhalb Stadtgrenzen
- [ ] Kantenabstände korrekt berechnet
- [ ] Gattungs-Viabilität ≥500 Bäume pro Stadt

### 5.2 Validierungsergebnisse

**Download-Ergebnisse:**

| Stadt   | Bäume   | CRS        | Geometrie-Typ |
| ------- | ------- | ---------- | ------------- |
| Hamburg | 229,013 | EPSG:25832 | MultiPoint    |
| Berlin  | 945,907 | EPSG:25833 | Point         |
| Rostock | 70,726  | EPSG:25833 | Point         |

**Harmonisierung-Ergebnisse:**

- ✅ Einheitliches Schema
- ✅ Normalisierte Gattungsnamen
- ✅ Keine Duplikate

**Filter-Ergebnisse (no_edge Variante):**

| Stadt   | Bäume nach Filter | Viable Genera |
| ------- | ----------------- | ------------- |
| Hamburg | 215,787           | 20            |
| Berlin  | 861,935           | 20            |
| Rostock | 62,428            | 20            |

---

## 6. Outputs

### 6.1 Finale Datenprodukte

**Dateistruktur:**

```
data/tree_cadastres/
├── raw/
│   ├── berlin_trees_raw.gpkg
│   ├── hamburg_trees_raw.gpkg
│   └── rostock_trees_raw.gpkg
├── processed/
│   ├── trees_harmonized.gpkg
│   ├── trees_filtered_viable_no_edge.gpkg
│   ├── trees_filtered_viable_edge_15m.gpkg
│   ├── trees_filtered_viable_edge_20m.gpkg
│   └── trees_filtered_viable_edge_30m.gpkg
└── metadata/
    ├── berlin_schema.json
    ├── hamburg_schema.json
    ├── rostock_schema.json
    ├── schema_summary.csv
    ├── genus_viability_*.csv
    ├── all_genera_counts_*.csv
    ├── genus_species_counts_no_edge.csv
    ├── filtering_losses_*.csv
    └── filtering_report_*.json
```

### 6.2 Scripts

**Hauptscripts:**

- `scripts/tree_cadastres/download_tree_cadastres.py`
- `scripts/tree_cadastres/harmonize_tree_cadastres.py`
- `scripts/tree_cadastres/filter_trees.py`

**Konfiguration:** `config.py`

---

## 7. Technische Details

### 7.1 Verwendete Bibliotheken

**Python-Packages:**

- `geopandas>=1.0.1` - Geodaten-Verarbeitung
- `pandas>=2.0.0` - Datenanalyse
- `numpy>=1.24.0` - Numerische Berechnungen
- `scipy>=1.10.0` - KD-Tree für Distanzberechnungen
- `requests>=2.32.3` - HTTP-Requests
- `owslib>=0.29.0` - WFS-Client

---

## 8. Referenzen

### 8.1 Datenquellen

- **Hamburg:** https://geodienste.hamburg.de/
- **Berlin:** https://fbinter.stadt-berlin.de/
- **Rostock:** https://www.geodaten-mv.de/

---

## 9. Anhang

### 9.1 Beispiel-Schema (harmonisiert)

| tree_id | city    | genus_latin | species_latin | plant_year | height_m | geometry   |
| ------- | ------- | ----------- | ------------- | ---------- | -------- | ---------- |
| 12345   | Hamburg | QUERCUS     | robur         | 1995       | 25.0     | POINT(...) |
| 67890   | Berlin  | ACER        | platanoides   | NaN        | 18.5     | POINT(...) |

### 9.2 System Requirements

- **Python Version:** 3.12+
- **RAM:** 8 GB empfohlen
- **Disk Space:** ~5 GB für alle Outputs
- **Netzwerk:** Internetzugang für Downloads

---

**Dokument-Ende**
