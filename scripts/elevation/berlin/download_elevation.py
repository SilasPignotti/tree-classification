"""
Lädt DOM und DGM Höhendaten für Berlin herunter und verarbeitet sie.

Datenquellen:
- DOM: Berlin FIS-Broker Atom Feed (CSV-XYZ in ZIP, 1m Auflösung)
- DGM: Berlin GDI Atom Feed (CSV-XYZ in ZIP, 1m Auflösung)

WICHTIG: Daten sind im XYZ-Format, nicht GeoTIFF!
Erfordert Konvertierung via GDAL wie Hamburg.
"""

import logging
import multiprocessing as mp
import shutil
import subprocess
import xml.etree.ElementTree as ET
from functools import partial
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.mask import mask
from rasterio.merge import merge
from tqdm import tqdm


# Konstanten
CITY = "Berlin"
DOM_FEED_URL = "https://fbinter.stadt-berlin.de/fb/feed/senstadt/a_dom1"
DGM_FEED_URL = "https://gdi.berlin.de/data/dgm1/atom"
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries_500m_buffer.gpkg")
OUTPUT_DIR = Path("data/raw/berlin")
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


def parse_atom_feed(feed_url: str) -> list[dict[str, str]]:
    """
    Parst Berlin Atom Feed und extrahiert Download-Links für XYZ-Kacheln.

    Berlin-spezifisch: Feed hat nested structure mit dataset feed.
    Tiles sind CSV-XYZ Format in ZIP-Archiven.

    Args:
        feed_url: URL des Atom Feeds

    Returns:
        Liste von Dictionaries mit 'title', 'url' für jede Kachel
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

    tiles = []
    # Berlin: Alle tiles sind als <link rel="section"> in EINEM entry
    for entry in root.findall("atom:entry", ns):
        for link in entry.findall("atom:link[@rel='section']", ns):
            title = link.get("title")
            url = link.get("href")

            if url and url.endswith(".zip"):
                # Extrahiere Kachel-ID aus dem Titel (z.B. "DOM1_380_5820")
                if title:
                    tile_id = title.replace("ATKIS® ", "").replace(".zip", "")
                else:
                    # Fallback: aus URL extrahieren
                    tile_id = Path(url).stem

                tiles.append({
                    "title": tile_id,
                    "url": url,
                })

    logger.info(f"Found {len(tiles)} tiles in feed")
    return tiles


def filter_tiles_by_coordinates(
    tiles: list[dict[str, str]], boundary_gdf: gpd.GeoDataFrame
) -> list[dict[str, str]]:
    """
    Filtert Kacheln basierend auf Koordinaten im Dateinamen.

    Berlin-Tiles: Format "DOM1 XXX_YYYY" wo XXX und YYYY km-Koordinaten
    in EPSG:25833 sind (nicht 25832!).

    Args:
        tiles: Liste von Tile-Dictionaries
        boundary_gdf: GeoDataFrame mit Stadtgrenze

    Returns:
        Gefilterte Liste von Tiles die Berlin überschneiden
    """
    logger.info("Pre-filtering tiles by coordinate-based naming...")

    # Transform boundary to EPSG:25833 (tile CRS)
    boundary_25833 = boundary_gdf.to_crs("EPSG:25833")
    boundary_bounds = boundary_25833.total_bounds
    minx, miny, maxx, maxy = boundary_bounds

    # Konvertiere zu km für Vergleich mit Tile-Namen
    minx_km = int(minx / 1000)
    miny_km = int(miny / 1000)
    maxx_km = int(maxx / 1000) + 1
    maxy_km = int(maxy / 1000) + 1

    # Erweitere Bounds um Puffer für Kachelgröße (2km)
    buffer_km = 2
    minx_km -= buffer_km
    miny_km -= buffer_km
    maxx_km += buffer_km
    maxy_km += buffer_km

    candidate_tiles = []

    for tile in tiles:
        try:
            # Format: "DOM1 368_5808" -> extrahiere "368_5808"
            title_clean = tile["title"].replace("DOM1 ", "").replace("DGM1 ", "")
            parts = title_clean.split("_")

            if len(parts) >= 2:
                # Koordinaten sind in km (z.B. 368 = 368km = 368000m)
                x_coord_km = int(parts[0])
                y_coord_km = int(parts[1])

                # Prüfe ob Kachel in erweitertem Bereich liegt
                if (minx_km <= x_coord_km <= maxx_km) and (
                    miny_km <= y_coord_km <= maxy_km
                ):
                    candidate_tiles.append(tile)
                    logger.debug(f"✓ Tile {tile['title']} in bounds")
                else:
                    logger.debug(f"✗ Tile {tile['title']} outside bounds")
        except (ValueError, IndexError) as e:
            # Wenn Parsing fehlschlägt, Tile vorsichtshalber behalten
            logger.debug(f"Failed to parse {tile['title']}: {e}, keeping tile")
            candidate_tiles.append(tile)

    logger.info(
        f"Pre-filter reduced tiles from {len(tiles)} to {len(candidate_tiles)}"
    )
    return candidate_tiles


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


def xyz_to_geotiff(xyz_path: Path, output_path: Path, crs: str = CRS) -> None:
    """
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit GDAL.

    Berlin Daten sind in EPSG:25833, müssen nach EPSG:25832 reprojiziert werden.

    Args:
        xyz_path: Pfad zur XYZ-Datei
        output_path: Ausgabe-GeoTIFF-Pfad
        crs: Ziel-CRS (EPSG:25832)
    """
    logger.info(f"Converting {xyz_path.name} to GeoTIFF...")

    # Temporäres GeoTIFF in source CRS
    temp_tif = output_path.parent / f"{output_path.stem}_temp.tif"

    # Schritt 1: gdal_translate - XYZ zu GeoTIFF in EPSG:25833 (source CRS)
    cmd_translate = [
        "gdal_translate",
        "-of", "GTiff",
        "-a_srs", "EPSG:25833",  # Richtige source CRS!
        "-co", "COMPRESS=LZW",
        str(xyz_path),
        str(temp_tif),
    ]

    # Schritt 2: gdalwarp - Reprojektion + Orientierung fix
    cmd_warp = [
        "gdalwarp",
        "-s_srs", "EPSG:25833",  # Source CRS
        "-t_srs", crs,  # Target CRS (EPSG:25832)
        "-r", "near",  # Nearest neighbor für 1m Daten
        "-overwrite",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BIGTIFF=IF_SAFER",
        str(temp_tif),
        str(output_path),
    ]

    try:
        # Translate
        subprocess.run(
            cmd_translate, check=True, capture_output=True, timeout=600
        )

        # Warp to reproject and fix orientation
        subprocess.run(
            cmd_warp, check=True, capture_output=True, timeout=600
        )

        # Cleanup temp
        temp_tif.unlink()

    except subprocess.CalledProcessError as e:
        logger.error(f"GDAL conversion failed: {e.stderr}")
        if temp_tif.exists():
            temp_tif.unlink()
        raise
    except subprocess.TimeoutExpired:
        logger.error("GDAL conversion timed out after 10 minutes")
        raise


def process_single_tile(
    tile: dict[str, str], temp_dir: Path, skip_download: bool
) -> Path | None:
    """
    Verarbeitet eine einzelne Kachel (für Parallelisierung).

    Args:
        tile: Tile-Dictionary mit 'title' und 'url'
        temp_dir: Temporäres Verzeichnis
        skip_download: Nur Konvertierung durchführen

    Returns:
        GeoTIFF-Pfad oder None bei Fehler
    """
    # Stelle sicher dass temp_dir existiert
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Download ZIP
    zip_path = temp_dir / f"{tile['title']}.zip"
    if not skip_download and not zip_path.exists():
        try:
            download_file(tile["url"], zip_path, f"Tile {tile['title']}")
        except Exception as e:
            logger.warning(f"Failed to download {tile['title']}: {e}")
            return None

    # Skip if ZIP doesn't exist
    if not zip_path.exists():
        return None

    # Extract XYZ
    try:
        extract_dir = temp_dir / "extracted" / tile["title"]
        xyz_files = extract_xyz_from_zip(zip_path, extract_dir)

        if not xyz_files:
            logger.warning(f"No XYZ files in {tile['title']}")
            return None

        # Convert to GeoTIFF
        geotiff_path = temp_dir / "geotiffs" / f"{tile['title']}.tif"
        geotiff_path.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already converted
        if geotiff_path.exists():
            return geotiff_path

        xyz_to_geotiff(xyz_files[0], geotiff_path)
        return geotiff_path

    except Exception as e:
        logger.warning(f"Failed to process {tile['title']}: {e}")
        return None


def download_and_convert_tiles(
    tiles: list[dict[str, str]], temp_dir: Path, skip_download: bool = False,
    n_workers: int = 3
) -> list[Path]:
    """
    Lädt Kacheln herunter, extrahiert XYZ und konvertiert zu GeoTIFF (parallelisiert).

    Args:
        tiles: Liste von Tile-Dictionaries
        temp_dir: Temporäres Verzeichnis
        skip_download: Nur Konvertierung durchführen, kein Download
        n_workers: Anzahl paralleler Worker

    Returns:
        Liste von GeoTIFF-Pfaden
    """
    # Partial function mit festen Parametern
    process_fn = partial(process_single_tile, temp_dir=temp_dir, skip_download=skip_download)

    # Parallele Verarbeitung
    with mp.Pool(n_workers) as pool:
        results = list(tqdm(
            pool.imap(process_fn, tiles),
            total=len(tiles),
            desc="Processing tiles"
        ))

    # Filter None-Werte
    geotiff_paths = [p for p in results if p is not None]

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
    boundary_gdf: gpd.GeoDataFrame, skip_download: bool = False
) -> None:
    """
    Verarbeitet Höhendaten von Atom Feed bis zum finalen Clip.

    Args:
        feed_url: Atom Feed URL
        data_type: "DOM" oder "DGM"
        temp_dir: Temporäres Verzeichnis
        output_path: Finaler Output-Pfad
        boundary_gdf: Stadtgrenze zum Clippen
        skip_download: Nur Konvertierung, kein Download
    """
    if output_path.exists() and validate_geotiff(output_path):
        logger.info(f"{data_type} already exists and is valid, skipping...")
        return

    # Parse feed
    tiles = parse_atom_feed(feed_url)

    # Filter by coordinates
    filtered_tiles = filter_tiles_by_coordinates(tiles, boundary_gdf)

    if not filtered_tiles:
        raise ValueError(f"No tiles found for {data_type} after filtering")

    # Download, extract, convert
    tile_dir = temp_dir / data_type.lower()
    geotiff_paths = download_and_convert_tiles(filtered_tiles, tile_dir, skip_download)

    if not geotiff_paths:
        raise ValueError(f"No GeoTIFF tiles created for {data_type}")

    # Mosaic and clip
    mosaic_and_clip(geotiff_paths, boundary_gdf, output_path)

    # Validate
    if not validate_geotiff(output_path):
        raise ValueError(f"Output validation failed for {output_path}")


def main(skip_download: bool = False) -> None:
    """
    Hauptfunktion: Lädt und verarbeitet Höhendaten für Berlin.

    Args:
        skip_download: Nur Konvertierung bestehender ZIPs, kein Download
    """
    logger.info("=" * 70)
    mode = "Processing only" if skip_download else "Download & Processing"
    logger.info(f"Berlin Elevation Data {mode} - DOM & DGM (XYZ Format)")
    logger.info("=" * 70)

    # Setup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    # Load city boundary
    logger.info(f"Loading boundary from {BOUNDARIES_PATH}...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    berlin_boundary = boundaries[boundaries["gen"] == CITY]

    if berlin_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    logger.info(f"Boundary loaded: CRS {berlin_boundary.crs}")

    # Process DOM
    dom_output = OUTPUT_DIR / "dom_1m.tif"
    try:
        process_elevation_data(
            DOM_FEED_URL, "DOM", temp_dir, dom_output, berlin_boundary, skip_download
        )
    except Exception as e:
        logger.error(f"DOM processing failed: {e}")
        raise

    # Process DGM
    dgm_output = OUTPUT_DIR / "dgm_1m.tif"
    try:
        process_elevation_data(
            DGM_FEED_URL, "DGM", temp_dir, dgm_output, berlin_boundary, skip_download
        )
    except Exception as e:
        logger.error(f"DGM processing failed: {e}")
        raise

    # Cleanup temp files
    logger.info("Cleaning up temporary files...")
    shutil.rmtree(temp_dir)

    logger.info("=" * 70)
    logger.info("Berlin elevation data processing complete!")
    logger.info(f"DOM: {dom_output}")
    logger.info(f"DGM: {dgm_output}")
    logger.info("=" * 70)


if __name__ == "__main__":
    import sys
    skip_download = "--skip-download" in sys.argv
    main(skip_download=skip_download)
