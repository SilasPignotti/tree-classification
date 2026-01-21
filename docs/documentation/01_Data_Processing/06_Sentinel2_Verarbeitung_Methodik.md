# Sentinel-2 Verarbeitung (Google Earth Engine)

**Projektphase:** Datenverarbeitung | **Autor:** Silas Pignotti | **Notebook:** `notebooks/01_processing/02_sentinel2_gee_download.ipynb`

## Übersicht

Beschaffung & Verarbeitung von Sentinel-2 Satellitendaten für 2021 via Google Earth Engine für Berlin, Hamburg und Rostock.

**Output pro Stadt/Monat:**

- 12 monatliche Median-Kompositionen (Jan-Dez)
- 10 spektrale Bänder (B2-B12)
- 13 Vegetationsindizes
- **Gesamt: 23 Bänder pro Datei**

**Spezifikation:**

- Quelle: Copernicus Sentinel-2 L2A (atmosph. korrigiert)
- GEE Collection: COPERNICUS/S2_SR_HARMONIZED
- Format: GeoTIFF, EPSG:25832, 10m Auflösung, Float32
- Speicher: ~8 GB gesamt (36 Dateien × 3 Städte × 12 Monate)

---

## Spektrale Bänder & Vegetationsindizes

### 10 Spektrale Bänder

| Band | Name       | Auflösung | Wellenlänge | Action |
| ---- | ---------- | --------- | ----------- | ------ |
| B2   | Blue       | 10m       | 490nm       | Direkt |
| B3   | Green      | 10m       | 560nm       | Direkt |
| B4   | Red        | 10m       | 665nm       | Direkt |
| B5   | Red Edge   | 20m       | 705nm       | → 10m↑ |
| B6   | Red Edge   | 20m       | 740nm       | → 10m↑ |
| B7   | Red Edge   | 20m       | 783nm       | → 10m↑ |
| B8   | NIR        | 10m       | 842nm       | Direkt |
| B8A  | Narrow NIR | 20m       | 865nm       | → 10m↑ |
| B11  | SWIR-1     | 20m       | 1610nm      | → 10m↑ |
| B12  | SWIR-2     | 20m       | 2190nm      | → 10m↑ |

↑ Bilinear Resampling zu 10m vor Aggregation

### 13 Vegetationsindizes

| Gruppe       | Index    | Formel                                     | Bereich     | Verwendung                    |
| ------------ | -------- | ------------------------------------------ | ----------- | ----------------------------- |
| **Basis**    | NDVI     | (B8 - B4) / (B8 + B4)                      | [-1, 1]     | Standard Vegetation           |
|              | GNDVI    | (B8 - B3) / (B8 + B3)                      | [-1, 1]     | Grün-sensibel                 |
|              | EVI      | 2.5 × (B8 - B4) / (B8 + 6×B4 - 7.5×B2 + 1) | [-1, 2.5]   | Enhanced, atmosphären-robust  |
|              | VARI     | (B3 - B4) / (B3 + B4 - B2)                 | [-1, 1]     | Sichtbar, urban-robust        |
| **Red-Edge** | NDre1    | (B8 - B5) / (B8 + B5)                      | [-1, 1]     | Baumarten-sensibel            |
|              | NDVIre   | (B8 - B6) / (B8 + B6)                      | [-1, 1]     | Chlorophyll-Proxy             |
|              | CIre     | (B8 / B5) - 1                              | [-1, 10]    | Red-Edge Chlorophyll Index    |
|              | IRECI    | (B7 - B4) / (B5 / B6)                      | [-5, 5]     | Invertiertes Red-Edge Index   |
|              | RTVIcore | 100×(B8 - B5) - 10×(B8 - B3)               | [-200, 200] | Red-Edge Transformation       |
| **SWIR**     | NDWI     | (B8 - B11) / (B8 + B11)                    | [-1, 1]     | Wasser-Index                  |
|              | MSI      | B11 / B8                                   | [0, 3]      | Feuchte-Stress-Index          |
|              | NDII     | (B8 - B12) / (B8 + B12)                    | [-1, 1]     | Infrarot-Differenz            |
| **Advanced** | kNDVI    | tanh(NDVI²)                                | [0, 1]      | Kernel-NDVI, nicht-linear LAI |

**Begründung Index-Auswahl:**

- Red-Edge (5 Indizes): Baumartenspezifische Signale
- SWIR (3 Indizes): Wasser/Feuchte-Differenzierung
- Basis (4 Indizes): Robuste Vegetation-Detektion
- Advanced (1 Index): Nicht-lineare LAI-Schätzung

