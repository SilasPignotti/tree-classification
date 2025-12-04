"""
Lädt DOM und DGM Höhendaten für Rostock herunter und verarbeitet sie.

Datenquellen:
- DOM: Geodaten MV Atom Feed (CSV-XYZ in ZIP für ganz MV, 1m Auflösung)
- DGM: Geodaten MV Atom Feed (CSV-XYZ in ZIP für ganz MV, 1m Auflösung)

WICHTIG: Räumliche Filterung erforderlich, da Feed ganz MV abdeckt (6407 Kacheln!)
Daten sind im XYZ-Format, erfordert GDAL-Konvertierung.
"""

import logging
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import box
from tqdm import tqdm


# Konstanten
CITY = "Rostock"
DOM_FEED_URL = "https://www.geodaten-mv.de/dienste/dom_atom"
DGM_FEED_URL = "https://www.geodaten-mv.de/dienste/dgm_atom"
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries_500m_buffer.gpkg")
OUTPUT_DIR = Path("data/CHM/raw/rostock")
CRS = "EPSG:25832"  # MV nutzt EPSG:25833, wird zu 25832 konvertiert
MAX_RETRIES = 3
MAX_WORKERS = 3  # Parallel processing


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

            return

        except (requests.RequestException, IOError) as e:
            logger.warning(f"Download attempt {attempt} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
            logger.info("Retrying...")


def get_dataset_feed_url(main_feed_url: str) -> str:
    """
    Extrahiert Dataset Feed URL aus dem Haupt-Atom Feed.

    Args:
        main_feed_url: URL des Haupt-Feeds

    Returns:
        URL des Dataset Feeds mit den eigentlichen Kacheln
    """
    response = requests.get(main_feed_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Finde den Link zum Dataset Feed (rel="alternate")
    for entry in root.findall("atom:entry", ns):
        link = entry.find(
            "atom:link[@rel='alternate'][@type='application/atom+xml']", ns
        )
        if link is not None:
            return link.get("href")

    raise ValueError("No dataset feed link found in main feed")


def parse_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    """
    Parst bbox-Attribut aus Atom Feed (lat/lon Format).

    Args:
        bbox_str: Bbox-String im Format "lat1 lon1 lat2 lon2"

    Returns:
        Tuple (lon1, lat1, lon2, lat2) für shapely.box
    """
    try:
        parts = bbox_str.split()
        lat1, lon1, lat2, lon2 = map(float, parts)
        # Konvertiere zu (minx, miny, maxx, maxy)
        return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
    except (ValueError, IndexError):
        return None


def parse_atom_feed(feed_url: str, boundary_gdf: gpd.GeoDataFrame) -> list[dict]:
    """
    Parst MV Atom Feed und filtert Kacheln nach räumlicher Überschneidung.

    MV-spezifisch: Feed hat 6407 Kacheln! bbox-Attribute erlauben Pre-Filtering.

    Args:
        feed_url: URL des Atom Feeds
        boundary_gdf: GeoDataFrame mit Stadtgrenze für Filterung

    Returns:
        Liste von Dictionaries mit 'title', 'url' für überschneidende Kacheln
    """
    logger.info(f"Parsing Atom feed: {feed_url}")

    # Schritt 1: Get dataset feed URL
    dataset_feed_url = get_dataset_feed_url(feed_url)
    logger.info(f"Found dataset feed: {dataset_feed_url}")

    # Schritt 2: Parse dataset feed für Kacheln
    response = requests.get(dataset_feed_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Boundary in WGS84 für bbox-Vergleich
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    boundary_bounds = box(*boundary_wgs84.total_bounds)

    tiles = []
    all_tiles_count = 0

    # MV: Alle tiles sind als <link rel="section"> mit bbox-Attribut
    for entry in root.findall("atom:entry", ns):
        for link in entry.findall("atom:link[@rel='section']", ns):
            all_tiles_count += 1

            title = link.get("title")
            url = link.get("href")
            bbox_str = link.get("bbox")

            if not (url and url.endswith(".zip")):
                continue

            # Räumliche Filterung via bbox
            if bbox_str:
                tile_bbox = parse_bbox(bbox_str)
                if tile_bbox:
                    tile_bounds = box(*tile_bbox)

                    # Prüfe Überschneidung
                    if not tile_bounds.intersects(boundary_bounds):
                        continue  # Skip Kacheln außerhalb Rostock

            # Extrahiere Kachel-ID aus URL (z.B. file=dom1_33_302_5992_2.zip)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            if "file" in params and params["file"]:
                filename = params["file"][0]
                tile_id = Path(filename).stem  # Entfernt .zip
            else:
                # Fallback: nutze title oder URL-path
                tile_id = title if title else Path(url).stem

            tile_id = tile_id.replace("_xyz", "")

            tiles.append({
                "title": tile_id,
                "url": url,
                "filename": filename if "file" in params else f"{tile_id}.zip",
            })

    logger.info(
        f"CRITICAL FILTERING: {len(tiles)} tiles intersect Rostock "
        f"(from {all_tiles_count} total MV tiles)"
    )
    return tiles


def extract_xyz_from_zip(zip_path: Path, extract_dir: Path) -> list[Path]:
    """
    Extrahiert XYZ/CSV-Dateien aus ZIP-Archiv.

    Nutzt system 'unzip' für bessere Kompatibilität.

    Args:
        zip_path: Pfad zum ZIP-Archiv
        extract_dir: Extraktionsverzeichnis

    Returns:
        Liste der extrahierten XYZ-Dateipfade
    """
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
    xyz_files.extend(extract_dir.rglob("*.csv"))
    xyz_files.extend(extract_dir.rglob("*.txt"))

    return xyz_files


def xyz_to_geotiff(
    xyz_path: Path, output_path: Path, source_crs: str = "EPSG:25833"
) -> None:
    """
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit NumPy/Rasterio.

    Rostock XYZ-Dateien haben unregelmäßige Whitespace-Trennung,
    daher verwenden wir numpy.loadtxt für robustes Parsen.

    Args:
        xyz_path: Pfad zur XYZ-Datei
        output_path: Ausgabe-GeoTIFF-Pfad
        source_crs: Quell-CRS (MV = EPSG:25833)
    """
    logger.info(f"Converting {xyz_path.name} to GeoTIFF...")

    import numpy as np
    from rasterio.transform import from_bounds

    # Lade XYZ-Daten (robust gegen variable Whitespace)
    logger.info("  Loading XYZ data...")
    data = np.loadtxt(xyz_path)
    x_coords, y_coords, z_values = data[:, 0], data[:, 1], data[:, 2]

    # Berechne Bounds und Grid-Parameter
    xmin, xmax = np.floor(x_coords.min()), np.ceil(x_coords.max())
    ymin, ymax = np.floor(y_coords.min()), np.ceil(y_coords.max())

    # Erstelle Grid in EPSG:25833
    width = int(xmax - xmin)
    height = int(ymax - ymin)

    logger.info(f"  Grid size: {width}x{height} pixels")

    # Erstelle leeres Raster
    raster = np.full((height, width), -9999.0, dtype=np.float32)

    # Fülle Raster mit XYZ-Werten (nearest neighbor)
    logger.info("  Filling grid...")
    x_indices = (x_coords - xmin).astype(int)
    y_indices = (ymax - y_coords).astype(int)  # Flip Y (raster coords)

    # Clip indices to grid bounds
    valid = (
        (x_indices >= 0) & (x_indices < width) &
        (y_indices >= 0) & (y_indices < height)
    )

    raster[y_indices[valid], x_indices[valid]] = z_values[valid]

    valid_pixels = (raster != -9999.0).sum()
    logger.info(f"  Filled {valid_pixels:,} / {raster.size:,} pixels")

    # Schritt 1: Speichere in EPSG:25833
    temp_tif = output_path.parent / f"{output_path.stem}_temp_25833.tif"

    transform = from_bounds(xmin, ymin, xmax, ymax, width, height)

    with rasterio.open(
        temp_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=np.float32,
        crs=source_crs,
        transform=transform,
        nodata=-9999.0,
        compress="lzw",
    ) as dst:
        dst.write(raster, 1)

    logger.info(f"  Saved intermediate file in {source_crs}")

    # Schritt 2: Reprojiziere mit gdalwarp zu EPSG:25832
    logger.info("  Reprojecting to EPSG:25832...")

    cmd_warp = [
        "gdalwarp",
        "-s_srs", source_crs,
        "-t_srs", CRS,
        "-r", "near",
        "-tr", "1.0", "1.0",
        "-overwrite",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=IF_SAFER",
        str(temp_tif),
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd_warp, check=True, capture_output=True, timeout=600, text=True
        )
        if result.stderr:
            logger.debug(f"gdalwarp: {result.stderr}")

        # Cleanup temp file
        temp_tif.unlink()

    except subprocess.CalledProcessError as e:
        logger.error(f"GDAL reprojection failed: {e.stderr}")
        if temp_tif.exists():
            temp_tif.unlink()
        raise
    except subprocess.TimeoutExpired:
        logger.error("GDAL reprojection timed out")
        if temp_tif.exists():
            temp_tif.unlink()
        raise


def process_single_tile(tile: dict[str, str], temp_dir: Path) -> Path | None:
    """
    Verarbeitet eine einzelne Kachel: Download, Extraktion, Konvertierung.

    Args:
        tile: Tile-Dictionary mit 'title', 'url', 'filename'
        temp_dir: Temporäres Verzeichnis

    Returns:
        GeoTIFF-Pfad oder None bei Fehler
    """
    try:
        # Download ZIP
        zip_filename = tile.get("filename", f"{tile['title']}.zip")
        zip_path = temp_dir / zip_filename

        if not zip_path.exists():
            download_file(tile["url"], zip_path, f"Tile {tile['title']}")

        # Extract XYZ
        extract_dir = temp_dir / "extracted" / tile["title"]
        xyz_files = extract_xyz_from_zip(zip_path, extract_dir)

        if not xyz_files:
            logger.warning(f"No XYZ files in {tile['title']}")
            return None

        # Convert to GeoTIFF
        geotiff_path = temp_dir / "geotiffs" / f"{tile['title']}.tif"
        geotiff_path.parent.mkdir(parents=True, exist_ok=True)

        xyz_to_geotiff(xyz_files[0], geotiff_path)
        return geotiff_path

    except Exception as e:
        logger.warning(f"Failed to process {tile['title']}: {e}")
        return None


def download_and_convert_tiles(
    tiles: list[dict[str, str]], temp_dir: Path
) -> list[Path]:
    """
    Lädt Kacheln herunter, extrahiert XYZ und konvertiert zu GeoTIFF (parallel).

    Args:
        tiles: Liste von Tile-Dictionaries (mit 'title', 'url', 'filename')
        temp_dir: Temporäres Verzeichnis

    Returns:
        Liste von GeoTIFF-Pfaden
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    geotiff_paths = []

    # Parallel processing mit ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit alle Tasks
        future_to_tile = {
            executor.submit(process_single_tile, tile, temp_dir): tile
            for tile in tiles
        }

        # Collect results mit Progress Bar
        for future in tqdm(
            as_completed(future_to_tile),
            total=len(tiles),
            desc="Processing tiles"
        ):
            result = future.result()
            if result is not None:
                geotiff_paths.append(result)

    logger.info(f"Successfully converted {len(geotiff_paths)} tiles to GeoTIFF")
    return geotiff_paths


def mosaic_and_clip(
    geotiff_paths: list[Path], boundary_gdf: gpd.GeoDataFrame, output_path: Path
) -> None:
    """
    Erstellt Mosaik aus GeoTIFFs und clippt auf Stadtgrenze.

    Args:
        geotiff_paths: Liste von GeoTIFF-Pfaden
        boundary_gdf: GeoDataFrame mit Stadtgrenze
        output_path: Ausgabe-Pfad
    """
    if len(geotiff_paths) == 0:
        raise ValueError("No GeoTIFF tiles to mosaic")

    logger.info(f"Mosaicking {len(geotiff_paths)} tiles...")

    # Öffne Dateien und filtere korrupte
    src_files = []
    for p in geotiff_paths:
        try:
            src = rasterio.open(p)
            src_files.append(src)
        except Exception as e:
            logger.warning(f"Skipping corrupted file {p.name}: {e}")
            continue

    if len(src_files) == 0:
        raise ValueError("No valid GeoTIFF tiles to mosaic")

    logger.info(f"Using {len(src_files)} valid tiles for mosaic")

    try:
        mosaic, out_trans = merge(src_files, method="first")

        # Temporäres Mosaik speichern
        temp_mosaic = output_path.parent / f"{output_path.stem}_temp.tif"

        out_meta = src_files[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans,
            "compress": "lzw",
            "tiled": True,
        })

        with rasterio.open(temp_mosaic, "w", **out_meta) as dest:
            dest.write(mosaic)

    finally:
        for src in src_files:
            src.close()

    # Clip auf Stadtgrenze
    logger.info("Clipping mosaic to city boundary...")

    with rasterio.open(temp_mosaic) as src:
        logger.info(f"Mosaic CRS: {src.crs}, Bounds: {src.bounds}")
        logger.info(f"Mosaic has {(src.read(1) != src.nodata).sum()} valid pixels")

        boundary_reproj = boundary_gdf.to_crs(src.crs)
        logger.info(f"Boundary CRS: {boundary_reproj.crs}, Bounds: {boundary_reproj.total_bounds}")

        out_image, out_transform = mask(
            src, boundary_reproj.geometry, crop=True, all_touched=True
        )

        valid_pixels = (out_image != src.nodata).sum()
        logger.info(f"Clipped image has {valid_pixels} valid pixels")

        if valid_pixels == 0:
            logger.error("WARNING: Clipped image is empty! Bounds may not overlap.")

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
    logger.info(f"Saved clipped raster to: {output_path}")


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
            _ = src.read(1, window=((0, 10), (0, 10)))
            logger.info(
                f"Validated {file_path.name}: "
                f"{src.width}x{src.height}, CRS: {src.crs}"
            )
        return True
    except Exception as e:
        logger.error(f"Validation failed for {file_path}: {e}")
        return False


def process_elevation_data(
    feed_url: str, data_type: str, temp_dir: Path, output_path: Path,
    boundary_gdf: gpd.GeoDataFrame
) -> None:
    """
    Verarbeitet Höhendaten von Atom Feed bis zum finalen Clip.

    Args:
        feed_url: Atom Feed URL
        data_type: "DOM" oder "DGM"
        temp_dir: Temporäres Verzeichnis
        output_path: Finaler Output-Pfad
        boundary_gdf: Stadtgrenze zum Clippen
    """
    if output_path.exists() and validate_geotiff(output_path):
        logger.info(f"{data_type} already exists and is valid, skipping...")
        return

    # Parse feed with spatial filtering (CRITICAL for MV!)
    tiles = parse_atom_feed(feed_url, boundary_gdf)

    if not tiles:
        raise ValueError(f"No tiles found for {data_type} after filtering")

    # Download, extract, convert
    tile_dir = temp_dir / data_type.lower()
    geotiff_paths = download_and_convert_tiles(tiles, tile_dir)

    if not geotiff_paths:
        raise ValueError(f"No GeoTIFF tiles created for {data_type}")

    # Mosaic and clip
    mosaic_and_clip(geotiff_paths, boundary_gdf, output_path)

    # Validate
    if not validate_geotiff(output_path):
        raise ValueError(f"Output validation failed for {output_path}")


def main() -> None:
    """Hauptfunktion: Lädt und verarbeitet Höhendaten für Rostock."""
    logger.info("=" * 70)
    logger.info("Rostock Elevation Data Download - DOM & DGM (XYZ Format)")
    logger.info("CRITICAL: Spatial filtering to avoid downloading all MV (6407 tiles)!")
    logger.info("=" * 70)

    # Setup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    # Load city boundary
    logger.info(f"Loading boundary from {BOUNDARIES_PATH}...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    rostock_boundary = boundaries[boundaries["gen"] == CITY]

    if rostock_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    logger.info(f"Boundary loaded: CRS {rostock_boundary.crs}")

    # Process DOM
    dom_output = OUTPUT_DIR / "dom_1m.tif"
    try:
        process_elevation_data(
            DOM_FEED_URL, "DOM", temp_dir, dom_output, rostock_boundary
        )
    except Exception as e:
        logger.error(f"DOM processing failed: {e}")
        raise

    # Process DGM
    dgm_output = OUTPUT_DIR / "dgm_1m.tif"
    try:
        process_elevation_data(
            DGM_FEED_URL, "DGM", temp_dir, dgm_output, rostock_boundary
        )
    except Exception as e:
        logger.error(f"DGM processing failed: {e}")
        raise

    # Cleanup temp files (commented out for debugging)
    # logger.info("Cleaning up temporary files...")
    # shutil.rmtree(temp_dir)
    logger.info(f"Keeping temp files for debugging in: {temp_dir}")

    logger.info("=" * 70)
    logger.info("Rostock elevation data processing complete!")
    logger.info(f"DOM: {dom_output}")
    logger.info(f"DGM: {dgm_output}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
