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
  - Handles XYZ ASCII format conversion to GeoTIFF using GDAL
  - Clips to city boundary with 500m buffer
  - Saves as `data/raw/hamburg/{dom,dgm}_1m.tif`
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
- Dependencies: `geopandas`, `requests`, `matplotlib`, `rasterio`, `feedparser`, `tqdm`, `numpy`

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
