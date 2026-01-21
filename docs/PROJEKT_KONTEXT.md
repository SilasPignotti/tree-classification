# Projekt-Kontext: Tree Species Classification

**Zweck:** Dieses Dokument fasst grundlegendes strukturelles Wissen über das Projekt zusammen, um bei zukünftigen Entwicklungsarbeiten schnell den Kontext wiederherzustellen.

---

## Projektübersicht

**Thema:** Machine Learning für Baumgattungs-Klassifikation in deutschen Städten basierend auf Sentinel-2 Satellitendaten

**Kernfrage:** Wie gut transferieren ML-Modelle zwischen verschiedenen Städten (Berlin, Hamburg, Rostock)?

**Wissenschaftlicher Fokus:**

- Cross-City Transfer Learning für urbane Baumkartierung
- Vergleich verschiedener ML-Paradigmen (Tree-based vs. Neural Networks)
- Praktische Anwendbarkeit mit begrenzten lokalen Daten (Fine-Tuning)

**Projektrahmen:**

- Einzelperson, 1 Semester
- Ressourcen-Constraints führen zu pragmatischen Entscheidungen
- Fokus auf reproduzierbare, nachvollziehbare Methodik

---

## Projektstruktur & Organisation

### Ordnerstruktur

```
project/
├── data/                          # Alle Daten (NICHT in Git)
│   ├── 01_raw/                   # Rohdaten aus Downloads
│   ├── 02_pipeline/              # Pipeline-Zwischenergebnisse
│   └── 03_experiments/           # Experiment-spezifische Daten
├── scripts/                       # Python-Skripte für Datenverarbeitung
│   ├── config.py                 # Zentrale Konfiguration
│   ├── boundaries/               # Stadt-Grenzen Download
│   ├── tree_cadastres/           # Baumkataster Verarbeitung
│   ├── chm/                      # Canopy Height Model
│   └── elevation/                # Geländehöhen
├── notebooks/                     # Jupyter Notebooks
│   ├── 01_processing/            # Datenverarbeitung
│   ├── 02_feature_engineering/   # Feature-Extraktion
│   └── 03_experiments/           # ML-Experimente
│       ├── 00_phase_0/           # Setup-Ablationsstudien
│       └── 01_phase_1/           # Algorithmus-Vergleich
├── docs/                          # Dokumentation
│   ├── arbeitsprotokolle/        # Wöchentliche Arbeitsprotokolle
│   ├── documentation/            # Methodikdokumentation
│   └── gpt_knowledge/            # Kompakte Zusammenfassungen
├── results/                       # Experiment-Ergebnisse
└── pyproject.toml                # Python-Projekt-Konfiguration
```

### Wichtige Konventionen

**Dateinamen:**

- Notebooks: `NN_description.ipynb` (mit führender Nummer für Reihenfolge)
- Scripts: `snake_case.py`
- Daten: `city_config_split.format` (z.B. `berlin_20m_edge_train.gpkg`)
- Metadaten: `descriptive_name.json/csv`

**Notebook-Struktur (Standard-Template):**

1. Overview & Methodology
2. Setup & Imports
3. Configuration & Parameters
4. [Verarbeitungsschritte - je nach Notebook]
5. Validation & Summary
6. Summary & Next Steps

**Python-Konventionen:**

- Python 3.13.5
- Dependencies in `pyproject.toml` (uv als Package Manager)
- Google Colab als primäre Ausführungsumgebung (GPU-Zugriff)
- Lokale Entwicklung in VSCode mit Jupyter

---

## Datenstruktur & Formate

### Geografische Daten

**Primärformat:** GeoPackage (`.gpkg`)

- Wird für alle räumlichen Zwischenschritte verwendet
- Enthält Geometrie + alle Features
- CRS: EPSG:25832 (UTM Zone 32N für Deutschland)

**ML-Format:** Parquet (`.parquet`)

- Für finale Feature-Datasets ohne Geometrie
- Deutlich schneller zu laden als GeoPackage
- Genutzt in Phase 1+ Experimenten

### Feature-Struktur

**Temporale Features:**

