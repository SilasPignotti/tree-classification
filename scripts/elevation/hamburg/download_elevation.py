"""
Lädt DOM und DGM Höhendaten für Hamburg herunter und verarbeitet sie.

Datenquellen:
- DOM: https://daten-hamburg.de (XYZ Format, 1m Auflösung)
- DGM: https://daten-hamburg.de (XYZ Format, 1m Auflösung)
"""

import logging
import shutil
import subprocess
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.mask import mask
from rasterio.merge import merge
from tqdm import tqdm


# Konstanten
CITY = "Hamburg"
DOM_URL = (
    "https://daten-hamburg.de/opendata/"
    "Digitales_Hoehenmodell_bDOM/dom1_xyz_HH_2021_04_30.zip"
)
DGM_URL = (
    "https://daten-hamburg.de/geographie_geologie_geobasisdaten/"
    "Digitales_Hoehenmodell/DGM1/dgm1_2x2km_XYZ_hh_2021_04_01.zip"
)
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries_500m_buffer.gpkg")
OUTPUT_DIR = Path("data/raw/hamburg")
CRS = "EPSG:25832"
MAX_RETRIES = 3


# Logging Setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def download_file(url: str, output_path: Path, desc: str) -> None:
    """
    Lädt eine Datei mit Progress Bar und Retry-Logik herunter.

    Args:
        url: Download-URL
        output_path: Ziel-Dateipfad
        desc: Beschreibung für Progress Bar

    Raises:
        requests.HTTPError: Bei Download-Fehlern nach allen Retries
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Downloading {desc} (Attempt {attempt}/{MAX_RETRIES})...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(output_path, "wb") as f, tqdm(
                desc=desc,
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)

            logger.info(f"Successfully downloaded {desc}")
            return

        except (requests.RequestException, IOError) as e:
            logger.warning(f"Download attempt {attempt} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
            logger.info("Retrying...")


def extract_xyz_from_zip(zip_path: Path, extract_dir: Path) -> list[Path]:
    """
    Extrahiert XYZ-Dateien aus ZIP-Archiv.

    Nutzt system 'unzip' command für bessere Kompatibilität mit verschiedenen
    ZIP-Kompressionsformaten.

    Args:
        zip_path: Pfad zum ZIP-Archiv
        extract_dir: Extraktionsverzeichnis

    Returns:
        Liste der extrahierten XYZ-Dateipfade
    """
    logger.info(f"Extracting {zip_path.name}...")
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Nutze system unzip für bessere Kompatibilität
    cmd = ["unzip", "-q", "-o", str(zip_path), "-d", str(extract_dir)]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as e:
        logger.error(f"Unzip failed: {e.stderr.decode()}")
        raise
    except subprocess.TimeoutExpired:
        logger.error("Unzip timed out after 5 minutes")
        raise

    # Finde extrahierte XYZ-Dateien
    xyz_files = list(extract_dir.rglob("*.xyz"))
    xyz_files.extend(extract_dir.rglob("*.txt"))

    logger.info(f"Extracted {len(xyz_files)} XYZ files")
    return xyz_files


def xyz_to_geotiff(
    xyz_path: Path, output_path: Path, crs: str = CRS
) -> None:
    """
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit GDAL.

    Args:
        xyz_path: Pfad zur XYZ-Datei
        output_path: Ausgabe-GeoTIFF-Pfad
        crs: Ziel-CRS

    Note:
        Nutzt gdal_translate über subprocess für robuste Konvertierung
    """
    import subprocess

    logger.info(f"Converting {xyz_path.name} to GeoTIFF...")

    cmd = [
        "gdal_translate",
        "-of", "GTiff",
        "-a_srs", crs,
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=YES",
        str(xyz_path),
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=600
        )
        logger.info(f"Conversion successful: {output_path.name}")
        if result.stdout:
            logger.debug(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"GDAL conversion failed: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error("GDAL conversion timed out after 10 minutes")
        raise


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
    logger.info(f"Using gdalwarp to mosaic {len(geotiff_paths)} tiles...")

    # Create VRT from all tiles
    temp_vrt = output_path.parent / f"{output_path.stem}_temp.vrt"
    temp_mosaic = output_path.parent / f"{output_path.stem}_temp.tif"

    # Build VRT
    vrt_cmd = ["gdalbuildvrt", str(temp_vrt)] + [str(p) for p in geotiff_paths]

    try:
        subprocess.run(vrt_cmd, check=True, capture_output=True, timeout=300)
        logger.info(f"Created VRT with {len(geotiff_paths)} tiles")
    except subprocess.CalledProcessError as e:
        logger.error(f"VRT creation failed: {e.stderr.decode()}")
        raise

    # Get boundary bounds in raster CRS
    with rasterio.open(geotiff_paths[0]) as src:
        raster_crs = src.crs
    boundary_reproj = boundary_gdf.to_crs(raster_crs)
    minx, miny, maxx, maxy = boundary_reproj.total_bounds

    # Warp and clip VRT to boundary
    warp_cmd = [
        "gdalwarp",
        "-te", str(minx), str(miny), str(maxx), str(maxy),
        "-te_srs", str(raster_crs),
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=YES",
        str(temp_vrt),
        str(output_path),
    ]

    try:
        subprocess.run(warp_cmd, check=True, capture_output=True, timeout=1800)
        logger.info(f"Warped and clipped to boundary")
    except subprocess.CalledProcessError as e:
        logger.error(f"Gdalwarp failed: {e.stderr.decode()}")
        raise

    # Cleanup temp files
    temp_vrt.unlink()

    logger.info(f"Mosaic saved to: {output_path}")


def mosaic_and_clip(
    geotiff_paths: list[Path], boundary_gdf: gpd.GeoDataFrame, output_path: Path
) -> None:
    """
    Mosaiciert mehrere GeoTIFF-Tiles und clippt auf Stadtgrenze.

    Args:
        geotiff_paths: Liste von GeoTIFF-Pfaden
        boundary_gdf: GeoDataFrame mit Stadtgrenze
        output_path: Ausgabe-Pfad
    """
    if not geotiff_paths:
        raise ValueError("No GeoTIFF tiles to mosaic")

    logger.info(f"Mosaicking {len(geotiff_paths)} tiles...")

    # Öffne alle Tiles und prüfe auf "upside down" Raster
    src_files = []
    needs_flip = False
    for path in geotiff_paths:
        try:
            src = rasterio.open(path)
            # Check if raster is upside down (negative pixel height)
            if src.transform.e < 0:  # Negative Y pixel size
                needs_flip = True
            src_files.append(src)
        except Exception as e:
            logger.warning(f"Could not open {path}: {e}")

    if not src_files:
        raise ValueError("No valid GeoTIFF tiles to mosaic")

    logger.info(f"Using {len(src_files)} valid tiles for mosaic")

    if needs_flip:
        logger.warning(
            "Detected upside-down rasters (negative pixel height). "
            "Using gdalwarp workaround..."
        )
        # Close files for gdalwarp approach
        for src in src_files:
            src.close()
        src_files = []

        # Use gdalwarp to merge upside-down rasters
        return mosaic_with_gdalwarp(geotiff_paths, boundary_gdf, output_path)

    try:
        # Mosaic tiles with rasterio
        mosaic, out_trans = merge(src_files, method="first")

        # Temporäres Mosaic speichern
        temp_mosaic = output_path.parent / f"{output_path.stem}_temp.tif"
        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans,
            "compress": "lzw",
        })

        with rasterio.open(temp_mosaic, "w", **out_meta) as dest:
            dest.write(mosaic)

        logger.info(f"Mosaic created: {mosaic.shape[1]}x{mosaic.shape[2]} pixels")

    finally:
        # Schließe alle Source-Files
        for src in src_files:
            src.close()

    # Clip to boundary
    logger.info("Clipping mosaic to city boundary...")

    with rasterio.open(temp_mosaic) as src:
        boundary_reproj = boundary_gdf.to_crs(src.crs)

        out_image, out_transform = mask(
            src, boundary_reproj.geometry, crop=True, all_touched=True
        )

        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "compress": "lzw",
        })

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)

    # Cleanup temp mosaic
    temp_mosaic.unlink()

    logger.info(f"Clipped mosaic saved to: {output_path}")


def validate_geotiff(file_path: Path) -> bool:
    """
    Validiert GeoTIFF-Datei.

    Args:
        file_path: Pfad zur GeoTIFF-Datei

    Returns:
        True wenn valide, sonst False
    """
    try:
        with rasterio.open(file_path) as src:
            _ = src.read(1, window=((0, 10), (0, 10)))  # Test read
            logger.info(
                f"Validated {file_path.name}: "
                f"{src.width}x{src.height}, CRS: {src.crs}"
            )
        return True
    except Exception as e:
        logger.error(f"Validation failed for {file_path}: {e}")
        return False


def process_elevation_data(
    url: str, data_type: str, temp_dir: Path, output_path: Path,
    boundary_gdf: gpd.GeoDataFrame
) -> None:
    """
    Verarbeitet Höhendaten von Download bis zum finalen Clip.

    Args:
        url: Download-URL
        data_type: "DOM" oder "DGM"
        temp_dir: Temporäres Verzeichnis
        output_path: Finaler Output-Pfad
        boundary_gdf: Stadtgrenze zum Clippen
    """
    # Skip if output already exists and is valid
    if output_path.exists() and validate_geotiff(output_path):
        logger.info(f"{data_type} already exists and is valid, skipping...")
        return

    # Download ZIP
    zip_path = temp_dir / f"{data_type.lower()}.zip"
    download_file(url, zip_path, f"{data_type} ZIP")

    # Extract XYZ
    extract_dir = temp_dir / data_type.lower()
    xyz_files = extract_xyz_from_zip(zip_path, extract_dir)

    if not xyz_files:
        raise FileNotFoundError(f"No XYZ files found in {zip_path}")

    logger.info(f"Found {len(xyz_files)} XYZ files to process")

    # Convert ALL XYZ files to GeoTIFF
    geotiff_dir = temp_dir / f"{data_type.lower()}_tif"
    geotiff_dir.mkdir(exist_ok=True)
    geotiff_paths = []

    for i, xyz_file in enumerate(xyz_files, 1):
        logger.info(f"Converting tile {i}/{len(xyz_files)}: {xyz_file.name}")
        geotiff_path = geotiff_dir / f"{xyz_file.stem}.tif"
        try:
            xyz_to_geotiff(xyz_file, geotiff_path)
            geotiff_paths.append(geotiff_path)
        except Exception as e:
            logger.warning(f"Failed to convert {xyz_file.name}: {e}")

    if not geotiff_paths:
        raise ValueError("No GeoTIFF tiles were successfully created")

    logger.info(f"Successfully converted {len(geotiff_paths)}/{len(xyz_files)} tiles")

    # Mosaic all tiles and clip to boundary
    mosaic_and_clip(geotiff_paths, boundary_gdf, output_path)

    # Validate
    if not validate_geotiff(output_path):
        raise ValueError(f"Output validation failed for {output_path}")


def main() -> None:
    """Hauptfunktion: Lädt und verarbeitet Höhendaten für Hamburg."""
    logger.info("=" * 70)
    logger.info(f"Hamburg Elevation Data Download - DOM & DGM")
    logger.info("=" * 70)

    # Setup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    # Load city boundary
    logger.info(f"Loading boundary from {BOUNDARIES_PATH}...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    hamburg_boundary = boundaries[boundaries["gen"] == CITY]

    if hamburg_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    logger.info(f"Boundary loaded: CRS {hamburg_boundary.crs}")

    # Process DOM
    dom_output = OUTPUT_DIR / "dom_1m.tif"
    try:
        process_elevation_data(
            DOM_URL, "DOM", temp_dir, dom_output, hamburg_boundary
        )
    except Exception as e:
        logger.error(f"DOM processing failed: {e}")
        raise

    # Process DGM
    dgm_output = OUTPUT_DIR / "dgm_1m.tif"
    try:
        process_elevation_data(
            DGM_URL, "DGM", temp_dir, dgm_output, hamburg_boundary
        )
    except Exception as e:
        logger.error(f"DGM processing failed: {e}")
        raise

    # Cleanup temp files
    logger.info("Cleaning up temporary files...")
    shutil.rmtree(temp_dir)

    logger.info("=" * 70)
    logger.info("Hamburg elevation data processing complete!")
    logger.info(f"DOM: {dom_output}")
    logger.info(f"DGM: {dgm_output}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
