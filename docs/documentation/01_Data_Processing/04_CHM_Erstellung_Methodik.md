# CHM-Erstellung

## Zweck

Erstellung eines qualitätsgesicherten Canopy Height Models für Baumhöhen, strukturelle Merkmale und Baumklassifikation:

$$CHM = DOM - DGM$$

Wobei:

- **DOM:** Digitales Oberflächenmodell (Objekte + Terrain)
- **DGM:** Digitales Geländemodell (nacktes Terrain)
- **CHM:** Normalisierte Höhe von Vegetation und Gebäuden

## Zielstädte & Output

| Stadt   | CHM 1m (roh) | CHM 1m (gefiltert) | Status |
| ------- | ------------ | ------------------ | ------ |
| Berlin  | GeoTIFF      | GeoTIFF, 0–50m     | ✅     |
| Hamburg | GeoTIFF      | GeoTIFF, 0–50m     | ✅     |
| Rostock | GeoTIFF      | GeoTIFF, 0–50m     | ✅     |

**Output-Verzeichnis:** `data/CHM/processed/`

## Datenquellen

**Voraussetzungen:** Harmonisierte DOM- und DGM-Daten (EPSG:25832, identische Dimensionen, NoData = -9999)

**Eingabedateien:**

- `data/CHM/raw/{berlin,hamburg,rostock}/dom_1m.tif`
- `data/CHM/raw/{berlin,hamburg,rostock}/dgm_1m.tif`

## Methodisches Vorgehen

### Phase 1: CHM-Berechnung (Roh)

**Schritte:**

1. Lade DOM und DGM (NoData → NaN)
2. Prüfe Dimensionsübereinstimmung
3. Berechne CHM = DOM − DGM
4. Erstelle Stadtgrenzen-Maske
5. Berechne Statistiken innerhalb Stadtgrenzen
6. Speichere CHM als GeoTIFF

**Wichtig:** Keine Qualitätsfilter in dieser Phase—alle Werte (negativ, sehr hoch) bleiben erhalten für spätere Analyse.

**Script:** `uv run python scripts/chm/create_chm.py`

### Phase 2: Verteilungsanalyse

Analyse der CHM-Werteverteilung für fundierte Filterstrategien:

**Negative Werte:**

- **< −5m:** Wasserflächen, starke Artefakte
- **−5 bis −2m:** Brücken, Interpolationsfehler
- **−2 bis 0m:** Kleine Messunsicherheiten

**Hohe Werte:**

- **> 50m:** Hochhäuser, unrealistisch für Bäume
- **> 60m:** Wahrscheinlich Messfehler

**Ergebnisse:**

| Stadt   | Negativ % | <−5m | −5 bis −2m | −2 bis 0m | >50m  | 0–50m Valid |
| ------- | --------- | ---- | ---------- | --------- | ----- | ----------- |
| Berlin  | 7.0%      | 0.0% | 0.0%       | 7.0%      | 0.03% | 93.0%       |
| Hamburg | 18.0%     | 1.1% | 2.4%       | 14.5%     | 0.03% | 82.0%       |
| Rostock | 27.0%     | 0.0% | 0.0%       | 27.0%     | 0.01% | 73.0%       |

**Interpretation:** 96–99% negativer Werte liegen zwischen −2m und 0m (Messunsicherheit). Hamburg: 18% negativ, hauptsächlich wegen Wasserflächen (Elbe, Hafen). Rostock: 27% negativ (Küstenlage).

**Script:** `uv run python scripts/chm/analyze_chm_distribution.py`

### Phase 3: CHM-Harmonisierung (Filterung)

**Angewendete Filter:**

| Filter | Bedingung      | Aktion   | Begründung                           |
| ------ | -------------- | -------- | ------------------------------------ |
| 1      | −2m ≤ CHM < 0m | → 0      | Messunsicherheit auf Boden setzen    |
| 2      | CHM < −2m      | → NoData | Wasserflächen, Brücken, Artefakte    |
| 3      | CHM > 50m      | → NoData | Hochhäuser, nicht relevant für Bäume |

**Schwellwert-Begründung:**

- **−2m:** Trennpunkt zwischen Messunsicherheit und echten Artefakten
- **50m:** Maximale Baumhöhe Deutschland ~45m (Douglasien)

**Filterungsergebnisse:**

