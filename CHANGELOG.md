# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project structure with data directories (`data/raw/`, `data/processed/`, `data/boundaries/`), scripts, notebooks, and docs
- UV virtual environment setup for dependency management
- Restructured scripts into city-specific subfolders:
  - `scripts/boundaries/download_city_boundaries.py` - City boundary download
  - `scripts/elevation/{hamburg,berlin,rostock}/download_elevation.py` - Elevation data per city
- City boundaries script (`scripts/boundaries/download_city_boundaries.py`):
  - Downloads administrative boundaries for Hamburg, Berlin, and Rostock from BKG WFS service
  - Cleans boundary data by removing duplicates and selecting relevant columns
  - Filters MultiPolygon geometries to keep only largest polygon (mainland) per city
  - Creates 500m buffer zones around city boundaries
  - Saves to `data/boundaries/` as GeoPackage files
  - Generates visualization comparing original and buffered boundaries
- Hamburg elevation script (`scripts/elevation/hamburg/download_elevation.py`):
  - Downloads DOM and DGM from Hamburg Open Data portal
  - **Data format**: XYZ ASCII in ZIP (multiple tiles covering city)
  - **Fixed**: Initial version only processed first tile (1km²) - now processes all ~850+ tiles
  - Converts ALL XYZ tiles to GeoTIFF using `gdal_translate`
  - **Handles mixed raster orientations** - uses direct `gdalwarp` merge (no VRT) for tiles with inconsistent Y-axis direction
  - Mosaics all tiles with `rasterio.merge` (DOM) or `gdalwarp` (DGM with orientation issues)
  - Clips to city boundary with 500m buffer
  - Saves as `data/raw/hamburg/{dom,dgm}_1m.tif`
  - **Validation results**: DOM 2.3GB (40,363×39,000 pixels), DGM 1.1GB (40,418×39,132 pixels)
  - Full city coverage: ~736 km²
- Berlin elevation script (`scripts/elevation/berlin/download_elevation.py`):
  - Parses nested Atom feed structure for DOM and DGM tiles
  - **Data format**: XYZ ASCII in ZIP (not GeoTIFF as originally documented)
  - Filters tiles by coordinate-based naming pattern
  - Converts XYZ to GeoTIFF using GDAL (`gdal_translate`)
  - Mosaics multiple tiles if needed
  - Clips to city boundary with 500m buffer
  - Saves as `data/raw/berlin/{dom,dgm}_1m.tif`
- Rostock elevation script (`scripts/elevation/rostock/download_elevation.py`):
  - Parses Geodaten MV Atom feeds for DOM and DGM
  - **Data format**: XYZ ASCII in ZIP (EPSG:25833, irregular whitespace delimiters)
  - **Critical spatial filtering** using bbox attributes in feed to avoid downloading entire MV state (32,035 tiles total!)
  - Filters to ~115 DOM tiles and ~230 DGM tiles for Rostock using spatial intersection
  - **Parallel processing** with 3 workers for faster tile conversion
  - **Custom NumPy/Rasterio gridding** - `gdal_grid` failed due to VRT parsing issues with irregular whitespace format
  - Loads XYZ data with `numpy.loadtxt` (handles variable whitespace), grids to 1m raster, then reprojects
  - Reprojects from EPSG:25833 to EPSG:25832 for consistency using `gdalwarp`
  - Mosaics intersecting tiles and clips to city boundary
  - Saves as `data/raw/rostock/{dom,dgm}_1m.tif`
  - **Validation results**: DOM 657MB (48.2% valid pixels), DGM 584MB (47.9% valid pixels)
  - ~52% NoData expected due to irregular city boundary clipping and Baltic Sea water bodies
- Sentinel-2 download script (`scripts/sentinel2/download_sentinel2.py`):
  - Downloads Sentinel-2 L2A monthly median composites using openEO (Copernicus Data Space)
  - Cloud-native processing: cloud masking (SCL band), temporal aggregation, resampling all server-side
  - **Output**: 10 spectral bands (B02-B12, excluding B01/B09/B10) @ 10m resolution
  - Cloud masking excludes: shadows (3), medium clouds (8), high clouds (9), thin cirrus (10)
  - 20m bands (B05-B07, B8A, B11, B12) resampled to 10m via bilinear interpolation
  - **CLI interface**: `--cities`, `--year`, `--months` (range notation e.g. "4-10"), `--output`, `--no-resume`
  - Checkpointing: skips already downloaded and validated files (use `--no-resume` to override)
  - Validation checks: band count (10), CRS, resolution (~10m), valid pixels >30%, reflectance 0-10000
  - **Expected output**: `data/sentinel2/{city}/S2_2024_{MM}_median.tif` (36 files total)
