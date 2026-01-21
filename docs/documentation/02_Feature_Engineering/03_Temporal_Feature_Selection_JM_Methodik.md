# Temporal Feature Selection: Jeffries-Matusita Analyse

**Notebook:** `notebooks/02_feature_engineering/03a_temporal_feature_selection_JM.ipynb`  
**Laufzeit:** ~45-60 min  
**Output:** 184 zeitliche Features (März-Oktober statt alle 12 Monate)

## Ziel & Methodik

**Jeffries-Matusita (JM) Distance Analysis** zur Identifikation diskriminativster Monate für Baumarten-Klassifikation. Die Pipeline reduziert Sentinel-2 Temporal Features von 12 auf 8 Monate (März-Oktober) durch monatliche Separabilität-Analyse aller Gattungspaare.

**JM-Interpretation:** Distanz zwischen 0 (vollständige Überlappung) und 2 (perfekte Separabilität). JM ≥1.0 = akzeptable Diskriminierung.

## Output

**Reduzierte GeoPackages:**

- `trees_temporal_reduced_no_edge.gpkg`: 1.028M Bäume, 190 Features (-33%)
- `trees_temporal_reduced_20m_edge.gpkg`: 0.875M Bäume, 190 Features (-33%)

**Metadaten:** jm_distances_by_month.csv, selected_months.json, Visualisierungen (Linienchart, Heatmap)

**Ausgewählte Monate:** März-Oktober (8 kontinuierliche Monate mit JM ≥0.72 in allen Städten)

### 1.3 Untersuchungsgebiete

Berlin (kontinental), Hamburg (maritim, frühere Phänologie), Rostock (baltische Küste, variable Phänologie)

## Workflow

**Phase 1:** JM-Berechnung für alle Monate/Städte/Gattungspaare (171 Paare, 23 Bänder, 36 Stadt-Monat Kombinationen)

**Phase 2:** Identifikation gültiger Monate (JM ≥50% max in allen Städten) → März-Oktober selektiert

**Phase 3:** Feature-Reduktion: Filtere Sentinel-2 Features außerhalb März-Oktober, behalte Metadaten & CHM

**Input:** trees*qc_no_edge.gpkg, trees_qc_edge_20m.gpkg (280 Features)  
**Output:** trees_temporal_reduced*\*.gpkg (190 Features: 4 CHM + 184 S2)

## JM-Konzept & Phänologie

**Jeffries-Matusita Distance** (Bhattacharyya-basiert):

- JM ∈ [0,2]: 0=Überlappung, 1=akzeptabel, 2=perfekt separierbar
- Univariat pro Feature berechnet, über alle Gattungspaare (171 Paare × 23 Bänder) gemittelt
- Resultat: Monatliche JM-Werte zeigen saisonale Struktur

**Phänologische Phasen:**

- **Jan-Feb, Nov-Dec (Winter):** JM ~0.4-0.5 (niedrig: keine Blätter, 60-80% Cloud Cover)
- **März-April, Sept-Okt (Übergänge):** JM ~0.8-1.2 (moderat: Blattaustrieb/Seneszenz)
- **Mai-Aug (Peak):** JM ~1.3-1.4 (hoch: maximale Gattungs-Unterschiede in Spektral-Signaturen)

**Aggregation:** Mean JM über paarweise univariate Distanzen = interpretierbar, rechenbar

## Datenquellen & Implementierung

**Input:** trees*qc*\*.gpkg (1.028M Laubbäume, 280 Features: 4 CHM + 276 S2)

**JM-Berechnung:** Univariat pro Gattungspaar/Feature, gemittelt. JM = 2(1 - exp(-B)) wobei B = Bhattacharyya Distanz

**Selektion:** Schwellenwert = 50% max(JM_median) pro Stadt. Monate mit JM≥Threshold in ALLEN 3 Städten → März-Oktober

**Ergebnis (Berlin, No-Edge Beispiel):**
| Monat | JM | Interpretation |
|-------|-----|--------|
| 1,2,11,12 | 0.38-0.55 | Schwach (Winter) |
| 3,4,9,10 | 0.82-1.18 | Moderat (Übergänge) |
| 5,6,7,8 | 1.32-1.45 | Hoch (Peak) |

````

**Ergebnis:**

- **Vorher:** 280 Features (4 CHM + 276 S2)
- **Nachher:** 190 Features (4 CHM + 184 S2 aus 23 Bändern × 8 Monate)
- **Reduktion:** -33% Features

**Export:**

