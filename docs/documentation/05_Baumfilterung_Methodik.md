# 05 Baumkataster: Räumliche Filterung und Gattungs-Viabilitätsbewertung

## Übersicht

Dieses Dokument beschreibt die Methodik zur räumlichen Filterung und Gattungs-Viabilitätsbewertung der harmonisierten Baumkataster-Daten. Ziel ist die Erstellung von zwei gefilterten Datensätzen für die nachfolgende Feature-Extraktion und Klassifikation.

---

## 1. Eingangsdaten

| Eigenschaft            | Wert                                                  |
| ---------------------- | ----------------------------------------------------- |
| **Eingabedatei**       | `data/tree_cadastres/processed/trees_harmonized.gpkg` |
| **Anzahl Bäume**       | 1.245.676                                             |
| **Städte**             | Berlin, Hamburg, Rostock                              |
| **CRS**                | EPSG:25832                                            |
| **Gattungen (gesamt)** | 121                                                   |

---

## 2. Filterpipeline

### 2.1 Skript

**Datei:** `scripts/tree_cadastres/filter_trees.py`

### 2.2 Ablauf

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Filterpipeline                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Zeitlicher Filter (plant_year ≤ 2021)                                   │
│  2. Räumlicher Filter (Stadtgrenzen ohne 500m-Puffer)                       │
│  3. Kantenabstands-Berechnung (KD-Tree pro Gattung)                         │
│  4. Variante A: Gattungs-Viabilitätsfilter (ohne Kantenfilter)              │
│  5. Variante B: Kantenfilter (≥15m) + Gattungs-Viabilitätsfilter            │
│  6. Räumliche Gitterzuweisung (1km²-Zellen)                                 │
│  7. Export beider Varianten                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Filterschritte im Detail

### 3.1 Zeitlicher Filter

**Ziel:** Ausschluss von Bäumen, die nach dem CHM-Referenzjahr gepflanzt wurden.

| Parameter          | Wert                                        |
| ------------------ | ------------------------------------------- |
| **CHM-Referenz**   | 2021                                        |
| **Filterregel**    | `plant_year ≤ 2021` ODER `plant_year = NaN` |
| **Ausgeschlossen** | 18.184 Bäume (1,5%)                         |
| **Behalten**       | 1.227.492 Bäume                             |

**Begründung:**

- Das CHM (Canopy Height Model) basiert auf DOM/DGM-Daten mit Referenzjahr 2021
- Bäume, die nach 2021 gepflanzt wurden, können nicht im CHM repräsentiert sein
- Bäume ohne Pflanzjahr (Rostock: alle NaN) werden behalten, da sie vermutlich älter sind

### 3.2 Räumlicher Filter (Stadtgrenzen)

**Ziel:** Fokussierung auf den urbanen Kern, Entfernung von Bäumen im 500m-Pufferbereich.

| Parameter          | Wert                                   |
| ------------------ | -------------------------------------- |
| **Eingabe**        | `data/boundaries/city_boundaries.gpkg` |
| **Methode**        | Spatial Join (`within`)                |
| **Ausgeschlossen** | 5.558 Bäume (0,5%)                     |
| **Behalten**       | 1.221.934 Bäume                        |

**Begründung:**

- Die Sentinel-2- und CHM-Daten wurden mit 500m-Puffer heruntergeladen
- Für die Klassifikation sind nur Bäume innerhalb der administrativen Stadtgrenzen relevant
- Randeffekte werden durch Entfernung des Pufferbereichs minimiert

### 3.3 Kantenabstands-Berechnung

**Ziel:** Für jeden Baum den minimalen Abstand zum nächsten Baum einer anderen Gattung berechnen.

| Parameter         | Wert                            |
| ----------------- | ------------------------------- |
| **Algorithmus**   | KD-Tree (scipy.spatial.cKDTree) |
| **Komplexität**   | O(n log n) pro Gattung          |
| **Ausgabespalte** | `min_dist_other_genus` (Meter)  |
| **Gattungen**     | 120 (ohne NaN)                  |

**Implementierung:**

```python
for genus in unique_genera:
    same_genus = trees[trees['genus_latin'] == genus]
    other_genus = trees[trees['genus_latin'] != genus]

    tree = cKDTree(coords_other)
    distances, _ = tree.query(coords_same, k=1)

    trees.loc[same_genus.index, 'min_dist_other_genus'] = distances
```

**Begründung:**

- Bäume nahe an anderen Gattungen können zu spektralen Mischsignalen führen
- Der Kantenabstand ermöglicht die Identifikation von "reinen" Klassifikationsproben
- Die KD-Tree-Struktur ermöglicht effiziente Nearest-Neighbor-Suchen

