# GitHub Copilot Instructions - Tree Classification Project

## Project Overview

Cross-city tree species classification using Sentinel-2 satellite data and Canopy Height Models (CHM). Focuses on transfer learning between German cities (Berlin/Hamburg → Rostock) with reproducible ML pipelines.

## Execution Environment

**Primary:** Google Colab (NOT local) - notebooks mount Google Drive at `/content/drive/MyDrive/Studium/Geoinformation/Module/Projektarbeit`

- Always use Colab-style imports: `from google.colab import drive` before `drive.mount('/content/drive')`
- Base paths reference Google Drive, not local filesystem
- Data directory is excluded from git (lives only on Drive)

**Local:** Used only for scripts in `scripts/` (boundaries, tree_cadastres, chm, elevation)

## Project Structure & Data Flow

```
data/                          # Google Drive only, NOT in git
├── 01_raw/                   # Downloads (tree cadastres, DOM/DGM)
├── 02_pipeline/              # Processing outputs (harmonized trees, CHM, Sentinel-2)
│   ├── 01_corrected/         # trees_corrected_{city}.gpkg (harmonized cadastres)
│   ├── 05_spatial_splits/    # berlin.parquet, rostock.parquet (ML-ready splits)
│   └── ...
└── 03_experiments/           # Experiment results by phase
    ├── 00_phase_0/           # Setup ablations (CHM, dataset, features)
    └── 01_phase_1/           # Algorithm ranking

scripts/                       # Local Python scripts (download/preprocessing)
notebooks/                     # Jupyter notebooks (Colab execution)
├── 01_processing/            # CHM resampling, Sentinel-2 GEE
├── 02_feature_engineering/   # Feature extraction, QC, spatial splits
└── 03_experiments/           # ML experiments by phase
```

## Critical Configuration

**Central config:** `scripts/config.py` defines:

- `TARGET_CRS = "EPSG:25832"` (UTM Zone 32N) - ALL geospatial data must use this
- `CITIES = ["Berlin", "Hamburg", "Rostock"]`
- Sentinel-2 bands: 10 spectral (B02-B12) + 5 vegetation indices
- Tree cadastre schema: `tree_id`, `city`, `genus_latin`, `species_latin`, `height_m`, `geometry`

**Reproducibility:** Always use `random_seed=42` in ML experiments

## Key Conventions

### File Naming

- Notebooks: `NN_description.ipynb` (leading number for ordering)
- Data: `{city}_{config}_{split}.{ext}` (e.g., `berlin_20m_edge_train.parquet`)
- CHM rasters: `CHM_10m_{mean|max|std}_{city}.tif`
- Sentinel-2: `S2_{city}_2021_{MM}_median.tif` (monthly composites)

### Data Formats

- **Vector:** GeoPackage (`.gpkg`) for geospatial, Parquet (`.parquet`) for ML (no geometry)
- **Raster:** GeoTIFF with LZW compression, 10m resolution aligned
- **Metadata:** JSON for configs/results, CSV for tabular metrics

### Notebook Structure (Standard Template)

1. Overview & Methodology
2. Setup & Imports (include Colab mount)
3. Configuration & Parameters
4. [Processing steps]
5. Validation & Summary
6. Summary & Next Steps

## ML Experiment Philosophy

### Phase Structure

- **Phase 0:** Setup ablations (fix base config: No CHM, 20m-Edge dataset, Top-50 features)
- **Phase 1:** Algorithm ranking (coarse HP tuning on Berlin to select 1 ML + 1 NN)
- **Phase 2:** Cross-city transfer evaluation
- **Phase 3:** Fine-tuning experiments
- **Phase 4:** Post-hoc analyses (tree-type effects, feature contributions, outliers)

### Decision Principles

- **Occam's Razor:** Choose simpler model if performance delta < 2-3%
- **Spatial Split:** 500m blocks prevent data leakage (never random split)
- **Feature Groups:** Spectral bands + vegetation indices × 8 months (Apr-Nov); CHM optional
- **Normalization:** StandardScaler fit ONLY on train, then transform val/test

## Common Workflows

### Running Notebooks

```python
# ALWAYS start Colab notebooks with:
from google.colab import drive
drive.mount('/content/drive')

BASE_DIR = Path("/content/drive/MyDrive/Studium/Geoinformation/Module/Projektarbeit")
DATA_DIR = BASE_DIR / "data"
```

### Local Script Execution

```bash
# Install dependencies via uv (package manager)
uv run python scripts/chm/create_chm.py
uv run python scripts/tree_cadastres/harmonize_tree_cadastres.py
```

### Feature Engineering Pipeline

1. `01_feature_extraction.ipynb` → Extract CHM + S2 features (280 total)
2. `02_data_quality_control.ipynb` → NaN handling (spatial imputation), outlier flagging
3. `03x_*_selection.ipynb` → Feature subset selection (Phase 0 determines Top-50)
4. `04_spatial_splits.ipynb` → 500m block-based train/val/test splits

## Dependencies

**Core Stack:** Python 3.10+, geopandas, rasterio, numpy, pandas, scikit-learn, xgboost
**ML:** pytorch-tabnet (neural networks), matplotlib/seaborn (viz)
**Geospatial:** Google Earth Engine API (Sentinel-2 download), GDAL (raster ops)

**Colab-specific:** Most libraries pre-installed; only install: `geopandas`, `rasterio`, `pytorch-tabnet`

## Documentation Style

- **Prägnant:** Document ONLY what was done, not future plans
- **Tables preferred:** For HP configs, feature lists, dataset specs
- **[PLATZHALTER]:** Mark unfinished sections explicitly
- **No ML basics:** Assume knowledge of Random Forest, XGBoost, etc.
- Refer to Phase 0 docs for style reference (~460 lines for 3 experiments)

## Common Pitfalls

1. **Never** reference local paths in notebooks - always use Drive-mounted paths
2. **Never** use CHM in Phase 1+ without justification (overfitting risk per Phase 0)
3. **Never** normalize before splitting data (StandardScaler on train only!)
4. **Never** use random splits (spatial blocks required to prevent leakage)
5. GeoPackages are large (800k+ Berlin trees) - use Parquet for ML after feature extraction

## Key Files to Reference

- `docs/PROJEKT_KONTEXT.md` - Project philosophy, structure, methodological decisions
- `docs/documentation/00_Projektdesign_und_Methodik/01_Projektübersicht.md` - Research questions
- `notebooks/TEMPLATE_NOTEBOOK.ipynb` - Standard notebook structure
- `scripts/config.py` - All configuration constants

## Questions to Ask

When unclear about experiment setup: "Which Phase 0 decision applies here?"
When choosing algorithms: "Does Phase 1 ranking already select this?"
When handling NaN: "Should I apply spatial imputation (8-nearest neighbors) or flag for removal?"