- 8 Monate Sentinel-2 Daten (April-November, Vegetationsperiode)
- Monatliche Aggregation (Median) zur Rauschreduktion
- Feature-Format: `{basename}_{month}` (z.B. `B04_apr`, `ndvi_jul`)

**Feature-Gruppen:**

- Spektrale Bänder: B02-B12 (10m/20m resample auf 10m)
- Vegetation Indices: NDVI, EVI, VARI, SAVI, etc.
- Red-Edge Indices: NDREI, IRECI, CIred-edge, etc.
- Water Indices: NDWI, NDII
- Optional: CHM (Canopy Height Model) - mit Vorsicht wegen Overfitting

**Feature-Engineering Pipeline:**

- Feature-Extraktion: Zeitreihen-Statistiken (Median, Std, Slopes, etc.)
- NaN-Handling: Spatial Imputation (median of 8-nearest neighbors)
- Outlier Detection: IQR-basiert mit outlier_flag (nicht automatisch gefiltert)
- Plausibility Checks: Domain-spezifische Schwellwerte

### Daten-Splits

**Spatial Block Split (500m):**

- Verhindert räumliches Leakage zwischen Train/Val/Test
- Berlin/Hamburg: 70/20/10 (Train/Val/Test)
- Rostock: 50/50 (Zero-Shot/Fine-Tune-Eval)
- Stratifiziert nach Genus (Klassenbalance)

**Wichtig:** Normalisierung (StandardScaler) immer nur auf Train fitten, dann auf Val/Test anwenden!

---

## Experiment-Philosophie & Methodik

### Phasen-Struktur

Das Projekt folgt einer strikten Phasen-Struktur:

**Phase 0: Setup-Ablation** (Fixiere Basis-Konfiguration)

- Exp 0.1: CHM-Strategie → Entscheidung: No CHM (Overfitting-Risiko)
- Exp 0.2: Dataset-Wahl → Entscheidung: 20m-Edge (6 Genera, spektral rein)
- Exp 0.3: Feature Reduction → Entscheidung: Top-50 (102.5% Retention vs. All)

**Phase 1: Algorithmus-Vergleich** (Single-City Ranking)

- Coarse HP-Tuning auf Berlin
- Ziel: 1 ML (RF/XGBoost) + 1 NN (TabNet/CNN) für Phase 2
- Limitation: Single-City Selection für Transfer-Ziel (pragmatisch wegen Ressourcen)

**Phase 2: Transfer Evaluation**

- Berlin→Rostock, Hamburg→Rostock, Combined→Rostock
- Vergleich ML vs. NN Transfer-Robustheit

**Phase 3: Fine-Tuning**

- Wie viel lokale Daten kompensieren Transfer-Verlust?

**Phase 4: Post-hoc Analysen**

- Exp 4.1: Tree-Type-Effekt
- Exp 4.2: Genus-spezifische Transfer-Analyse
- Exp 4.3: Feature-Gruppen-Contribution
- Exp 4.4: Real-World-Robustheit
- Exp 4.5: Outlier-Removal Ablation

### Entscheidungsprinzipien

**Occam's Razor:**

- Bei ähnlicher Performance (Δ < 2-3%): Einfacheres Modell/weniger Features wählen
- Begründung: Bessere Generalisierung, weniger Overfitting-Risiko

**Wissenschaftliche Ehrlichkeit:**

- Limitationen offen benennen (z.B. "Single-City Selection für Transfer-Ziel")
- Overfitting-Probleme nicht verschweigen
- Unsicherheiten dokumentieren

**Pragmatismus:**

- Ressourcen-Constraints akzeptieren und dokumentieren
- "Good enough" statt "perfekt" wenn Zeit/Rechenleistung begrenzt
- Coarse Grid Search statt exhaustive für schnelles Ranking

**Reproduzierbarkeit:**

- Random Seed: 42 (überall)
- Alle Entscheidungen in Markdown dokumentiert
- Config-Files für alle Experimente

---

## Dokumentations-Stil

### Methodikdokumentation (docs/documentation/)

**Prinzip:** "Prägnant, nur was gemacht wurde, nicht vorgreifen"

**Struktur pro Experiment:**

