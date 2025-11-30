# 03 Baumkataster: Datenakquise und Harmonisierung

## Übersicht

Dieses Dokument beschreibt die Methodik zur Akquise und Harmonisierung der Baumkataster-Daten für die drei Untersuchungsstädte Berlin, Hamburg und Rostock. Die Daten dienen als Ground-Truth-Labels für die Baumarten-Klassifikation auf Gattungsebene.

---

## 1. Datenquellen

### 1.1 Berlin

| Eigenschaft      | Wert                                                      |
| ---------------- | --------------------------------------------------------- |
| **Datenquelle**  | Berliner Geodateninfrastruktur (GDI Berlin)               |
| **Service-Typ**  | WFS 2.0                                                   |
| **Endpunkt**     | `https://gdi.berlin.de/services/wfs/baumbestand`          |
| **Layer**        | `baumbestand:anlagenbaeume`, `baumbestand:strassenbaeume` |
| **Anzahl Bäume** | 945.907 (511.872 Anlagenbäume + 434.035 Straßenbäume)     |
| **CRS**          | EPSG:25833 (UTM Zone 33N)                                 |
| **Geometrietyp** | Point                                                     |

**Besonderheiten:**

- Zwei separate Layer werden kombiniert: Anlagen- und Straßenbäume
- Spalte `source_layer` dokumentiert die Herkunft jedes Baums
- Gattungsnamen bereits in Großbuchstaben (`ACER`, `TILIA`)

### 1.2 Hamburg

| Eigenschaft      | Wert                                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| **Datenquelle**  | Hamburg Urban Data Platform                                                                         |
| **Service-Typ**  | OGC API Features                                                                                    |
| **Endpunkt**     | `https://api.hamburg.de/datasets/v1/strassenbaumkataster/collections/strassenbaumkataster_hh/items` |
| **Anzahl Bäume** | 229.013                                                                                             |
| **CRS**          | EPSG:25832 (UTM Zone 32N)                                                                           |
| **Geometrietyp** | MultiPoint                                                                                          |

**Besonderheiten:**

- Moderner OGC API Features-Dienst (kein klassischer WFS)
- Paginierte Abfrage mit 10.000 Features pro Request
- Geometrie als MultiPoint (wird bei Harmonisierung zu Point konvertiert)
- Gattungsnamen in gemischter Schreibweise (`Tilia`, `Acer`)
- Kein `source_layer`-Feld vorhanden
- Keine Baumhöhe verfügbar

### 1.3 Rostock

| Eigenschaft      | Wert                                              |
| ---------------- | ------------------------------------------------- |
| **Datenquelle**  | Geodienste der Hansestadt Rostock                 |
| **Service-Typ**  | WFS 2.0                                           |
| **Endpunkt**     | `https://geo.sv.rostock.de/geodienste/baeume/wfs` |
| **Layer**        | `baeume:hro.baeume.baeume`                        |
| **Anzahl Bäume** | 70.756                                            |
| **CRS**          | EPSG:25833 (UTM Zone 33N)                         |
| **Geometrietyp** | Point                                             |

**Besonderheiten:**

- Kein Pflanzjahr verfügbar
- Gattungsnamen in gemischter Schreibweise (`Tilia`, `Acer`)
- `source_layer` vorhanden

---

## 2. Download-Prozess

### 2.1 Skript

**Datei:** `scripts/tree_cadastres/download_tree_cadastres.py`

### 2.2 Ablauf

```
┌─────────────────────────────────────────────────────────────┐
│                    Download-Pipeline                         │
├─────────────────────────────────────────────────────────────┤
│  1. Verbindung zu Geodienst (WFS/OGC API Features)          │
│  2. Abfrage aller verfügbaren Layer                          │
│  3. Download aller Features (ggf. paginiert)                 │
│  4. Speicherung als GeoPackage                               │
│  5. Schema-Extraktion (Metadaten)                            │
│  6. Validierung (Mindestanzahl, CRS, Geometrie)             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Ausgabedateien

```
data/tree_cadastres/
├── raw/
│   ├── berlin_trees_raw.gpkg      # 945.907 Bäume
│   ├── hamburg_trees_raw.gpkg     # 229.013 Bäume
│   └── rostock_trees_raw.gpkg     #  70.756 Bäume
└── metadata/
    ├── berlin_schema.json         # Detaillierte Spalteninformationen
    ├── hamburg_schema.json
    ├── rostock_schema.json
    ├── berlin_gattungen.csv       # Gattungsliste mit Häufigkeiten
    ├── hamburg_gattungen.csv
    ├── rostock_gattungen.csv
    ├── cross_city_gattungen.csv   # Stadtübergreifender Gattungsvergleich
    └── schema_summary.csv         # Spaltenvergleich aller Städte