### 3.4 Gattungs-Viabilitätsprüfung

**Ziel:** Identifikation von Gattungen mit ausreichenden Stichproben in allen drei Städten.

| Parameter             | Wert                                   |
| --------------------- | -------------------------------------- |
| **Mindestanzahl**     | 500 Bäume pro Stadt                    |
| **Erfordernis**       | ≥500 in Berlin UND Hamburg UND Rostock |
| **Viable (no_edge)**  | 20 Gattungen                           |
| **Viable (edge_15m)** | 8 Gattungen                            |

**Begründung:**

- Für statistisch robuste Klassifikation und Cross-City-Transfer werden ausreichende Stichproben pro Stadt benötigt
- 500 Samples pro Stadt ermöglichen stratifizierte Train/Val/Test-Splits
- Seltene Gattungen werden ausgeschlossen, um Class-Imbalance zu reduzieren

### 3.5 Kantenfilter (nur Variante B)

**Ziel:** Ausschluss von Bäumen mit <15m Abstand zu anderen Gattungen.

| Parameter          | Wert                  |
| ------------------ | --------------------- |
| **Schwellenwert**  | 15 Meter              |
| **Ausgeschlossen** | 751.608 Bäume (61,5%) |
| **Behalten**       | 470.326 Bäume         |

**Begründung für 15m-Schwellenwert:**

- Sentinel-2 Pixelgröße: 10m × 10m
- Diagonale eines Pixels: √(10² + 10²) ≈ 14,1m
- 15m entspricht ~1,5× Pixel-Diagonale
- Sicherheitsmarge gegen spektrale Kontamination durch Nachbargattungen

### 3.6 Räumliche Gitterzuweisung

**Ziel:** Vorbereitung für räumlich stratifiziertes Sampling in späteren Schritten.

| Parameter          | Wert                          |
| ------------------ | ----------------------------- |
| **Zellengröße**    | 1000m × 1000m (1 km²)         |
| **Ausgabespalten** | `grid_x`, `grid_y`, `grid_id` |

**Berechnung:**

```python
grid_x = floor(x / 1000)
grid_y = floor(y / 1000)
grid_id = f"{grid_x}_{grid_y}"
```

**Begründung:**

- Räumliche Autokorrelation kann zu Overfitting führen
- Gitterzellen ermöglichen Block-basierte Cross-Validation
- 1km²-Zellen bieten gute Balance zwischen räumlicher Separation und Stichprobengröße

---

## 4. Ausgabevarianten

### 4.1 Variante A: Ohne Kantenfilter (`no_edge`)

**Datei:** `data/tree_cadastres/processed/trees_filtered_viable_no_edge.gpkg`

| Metrik               | Wert      |
| -------------------- | --------- |
| **Dateigröße**       | 231 MB    |
| **Anzahl Bäume**     | 1.140.172 |
| **Anzahl Gattungen** | 20        |
| **Gitterzellen**     | 1.740     |

**Viable Gattungen:**
ACER, AESCULUS, ALNUS, BETULA, CARPINUS, CORYLUS, CRATAEGUS, FAGUS, FRAXINUS, MALUS, PINUS, PLATANUS, POPULUS, PRUNUS, QUERCUS, ROBINIA, SALIX, SORBUS, TILIA, ULMUS

### 4.2 Variante B: Mit 15m Kantenfilter (`edge_15m`)

**Datei:** `data/tree_cadastres/processed/trees_filtered_viable_edge_15m.gpkg`

| Metrik               | Wert    |
| -------------------- | ------- |
| **Dateigröße**       | 73 MB   |
| **Anzahl Bäume**     | 365.037 |
| **Anzahl Gattungen** | 8       |
| **Gitterzellen**     | 1.709   |

**Viable Gattungen:**
ACER, BETULA, FRAXINUS, POPULUS, PRUNUS, QUERCUS, SORBUS, TILIA

### 4.3 Gattungsvergleich

| Gattung  | no_edge (Anzahl) | edge_15m (Anzahl) | Verlust |
| -------- | ---------------- | ----------------- | ------- |
| TILIA    | 257.924          | 168.039           | 34,8%   |
| ACER     | 253.767          | 83.565            | 67,1%   |
| QUERCUS  | 162.763          | 63.127            | 61,2%   |
| BETULA   | 47.298           | 13.709            | 71,0%   |
| FRAXINUS | 35.380           | 12.590            | 64,4%   |
| PRUNUS   | 32.760           | 9.413             | 71,3%   |
| SORBUS   | 16.827           | 7.127             | 57,6%   |
| POPULUS  | 30.856           | 7.467             | 75,8%   |