```python
# Export reduzierte Datensätze
trees_reduced.to_file('trees_temporal_reduced_no_edge.gpkg', driver='GPKG')
trees_reduced.to_file('trees_temporal_reduced_20m_edge.gpkg', driver='GPKG')

# Export Metadaten
jm_results.to_csv('jm_distances_by_month.csv')

selected_metadata = {
    'selected_months': SELECTED_MONTHS,
    'removed_months': [m for m in range(1, 13) if m not in SELECTED_MONTHS],
    'feature_reduction': {
        'before': 276,
        'after': 184,
        'reduction_pct': 33.3
    }
}

with open('selected_months.json', 'w') as f:
    json.dump(selected_metadata, f, indent=2)
````

---

## 5. Datenqualität & Validierung

### 5.1 Qualitätsprüfungen

**[Prüfung 1: JM-Berechnung Korrektheit]**

- **Methode:** Validiere JM-Formel gegen bekannte Testfälle
- **Kriterium:** JM ∈ [0, 2] für alle Berechnungen
- **Ergebnis:** ✅ Bestanden (alle Werte im Bereich)

**[Prüfung 2: Cross-City Konsistenz]**

- **Methode:** Vergleiche JM-Muster über alle 3 Städte
- **Kriterium:** Monate mit hohem JM sollten konsistent sein über Städte
- **Ergebnis:** ✅ Bestanden
  - März-Oktober: Hohe JM in allen Städten
  - Jan-Feb, Nov-Dec: Niedrige JM konsistent über Städte

**[Prüfung 3: Phänologische Plausibilität]**

- **Methode:** Vergleiche JM-Trends mit bekannten Phenological Events
- **Kriterium:**
  - Anstieg März-April (Blattaustrieb) ✓
  - Peak Mai-Juli (volle Vegetation) ✓
  - Rückgang Aug-Okt (Seneszenz) ✓
- **Ergebnis:** ✅ Bestanden

**[Prüfung 4: Feature-Vollständigkeit nach Reduktion]**

- **Methode:** Zähle Spalten nach Filterung
- **Kriterium:** 190 Features pro Baum (4 CHM + 184 S2)
- **Ergebnis:** ✅ Bestanden

### 5.2 Fehlerbehandlung

**[Fehlertyp 1: NaN-Puffer bei JM-Berechnung]**

- **Problem:** Zu wenige Samples nach NaN-Entfernung (<10 pro Gattung/Monat)
- **Häufigkeit:** Selten, hauptsächlich Winter-Monate
- **Lösung:** Skip Gattungspaar wenn zu wenige Samples → nicht in JM-Aggregation einschließen

**[Fehlertyp 2: Division durch Null (Varianz = 0)]**

- **Problem:** Wenn alle Feature-Werte einer Gattung identisch sind
- **Häufigkeit:** Sehr selten (robuste Realdaten)
- **Lösung:** Regularisierung: $\sigma^2 = \max(\sigma^2, 10^{-10})$

### 5.3 Feature-Reduktion Auswirkungen

**Gewollte Reduktion (bewusste Filterung):**

| Kriterium         | Anzahl entfernt | % des Ursprungs | Begründung                           |
| ----------------- | --------------- | --------------- | ------------------------------------ |
| Winter-Monate (4) | 92              | 33.3%           | Niedrige JM, hohe NaN-Rate           |
| Erhaltene Monate  | 184             | 66.7%           | März-Oktober (high discriminability) |

---

## 6. Ergebnisse & Statistiken

### 6.1 Output-Übersicht

**Exportierte Dateien:**

```
data/02_pipeline/04_feature_reduction/01_temporal_selection/
├── data/
│   ├── trees_temporal_reduced_no_edge.gpkg       (1.028M Bäume, 190 Features)
│   └── trees_temporal_reduced_20m_edge.gpkg      (0.875M Bäume, 190 Features)
├── metadata/
│   ├── jm_distances_by_month.csv                 (36 Zeilen: 3 Städte × 12 Monate)
│   ├── selected_months.json                      (Auswahlmetadaten)
│   └── jm_analysis_report.md                     (Ausführlicher Report)
└── plots/
    ├── jm_distance_temporal_trends.png           (Linienchart: JM Trends)
    └── jm_distance_heatmap_no_edge.png           (Heatmap: Stadt × Monat)
```

### 6.2 JM-Distanz Statistiken (nach Stadt)

## Ergebnisse

**JM nach Stadt (März-Oktober):**

- Berlin: Mean JM=1.17 (1.038M Bäume)
- Hamburg: Mean JM=1.12 (170k Bäume)
- Rostock: Mean JM=1.19 (60k Bäume)

**Feature-Reduktion:**

- 280 → 190 Features (-33%): 4 CHM + 184 S2 (23 Bänder × 8 Monate)
- Alle 1.028M Bäume behalten
- Winter-Monate (JM<0.6) entfernt

**Output-Dateien:**

- trees_temporal_reduced_no_edge.gpkg (1.028M, 190 Features)
- trees_temporal_reduced_20m_edge.gpkg (875k, 190 Features)
- Visualisierungen: jm_distance_temporal_trends.png, jm_distance_heatmap_no_edge.png

## Design-Entscheidungen

**1. Jeffries-Matusita Distance vs. Alternativen:** JM etabliert in Remote-Sensing, skaliert [0,2], robust, nicht-parametrisch

**2. Cross-City Aggregation:** Nur Monate mit JM≥Threshold in ALLEN Städten (statt Mean). Garantiert Generalisierung

**3. Kontinuierliche 8-Monat Sequenz:** März-Oktober (phänologisch motiviert, einfacher für Zeitreihen-Modelle) statt Best-6-Months

**4. Mean JM (ungewichtet):** Alle 23 Features gleich gewichtet. Feature-Gewichte benötigen separate Selektion

## Reproduzierbarkeit

**Notebook:** `notebooks/02_feature_engineering/03a_temporal_feature_selection_JM.ipynb`

**Laufzeit:** 45-60 min (CPU-intensiv)  
**RAM:** 10-12 GB (Peak bei JM-Aggregation)  
**Disk:** ~500 MB Output

**Input:** trees*qc*_.gpkg  
**Output:** trees*temporal_reduced*_.gpkg + Visualisierungen
