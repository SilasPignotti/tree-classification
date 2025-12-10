"""
Lädt DOM und DGM Höhendaten für Rostock herunter und verarbeitet sie.

Datenquellen:
- DOM: Geodaten MV Atom Feed (XYZ in ZIP für ganz MV, 1m Auflösung)
- DGM: Geodaten MV Atom Feed (XYZ in ZIP für ganz MV, 1m Auflösung)

WICHTIG: Räumliche Filterung erforderlich (MV hat 6407 Kacheln!).
Prozess:
1. Parse Atom Feeds mit bbox-Filtering für Rostock
2. Download ZIPs, extrahiere XYZ
3. Numerisches Grid-Parsing (numpy)
4. Konvertiere zu GeoTIFF (EPSG:25833 -> EPSG:25832)
5. Mosaik + Clip auf Stadtgrenze mit Buffer
"""

import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.transform import from_bounds
from shapely.geometry import box
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


CITY = "Rostock"
OUTPUT_DIR = CHM_RAW_DIR / CITY.lower()
DOM_FEED_URL = ELEVATION_FEEDS["Rostock"]["DOM"]
DGM_FEED_URL = ELEVATION_FEEDS["Rostock"]["DGM"]
SOURCE_CRS = ELEVATION_SOURCE_CRS["Rostock"]
MAX_WORKERS = 3


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
    """Extrahiert Dataset Feed URL aus Haupt-Atom Feed (MV-spezifisch)."""
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


def parse_bbox(bbox_str: str) -> tuple[float, float, float, float] | None:
    """Parst bbox-Attribut aus Atom Feed (lat/lon Format)."""
    try:
        parts = bbox_str.split()
        lat1, lon1, lat2, lon2 = map(float, parts)
        return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
    except (ValueError, IndexError):
        return None


def parse_atom_feed(feed_url: str, boundary_gdf: gpd.GeoDataFrame) -> list[dict]:
    """
    Parst MV Atom Feed und filtert Kacheln nach räumlicher Überschneidung.
    
    MV hat 6407 Kacheln! bbox-Attribute erlauben Pre-Filtering.
    Format: "dom1_33_302_5992_2.zip" oder ähnlich.
    """
    # Schritt 1: Get dataset feed URL
    dataset_feed_url = get_dataset_feed_url(feed_url)

    # Schritt 2: Parse dataset feed
    response = requests.get(dataset_feed_url, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Boundary in WGS84 für bbox-Vergleich
    boundary_wgs84 = boundary_gdf.to_crs("EPSG:4326")
    boundary_bounds = box(*boundary_wgs84.total_bounds)

    tiles = []
    all_tiles_count = 0

    # MV: Alle tiles als <link rel="section"> mit bbox-Attribut
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
                    if not tile_bounds.intersects(boundary_bounds):
                        continue

            # Extrahiere Tile-ID aus URL
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            if "file" in params and params["file"]:
                filename = params["file"][0]
                tile_id = Path(filename).stem
            else:
                tile_id = title if title else Path(url).stem

            tile_id = tile_id.replace("_xyz", "")

            tiles.append({
                "title": tile_id,
                "url": url,
                "filename": filename if "file" in params else f"{tile_id}.zip",
            })

    return tiles


def extract_xyz_from_zip(zip_path: Path, extract_dir: Path) -> list[Path]:
    """Extrahiert XYZ-Dateien aus ZIP-Archiv."""
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
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit NumPy + Rasterio.
    
    Rostock XYZ-Dateien haben unregelmäßiges Whitespace.
    Zweiproxes:
    1. numpy.loadtxt für Grid-Parsing in EPSG:25833
    2. gdalwarp für Reprojizierung zu EPSG:25832
    """
    # Lade XYZ-Daten
    data = np.loadtxt(xyz_path)
    x_coords, y_coords, z_values = data[:, 0], data[:, 1], data[:, 2]

    # Berechne Bounds und Grid
    xmin, xmax = np.floor(x_coords.min()), np.ceil(x_coords.max())
    ymin, ymax = np.floor(y_coords.min()), np.ceil(y_coords.max())

    width = int(xmax - xmin)
    height = int(ymax - ymin)

    # Erstelle leeres Raster
    raster = np.full((height, width), -9999.0, dtype=np.float32)

    # Fülle mit XYZ-Werten
    x_indices = (x_coords - xmin).astype(int)
    y_indices = (ymax - y_coords).astype(int)

    valid = (
        (x_indices >= 0) & (x_indices < width) &
        (y_indices >= 0) & (y_indices < height)
    )

    raster[y_indices[valid], x_indices[valid]] = z_values[valid]

    # Speichere Zwischendatei in EPSG:25833
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
        crs=SOURCE_CRS,
        transform=transform,
        nodata=-9999.0,
        compress="lzw",
    ) as dst:
        dst.write(raster, 1)

    # Reprojiziere zu EPSG:25832
    cmd_warp = [
        "gdalwarp",
        "-s_srs", SOURCE_CRS,
        "-t_srs", TARGET_CRS,
        "-r", "near",
        "-tr", "1.0", "1.0",
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
    """Verarbeitet eine einzelne Kachel."""
    try:
        zip_path = temp_dir / tile["filename"]
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
    """Lädt und konvertiert Kacheln parallel."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    geotiff_paths = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_tile, tile, temp_dir): tile
            for tile in tiles
        }

        for future in tqdm(
            as_completed(futures),
            total=len(tiles),
            desc="Processing tiles"
        ):
            result = future.result()
            if result is not None:
                geotiff_paths.append(result)

    return geotiff_paths


def mosaic_and_clip(
    geotiff_paths: list[Path], boundary_gdf: gpd.GeoDataFrame, output_path: Path
) -> None:
    """Erstellt Mosaik und clippt auf Stadtgrenze."""
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

    tiles = parse_atom_feed(feed_url, boundary_gdf)

    if not tiles:
        raise ValueError(f"No tiles found for {data_type} after spatial filtering")

    tile_dir = temp_dir / data_type.lower()
    geotiff_paths = download_and_convert_tiles(tiles, tile_dir)

    if not geotiff_paths:
        raise ValueError(f"No GeoTIFF tiles created for {data_type}")

    mosaic_and_clip(geotiff_paths, boundary_gdf, output_path)

    if not validate_geotiff(output_path):
        raise ValueError(f"Output validation failed for {output_path}")


def main() -> None:
    """Hauptfunktion: Lädt und verarbeitet DOM & DGM für Rostock."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    boundaries = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
    rostock_boundary = boundaries[boundaries["gen"] == CITY]

    if rostock_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    # Process DOM
    dom_output = OUTPUT_DIR / "dom_1m.tif"
    process_elevation_data(
        DOM_FEED_URL, "DOM", temp_dir, dom_output, rostock_boundary
    )

    # Process DGM
    dgm_output = OUTPUT_DIR / "dgm_1m.tif"
    process_elevation_data(
        DGM_FEED_URL, "DGM", temp_dir, dgm_output, rostock_boundary
    )

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

    print(f"Rostock elevation data complete: {dom_output.name}, {dgm_output.name}")


if __name__ == "__main__":
    main()