**Verlorene Gattungen durch Kantenfilter:**
AESCULUS, ALNUS, CARPINUS, CORYLUS, CRATAEGUS, FAGUS, MALUS, PINUS, PLATANUS, ROBINIA, SALIX, ULMUS

Diese 12 Gattungen fallen in Variante B unter den Schwellenwert von 500 Bäumen pro Stadt.

---

## 5. Detaillierte Stichprobenverteilung

### 5.1 Variante A (no_edge) - Top-10 Gattungen

| Gattung  | Berlin  | Hamburg | Rostock | Gesamt  | Min/Stadt |
| -------- | ------- | ------- | ------- | ------- | --------- |
| TILIA    | 192.066 | 53.317  | 12.541  | 257.924 | 12.541    |
| ACER     | 210.610 | 31.258  | 11.899  | 253.767 | 11.899    |
| QUERCUS  | 106.312 | 50.054  | 6.397   | 162.763 | 6.397     |
| BETULA   | 31.899  | 8.714   | 6.685   | 47.298  | 6.685     |
| CARPINUS | 32.854  | 11.478  | 1.171   | 45.503  | 1.171     |
| ROBINIA  | 37.062  | 3.576   | 1.173   | 41.811  | 1.173     |
| PLATANUS | 29.474  | 9.894   | 598     | 39.966  | 598       |
| AESCULUS | 32.672  | 5.477   | 1.316   | 39.465  | 1.316     |
| FRAXINUS | 25.116  | 7.753   | 2.511   | 35.380  | 2.511     |
| PRUNUS   | 23.350  | 6.655   | 2.755   | 32.760  | 2.755     |

### 5.2 Variante B (edge_15m) - Alle 8 Gattungen

| Gattung  | Berlin  | Hamburg | Rostock | Gesamt  | Min/Stadt |
| -------- | ------- | ------- | ------- | ------- | --------- |
| TILIA    | 120.304 | 39.618  | 8.117   | 168.039 | 8.117     |
| ACER     | 63.523  | 15.066  | 4.976   | 83.565  | 4.976     |
| QUERCUS  | 33.102  | 28.277  | 1.748   | 63.127  | 1.748     |
| BETULA   | 8.731   | 3.258   | 1.720   | 13.709  | 1.720     |
| FRAXINUS | 7.701   | 3.818   | 1.071   | 12.590  | 1.071     |
| PRUNUS   | 5.245   | 3.244   | 924     | 9.413   | 924       |
| POPULUS  | 5.919   | 630     | 918     | 7.467   | 630       |
| SORBUS   | 2.395   | 3.524   | 1.208   | 7.127   | 1.208     |

---

## 6. Filterverluste

### 6.1 Schrittweise Verluste (Variante A)

| Schritt             | Vorher    | Nachher   | Verlust | Verlust % |
| ------------------- | --------- | --------- | ------- | --------- |
| Zeitlicher Filter   | 1.245.676 | 1.227.492 | 18.184  | 1,5%      |
| Räumlicher Filter   | 1.227.492 | 1.221.934 | 5.558   | 0,5%      |
| Gattungs-Viabilität | 1.221.934 | 1.140.172 | 81.762  | 6,7%      |
| **Gesamt**          | 1.245.676 | 1.140.172 | 105.504 | **8,5%**  |

### 6.2 Schrittweise Verluste (Variante B)

| Schritt             | Vorher    | Nachher   | Verlust | Verlust % |
| ------------------- | --------- | --------- | ------- | --------- |
| Zeitlicher Filter   | 1.245.676 | 1.227.492 | 18.184  | 1,5%      |
| Räumlicher Filter   | 1.227.492 | 1.221.934 | 5.558   | 0,5%      |
| Kantenfilter (≥15m) | 1.221.934 | 470.326   | 751.608 | 61,5%     |
| Gattungs-Viabilität | 470.326   | 365.037   | 105.289 | 22,4%     |
| **Gesamt**          | 1.245.676 | 365.037   | 880.639 | **70,7%** |

---

## 7. Räumliche Gitterstatistiken

### 7.1 Variante A (no_edge)

| Stadt   | Gitterzellen | Ø Bäume/Zelle |
| ------- | ------------ | ------------- |
| Berlin  | 895          | 963,1         |
| Hamburg | 695          | 310,5         |
| Rostock | 150          | 416,3         |
| Gesamt  | 1.740        | 655,3         |