---

## Datenquelle

| Property   | Wert                            |
| ---------- | ------------------------------- |
| Quelle     | Copernicus Sentinel-2 Mission   |
| Collection | COPERNICUS/S2_SR_HARMONIZED     |
| Level      | Level-2A (Bottom-of-Atmosphere) |
| Verfügbar  | 2017 - heute                    |
| Revisit    | 5 Tage (S2A + S2B kombiniert)   |
| Lizenz     | Open Data (Copernicus License)  |
| Features   | 13 Bänder + SCL Cloud-Mask      |

---

## Methodik

### 1. Cloud Masking (SCL-basiert)

**Scene Classification Layer (SCL) Whitelist:**

- ✓ Klasse 4 (Vegetation)
- ✓ Klasse 5 (Bare Soils)
- ❌ Klasse 7 (Unclassified) — ausgeschlossen für Robustheit

**Begründung:** Konservatives Masking vermeidet spektrale Artefakte und verbessert Transfer-Learning über Städte hinweg. Trade-off: Niedrigere Coverage akzeptabel für höhere Qualität.

**Auswirkung:** Monatliche Median-Kompositionen behalten typisch 20-55% der Daten nach Masking (Winter: <15% möglich).

### 2. Band-Resampling

20m Bänder (B5, B6, B7, B8A, B11, B12) werden mit **bilinearem Resampling** zu 10m vor Median-Aggregation transformiert.

**Vorteile:** Glatte Übergänge für Indizes, verhindert Blockbildung bei Red-Edge Bändern.

### 3. Physical Range Clipping

Alle spektralen Bänder werden vor Index-Berechnung auf [0, 10000] begrenzt:

**Zweck:** Verhindert Überläufe in Ratio-Indizes, konsistente Wertebereiche, vereinfacht ONNX-Export.

### 4. Monatliche Median-Aggregation

Pro Stadt & Monat: Alle verfügbaren Szenen median-aggregiert.

**Begründung Median statt Mean:**

- Robust gegen Ausreißer (Wolken-Artefakte, Sensor-Fehler)
- Bessere Qualität bei wenigen Szenen
- Keine Übersättigung heller Oberflächen

**Szenen pro Monat:** 4-8 im Durchschnitt (Winter: 2-4, Sommer: 8-12)

### 5. Export zu Google Drive

Export läuft **asynchron** auf GEE-Servern:

- Datei: `S2_<City>_2021_<MM>_median.tif`
- Ziel: Google Drive Ordner `sentinel2_2021_final`
- Laufzeit: 5-20 min pro Export
- Parallel möglich: Alle 36 Tasks gleichzeitig starten

---

## Ergebnisse & Validierung

### Datengrößen

| Stadt   | Dateigröße | 12 Monate   |
| ------- | ---------- | ----------- |
| Berlin  | ~460 MB    | 5.5 GB      |
| Hamburg | ~400 MB    | 4.8 GB      |
| Rostock | ~200 MB    | 2.4 GB      |
| **Σ**   | —          | **12.7 GB** |

### Coverage nach SCL-Masking

| Stadt   | Ø Coverage | Min (Winter) | Max (Sommer) |
| ------- | ---------- | ------------ | ------------ |
| Berlin  | 84.4%      | 52.1%        | 95.7%        |
| Hamburg | 77.5%      | 19.5%        | 95.6%        |
| Rostock | 83.4%      | 28.1%        | 99.0%        |

**Wintermonate-Warnung:** Hamburg Jan/Nov und Rostock Jan unter 15% Coverage → eingeschränkte Nutzbarkeit für saisonale Features.

### Validierung (7 Checks)

| Check              | Kriterium         | Status            |
| ------------------ | ----------------- | ----------------- |
| 1. Bänder          | 23/23 vorhanden   | ✓                 |
| 2. CRS             | EPSG:25832        | ✓                 |
| 3. Auflösung       | 10m               | ✓                 |
| 4. Datentyp        | Float32           | ✓                 |
| 5. Coverage        | >15% (min)        | ✓ (außer 3 Fälle) |
| 6. Spektral-Ranges | [0, 10000] gültig | ✓                 |
| 7. Spatial Align   | 10m Grid Match    | ✓                 |

**Alle 36 Dateien validiert & bestanden** ✓

---

## Spektrale Wertebereiche (Real 2021)

**Beispiel Berlin (Juli):**

