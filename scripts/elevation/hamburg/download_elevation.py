"""
Lädt DOM und DGM Höhendaten für Hamburg herunter und verarbeitet sie.

Datenquellen:
- DOM: Hamburg Opendata (XYZ in ZIP, 1m Auflösung)
- DGM: Hamburg Opendata (XYZ in ZIP, 1m Auflösung)

Prozess:
1. Download ZIPs direkt (keine Atom-Feeds)
2. Extrahiere XYZ-Dateien
3. Konvertiere XYZ zu GeoTIFF (Hamburg bereits in EPSG:25832)
4. Mosaik + Clip auf Stadtgrenze mit Buffer
"""

import subprocess
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


CITY = "Hamburg"
OUTPUT_DIR = CHM_RAW_DIR / CITY.lower()
DOM_URL = ELEVATION_FEEDS["Hamburg"]["DOM"]
DGM_URL = ELEVATION_FEEDS["Hamburg"]["DGM"]
SOURCE_CRS = ELEVATION_SOURCE_CRS["Hamburg"]


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
    xyz_files.extend(extract_dir.rglob("*.txt"))

    return xyz_files


def xyz_to_geotiff(xyz_path: Path, output_path: Path) -> None:
    """
    Konvertiert XYZ ASCII-Datei zu GeoTIFF mit GDAL.
    
    Hamburg ist bereits in EPSG:25832 (target CRS).
    Direktkonvertierung ohne Reprojizierung.
    """
    cmd = ["gdal_translate", "-of", "GTiff", "-a_srs", SOURCE_CRS] + GDAL_TRANSLATE_OPTS + [str(xyz_path), str(output_path)]

    try:
        subprocess.run(
            cmd, check=True, capture_output=True, timeout=ELEVATION_TIMEOUT_S
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"GDAL translate failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GDAL translate timed out")


def process_single_tile(
    tile_dict: dict[str, str], temp_dir: Path
) -> Path | None:
    """Verarbeitet eine einzelne Kachel: Download -> Extraktion -> Konvertierung."""
    try:
        zip_path = temp_dir / tile_dict["filename"]
        if not zip_path.exists():
            download_file(tile_dict["url"], zip_path)

        extract_dir = temp_dir / "extracted" / tile_dict["name"]
        xyz_files = extract_xyz_from_zip(zip_path, extract_dir)

        if not xyz_files:
            return None

        geotiff_path = temp_dir / "geotiffs" / f"{tile_dict['name']}.tif"
        geotiff_path.parent.mkdir(parents=True, exist_ok=True)

        # Hamburg kann mehrere XYZ-Dateien haben, konvertiere alle
        for xyz_file in xyz_files:
            xyz_to_geotiff(xyz_file, geotiff_path)
            break  # Nutze nur erste Datei

        return geotiff_path

    except Exception:
        return None


def download_and_convert_tiles(
    urls: dict[str, str], temp_dir: Path
) -> list[Path]:
    """Lädt und konvertiert DOM und DGM."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    geotiff_paths = []

    for data_type, url in urls.items():
        try:
            tile_dict = {
                "name": data_type.lower(),
                "url": url,
                "filename": f"{data_type.lower()}.zip",
            }
            result = process_single_tile(tile_dict, temp_dir)
            if result is not None:
                geotiff_paths.append(result)
        except Exception:
            continue

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
    urls: dict[str, str], temp_dir: Path, output_paths: dict[str, Path],
    boundary_gdf: gpd.GeoDataFrame
) -> None:
    """Verarbeitet DOM und DGM zusammen (Hamburg ist One-Shot)."""
    # Check if both already exist
    if all(p.exists() and validate_geotiff(p) for p in output_paths.values()):
        return

    # Hamburg: Download both DOM and DGM
    geotiff_paths = download_and_convert_tiles(urls, temp_dir)

    if not geotiff_paths:
        raise ValueError("No GeoTIFF tiles created")

    # Hamburg hat nur eine Datei je Typ, kein Mosaic nötig
    # Aber wir clippen trotzdem auf Boundary mit Buffer
    for geotiff_path in geotiff_paths:
        # Bestimme output file basierend auf naming
        if "dom" in geotiff_path.stem.lower():
            output_path = output_paths["DOM"]
        else:
            output_path = output_paths["DGM"]

        # Clip to boundary (tqdm nicht nötig, nur eine Datei)
        with rasterio.open(geotiff_path) as src:
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

    # Validate
    for data_type, output_path in output_paths.items():
        if not validate_geotiff(output_path):
            raise ValueError(f"Output validation failed for {output_path}")


def main() -> None:
    """Hauptfunktion: Lädt und verarbeitet DOM & DGM für Hamburg."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = OUTPUT_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    boundaries = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
    hamburg_boundary = boundaries[boundaries["gen"] == CITY]

    if hamburg_boundary.empty:
        raise ValueError(f"No boundary found for {CITY}")

    # Hamburg: Direct download URLs
    urls = {
        "DOM": DOM_URL,
        "DGM": DGM_URL,
    }

    output_paths = {
        "DOM": OUTPUT_DIR / "dom_1m.tif",
        "DGM": OUTPUT_DIR / "dgm_1m.tif",
    }

    process_elevation_data(urls, temp_dir, output_paths, hamburg_boundary)

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

    print(f"Hamburg elevation data complete: {list(output_paths.values())}")


if __name__ == "__main__":
    main()