- CHM (Canopy Height Model) creation script (`scripts/chm/create_chm.py`):
  - Computes CHM = DOM - DGM for Hamburg, Berlin, and Rostock
  - Handles shape mismatches by cropping to common extent (e.g., Berlin: 37360×46092 → 37359×46092)
  - Applies quality filters: negative values → 0, outliers >60m → 60m (capped)
  - Computes statistics for full extent and city core (masked by `city_boundaries.gpkg`)
  - Generates comprehensive visualizations: histograms, box plots, CDFs, spatial maps, QA plots
  - Saves cleaned CHMs to `data/processed/CHM_1m_{City}.tif` with DEFLATE compression (predictor=3, 512×512 tiles)
  - Exports statistics to `data/processed/chm_statistics.csv`
  - Smart skip logic: preserves existing city statistics when re-running
  - **Output files**:
    - Hamburg: 1.7GB (40,363×39,000 pixels, 47.5% valid, mean 4.08m)
    - Berlin: 2.3GB (46,092×37,359 pixels, 54.6% valid, mean 6.39m)
    - Rostock: 465MB (19,822×22,953 pixels, 46.6% valid, mean 5.03m)
  - **Quality validation**: All cities passed plausibility checks (0 negative pixels, 0 outliers >60m)
- Jupyter notebook for CHM analysis (`notebooks/chm/chm_creation_qa.ipynb`):
  - Interactive version of CHM creation with detailed exploration
  - Same processing pipeline as Python script
- Documentation:
  - `docs/documentation/01_Datenakquise_Methodik.md` - Elevation data acquisition methodology
  - `docs/documentation/02_CHM_Berechnung_Methodik.md` - CHM calculation and quality assessment methodology
- Tree cadastre download script (`scripts/tree_cadastres/download_tree_cadastres.py`):
  - Downloads tree cadastre data for Hamburg, Berlin, and Rostock
  - **Hamburg**: OGC API Features (229,013 trees, 22 attributes)
  - **Berlin**: WFS with two layers combined (anlagenbaeume + strassenbaeume = 945,907 trees, 22 attributes)
  - **Rostock**: WFS (70,756 trees, 17 attributes)
  - Extracts comprehensive schema metadata: dtypes, null counts, unique values, sample values
  - Generates cross-city comparison CSV (`schema_summary.csv`)
  - Saves individual schema JSONs per city
  - **Output**: `data/tree_cadastres/raw/{city}_trees_raw.gpkg` + `data/tree_cadastres/metadata/`
- Tree cadastre harmonization script (`scripts/tree_cadastres/harmonize_tree_cadastres.py`):
  - Harmonizes Berlin, Hamburg, and Rostock tree cadastres into unified schema
  - **CRS harmonization**: Berlin/Rostock EPSG:25833 → EPSG:25832 (Hamburg already 25832)
  - **Geometry unification**: Hamburg MultiPoint → Point conversion
  - **Schema normalization**: 10 standardized columns (`tree_id`, `city`, `genus_latin`, `species_latin`, `plant_year`, `height_m`, `crown_diameter_m`, `stem_circumference_cm`, `source_layer`, `geometry`)
  - **Genus normalization**: Uppercase Latin genus names for consistent classification labels
  - **Validation**: CRS check, geometry type check, uniqueness check, city presence check
  - **Output**: `data/tree_cadastres/processed/trees_harmonized.gpkg` (210.5 MB, 1,245,676 trees)
  - **Statistics**: Top genera: TILIA (20.9%), ACER (20.6%), QUERCUS (13.3%)
- Documentation:
  - `docs/documentation/03_Baumkataster_Methodik.md` - Tree cadastre acquisition and harmonization methodology
- Tree cadastre filtering script (`scripts/tree_cadastres/filter_trees.py`):
  - Applies temporal, spatial, and genus viability filters to harmonized tree data
  - **Temporal filter**: Excludes trees planted after CHM reference year (2021), retains NaN plant_year
  - **Spatial filter**: Clips to city boundaries (removes 500m buffer zone trees)
  - **Edge distance calculation**: KD-Tree per genus for O(n log n) nearest-neighbor search
  - **Genus viability check**: Identifies genera with ≥500 samples in ALL three cities
  - **Spatial grid assignment**: 1km² cells for future stratified sampling (`grid_id` column)
  - **Two output variants**:
    - `trees_filtered_viable_no_edge.gpkg`: 1,140,172 trees, 20 viable genera
    - `trees_filtered_viable_edge_15m.gpkg`: 365,037 trees (≥15m from other genera), 8 viable genera
  - **Viable genera (no_edge)**: ACER, AESCULUS, ALNUS, BETULA, CARPINUS, CORYLUS, CRATAEGUS, FAGUS, FRAXINUS, MALUS, PINUS, PLATANUS, POPULUS, PRUNUS, QUERCUS, ROBINIA, SALIX, SORBUS, TILIA, ULMUS
  - **Viable genera (edge_15m)**: ACER, BETULA, FRAXINUS, POPULUS, PRUNUS, QUERCUS, SORBUS, TILIA
  - **Metadata exports**: `genus_viability_{variant}.csv`, `all_genera_counts_{variant}.csv`, `filtering_losses_{variant}.csv`, `filtering_report_{variant}.json`
  - **Filtering losses**: 1.5% temporal, 0.5% spatial, 6.7%/22.4% genus viability (no_edge/edge_15m)
- Dependencies: `geopandas`, `requests`, `matplotlib`, `rasterio`, `feedparser`, `tqdm`, `numpy`, `pandas`, `openeo`, `jupyter`, `jupyterlab`, `owslib`, `scipy`

### Changed

- N/A

### Deprecated

- N/A

### Removed

- N/A

### Fixed

- N/A

### Security

- N/A