| Band/Index | Bereich   | Mean | Std  |
| ---------- | --------- | ---- | ---- |
| B2 (Blue)  | 0-3000    | 785  | 420  |
| B4 (Red)   | 0-2500    | 680  | 380  |
| B8 (NIR)   | 100-4000  | 1950 | 680  |
| NDVI       | 0.15-0.65 | 0.42 | 0.12 |
| NDVIre     | 0.20-0.60 | 0.44 | 0.10 |
| kNDVI      | 0.01-0.70 | 0.32 | 0.18 |

---

## Designentscheidungen

### Monatliche Median-Aggregation

- Robust gegen Ausreißer (vs. Mean)
- Bessere Qualität bei wenigen Szenen pro Monat
- Temporale Auflösung: Monatlich (trade-off zwischen Detail & Stabilität)

### Konservatives SCL-Masking (nur Klassen 4,5)

- Ausschluss Klasse 7 (Unclassified) für höhere Robustheit
- Trade-off: 20-55% Coverage vs. hohe spektrale Qualität
- Bessere Generalisierung über Städte hinweg

### Bilinear Resampling für 20m Bänder

- Glatte Übergänge für Vegetationsindizes (vs. Nearest-Neighbor)
- Standard für optische Fernerkundung
- ~20-30% Overhead akzeptabel

### 13 Vegetationsindizes (umfassend)

- Deckt alle spektralen Bereiche ab (sichtbar, Red-Edge, SWIR)
- Redundanz für robuste Feature-Engineering
- Red-Edge Indizes für Baumarten-Differenzierung

---

## Bekannte Limitationen

1. **Wintermonate Coverage:** Dezember-Februar <30% Coverage, teilweise <15% (Hamburg Jan: 8.2%, Rostock Jan: 1.3%)

2. **Räumliche Auflösung:** 10m begrenzt Detailerkennung bei kleinen Bäumen (<5m Kronendurchmesser)

3. **Temporale Auflösung:** Monatliche Kompositionen glätten sub-monatliche phänologische Events

4. **Mixed-Pixel-Effekte:** Waldränder und heterogene urbane Szenen können spektrale Artefakte zeigen

5. **Spektrale Sättigung:** NDVI sättigt bei hoher Vegetation, daher ergänzende Indizes (EVI, kNDVI) nötig

---

## Runtime & Ressourcen

| Phase              | Dauer     |
| ------------------ | --------- |
| GEE Processing     | 10-15 min |
| Export (36 Tasks)  | 2-4h      |
| Download/Migration | 30-60 min |
| Validierung        | 10-20 min |
| **Gesamt**         | **3-5h**  |

**Parallele Verarbeitung:** Alle 36 Tasks können gleichzeitig starten. GEE managed Skalierung automatisch.

---

## Tools & Abhängigkeiten

**Python Stack:**

- Google Earth Engine API 0.1.384+
- geopandas 0.13+, rasterio 1.3.9+, numpy 1.24+

**Externe Tools:**

- GEE Cloud Computing (kostenlos für Forschung)
- Google Drive Storage (~13 GB)

**Input:**

- Stadtgrenze (GeoJSON/Shapefile)
- GEE Authentifizierung (OAuth 2.0)

**Output:**

- 36 × GeoTIFF (S2*<City>\_2021*<MM>\_median.tif)
- Speicherort: `/data/sentinel2_2021/`

---

## Lessons Learned

**Challenge 1 - Wintermonate:** Hohe Bewölkung → Coverage <15% in Hamburg/Rostock. **Fazit:** Fokus auf Mai-Oktober für robuste Features, Winterdaten separieren oder interpolieren.

**Challenge 2 - SCL-Masking Trade-off:** Klasse 7 (Unclassified) ausschließen → niedrigere Coverage aber höhere Qualität. **Fazit:** Konservativ besser für Transfer-Learning.

**Challenge 3 - 20m Band Resampling:** Notwendig für konsistente 10m Grid → +20-30% Rechenzeit. **Fazit:** Bilinear ist Standard, Kosten gering.

**Challenge 4 - GEE Task Limits:** Max ~10 concurrent Tasks. **Fazit:** Sequenzielles Starten, GEE queued automatisch.

---

## Empfehlungen für Feature Engineering

1. **Saisonal-Fokus:** Nutze Mai-Oktober als robuste 6-Monat-Serie (Coverage >35%)
2. **Index-Redundanz:** Nutze alle 13 Indizes für Robustheit, Feature-Selection later
3. **Wasserflächen:** Maskiere explizit vor ML-Training (NDWI < 0)
4. **Urban-Noise:** VARI & GNDVI sind atmosphären-robust in urbanen Szenen
5. **Baumarten-Features:** Red-Edge Indizes (NDre1, NDVIre, CIre) sind baumarten-sensibel
