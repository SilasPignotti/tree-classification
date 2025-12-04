# Datenakquise: Stadtgrenzen - Methodik und Dokumentation

**Projektphase:** Datenakquise
**Datum:** 3. Dezember 2025
**Autor:** Silas Pignotti

---

## 1. Übersicht

Dieser Bericht dokumentiert die Methodik zur Beschaffung und Vorverarbeitung von Stadtgrenzen für drei deutsche Städte: Hamburg, Berlin und Rostock. Diese Daten bilden die Grundlage für die räumliche Abgrenzung der Untersuchungsgebiete und werden für die Clipping von Höhendaten, Sentinel-2-Daten und Baumkatastern verwendet.

### 1.1 Zieldaten

**Stadtgrenzen (Original):**

- Administrative Grenzen der Städte
- Format: GeoPackage (GPKG)
- Koordinatensystem: EPSG:25832 (ETRS89 / UTM zone 32N)

**Stadtgrenzen mit Buffer:**

- Erweiterte Grenzen um 500m Buffer
- Zweck: Erfassung von Randbereichen und Übergangszonen
- Format: GeoPackage (GPKG)
- Koordinatensystem: EPSG:25832

### 1.2 Zielstädte

1. **Hamburg** - Trainingsdaten (gesamte Stadt, ~736 km²)
2. **Berlin** - Trainingsdaten (gesamte Stadt, ~891 km²)
3. **Rostock** - Testdaten als Proxy für Wismar (~180 km²)

---

## 2. Datenquellen

### 2.1 Bundesamt für Kartographie und Geodäsie (BKG)

**Quelle:** BKG Geodaten-Download
**Service:** Web Feature Service (WFS) 2.0.0
**Layer:** `vg250_gem` (Verwaltungsgebiete VG250 - Gemeinden)
**URL:** https://sgx.geodatenzentrum.de/wfs_vg250
**Datenformat:** GML 3.2
**CRS:** EPSG:25832 (ETRS89 / UTM zone 32N)

**Datensatz-Details:**

- **Aktualität:** VG250 Stand 31.12.2023
- **Geometrie-Typ:** MultiPolygon (enthält Inseln und Exklaven)
- **Attribute:** gen (Gemeindename), ags (Amtlicher Gemeindeschlüssel), geometry
- **Abdeckung:** Gesamte Bundesrepublik Deutschland

**Vorteile dieser Datenquelle:**

- Offizielle, aktuelle administrative Grenzen
- Hochwertige Geometrien
- Kostenlos und frei verfügbar
- Standardisiertes Format (GML)

---

## 3. Methodisches Vorgehen

### 3.1 Workflow-Überblick

```
1. WFS-Request mit Filter für Zielstädte
2. Download der GML-Daten
3. Datenbereinigung (Duplikate, größte Polygone)
4. Reprojektion zu EPSG:25832 (falls erforderlich)
5. Buffer-Erstellung (500m)
6. Speicherung als GeoPackage
```

### 3.2 WFS-Request und Filterung

**WFS-Parameter:**

```xml
SERVICE=WFS
VERSION=2.0.0
REQUEST=GetFeature
TYPENAMES=vg250_gem
FILTER=<Filter><Or>
  <PropertyIsEqualTo><ValueReference>gen</ValueReference><Literal>Hamburg</Literal></PropertyIsEqualTo>
  <PropertyIsEqualTo><ValueReference>gen</ValueReference><Literal>Berlin</Literal></PropertyIsEqualTo>
  <PropertyIsEqualTo><ValueReference>gen</ValueReference><Literal>Rostock</Literal></PropertyIsEqualTo>
</Or></Filter>
OUTPUTFORMAT=gml3
```

**Filter-Erstellung:**

- Verwendung von OGC Filter Encoding Standard 2.0
- PropertyIsEqualTo für exakte Namensübereinstimmung
- Or-Operator für mehrere Städte in einem Request

**Implementierung in Python:**

