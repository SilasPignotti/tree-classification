"""
Zentrale Konfiguration für alle Skripte.
"""

from pathlib import Path

# =============================================================================
# Projekt-Verzeichnisse
# =============================================================================
DATA_DIR = Path("data")
BOUNDARIES_DIR = DATA_DIR / "boundaries"
SENTINEL2_DIR = DATA_DIR / "sentinel2"
CHM_DIR = DATA_DIR / "CHM"
TREE_CADASTRES_DIR = DATA_DIR / "tree_cadastres"

# =============================================================================
# Städte
# =============================================================================
CITIES = ["Berlin", "Hamburg", "Rostock"]

# =============================================================================
# Koordinatensysteme
# =============================================================================
TARGET_CRS = "EPSG:25832"  # ETRS89 / UTM Zone 32N
WGS84_CRS = "EPSG:4326"

# =============================================================================
# Stadtgrenzen
# =============================================================================
BOUNDARIES_PATH = BOUNDARIES_DIR / "city_boundaries.gpkg"
BOUNDARIES_BUFFERED_PATH = BOUNDARIES_DIR / "city_boundaries_500m_buffer.gpkg"
BUFFER_DISTANCE_M = 500

# BKG WFS-Dienst
BKG_WFS_URL = "https://sgx.geodatenzentrum.de/wfs_vg250"
BKG_WFS_LAYER = "vg250:vg250_gem"

# =============================================================================
# Sentinel-2
# =============================================================================
TARGET_RESOLUTION = 10  # Meter

# openEO Backend
OPENEO_BACKEND = "openeo.dataspace.copernicus.eu"

# Spektrale Bänder
SPECTRAL_BANDS = [
    "B02",  # Blue (10m)
    "B03",  # Green (10m)
    "B04",  # Red (10m)
    "B05",  # Red Edge 1 (20m → 10m)
    "B06",  # Red Edge 2 (20m → 10m)
    "B07",  # Red Edge 3 (20m → 10m)
    "B08",  # NIR (10m)
    "B8A",  # Narrow NIR (20m → 10m)
    "B11",  # SWIR 1 (20m → 10m)
    "B12",  # SWIR 2 (20m → 10m)
]

# SCL-Werte für Cloud-Masking
# 3=Cloud shadows, 8=Cloud medium, 9=Cloud high, 10=Thin cirrus
CLOUD_MASK_VALUES = [3, 8, 9, 10]

# Vegetationsindizes
VEGETATION_INDICES = ["NDre", "NDVIre", "kNDVI", "VARI", "RTVIcore"]

# Gesamtzahl der Output-Bänder
EXPECTED_BAND_COUNT = len(SPECTRAL_BANDS) + len(VEGETATION_INDICES)

# =============================================================================
# Baumkataster
# =============================================================================
TREE_CADASTRES_RAW_DIR = TREE_CADASTRES_DIR / "raw"
TREE_CADASTRES_PROCESSED_DIR = TREE_CADASTRES_DIR / "processed"
TREE_CADASTRES_METADATA_DIR = TREE_CADASTRES_DIR / "metadata"
TREE_CADASTRES_VALIDATION_DIR = TREE_CADASTRES_DIR / "validation"

TREE_CADASTRE_CONFIG = {
    "Hamburg": {
        "type": "ogc_api_features",
        "url": "https://api.hamburg.de/datasets/v1/strassenbaumkataster/collections/strassenbaumkataster_hh/items",
    },
    "Berlin": {
        "type": "wfs",
        "url": "https://gdi.berlin.de/services/wfs/baumbestand",
        "layers": ["baumbestand:anlagenbaeume", "baumbestand:strassenbaeume"],
    },
    "Rostock": {
        "type": "wfs",
        "url": "https://geo.sv.rostock.de/geodienste/baeume/wfs",
        "layers": None,  # Alle Layer verwenden
    },
}

# =============================================================================
# Baumfilterung
# =============================================================================
CHM_REFERENCE_YEAR = 2021
MIN_SAMPLES_PER_CITY = 500
EDGE_DISTANCE_THRESHOLDS_M = [15, 20, 30]
GRID_CELL_SIZE_M = 1000

# Harmonisiertes Zielschema für Baumkataster
TREE_CADASTRE_COLUMNS = [
    "tree_id",
    "city",
    "genus_latin",
    "species_latin",
    "plant_year",
    "height_m",
    "crown_diameter_m",
    "stem_circumference_cm",
    "source_layer",
    "geometry",
]

# =============================================================================
# Höhendaten (DOM/DGM)
# =============================================================================
CHM_RAW_DIR = CHM_DIR / "raw"
CHM_PROCESSED_DIR = CHM_DIR / "processed"
ELEVATION_RESOLUTION_M = 1  # 1m Auflösung

# Source CRS für verschiedene Bundesländer
ELEVATION_SOURCE_CRS = {
    "Berlin": "EPSG:25833",      # UTM Zone 33N
    "Hamburg": "EPSG:25832",     # UTM Zone 32N (already target CRS)
    "Rostock": "EPSG:25833",     # MV: UTM Zone 33N
}

# Download-URLs und Feed-Endpoints
ELEVATION_FEEDS = {
    "Berlin": {
        "DOM": "https://fbinter.stadt-berlin.de/fb/feed/senstadt/a_dom1",
        "DGM": "https://gdi.berlin.de/data/dgm1/atom",
        "type": "atom_nested",  # Feed hat nested structure
    },
    "Hamburg": {
        "DOM": "https://daten-hamburg.de/opendata/"
               "Digitales_Hoehenmodell_bDOM/dom1_xyz_HH_2021_04_30.zip",
        "DGM": "https://daten-hamburg.de/geographie_geologie_geobasisdaten/"
               "Digitales_Hoehenmodell/DGM1/dgm1_2x2km_XYZ_hh_2021_04_01.zip",
        "type": "direct_download",  # Direct download links
    },
    "Rostock": {
        "DOM": "https://www.geodaten-mv.de/dienste/dom_atom",
        "DGM": "https://www.geodaten-mv.de/dienste/dgm_atom",
        "type": "atom_filtered",  # Atom feed with spatial filtering (MV has 6407 tiles!)
    },
}

# Konvertierungsparameter
GDAL_TRANSLATE_OPTS = [
    "-of", "GTiff",
    "-co", "COMPRESS=LZW",
    "-co", "TILED=YES",
    "-co", "BIGTIFF=IF_SAFER",
]

GDALWARP_OPTS = [
    "-r", "near",  # Nearest neighbor für 1m Daten
    "-co", "COMPRESS=LZW",
    "-co", "TILED=YES",
    "-co", "BIGTIFF=IF_SAFER",
]

# Download-Parameter
ELEVATION_MAX_RETRIES = 3
ELEVATION_DOWNLOAD_TIMEOUT_S = 60
ELEVATION_TIMEOUT_S = 600  # 10 min für GDAL-Operationen