1. **Forschungsfrage** - Was wird getestet?
2. **Methodik** - Wie wurde getestet? (kompakt, Tabellen bevorzugt)
3. **Ergebnisse** - Was kam raus? (Zahlen, Plots)
4. **Entscheidung & Begründung** - Was wurde gewählt und warum?
5. **Designentscheidungen** - Trade-offs und Rationale
6. **Validierung** - Sanity Checks und Plausibilität

**Stil-Referenz:** Phase 0 Dokumentation

- ~460 Zeilen für 3 Experimente
- Keine Vorgriffe auf zukünftige Experimente
- Ehrlich über Limitationen
- [PLATZHALTER] für noch nicht ausgeführte Teile

**Anti-Pattern:**

- ❌ Lange Einleitungen
- ❌ Erklärung von Basis-ML-Konzepten
- ❌ Detaillierte Hyperparameter-Beschreibungen (nur in Tabellen)
- ❌ Redundante Wiederholungen

### Arbeitsprotokolle (docs/arbeitsprotokolle/)

**Format:** Wöchentlich, Markdown

- Datum im Dateinamen: `AP_XX_YYYY-MM-DD_bis_YYYY-MM-DD.md`
- Struktur: Ziele → Durchgeführt → Probleme → Nächste Schritte
- Bilder im Unterordner `bilder/`

### GPT-Knowledge (docs/gpt_knowledge/)

**Zweck:** Kompakte Zusammenfassungen für schnelles Einlesen

- Aggregiert aus detaillierter Dokumentation
- Max 1-2 Seiten pro Phase
- Fokus auf Entscheidungen und Ergebnisse

---

## Technische Details

### Python-Environment

**Package Manager:** uv (modern, schnell)

```bash
uv sync  # Dependencies installieren
uv add package_name  # Package hinzufügen
```

**Wichtige Dependencies:**

- geopandas, rasterio: Geodaten
- scikit-learn: ML-Basics
- xgboost: Gradient Boosting
- pytorch-tabnet: TabNet (pip install nicht via uv wegen Komplexität)
- matplotlib, seaborn: Visualisierung

### Google Colab Integration

**Mount-Point:** `/content/drive/MyDrive/Studium/Geoinformation/Module/Projektarbeit`

**Workflow:**

1. Notebook lokal in VSCode entwickeln
2. In Colab hochladen für Ausführung (GPU)
3. Outputs zurück in Drive synced

**Pro-Tipp:** BASE_DIR in Config-Cell für lokale/Colab Ausführung

### Git & Version Control

**Wichtig:** `data/` Ordner ist in `.gitignore`!

- Nur Code und Dokumentation in Git
- Daten zu groß für GitHub
- Backup über Google Drive

**Branch-Strategie:**

- `main`: Stabile Version
- Feature-Branches bei Bedarf

---

## Häufige Stolpersteine & Lösungen

### Problem: Spatial Leakage

**Lösung:** Spatial Block CV (500m Blocks), nie Standard Random Split bei räumlichen Daten

### Problem: CHM-Overfitting

**Symptom:** 100% Train Accuracy, 47% Train-Val Gap
**Lösung:** CHM weglassen oder heavy regularization (Phase 0 Entscheidung)

### Problem: Memory bei großen GeoPackages

**Lösung:**

- Parquet für ML-Workflows
- Subsample für schnelles Prototyping
- Colab Runtime mit High-RAM

### Problem: NaN in Features

**Lösung:**

- Spatial Imputation (8-nearest neighbors) statt globaler Median
- Validierung nach jedem Verarbeitungsschritt

### Problem: Class Imbalance

**Lösung:**

- `class_weight='balanced'` in RF/XGBoost
- Custom class_weights in PyTorch
- Stratified Sampling in Splits

### Problem: Inkonsistente Feature-Namen

**Lösung:**

- Zentrale `selected_features.json` aus Phase 0
- Validierung in jedem Notebook (validate_features() Funktion)

---

## Best Practices (aus dem Projekt gelernt)

### Notebooks

