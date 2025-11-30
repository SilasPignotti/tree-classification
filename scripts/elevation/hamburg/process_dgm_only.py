"""
Verarbeitet bereits konvertierte DGM GeoTIFF-Tiles zu finalem DGM.

Nutzt vorhandene Tiles in data/raw/hamburg/temp/dgm_tif/
"""

import logging
import subprocess
from pathlib import Path

import geopandas as gpd
import rasterio

# Konstanten
CITY = "Hamburg"
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries_500m_buffer.gpkg")
TEMP_DIR = Path("data/raw/hamburg/temp")
GEOTIFF_DIR = TEMP_DIR / "dgm_tif"
OUTPUT_PATH = Path("data/raw/hamburg/dgm_1m.tif")

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fix_upside_down_tiles(geotiff_paths: list[Path]) -> list[Path]:
    """
    Korrigiert upside-down Tiles durch Flip.

    Args:
        geotiff_paths: Liste von GeoTIFF-Pfaden

    Returns:
        Liste von korrigierten GeoTIFF-Pfaden
    """
    fixed_dir = geotiff_paths[0].parent / "fixed"
    fixed_dir.mkdir(exist_ok=True)
    fixed_paths = []

    logger.info("Checking and fixing tile orientations...")

    for i, path in enumerate(geotiff_paths, 1):
        if i % 100 == 0:
            logger.info(f"Processed {i}/{len(geotiff_paths)} tiles...")

        with rasterio.open(path) as src:
            # Check if upside down (negative Y pixel size)
            if src.transform.e < 0:
                # Tile is upside down - flip it with gdalwarp
                fixed_path = fixed_dir / path.name
                flip_cmd = [
                    "gdalwarp",
                    "-overwrite",
                    "-co",
                    "COMPRESS=LZW",
                    str(path),
                    str(fixed_path),
                ]
                subprocess.run(flip_cmd, check=True, capture_output=True, timeout=60)
                fixed_paths.append(fixed_path)
            else:
                # Tile is correct - use as is
                fixed_paths.append(path)

    logger.info(f"Fixed {len(fixed_paths)} tiles")
    return fixed_paths


def mosaic_with_gdalwarp(
    geotiff_paths: list[Path], boundary_gdf: gpd.GeoDataFrame, output_path: Path
) -> None:
    """
    Mosaiciert Tiles mit gdalwarp (für upside-down Raster).

    Args:
        geotiff_paths: Liste von GeoTIFF-Pfaden
        boundary_gdf: GeoDataFrame mit Stadtgrenze
        output_path: Ausgabe-Pfad
    """
    logger.info(f"Using gdalwarp to directly mosaic {len(geotiff_paths)} tiles...")
    logger.info("This may take 10-15 minutes for 868 tiles...")

    # Get boundary bounds in raster CRS
    with rasterio.open(geotiff_paths[0]) as src:
        raster_crs = src.crs
    boundary_reproj = boundary_gdf.to_crs(raster_crs)
    minx, miny, maxx, maxy = boundary_reproj.total_bounds

    # Merge all tiles directly with gdalwarp (no VRT - handles mixed orientations)
    warp_cmd = [
        "gdalwarp",
        "-te",
        str(minx),
        str(miny),
        str(maxx),
        str(maxy),
        "-te_srs",
        str(raster_crs),
        "-co",
        "COMPRESS=LZW",
        "-co",
        "TILED=YES",
        "-co",
        "BIGTIFF=YES",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        "-multi",  # Enable multithreading
    ] + [str(p) for p in geotiff_paths] + [str(output_path)]

    try:
        logger.info("Running gdalwarp merge (this will take a while)...")
        result = subprocess.run(
            warp_cmd,
            check=True,
            capture_output=True,
            timeout=3600,  # 1 hour timeout
            text=True
        )
        logger.info(f"Successfully merged and clipped {len(geotiff_paths)} tiles")
    except subprocess.CalledProcessError as e:
        logger.error(f"Gdalwarp failed: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error("Gdalwarp timed out after 1 hour")
        raise

    logger.info(f"Mosaic saved to: {output_path}")


def main() -> None:
    """Hauptfunktion: Mosaiciert DGM-Tiles."""
    logger.info("=" * 70)
    logger.info("Hamburg DGM Mosaic - Processing existing tiles")
    logger.info("=" * 70)

    # Check if tiles exist
    if not GEOTIFF_DIR.exists():
        raise FileNotFoundError(f"Tile directory not found: {GEOTIFF_DIR}")

    geotiff_paths = sorted(GEOTIFF_DIR.glob("*.tif"))

    if not geotiff_paths:
        raise FileNotFoundError(f"No GeoTIFF tiles found in {GEOTIFF_DIR}")

    logger.info(f"Found {len(geotiff_paths)} DGM tiles")

    # Load city boundary
    logger.info(f"Loading boundary from {BOUNDARIES_PATH}...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    hamburg_boundary = boundaries[boundaries["gen"] == CITY]

    if hamburg_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    logger.info(f"Boundary loaded: CRS {hamburg_boundary.crs}")

    # Mosaic and clip
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mosaic_with_gdalwarp(geotiff_paths, hamburg_boundary, OUTPUT_PATH)

    # Validate
    with rasterio.open(OUTPUT_PATH) as src:
        logger.info(
            f"DGM created: {src.width}x{src.height} pixels, "
            f"CRS: {src.crs}, Size: {OUTPUT_PATH.stat().st_size / 1024**2:.1f} MB"
        )

    logger.info("=" * 70)
    logger.info("DGM processing complete!")
    logger.info(f"Output: {OUTPUT_PATH}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