### 7.2 Variante B (edge_15m)

| Stadt   | Gitterzellen | Ø Bäume/Zelle |
| ------- | ------------ | ------------- |
| Berlin  | 882          | 280,0         |
| Hamburg | 684          | 142,4         |
| Rostock | 143          | 144,6         |
| Gesamt  | 1.709        | 213,6         |

---

## 8. Ausgabeschema

Beide Varianten haben identisches Schema:

| Spalte                  | Typ    | Beschreibung                          |
| ----------------------- | ------ | ------------------------------------- |
| `tree_id`               | string | Eindeutige Baum-ID                    |
| `city`                  | string | Stadtname                             |
| `genus_latin`           | string | Lateinischer Gattungsname (UPPERCASE) |
| `species_latin`         | string | Lateinischer Artname                  |
| `plant_year`            | Int64  | Pflanzjahr (nullable)                 |
| `height_m`              | float  | Baumhöhe in Metern                    |
| `crown_diameter_m`      | float  | Kronendurchmesser in Metern           |
| `stem_circumference_cm` | float  | Stammumfang in Zentimetern            |
| `source_layer`          | string | Quell-Layer                           |
| `min_dist_other_genus`  | float  | Abstand zur nächsten Fremdgattung (m) |
| `grid_x`                | int    | Gitter-X-Koordinate (1km)             |
| `grid_y`                | int    | Gitter-Y-Koordinate (1km)             |
| `grid_id`               | string | Gitterzellenkennung (z.B. "567_5934") |
| `geometry`              | Point  | Punktgeometrie (EPSG:25832)           |

---

## 9. Metadaten-Ausgaben

```
data/tree_cadastres/
├── processed/
│   ├── trees_filtered_viable_no_edge.gpkg
│   ├── trees_filtered_viable_edge_15m.gpkg
│   ├── filtering_report_no_edge.json
│   └── filtering_report_edge_15m.json
└── metadata/
    ├── genus_viability_no_edge.csv      # Viable Gattungen mit Zählungen
    ├── genus_viability_edge_15m.csv
    ├── all_genera_counts_no_edge.csv    # Alle Gattungen (Dokumentation)
    ├── all_genera_counts_edge_15m.csv
    ├── filtering_losses_no_edge.csv     # Schritt-für-Schritt Verluste
    └── filtering_losses_edge_15m.csv
```

---

## 10. Verwendung

```bash
uv run python scripts/tree_cadastres/filter_trees.py
```

**Laufzeit:** ~5-10 Minuten (hauptsächlich KD-Tree-Berechnung)

---

## 11. Technische Abhängigkeiten

| Paket       | Version | Verwendung                   |
| ----------- | ------- | ---------------------------- |
| `geopandas` | ≥0.14   | Geodaten-Handling            |
| `scipy`     | ≥1.10   | KD-Tree für Nearest-Neighbor |
| `pandas`    | ≥2.0    | Datenverarbeitung            |
| `numpy`     | ≥1.24   | Numerische Operationen       |

---

## 12. Entscheidungsmatrix: Variante A vs. B

| Kriterium               | Variante A (no_edge) | Variante B (edge_15m) |
| ----------------------- | -------------------- | --------------------- |
| **Stichprobengröße**    | 1.140.172            | 365.037               |
| **Gattungsanzahl**      | 20                   | 8                     |
| **Spektrale Reinheit**  | Niedriger            | Höher                 |
| **Statistische Power**  | Höher                | Niedriger             |
| **Generalisierbarkeit** | Breiter              | Fokussierter          |
| **Empfohlener Einsatz** | Explorative Analyse  | Finale Klassifikation |

**Empfehlung:**

- **Variante A** für initiale Modellentwicklung und Hyperparameter-Tuning
- **Variante B** für finale Modellvalidierung und Cross-City-Transfer-Experimente

---

## 13. Nächste Schritte

Die gefilterten Datensätze sind bereit für:

1. **Feature-Extraktion:** Spatial Join mit Sentinel-2 und CHM-Rastern
2. **Größenklassen-Zuweisung:** CHM-basierte Baumhöhen-Klassifikation
3. **Stratifiziertes Sampling:** Räumlich getrennte Train/Val/Test-Splits
4. **Klassifikation:** Random Forest vs. 1D-CNN Modelltraining

---

## 14. Referenzen

- [SciPy cKDTree Dokumentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html)
- [GeoPandas Spatial Joins](https://geopandas.org/en/stable/docs/user_guide/mergingdata.html)
- Sentinel-2 Pixelgröße: 10m × 10m (Bands B02-B04, B08)
