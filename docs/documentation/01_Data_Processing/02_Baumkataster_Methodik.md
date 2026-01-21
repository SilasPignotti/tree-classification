# Datenakquise: Baumkataster

## Zweck

Beschaffung, Harmonisierung und Filterung von Baumkataster-Daten für Machine-Learning-Training:

- Harmonisierung heterogener Datenquellen zu einheitlichem Schema
- Räumliche Filterung (Stadtgrenzen-Clipping)
- Gattungs-Viabilitätsprüfung (≥500 Bäume pro Gattung in allen Städten)
- Temporale Filterung (Pflanzjahr ≤ 2021)

## Zielstädte

| Stadt       | Zweck    | Rohdaten      |
| ----------- | -------- | ------------- |
| **Hamburg** | Training | 229,013 Bäume |
| **Berlin**  | Training | 945,907 Bäume |
| **Rostock** | Test     | 70,586 Bäume  |

## Output

- `trees_harmonized.gpkg` – Einheitliches Schema für alle Städte
- `trees_filtered_viable.gpkg` – 1,140,041 Bäume in 20 viablen Gattungen
- Metadaten: Schema, Gattungs-Viabilität, Filtering-Bericht

## Datenquellen

| Stadt       | Service          | Format  | CRS        | Besonderheiten                           |
| ----------- | ---------------- | ------- | ---------- | ---------------------------------------- |
| **Hamburg** | OGC API Features | GeoJSON | EPSG:25832 | Pagination, MultiPoint-Geometrien        |
| **Berlin**  | WFS 2.0.0        | GML 3.2 | EPSG:25833 | Zwei Layer (Anlagenbäume + Straßenbäume) |
| **Rostock** | WFS 2.0.0        | GML 3.2 | EPSG:25833 | Einzelner Layer, über Geodaten MV        |

**Quellen:**

- Hamburg: https://geodienste.hamburg.de/HH_WFS_Baumkataster
- Berlin: https://fbinter.stadt-berlin.de/fb/wfs/data/senstadt/s_wfs_baumbestand
- Rostock: https://www.geodaten-mv.de/dienste/baumkataster_rostock

## Methodisches Vorgehen

### Download

- **Hamburg:** OGC API Features mit Pagination
- **Berlin:** WFS mit zwei separaten Layern (Anlagenbäume + Straßenbäume)
- **Rostock:** WFS mit einzelnem Layer

**Validierung:** ≥10,000 Bäume pro Stadt, korrekte Geometrien (Point/MultiPoint), CRS EPSG:25832/25833

### Schema-Extraktion

Dokumentation heterogener Eingangsdaten mit Metadaten:

- `berlin_schema.json`, `hamburg_schema.json`, `rostock_schema.json`
- `schema_summary.csv`

### Harmonisierung

**Normalisierung:**

- Gattung → UPPERCASE (z.B. "quercus" → "QUERCUS")
- Art → lowercase
- CRS → EPSG:25832

**Stadt-spezifische Mappings:**

- **Berlin:** gisid → tree_id, gattung → genus_latin, art_bot → species_latin; tree_type aus Layer-Namen ("Anlagenbaum"/"Straßenbaum")
- **Hamburg:** baumid → tree_id, gattung_latein → genus_latin, art_latein → species_latin; tree_type = NaN
- **Rostock:** uuid → tree_id, gattung_botanisch → genus_latin, art_botanisch → species_latin; tree_type = NaN

**Output:** `trees_harmonized.gpkg` (einheitliches Schema)

### Filterung

**Schritte:**

1. Temporale Filterung: Pflanzjahr ≤ 2021
2. Räumliche Filterung: Within Stadtgrenzen (spatial join)
3. Gattungs-Viabilität: ≥500 Bäume pro Gattung in ALLEN Städten

**Parameter:**

- CHM Reference Year: 2021
- Min samples per genus: 500
- Required in all cities: True

**Rationale für 500-Schwellenwert:** Heuristik basierend auf 10-20 Samples pro Feature (bei ~50 Features ergibt ~500-1000 Mindestgröße). Keine formale Power-Analyse durchgeführt (Ressourcen-begrenzt).

**⚠️ Hinweis:** Edge-Distanz-Berechnungen erfolgen NACH CHM-Positionskorrektur in separatem Script

**Output:** `trees_filtered_viable.gpkg` (1,140,041 Bäume, 20 viable Gattungen) + Metadaten

## Datenqualität & Validierung

✅ Download: ≥10,000 Bäume pro Stadt, korrekte Geometrien, CRS validiert  
✅ Harmonisierung: Einheitliches Schema, keine Duplikate, normalisierte Gattungsnamen  
✅ Filterung: Temporal (≤2021), räumlich (within Stadtgrenzen), Gattungs-Viabilität (≥500/Stadt)

**Ergebnisse nach Filterung:**

| Stadt      | Rohdaten      | Gefiltert     | Viable Genera |
| ---------- | ------------- | ------------- | ------------- |
| Hamburg    | 229,013       | 215,787       | 20            |
| Berlin     | 945,907       | 861,935       | 20            |
| Rostock    | 70,586        | 62,319        | 20            |
| **Gesamt** | **1,245,506** | **1,140,041** | **20**        |

## Output & Statistiken

**Dateien:**

- `data/tree_cadastres/raw/` – 3 Rohdateien (pro Stadt)
- `data/tree_cadastres/processed/trees_harmonized.gpkg` – Harmonisiert
- `data/tree_cadastres/processed/trees_filtered_viable.gpkg` – Gefiltert (1,140,041 Bäume)
- `data/tree_cadastres/metadata/` – Schema, Viabilität, Filtering-Bericht

**Finaler Datensatz (trees_filtered_viable):**

- **1,140,041** Bäume in **20** viablen Gattungen
- Hamburg: 215,787 (18.9%)
- Berlin: 861,935 (75.6%)
- Rostock: 62,319 (5.5%)

## Herausforderungen & Lösungen

**Heterogene APIs:** OGC API Features (Hamburg) vs. WFS (Berlin, Rostock) → stadt-spezifische Download-Funktionen

**Gattungs-Normalisierung:** Inkonsistente Schreibweisen → UPPERCASE Gattung, lowercase Art, Entfernung Gattungspräfixe

**Berlin Layer-Struktur:** Zwei WFS-Layer (Anlagenbäume/Straßenbäume) → Mapping zu `tree_type` Spalte

**MultiPoint-Geometrien:** Hamburg nutzt MultiPoint → Konvertierung zu Point

## Reproduzierbarkeit

**Scripts:**

1. `scripts/tree_cadastres/download_tree_cadastres.py` (~10–15 min)
2. `scripts/tree_cadastres/harmonize_tree_cadastres.py` (~5–10 min)
3. `scripts/tree_cadastres/filter_trees.py` (~15–20 min)

**Konfiguration:** `scripts/config.py`

**Ressourcen:**

- RAM: ~8 GB
- Disk: ~5 GB Output
- Netzwerk: Internetzugang für API/WFS

**Abhängigkeiten:**

- `data/boundaries/city_boundaries.gpkg` (für räumliche Filterung)
- Zugang zu Hamburg/Berlin/Rostock WFS und APIs

---

**Version:** 1.1 | **Aktualisiert:** 21. Januar 2026