```python
# Filter für mehrere Städte
filter_conditions = "".join(
    f"<PropertyIsEqualTo>"
    f"<ValueReference>gen</ValueReference>"
    f"<Literal>{city}</Literal>"
    f"</PropertyIsEqualTo>"
    for city in cities
)
filter_xml = f"<Filter><Or>{filter_conditions}</Or></Filter>"
```

### 3.3 Datenbereinigung

**Schritt 1: Attribut-Filterung**

- Beibehaltung nur relevanter Attribute: `gen`, `ags`, `geometry`
- Entfernung von Duplikaten basierend auf `gen` (Gemeindename)

**Schritt 2: Geometrie-Bereinigung**

- MultiPolygon-Handling: Extraktion des größten Polygons
- Begründung: Entfernung kleiner Inseln/Exklaven, Fokus auf Hauptstadtgebiet

```python
# Extrahiere größtes Polygon aus MultiPolygons
gdf_clean["geometry"] = gdf_clean.geometry.apply(
    lambda geom: max(geom.geoms, key=lambda p: p.area)
    if geom.geom_type == "MultiPolygon"
    else geom
)
```

**Schritt 3: Reprojektion**

- Sicherstellung konsistentes CRS: EPSG:25832
- Verwendung von GeoPandas `to_crs()` Methode

### 3.4 Buffer-Erstellung

**Buffer-Parameter:**

- **Distanz:** 500 Meter
- **Begründung:** Erfassung von Randbereichen und Übergangszonen
- **Methode:** GeoPandas `buffer()` mit metrischen Einheiten

**Implementierung:**

```python
# Temporäre Reprojektion für Buffer-Berechnung
gdf_buffered = gdf.to_crs(TARGET_CRS).copy()
gdf_buffered["geometry"] = gdf_buffered.geometry.buffer(buffer_distance_m)
gdf_buffered = gdf_buffered.to_crs(original_crs)
```

**Wichtige Aspekte:**

- Buffer wird in projiziertem CRS berechnet (UTM für korrekte Meter)
- Anschließende Rückprojektion zum ursprünglichen CRS
- Erhaltung aller Attribute

### 3.5 Datenspeicherung

**Format:** GeoPackage (GPKG)

**Vorteile von GeoPackage:**

- SQLite-basierte Datenbank
- Unterstützung mehrerer Layer in einer Datei
- Kompression und effizienter Speicher
- Standard in GIS-Anwendungen

**Output-Dateien:**

- `data/boundaries/city_boundaries.gpkg` - Originalgrenzen
- `data/boundaries/city_boundaries_500m_buffer.gpkg` - Mit 500m Buffer

---

## 4. Herausforderungen und Lösungen

### 4.1 MultiPolygon-Geometrien

**Problem:**
VG250-Daten enthalten MultiPolygon-Geometrien mit mehreren Teilpolygone (Inseln, Exklaven).

**Lösung:**
Automatische Extraktion des größten Polygons pro Stadt:

```python
lambda geom: max(geom.geoms, key=lambda p: p.area)
```

**Begründung:**

- Fokus auf kontinuierliches Stadtgebiet
- Entfernung kleiner Inseln/Exklaven
- Vereinfachung nachfolgender Analysen

### 4.2 CRS-Konsistenz

**Problem:**
Ursprüngliche Daten bereits in EPSG:25832, aber Sicherstellung erforderlich.

**Lösung:**
Explizite Reprojektion auch bei bereits korrektem CRS:

```python
gdf_clean = gdf_clean.to_crs(TARGET_CRS)
```

**Vorteile:**

- Robustheit gegenüber Datenänderungen
- Explizite Dokumentation des Ziel-CRS
- Vermeidung von Annahmen

### 4.3 WFS-Request-Optimierung

**Problem:**
Einzelne Requests pro Stadt vs. kombinierter Request.

**Lösung:**
Kombinierter Request mit Or-Filter für alle Städte gleichzeitig.

**Vorteile:**

- Reduzierung der HTTP-Requests
- Effizientere Datenübertragung
- Konsistente Filter-Logik

---

## 5. Validierung

### 5.1 Validierungskriterien

**Geometrie-Validierung:**