```

---

## 3. Harmonisierung

### 3.1 Skript

**Datei:** `scripts/tree_cadastres/harmonize_tree_cadastres.py`

### 3.2 Zielschema

Das harmonisierte Datenset enthält folgende Spalten:

| Spalte                  | Typ    | Beschreibung                                        |
| ----------------------- | ------ | --------------------------------------------------- |
| `tree_id`               | string | Eindeutige Baum-ID (stadtspezifisch)                |
| `city`                  | string | Stadtname: "Berlin", "Hamburg", "Rostock"           |
| `genus_latin`           | string | Lateinischer Gattungsname, normalisiert (UPPERCASE) |
| `species_latin`         | string | Lateinischer Artname (informativ, nicht Label)      |
| `plant_year`            | Int64  | Pflanzjahr (nullable, Rostock: alle NaN)            |
| `height_m`              | float  | Baumhöhe in Metern (nullable, Hamburg: alle NaN)    |
| `crown_diameter_m`      | float  | Kronendurchmesser in Metern                         |
| `stem_circumference_cm` | float  | Stammumfang in Zentimetern                          |
| `source_layer`          | string | Quell-Layer (nullable, Hamburg: NaN)                |
| `geometry`              | Point  | Punktgeometrie (EPSG:25832)                         |

### 3.3 Transformationen

#### 3.3.1 CRS-Harmonisierung

| Stadt   | Quell-CRS  | Ziel-CRS   | Transformation |
| ------- | ---------- | ---------- | -------------- |
| Berlin  | EPSG:25833 | EPSG:25832 | Reprojizierung |
| Hamburg | EPSG:25832 | EPSG:25832 | Keine          |
| Rostock | EPSG:25833 | EPSG:25832 | Reprojizierung |

#### 3.3.2 Geometrie-Vereinheitlichung

- **Hamburg:** MultiPoint → Point (erster Punkt des MultiPoint)
- **Berlin/Rostock:** Bereits Point, keine Änderung

#### 3.3.3 Spalten-Mapping

**Berlin:**
| Quellspalte | Zielspalte |
|-------------|------------|
| `gisid` | `tree_id` |
| `gattung` | `genus_latin` (→ UPPERCASE) |
| `art_bot` | `species_latin` |
| `pflanzjahr` | `plant_year` (String → Int) |
| `baumhoehe` | `height_m` |
| `kronedurch` | `crown_diameter_m` |
| `stammumfg` | `stem_circumference_cm` |
| `source_layer` | `source_layer` |

**Hamburg:**
| Quellspalte | Zielspalte |
|-------------|------------|
| `baumid` | `tree_id` |
| `gattung_latein` | `genus_latin` (→ UPPERCASE) |
| `art_latein` | `species_latin` |
| `pflanzjahr_portal` | `plant_year` (Float → Int) |
| — | `height_m` (NaN) |
| `kronendurchmesser` | `crown_diameter_m` |
| `stammumfang` | `stem_circumference_cm` |
| — | `source_layer` (NaN) |

**Rostock:**
| Quellspalte | Zielspalte |
|-------------|------------|
| `uuid` | `tree_id` |
| `gattung_botanisch` | `genus_latin` (→ UPPERCASE) |
| `art_botanisch` | `species_latin` |
| — | `plant_year` (NaN) |
| `hoehe` | `height_m` |
| `kronendurchmesser` | `crown_diameter_m` |
| `stammumfang` | `stem_circumference_cm` |
| `source_layer` | `source_layer` |

#### 3.3.4 Gattungsnamen-Normalisierung

Alle Gattungsnamen werden zu Großbuchstaben konvertiert:

- `Tilia` → `TILIA`
- `Acer` → `ACER`
- `Quercus` → `QUERCUS`

Dies stellt konsistente Klassifikationslabels über alle Städte sicher.

### 3.4 Ausgabedatei

**Pfad:** `data/tree_cadastres/processed/trees_harmonized.gpkg`

| Metrik                 | Wert       |
| ---------------------- | ---------- |
| **Dateigröße**         | 210,5 MB   |
| **Gesamtanzahl Bäume** | 1.245.676  |
| **Geometrietyp**       | Point      |
| **CRS**                | EPSG:25832 |

---

## 4. Datenqualität

### 4.1 Baumverteilung nach Stadt

| Stadt      | Anzahl Bäume  | Anteil   |
| ---------- | ------------- | -------- |
| Berlin     | 945.907       | 75,9%    |
| Hamburg    | 229.013       | 18,4%    |
| Rostock    | 70.756        | 5,7%     |
| **Gesamt** | **1.245.676** | **100%** |

### 4.2 Top-15 Gattungen

| Rang | Gattung  | Anzahl  | Anteil |
| ---- | -------- | ------- | ------ |
| 1    | TILIA    | 260.659 | 20,9%  |
| 2    | ACER     | 257.180 | 20,6%  |
| 3    | QUERCUS  | 165.576 | 13,3%  |
| 4    | BETULA   | 47.894  | 3,8%   |
| 5    | CARPINUS | 46.557  | 3,7%   |
| 6    | ROBINIA  | 42.212  | 3,4%   |
| 7    | PLATANUS | 40.357  | 3,2%   |
| 8    | AESCULUS | 39.825  | 3,2%   |
| 9    | FRAXINUS | 36.336  | 2,9%   |
| 10   | PRUNUS   | 33.853  | 2,7%   |
| 11   | POPULUS  | 31.719  | 2,5%   |
| 12   | PINUS    | 30.598  | 2,5%   |
| 13   | ULMUS    | 22.133  | 1,8%   |
| 14   | FAGUS    | 21.868  | 1,8%   |
| 15   | SORBUS   | 17.300  | 1,4%   |

Die Top-3 Gattungen (TILIA, ACER, QUERCUS) machen bereits **54,8%** aller Bäume aus.

### 4.3 Fehlende Werte

| Spalte          | Null-Anteil | Bemerkung            |
| --------------- | ----------- | -------------------- |
| `genus_latin`   | 1,2%        | Unbekannte Gattung   |
| `species_latin` | 1,1%        | Unbekannte Art       |
| `plant_year`    | 21,0%       | Rostock komplett NaN |
| `height_m`      | 30,4%       | Hamburg komplett NaN |
| `source_layer`  | 18,4%       | Hamburg komplett NaN |

### 4.4 Validierungschecks

Das Harmonisierungsskript führt folgende automatische Validierungen durch:

1. **CRS-Check:** Ziel-CRS EPSG:25832 wird verifiziert
2. **Geometrie-Check:** Alle Geometrien müssen vom Typ `Point` sein
3. **Eindeutigkeits-Check:** Kombination `(city, tree_id)` muss eindeutig sein
4. **Vollständigkeits-Check:** Alle drei Städte müssen im Ergebnis enthalten sein

---

## 5. Verwendung der Skripte

### 5.1 Download

```bash
uv run python scripts/tree_cadastres/download_tree_cadastres.py
```

**Laufzeit:** ~10-15 Minuten (abhängig von Serverauslastung)

### 5.2 Harmonisierung

```bash
uv run python scripts/tree_cadastres/harmonize_tree_cadastres.py
```

**Laufzeit:** ~2-3 Minuten

---

## 6. Technische Abhängigkeiten

| Paket       | Version | Verwendung              |
| ----------- | ------- | ----------------------- |
| `geopandas` | ≥0.14   | Geodaten-Handling       |
| `owslib`    | ≥0.29   | WFS-Zugriff             |
| `pandas`    | ≥2.0    | Datenverarbeitung       |
| `numpy`     | ≥1.24   | Numerische Operationen  |
| `requests`  | ≥2.31   | HTTP-Requests (OGC API) |

---

## 7. Bekannte Einschränkungen

1. **Zeitliche Konsistenz:** Die Daten stammen aus unterschiedlichen Aktualisierungszyklen der Städte
2. **Pflanzjahr Rostock:** Nicht verfügbar, limitiert altersbasierte Analysen
3. **Baumhöhe Hamburg:** Nicht verfügbar, limitiert höhenbasierte Analysen
4. **Gattungs-Unbekannt:** ~1,2% der Bäume haben keine Gattungszuordnung
5. **Label-Ebene:** Klassifikation erfolgt auf Gattungs-Level, nicht auf Art-Level

---

## 8. Referenzen

- [Berliner Baumbestand WFS](https://gdi.berlin.de/services/wfs/baumbestand)
- [Hamburg Urban Data Platform - Straßenbaumkataster](https://api.hamburg.de/datasets/v1/strassenbaumkataster)
- [Geodienste Rostock - Bäume](https://geo.sv.rostock.de/geodienste/baeume/wfs)
- [OGC API Features Spezifikation](https://ogcapi.ogc.org/features/)
- [WFS 2.0 Standard](https://www.ogc.org/standard/wfs/)
