# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Multiple edge filter variants** for tree cadastre filtering:
  - `edge_15m`: 363.571 trees, 8 genera (standard)
  - `edge_20m`: 280.524 trees, 7 genera
  - `edge_30m`: 195.118 trees, 6 genera
  - Enables trade-off analysis between sample size and spectral purity
- Power analysis documentation for 500-sample threshold in `05_Baumfilterung_Methodik.md`

- Sentinel-2 coverage validation script (`scripts/sentinel2/validate_coverage.py`):
  - Creates CSV report with quality metrics for all Sentinel-2 files
  - Metrics: cloud-free coverage (%), band count, file size, resolution, CRS, data range
  - Coverage calculated relative to city geometry (not BBox)
  - Summary statistics per city with problem month identification
  - **Output**: `data/sentinel2/coverage_report.csv`
  - **Results**: Hamburg 84.5% mean, Berlin 92.0% mean, Rostock 96.1% mean coverage
  - **Problem months**: Hamburg Dec (17.1%), Berlin Nov (21.1%)

### Changed

- **Tree filter now treats NaN-genus trees as contamination sources**:
  - Trees without genus are included in edge distance calculation
  - A known-genus tree near a NaN-genus tree is filtered out
  - NaN-genus trees themselves are not exported
  - 14.282 NaN-genus trees affect edge calculations
- CHM quality filters now set negative values to NoData instead of 0:
  - **Rationale**: Negative CHM values indicate water, bridges, or interpolation errors - not vegetation
  - Setting to 0 artificially skewed statistics (median was 0.26m instead of realistic ~8m)
  - Now: negative values → NoData, outliers >60m → NoData
  - Expected mean ranges updated: 500m Buffer 4-25m, City Core 6-30m
- CHM statistics now use geometry-based valid_percent calculation:
  - `compute_statistics()` accepts optional `reference_mask` parameter
  - Valid percent calculated as `valid_in_geometry / pixels_in_geometry` (not BBox)
  - New `create_geometry_mask()` helper function
  - `mask_to_city_core()` now returns tuple (masked_chm, geometry_mask)
  - Process steps increased from 8 to 9 (added "Geometrie-Masken erstellen")
  - Output now shows "Valid: XX.X%" in console
- Sentinel-2 download script CRS and clipping improvements:
  - Added `reproject_and_clip()` function for local CRS conversion (EPSG:32632 → EPSG:25832)
  - Clips output to city boundary geometry (not just BBox)
  - `validate_output()` now accepts `city_geometry` parameter for correct cloud-free calculation
  - Cloud-free coverage now calculated relative to city geometry pixels

### Fixed

- CHM JSON serialization error (`TypeError: Object of type int64 is not JSON serializable`):
  - Added `int()` cast for numpy int64 values in `compute_statistics()` and `apply_quality_filters()`
  - Added `round()` for cleaner float output
- Sentinel-2 validation showed misleading "valid pixel" percentages:
  - Previously: ~52.8% for Hamburg (actually city boundary coverage within BBox)
  - Now: Shows true cloud-free coverage (e.g., Jan: 100%, Dec: 17.1%)
- CHM valid_percent calculation used BBox instead of city geometry:
  - Previously: `valid_count / chm.size` (underestimated actual coverage)
  - Now: `valid_in_geometry / pixels_in_geometry` (correct coverage metric)

### Removed

- Temporary diagnostic scripts: `scripts/chm/analyze_alignment.py`, `scripts/chm/chm_diagnostic_report.py`

---

## [0.6.0] - 2025-12-02

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
- Data validation script (`scripts/validation/validate_data.py`):
  - Pre-feature-extraction quality checks for spatial alignment and data consistency
  - **Priority 0 - CRS & Projection Validation**:
    - Check 0.1: Input CRS verification (verifies CHM EPSG:25832, S2/cadastre EPSG:32632)
    - Check 0.2: CRS consistency check (validates project uses EPSG:32632 throughout)
  - **Priority 0.5 - Extended CHM Resampling**:
    - Check 0.3: CHM resampling to 10m with three aggregation methods (mean, max, std)
    - Generates `CHM_10m_mean_{city}.tif`, `CHM_10m_max_{city}.tif`, `CHM_10m_std_{city}.tif`
    - STD computed via variance formula: sqrt(E[X²] - E[X]²)
  - **Priority 0.75 - Spatial Alignment Verification**:
    - Check 0.4: Correlation-based offset detection (-20m to +20m in 10m steps)
    - Check 0.5: Tree point NDVI-CHM correlation (hexbin scatterplots)
    - Check 0.6: Transect profile analysis (3 transects per city through known parks)
    - Check 0.7: Known-feature validation (park bounding boxes with CHM/NDVI thresholds)
  - **Priority 1 - Critical Checks (STOPPERS)**:
    - Check 1.1: CHM ↔ Sentinel-2 grid alignment (resamples CHM 1m → 10m matching S2 grid)
    - Check 1.2: CHM plausibility at tree points (compares CHM_mean vs CHM_max)
  - **Priority 2 - Informative Checks**:
    - Check 2.1: Visual spot checks (9 random 500m² tiles with CHM, NDVI, tree points overlay)
    - Check 2.2: Height correlation (cadastre height vs. CHM height for Berlin/Rostock)
    - Check 2.3: Temporal consistency (S2 monthly reflectance patterns, summer/winter NIR ratio)
  - **Priority 3 - Ablation Preparation**:
    - Check 3.2: Band correlation sanity check (10-band correlation matrix)
  - **Output files**:
    - `data/CHM/processed/CHM_10m/CHM_10m_{mean,max,std}_{City}.tif` - CHM variants at 10m resolution
    - `data/validation/crs_verification_report.csv` - CRS verification results
    - `data/validation/chm_resampling_extended_report.csv` - Resampling statistics
    - `data/validation/offset_detection_{City}.png` - Offset correlation heatmaps
    - `data/validation/offset_detection_results.csv` - Offset detection metrics
    - `data/validation/tree_point_correlation_{City}.png` - NDVI-CHM scatterplots
    - `data/validation/tree_point_correlation_stats.csv` - Correlation statistics
    - `data/validation/transect_{City}_t{1-3}.png` - Transect profile plots
    - `data/validation/transect_analysis_results.csv` - Transect peak alignment
    - `data/validation/known_feature_validation.csv` - Park validation results
    - `data/validation/grid_alignment_report.json` - Grid alignment metrics
    - `data/validation/chm_plausibility_stats.csv` - Tree point plausibility statistics
    - `data/validation/visual_alignment_{city}_tile{1-3}.png` - 9 visual alignment plots
    - `data/validation/height_correlation_{city}.png` - Height correlation scatterplots
    - `data/validation/temporal_consistency_{city}.png` - Monthly reflectance time series
    - `data/validation/band_correlation_heatmap.png` - S2 inter-band correlation matrix
    - `data/validation/validation_summary_report.md` - Final summary report
- Dependencies: `geopandas`, `requests`, `matplotlib`, `rasterio`, `feedparser`, `tqdm`, `numpy`, `pandas`, `openeo`, `jupyter`, `jupyterlab`, `owslib`, `scipy`, `seaborn`