1. **Utility-Funktionen** immer am Anfang definieren (print_section, validate_features, etc.)
2. **Sektion-Header** mit `print_section()` für Übersichtlichkeit in Colab-Output
3. **Validation** nach jedem größeren Schritt (NaN-Check, Feature-Count, Genus-Balance)
4. **Export Summary** am Ende mit Statistiken

### Datenverarbeitung

1. **Pipeline-Struktur:** `01_raw → 02_pipeline → 03_experiments`
2. **Intermediate Outputs:** GeoPackage mit allen Features für Flexibilität
3. **Metadata Files:** JSON für Metadaten (data_prep_report.json), CSV für tabellarische Auswertungen
4. **Plots speichern:** Immer als PNG mit 300 DPI

### Experimente

1. **Config-First:** Alle Parameter in Config-Cells, keine Magic Numbers im Code
2. **Output-Struktur:** Jedes Experiment eigener Ordner mit standardisierten Dateien
3. **Reproducibility:** Random Seed, sklearn-Versionen, Colab-Runtime-Type dokumentieren
4. **Ablation-Prinzip:** Eine Variable pro Experiment ändern

### Dokumentation

1. **Concurrent:** Während Experiment, nicht nachträglich
2. **Decision-First:** Entscheidung + Begründung wichtiger als alle Details
3. **Visual:** Tabellen und Plots bevorzugen statt lange Texte
4. **Honest:** Limitations nicht verschweigen

---

## Projekt-Status & Deliverables

### Abgeschlossen (Stand: 20. Januar 2026)

- ✅ Phase 0: Alle 3 Experimente (CHM, Dataset, Features)
- ✅ Phase 0 Dokumentation (prägnanter Stil etabliert)
- ✅ Phase 1: Data Preparation (6 Parquet-Datasets)
- ✅ Phase 1 Dokumentation (Template mit Platzhaltern)

### In Progress

- 🔵 Phase 1: Algorithm Comparison (Notebook erstellt, noch nicht ausgeführt)
  - 01_algorithm_comparison Notebook (RF, XGBoost, TabNet)
  - Expected Runtime: 3-4h in Colab

### Geplant

- ⚪ Phase 2: Transfer Evaluation
- ⚪ Phase 3: Fine-Tuning
- ⚪ Phase 4: Post-hoc Analysen (inkl. Outlier-Removal Ablation)

### Finale Deliverables (Semesterende)

- Dokumentation aller Experimente (Markdown)
- Trained Models (Best ML + Best NN)
- Transfer-Evaluation Report
- Arbeitsprotokolle (wöchentlich)
- Optional: Paper-Draft

---

## Kommunikation & Präferenzen

**Sprache:**

- Dokumentation: Deutsch (für deutschsprachige Publikation)
- Code/Variablen: Englisch (Standard in ML)
- Kommentare: Deutsch bevorzugt

**Dateiformate:**

- Dokumentation: Markdown (nicht Word/PDF bis finaler Export)
- Code: Jupyter Notebooks für Exploration, Scripts für Produktion
- Plots: PNG (300 DPI)
- Daten: GeoPackage (Processing), Parquet (ML)

**Arbeitsweise:**

- Iterativ: Erst prototypen, dann dokumentieren
- Bottom-up: Aus Notebooks extrahieren, nicht top-down planen
- Pragmatisch: "Good enough" mit dokumentierten Limitationen

---

## Nützliche Referenzen im Projekt

**Haupt-Dokumente:**

- `docs/documentation/03_Experiments/00_Experiment_Design.md` - Gesamtübersicht aller Experimente
- `docs/documentation/03_Experiments/01_Phase_0_Methodik.md` - Stil-Referenz für Dokumentation
- `scripts/config.py` - Zentrale Pfade und Konstanten
- `notebooks/TEMPLATE_NOTEBOOK.ipynb` - Notebook-Template

**Config-Files:**

- `data/03_experiments/00_phase_0/03_experiment_feature_reduction/metadata/selected_features.json` - Finale Feature-Liste (Top-50)
- `data/03_experiments/01_phase_1/00_data_preparation/metadata/data_prep_report.json` - Dataset-Statistiken

---

**Letzte Aktualisierung:** 20. Januar 2026  
**Projekt-Phase:** Phase 1 (Algorithm Comparison in Progress)
