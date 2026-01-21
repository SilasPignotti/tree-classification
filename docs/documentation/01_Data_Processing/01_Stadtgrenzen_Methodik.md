# Datenakquise: Stadtgrenzen

## Zweck

Beschaffung offizieller administrativer Stadtgrenzen als räumliche Referenz für:

- Clipping von Höhendaten (DOM/DGM)
- Räumliche Filterung von Sentinel-2-Daten
- Filterung von Baumkatastern
- Definition eines 500m Buffers für Randbereiche

## Zielstädte

| Stadt       | Zweck       | Fläche   |
| ----------- | ----------- | -------- |
| **Hamburg** | Training    | ~755 km² |
| **Berlin**  | Training    | ~891 km² |
| **Rostock** | Test-/Proxy | ~181 km² |

## Datenquelle

**BKG VG250-Daten** (Bundesamt für Kartographie und Geodäsie)

- **Service:** Web Feature Service (WFS) 2.0.0
- **Layer:** `vg250_gem` (Verwaltungsgebiete - Gemeinden)
- **URL:** https://sgx.geodatenzentrum.de/wfs_vg250
- **Format:** GML 3.2
- **CRS:** EPSG:25832 (ETRS89 / UTM zone 32N)
- **Aktualität:** Stand 31.12.2023

**Vorteile:** Offizielle, hochwertige Grenzen; kostenlos; standardisiertes Format

## Methodisches Vorgehen

### WFS-Request & Filterung

**Methode:** OGC Filter Encoding Standard 2.0 mit Or-Operator für alle drei Städte in einem Request  
**Filter:** PropertyIsEqualTo für exakte Namensübereinstimmung (Hamburg, Berlin, Rostock)

**Vorteil:** Reduziert HTTP-Requests, effizientere Datenübertragung

### Datenbereinigung

**Schritte:**

1. **Attribut-Filterung:** Nur gen, ags, geometry behalten; Duplikate entfernt
2. **Geometrie-Bereinigung:** Nur größtes Polygon aus MultiPolygon extrahieren (Fokus auf Hauptstadtgebiet, Entfernung von Inseln/Exklaven)
3. **Reprojektion:** Sicherstellung EPSG:25832

### Buffer-Erstellung

**Parameter:** 500m Buffer  
**Zweck:** Erfassung von Randbereichen und Übergangszonen  
**Methode:** Buffer in projiziertem CRS (UTM) für korrekte Meter berechnet

### Datenspeicherung

**Format:** GeoPackage (GPKG)

- SQLite-basiert, komprimierbar, Standard in GIS
- **Output:** `city_boundaries.gpkg` (Original) + `city_boundaries_500m_buffer.gpkg` (mit Buffer)

## Datenqualität & Validierung

**Geometrie-Validierung:**

- ✅ Alle Geometrien sind valide Polygone, keine Selbstüberschneidungen
- ✅ Korrekte Topologie

**Attribut-Validierung:**

- ✅ Alle Städte vorhanden (Hamburg, Berlin, Rostock)
- ✅ Keine Duplikate
- ✅ AGS-Schlüssel plausibel

**CRS-Validierung:**

- ✅ Alle Layer in EPSG:25832

**Buffer-Validierung:**

- ✅ Buffer-Geometrien umschließen Originalgrenzen
- ✅ Korrekte Buffer-Distanz (~500m)

### Validierungsergebnisse

**Originalgrenzen:**

- 3 Features (Hamburg, Berlin, Rostock)
- CRS: EPSG:25832
- Geometrie-Typ: Polygon
- Flächen: Hamburg ~755 km², Berlin ~891 km², Rostock ~181 km²

**Buffer-Grenzen:**

- 3 Features mit Buffer-Geometrien
- Flächenzuwachs: Hamburg ~12.6%, Berlin ~11.1%, Rostock ~10.5%

## Output & Statistiken

**Dateien:**

- `data/boundaries/city_boundaries.gpkg` – Originalgrenzen (3 Features, Polygon, gen/ags-Attribute)
- `data/boundaries/city_boundaries_500m_buffer.gpkg` – Mit Buffer (3 Features, Polygon)

**Stadtflächen:**

| Stadt   | Original | Mit Buffer | Zuwachs |
| ------- | -------- | ---------- | ------- |
| Hamburg | ~755 km² | ~850 km²   | ~12.6%  |
| Berlin  | ~891 km² | ~990 km²   | ~11.1%  |
| Rostock | ~181 km² | ~200 km²   | ~10.5%  |

## Herausforderungen & Lösungen

**MultiPolygon-Geometrien:** VG250-Daten enthalten Inseln/Exklaven → Lösung: Automatische Extraktion des größten Polygons pro Stadt

**CRS-Konsistenz:** Explizite Reprojektion zu EPSG:25832 für Robustheit

**WFS-Optimierung:** Kombinierter Request mit Or-Filter statt einzelner Requests pro Stadt

## Reproduzierbarkeit

**Script:** `scripts/boundaries/download_city_boundaries.py`  
**Laufzeit:** ~2–5 Minuten  
**RAM-Bedarf:** ~500 MB  
**Output-Größe:** ~50 MB  
**Konfiguration:** `scripts/config.py` (URLs, Layer-Namen, CRS, Buffer-Distanz)

---

**Version:** 1.0 | **Aktualisiert:** 3. Dezember 2025
