# CHM-Resampling: 1m → 10m

**Notebook:** `notebooks/processing/03_chm_resampling.ipynb`  
**Plattform:** Google Colab (12 GB RAM)  
**Laufzeit:** ~25 Minuten

## Ziel & Methodik

Resampling des Canopy Height Models von 1m auf 10m Auflösung (Sentinel-2 Pixelgröße). Die **windowed Verarbeitung** (512×512 Kacheln) minimiert RAM-Bedarf durch kachelbasierte Aggregation statt vollständiger Laden aller Daten.

**Aggregationsvarianten (je 10m×10m Pixel):**

| Variante     | Methode            | Bedeutung                                  | Verwendung               |
| ------------ | ------------------ | ------------------------------------------ | ------------------------ |
| **CHM_mean** | Mittelwert         | Durchschnittliche Vegetationshöhe im Pixel | Hauptfeature für Modelle |
| **CHM_max**  | Maximum            | Höchster Punkt im Pixel                    | Detektion spitzer Kronen |
| **CHM_std**  | Standardabweichung | Höhenvariabilität                          | Struktur-Information     |

**Output:** 9 GeoTIFF-Dateien (3 Varianten × 3 Städte: Hamburg, Berlin, Rostock), ~500 MB Gesamtgröße.

## Technische Lösung

**RAM-Optimierung:** Windowed Verarbeitung mit 512×512 Kacheln @ 1m (~1 MB pro Kachel). Peak: 1-2 GB inkl. rasterio Overhead.

**Aggregationsstrategie:**

- **Pass 1:** Mean + Max synchron (jeweils 10×10 Blöcke, NoData-Handling)
- **Pass 2:** Std separat (≥2 gültige Werte erforderlich; Bedingung: Mindestens 2 gültige Pixel für sinnvolle Std-Berechnung)

## Verarbeitungsablauf

**Konfiguration:**

- SCALE_FACTOR = 10 (1m → 10m)
- TILE_SIZE = 512 px @ 1m Auflösung (~1 MB; nach Resampling 52×52 @ 10m)
- CRS: EPSG:25832, NoData: -9999, Kompression: lzw

**Pipeline:**

1. **Pass 1:** Windowed Mean + Max in Output-Dateien schreiben
2. **Pass 2:** Windowed Std in separater Output-Datei
3. **Validierung:** Dimensionen korrekt (⌈Input/10⌉), CRS, NoData, Wertebereich 0-50m

## Datenqualität

**Validierungskriterien:** Dimensionen ⌈Input/10⌉, CRS EPSG:25832, NoData -9999, Wertebereich 0-50m, Grid-Alignment, Coverage 70-90%.

**Typische Ressourcen:**
| Stadt | Input | Output | Laufzeit |
| ------- | ----- | -------- | -------- |
| Berlin | 46k×37k | 4600×3700 | 3-4h |
| Hamburg | 40k×39k | 4000×3900 | 2-3h |
| Rostock | 20k×23k | 2000×2300 | 30-45min |

## Output & Features

**CHM_mean:** Durchschnittliche Vegetationshöhe (0-1m Offenflächen ~20-30%, 5-15m Stadtbäume ~30-40%, >30m rare <1%). Primäres Feature für Klassifikation.

**CHM_max:** Kronenspitzenhöhe. Indikator für Homogenität (max ≈ mean: einzelner Baum/Rasen; max >> mean: mehrere Bäume). Erkennt spitze Kronen (Tannen, Fichten).

**CHM_std:** Höhenvariabilität (0-1m homogen, 1-5m moderat, >5m heterogen). NoData wenn <2 gültige Pixel. Differenziert Monokulturen/Mischwälder und geschlossene Kronendächer.

## Ausführung & Ressourcen

**Laufzeit (Colab, Google Drive):**

- Berlin: ~12:16 min (6643 Kacheln)
- Hamburg: ~9:58 min (6083 Kacheln)
- Rostock: ~2:52 min (1755 Kacheln)
- **Gesamt: ~25 Minuten**

**Ressourcen:**

- RAM: 1-2 GB Peak (windowed processing)
- Disk: ~500 MB Output
- CPU: Single-threaded (rasterio)

## Nachgelagerte Schritte

**Feature-Extraction:** Kombination CHM 10m mit Sentinel-2 zur Erzeugung räumlicher Features pro Baum.

**Modell-Input:** CHM_mean (primäres Height Feature), CHM_max (Kronenmorphologie), CHM_std (Strukturheterogenität).

## Bekannte Limitationen

**Edge-Pixel (Ceiling-Division):** Eingabegrößen nicht durch 10 teilbar → Output größer als mathematisch erwartet (z.B. 46,003 px → ⌈46,003/10⌉ = 4,601 px). rasterio handhabt NoData-Padding automatisch.

**CHM_std bei <2 Pixeln:** Std nicht definiert bei weniger als 2 gültigen Werten → NoData. Coverage CHM_std (~18%) etwas niedriger als CHM_mean/max.

**Memory bei großen Kacheln:** TILE_SIZE=512 optimiert für 12GB Colab RAM. Bei kleineren Maschinen: TILE_SIZE=256 verwenden.

## Reproduzierbarkeit

**Notebook:** `notebooks/processing/03_chm_resampling.ipynb`

**Input:** `data/CHM/processed/CHM_1m_*.tif` (3 gefilterte 1m-Raster)

**Output:** `data/CHM/processed/CHM_10m/` (9 GeoTIFF-Dateien: mean/max/std für Berlin, Hamburg, Rostock)

**Dependencies:** numpy, rasterio, tqdm

---

**Version:** 1.0  
**Referenzen:** [04_CHM_Erstellung_Methodik.md](04_CHM_Erstellung_Methodik.md) (CHM 1m Input)
