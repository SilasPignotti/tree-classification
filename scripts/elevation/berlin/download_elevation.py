"""
Lädt DOM und DGM Höhendaten für Berlin herunter und verarbeitet sie.

Datenquellen:
- DOM: Berlin FIS-Broker Atom Feed (XYZ in ZIP, 1m Auflösung)
- DGM: Berlin GDI Atom Feed (XYZ in ZIP, 1m Auflösung)

Prozess:
1. Parse Atom Feeds (nested structure)
2. Filter Kacheln nach Koordinaten im Dateinamen (boundary + 500m buffer)
3. Download ZIPs, extrahiere XYZ
4. Konvertiere XYZ zu GeoTIFF (EPSG:25833 -> EPSG:25832)
5. Mosaik + Clip auf Stadtgrenze mit Buffer
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.mask import mask
from rasterio.merge import merge
from tqdm import tqdm

from scripts.config import (
    BOUNDARIES_BUFFERED_PATH,
    CHM_RAW_DIR,
    ELEVATION_FEEDS,
    ELEVATION_MAX_RETRIES,
    ELEVATION_SOURCE_CRS,
    ELEVATION_TIMEOUT_S,
    GDAL_TRANSLATE_OPTS,
    GDALWARP_OPTS,
    TARGET_CRS,
)


CITY = "Berlin"
OUTPUT_DIR = CHM_RAW_DIR / CITY.lower()
DOM_FEED_URL = ELEVATION_FEEDS["Berlin"]["DOM"]
DGM_FEED_URL = ELEVATION_FEEDS["Berlin"]["DGM"]
SOURCE_CRS = ELEVATION_SOURCE_CRS["Berlin"]


def download_file(url: str, output_path: Path) -> None:
    """Lädt eine Datei mit Retry-Logik herunter."""
    for attempt in range(1, ELEVATION_MAX_RETRIES + 1):
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            with open(output_path, "wb") as f, tqdm(
                desc=f"Downloading {output_path.name}",
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
            if attempt == ELEVATION_MAX_RETRIES:
                raise

    raise RuntimeError(f"Failed to download {url} after {ELEVATION_MAX_RETRIES} attempts")


def get_dataset_feed_url(main_feed_url: str) -> str:
    """Extrahiert Dataset Feed URL aus Haupt-Atom Feed (Berlin-spezifisch)."""
    response = requests.get(main_feed_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

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
    
    Berlin-Struktur: nested feed mit dataset-feed, tiles als <link rel="section">.
    Format: "DOM1 XXX_YYYY" oder "DGM1 XXX_YYYY" (km-Koordinaten in EPSG:25833).
    """
    # Schritt 1: Get dataset feed URL
    dataset_feed_url = get_dataset_feed_url(feed_url)

    # Schritt 2: Parse dataset feed
    response = requests.get(dataset_feed_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    tiles = []
    for entry in root.findall("atom:entry", ns):
        for link in entry.findall("atom:link[@rel='section']", ns):
            title = link.get("title")
            url = link.get("href")

            if url and url.endswith(".zip"):
                if title:
                    tile_id = title.replace("ATKIS® ", "").replace(".zip", "")
                else:
                    tile_id = Path(url).stem

                tiles.append({
                    "title": tile_id,
                    "url": url,
                })

    return tiles


def filter_tiles_by_coordinates(
    tiles: list[dict[str, str]], boundary_gdf: gpd.GeoDataFrame
) -> list[dict[str, str]]:
    """
    Filtert Kacheln basierend auf Koordinaten im Dateinamen.
    
    Berlin-Tiles: Format "DOM1 XXX_YYYY" mit km-Koordinaten in EPSG:25833.
    Es wird auf die gepufferte Grenze gefiltert um komplette DOM/DGM zu erhalten.
    """
    # Transform zu EPSG:25833 (Tile-CRS)
    boundary_25833 = boundary_gdf.to_crs("EPSG:25833")
    boundary_bounds = boundary_25833.total_bounds
    minx, miny, maxx, maxy = boundary_bounds

    # Konvertiere zu km
    minx_km = int(minx / 1000)
    miny_km = int(miny / 1000)
    maxx_km = int(maxx / 1000) + 1
    maxy_km = int(maxy / 1000) + 1

    # Erweitere um Kachelgröße (2km)
    buffer_km = 2
    minx_km -= buffer_km
    miny_km -= buffer_km
    maxx_km += buffer_km
    maxy_km += buffer_km

    candidate_tiles = []
    for tile in tiles:
        try:
            title_clean = tile["title"].replace("DOM1 ", "").replace("DGM1 ", "")
            parts = title_clean.split("_")

            if len(parts) >= 2:
                x_coord_km = int(parts[0])
                y_coord_km = int(parts[1])

                if (minx_km <= x_coord_km <= maxx_km) and (
                    miny_km <= y_coord_km <= maxy_km
                ):
                    candidate_tiles.append(tile)
        except (ValueError, IndexError):
            # Bei Parsing-Fehler vorsichtshalber behalten
            candidate_tiles.append(tile)

    return candidate_tiles


def extract_xyz_from_zip(zip_path: Path, extract_dir: Path) -> list[Path]:
    """Extrahiert XYZ-Dateien aus ZIP-Archiv via system unzip."""
    extract_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["unzip", "-q", "-o", str(zip_path), "-d", str(extract_dir)]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Unzip failed: {e.stderr.decode()}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Unzip timed out after 5 minutes")

    xyz_files = list(extract_dir.rglob("*.xyz"))
    xyz_files.extend(extract_dir.rglob("*.csv"))
    xyz_files.extend(extract_dir.rglob("*.txt"))

    return xyz_files


def xyz_to_geotiff(xyz_path: Path, output_path: Path) -> None:
    """
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit GDAL.
    
    Zweiteiliger Prozess:
    1. gdal_translate: XYZ -> GeoTIFF in EPSG:25833
    2. gdalwarp: Reprojizierung zu EPSG:25832 + Orientierungscorrection
    """
    temp_tif = output_path.parent / f"{output_path.stem}_temp.tif"

    # Schritt 1: translate mit korrektem source CRS
    cmd_translate = ["gdal_translate", "-of", "GTiff", "-a_srs", SOURCE_CRS] + GDAL_TRANSLATE_OPTS + [str(xyz_path), str(temp_tif)]

    try:
        subprocess.run(
            cmd_translate, check=True, capture_output=True, timeout=ELEVATION_TIMEOUT_S
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"GDAL translate failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GDAL translate timed out")

    # Schritt 2: warp für Reprojizierung
    cmd_warp = [
        "gdalwarp",
        "-s_srs", SOURCE_CRS,
        "-t_srs", TARGET_CRS,
        "-overwrite",
    ] + GDALWARP_OPTS + [str(temp_tif), str(output_path)]

    try:
        subprocess.run(
            cmd_warp, check=True, capture_output=True, timeout=ELEVATION_TIMEOUT_S
        )
        temp_tif.unlink()
    except subprocess.CalledProcessError as e:
        if temp_tif.exists():
            temp_tif.unlink()
        raise RuntimeError(f"GDAL warp failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        if temp_tif.exists():
            temp_tif.unlink()
        raise RuntimeError("GDAL warp timed out")


def process_single_tile(
    tile: dict[str, str], temp_dir: Path
) -> Path | None:
    """Verarbeitet eine einzelne Kachel: Download -> Extraktion -> Konvertierung."""
    try:
        zip_path = temp_dir / f"{tile['title']}.zip"
        if not zip_path.exists():
            download_file(tile["url"], zip_path)

        extract_dir = temp_dir / "extracted" / tile["title"]
        xyz_files = extract_xyz_from_zip(zip_path, extract_dir)

        if not xyz_files:
            return None

        geotiff_path = temp_dir / "geotiffs" / f"{tile['title']}.tif"
        geotiff_path.parent.mkdir(parents=True, exist_ok=True)

        xyz_to_geotiff(xyz_files[0], geotiff_path)
        return geotiff_path

    except Exception:
        return None


def download_and_convert_tiles(
    tiles: list[dict[str, str]], temp_dir: Path
) -> list[Path]:
    """Lädt und konvertiert alle Kacheln sequenziell."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    geotiff_paths = []

    for tile in tqdm(tiles, desc="Processing tiles"):
        result = process_single_tile(tile, temp_dir)
        if result is not None:
            geotiff_paths.append(result)

    return geotiff_paths


def mosaic_and_clip(
    geotiff_paths: list[Path], boundary_gdf: gpd.GeoDataFrame, output_path: Path
) -> None:
    """Erstellt Mosaik aus GeoTIFFs und clippt auf Stadtgrenze."""
    if not geotiff_paths:
        raise ValueError("No GeoTIFF tiles to mosaic")

    src_files = []
    for p in geotiff_paths:
        try:
            src = rasterio.open(p)
            src_files.append(src)
        except Exception:
            continue

    if not src_files:
        raise ValueError("No valid GeoTIFF tiles to mosaic")

    try:
        mosaic, out_trans = merge(src_files, method="first")
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

    # Clip to boundary
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

    temp_mosaic.unlink()


def validate_geotiff(file_path: Path) -> bool:
    """Validiert GeoTIFF-Datei."""
    try:
        with rasterio.open(file_path) as src:
            _ = src.read(1, window=((0, 10), (0, 10)))
        return True
    except Exception:
        return False


def process_elevation_data(
    feed_url: str, data_type: str, temp_dir: Path, output_path: Path,
    boundary_gdf: gpd.GeoDataFrame
) -> None:
    """Verarbeitet Höhendaten von Atom Feed bis zum finalen Output."""
    if output_path.exists() and validate_geotiff(output_path):
        return

    tiles = parse_atom_feed(feed_url)
    filtered_tiles = filter_tiles_by_coordinates(tiles, boundary_gdf)

    if not filtered_tiles:
        raise ValueError(f"No tiles found for {data_type} after filtering")

    tile_dir = temp_dir / data_type.lower()
    geotiff_paths = download_and_convert_tiles(filtered_tiles, tile_dir)

    if not geotiff_paths:
        raise ValueError(f"No GeoTIFF tiles created for {data_type}")

    mosaic_and_clip(geotiff_paths, boundary_gdf, output_path)

    if not validate_geotiff(output_path):
        raise ValueError(f"Output validation failed for {output_path}")


def main() -> None:
    """Hauptfunktion: Lädt und verarbeitet DOM & DGM für Berlin."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    boundaries = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
    berlin_boundary = boundaries[boundaries["gen"] == CITY]

    if berlin_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    # Process DOM
    dom_output = OUTPUT_DIR / "dom_1m.tif"
    process_elevation_data(
        DOM_FEED_URL, "DOM", temp_dir, dom_output, berlin_boundary
    )

    # Process DGM
    dgm_output = OUTPUT_DIR / "dgm_1m.tif"
    process_elevation_data(
        DGM_FEED_URL, "DGM", temp_dir, dgm_output, berlin_boundary
    )

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

    print(f"Berlin elevation data complete: {dom_output.name}, {dgm_output.name}")


if __name__ == "__main__":
    main()