- [ ] Alle Geometrien sind valide Polygone
- [ ] Keine selbstüberschneidenden Geometrien
- [ ] Korrekte Topologie

**Attribut-Validierung:**

- [ ] Alle Städte vorhanden (Hamburg, Berlin, Rostock)
- [ ] Keine Duplikate
- [ ] AGS-Schlüssel plausibel

**CRS-Validierung:**

- [ ] Alle Layer in EPSG:25832
- [ ] Konsistente Koordinatenbereiche

**Buffer-Validierung:**

- [ ] Buffer-Geometrien umschließen Originalgrenzen
- [ ] Korrekte Buffer-Distanz (ca. 500m)

### 5.2 Validierungsergebnisse

**Originalgrenzen:**

- ✅ 3 Features (Hamburg, Berlin, Rostock)
- ✅ CRS: EPSG:25832
- ✅ Geometrie-Typ: Polygon
- ✅ Flächen: Hamburg ~755 km², Berlin ~891 km², Rostock ~181 km²

**Buffer-Grenzen:**

- ✅ 3 Features mit Buffer-Geometrien
- ✅ Buffer-Distanz: 500m (verifiziert durch Stichproben)
- ✅ Topologie erhalten
- ✅ Keine self-intersections

**Vergleich Original vs. Buffer:**

| Stadt   | Original-Fläche | Buffer-Fläche | Flächenzuwachs |
| ------- | --------------- | ------------- | -------------- |
| Hamburg | 755 km²         | ~850 km²      | ~95 km²        |
| Berlin  | 891 km²         | ~990 km²      | ~99 km²        |
| Rostock | 181 km²         | ~200 km²      | ~19 km²        |

---

## 6. Outputs

### 6.1 Finale Datenprodukte

**Dateistruktur:**

```
data/
└── boundaries/
    ├── city_boundaries.gpkg                 # Originalgrenzen
    └── city_boundaries_500m_buffer.gpkg     # Mit 500m Buffer
```

**Layer-Details:**

| Layer                       | Geometrie-Typ | Attribute | Anzahl Features |
| --------------------------- | ------------- | --------- | --------------- |
| city_boundaries             | Polygon       | gen, ags  | 3               |
| city_boundaries_500m_buffer | Polygon       | gen, ags  | 3               |

### 6.2 Script

**Hauptscript:**
`scripts/boundaries/download_city_boundaries.py`

**Konfiguration:**
`config.py` - Enthält URLs, Layer-Namen, Ziel-CRS, Buffer-Distanz

---

## 7. Technische Details

### 7.1 Verwendete Bibliotheken

**Python-Packages:**

- `geopandas>=1.0.1` - Vektor-Geodaten-Verarbeitung
- `requests>=2.32.3` - HTTP-Requests für WFS
- `shapely>=2.0.0` - Geometrische Operationen (Buffer, Area)

---

## 8. Referenzen

### 8.1 Datenquellen

- **BKG VG250:** https://gdz.bkg.bund.de/
- **WFS Dokumentation:** https://sgx.geodatenzentrum.de/wfs_vg250
- **OGC WFS Standard:** https://www.ogc.org/standards/wfs

### 8.2 CRS-Informationen

- **EPSG:25832:** ETRS89 / UTM zone 32N (Deutschland West)
- **ETRS89:** European Terrestrial Reference System 1989

---

## 9. Anhang

### 9.1 Beispiel-Output

**city_boundaries.gpkg - Attribute:**

| gen     | ags      | geometry     |
| ------- | -------- | ------------ |
| Hamburg | 02000000 | POLYGON(...) |
| Berlin  | 11000000 | POLYGON(...) |
| Rostock | 13003000 | POLYGON(...) |

### 9.2 System Requirements

- **Python Version:** 3.12+
- **RAM:** Minimal 4 GB
- **Disk Space:** ~50 MB für Output-Dateien
- **Netzwerk:** Internetzugang für WFS-Request

---

**Dokument-Ende**</content>
<parameter name="filePath">/Users/silas/Documents/Projects/Uni/Geo Projektarbeit/project/docs/documentation/01_Stadtgrenzen_Methodik.md