| Stadt   | Original | Auf 0 gesetzt | Entfernt (negativ) | Entfernt (>50m) | Final | Verlust % |
| ------- | -------- | ------------- | ------------------ | --------------- | ----- | --------- |
| Berlin  | 941M     | 67M           | 83K                | 298K            | 941M  | 0.04%     |
| Hamburg | 747M     | 116M          | 27M                | 186K            | 720M  | 3.60%     |
| Rostock | 219M     | 67M           | 78K                | 16K             | 219M  | 0.04%     |

**Validierung nach Filter:**

- Min = 0m (keine negativen Werte)
- Max ≤ 50m (gefiltert)
- Coverage 70–90%

⚠️ **WARNUNG:** Dieses Script überschreibt die CHM-Dateien! Backup empfohlen:

```bash
cp -r data/CHM/processed data/CHM/processed_backup
```

**Script:** `uv run python scripts/chm/harmonize_chm.py`

## Datenqualität & Validierung

**Nach Phase 1 (Roh-CHM):**

- Coverage: >95% innerhalb Stadtgrenzen
- Mean: 3–7m (städtische Gebiete)
- Negative Pixel: 5–30% (je nach Stadt)

**Nach Phase 3 (Harmonisiert):**

- Coverage: 70–90% (durch Filter reduziert)
- Mean: 4–10m (städtische Gebiete)
- Min: 0m (keine negativen Werte)
- Max: ≤50m (gefiltert)

**Visuelle Prüfung in QGIS:**

- Straßen: ~0m
- Parks: 5–20m (Baumkronen)
- Wälder: 15–30m (homogen)
- Wasserflächen: NoData (nach Harmonisierung)

## Output & Statistiken

**Dateien:**

- `data/CHM/processed/CHM_1m_{Berlin,Hamburg,Rostock}.tif` – Gefilterte CHM-Dateien
- `data/CHM/processed/stats_{Berlin,Hamburg,Rostock}.json` – Statistiken
- `data/CHM/analysis/chm_distribution_{analysis.json, summary.csv}`

**Vergleich Roh vs. Gefiltert:**

| Stadt   | Roh (Pixel) | Auf 0 | Negativ | >50m | Final | Verlust |
| ------- | ----------- | ----- | ------- | ---- | ----- | ------- |
| Berlin  | 941M        | 67M   | 83K     | 298K | 941M  | 0.04%   |
| Hamburg | 747M        | 116M  | 27M     | 186K | 720M  | 3.60%   |
| Rostock | 219M        | 67M   | 78K     | 16K  | 219M  | 0.04%   |

## Ausführung

**Workflow (Schritt-für-Schritt):**

```bash
# 1. CHM-Berechnung (Roh) + Statistiken
uv run python scripts/chm/create_chm.py

# 2. Verteilungsanalyse (für Filterung)
uv run python scripts/chm/analyze_chm_distribution.py

# 3. Backup erstellen (wichtig!)
cp -r data/CHM/processed data/CHM/processed_backup

# 4. CHM-Harmonisierung (Filterung, überschreibt!)
uv run python scripts/chm/harmonize_chm.py

# 5. Statistiken aktualisieren
uv run python scripts/chm/create_chm.py
```

**Runtime & Ressourcen:**

- Laufzeit: ~15–30 Minuten (gesamt)
  - Phase 1 (create_chm): 10–20 min
  - Phase 2 (analyze): 2–5 min
  - Phase 3 (harmonize): 3–5 min
- RAM: ~16–32 GB
- Disk: ~10–15 GB Output

**Abhängigkeiten:**

- Input: `data/CHM/raw/{city}/{dom,dgm}_1m.tif` + `data/boundaries/city_boundaries.gpkg`
- Output: `data/CHM/processed/` + `data/CHM/analysis/`

## Limitationen & Offene Fragen

**Bekannte Limitationen:**

- Wasserflächen: Hamburg ~3.6% Filter-Verlust durch Elbe/Hafen
- Gebäude >50m: Ausgefiltert, aber könnten für urbane Analyse relevant sein
- Messunsicherheit: −2m bis 0m Schwellwert ist projektspezifisch

**Future Work:**

- Multi-Jahr-Analyse zur Validierung der Filterstrategien
- Adaptive Schwellwerte basierend auf Landnutzung
- Gebäude-Maske für bessere Trennung Vegetation ↔ Gebäude

---

**Version:** 1.1 | **Aktualisiert:** 6. Januar 2026
