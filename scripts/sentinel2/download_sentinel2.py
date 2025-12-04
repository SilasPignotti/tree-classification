"""
Lädt Sentinel-2 L2A Monatskompositionen für Hamburg, Berlin und Rostock herunter.

Nutzt openEO (Copernicus Data Space Ecosystem) für cloud-native Verarbeitung:
- Cloud-Masking mit SCL-Band
- Temporale Median-Aggregation
- Resampling auf 10m Auflösung
- Output: 10 Bänder pro Monat (B02-B12, ohne B01/B09/B10)

Post-Processing (lokal):
- Reprojektion zu EPSG:25832 (ETRS89 / UTM Zone 32N)
- Clipping auf Stadtgrenzen mit 500m Buffer
- Speicheroptimierung durch präzises Clipping

Datenquelle: Copernicus Data Space Ecosystem (https://openeo.dataspace.copernicus.eu)
"""

import argparse
import sys
import tempfile
from calendar import monthrange
from pathlib import Path

import geopandas as gpd
import numpy as np
import openeo
import rasterio
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BOUNDARIES_BUFFERED_PATH,
    CITIES,
    CLOUD_MASK_VALUES,
    EXPECTED_BAND_COUNT,
    OPENEO_BACKEND,
    SENTINEL2_DIR,
    SPECTRAL_BANDS,
    TARGET_CRS,
    TARGET_RESOLUTION,
    VEGETATION_INDICES,
)


def get_month_range(year: int, month: int) -> tuple[str, str]:
    """
    Gibt Start- und Enddatum für einen Monat zurück.
    """
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def load_city_bounds(city_name: str) -> tuple[dict, gpd.GeoDataFrame]:
    """
    Lädt Stadtgrenzen aus GeoPackage und gibt Bounding Box sowie Geometrie zurück.
    """
    boundaries = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
    
    city_data = boundaries[boundaries["gen"] == city_name]
    
    # Reprojektion zu EPSG:4326 für openEO (erwartet lat/lon)
    city_data_wgs84 = city_data.to_crs("EPSG:4326")
    bounds = city_data_wgs84.total_bounds  # [minx, miny, maxx, maxy]

    bbox = {
        "west": bounds[0],
        "south": bounds[1],
        "east": bounds[2],
        "north": bounds[3],
        "crs": "EPSG:4326",
    }

    return bbox, city_data


def connect_openeo() -> openeo.Connection:
    """
    Stellt Verbindung zu openEO Backend her und authentifiziert.
    """
    import re
    import webbrowser

    connection = openeo.connect(OPENEO_BACKEND)

    def show_device_code(message: str) -> None:
        print("\n" + "=" * 70)
        print("AUTHENTICATION REQUIRED")
        print("=" * 70)
        print(message)
        print("=" * 70 + "\n")

        url_match = re.search(r"https?://[^\s]+", message)
        if url_match:
            try:
                webbrowser.open(url_match.group(0))
                print("(Browser should open automatically)")
            except Exception:
                print("(Please open the URL manually)")

    connection.authenticate_oidc_device(
        provider_id="CDSE",
        display=show_device_code,
    )

    return connection


def process_monthly_composite(
    connection: openeo.Connection,
    city_name: str,
    bbox: dict,
    year: int,
    month: int,
    output_path: Path,
) -> None:
    """
    Verarbeitet und lädt ein monatliches Sentinel-2 Komposit herunter.
    """
    start_date, end_date = get_month_range(year, month)

    s2_cube = connection.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=bbox,
        temporal_extent=[start_date, end_date],
        bands=SPECTRAL_BANDS + ["SCL"],
    )

    # Cloud masking: exclude all problematic SCL values
    scl = s2_cube.band("SCL")
    # Since DataCube doesn't have isin() or logical_not(), use ~ for NOT
    cloud_mask = (
        (scl == CLOUD_MASK_VALUES[0]) |
        (scl == CLOUD_MASK_VALUES[1]) |
        (scl == CLOUD_MASK_VALUES[2]) |
        (scl == CLOUD_MASK_VALUES[3])
    )
    mask = ~cloud_mask

    s2_monthly = (
        s2_cube.mask(~mask)
        .filter_bands(SPECTRAL_BANDS)
        .resample_spatial(resolution=TARGET_RESOLUTION, method="bilinear")
        .reduce_dimension(dimension="t", reducer="median")
    )

    job = s2_monthly.execute_batch(
        out_format="GTiff",
        title=f"S2_{city_name}_{year}_{month:02d}",
        outputfile=output_path,
        job_options={"driver-memory": "4g", "executor-memory": "4g"},
    )
    job.start_and_wait()
    job.download_result(output_path)


def reproject_and_add_indices(
    input_path: Path,
    output_path: Path,
) -> None:
    """
    Reprojiziert Raster zu EPSG:25832 und fügt Vegetationsindizes hinzu.
    
    Output-Bänder: 10 Spektralbänder + 5 Indizes
    - NDre: (B8A - B05) / (B8A + B05)
    - NDVIre: (B8A - B04) / (B8A + B04)  
    - kNDVI: tanh((B08 - B04)² / (B08 + B04)²)
    - VARI: (B03 - B04) / (B03 + B04 - B02)
    - RTVIcore: 100*(B8A - B05) - 10*(B8A - B04)
    """
    with rasterio.open(input_path) as src:
        dst_crs = CRS.from_string(TARGET_CRS)
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds,
            resolution=TARGET_RESOLUTION,
        )

        # Reproject all spectral bands
        bands = {}
        for i, name in enumerate(SPECTRAL_BANDS, start=1):
            dst_array = np.zeros((height, width), dtype=np.float32)
            reproject(
                source=rasterio.band(src, i),
                destination=dst_array,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )
            bands[name] = dst_array
        
        # Calculate vegetation indices
        eps = 1e-8
        b02, b03, b04 = bands["B02"], bands["B03"], bands["B04"]
        b05, b08, b8a = bands["B05"], bands["B08"], bands["B8A"]
        
        indices = {
            "NDre": (b8a - b05) / (b8a + b05 + eps),
            "NDVIre": (b8a - b04) / (b8a + b04 + eps),
            "kNDVI": np.tanh(((b08 - b04) / (b08 + b04 + eps)) ** 2),
            "VARI": (b03 - b04) / (b03 + b04 - b02 + eps),
            "RTVIcore": 100 * (b8a - b05) - 10 * (b8a - b04),
        }
        
        # Write output
        dst_meta = src.meta.copy()
        dst_meta.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "count": len(SPECTRAL_BANDS) + len(VEGETATION_INDICES),
            "dtype": "float32",
            "compress": "lzw",
            "predictor": 2,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
        })

        with rasterio.open(output_path, "w", **dst_meta) as dst:
            for i, name in enumerate(SPECTRAL_BANDS, start=1):
                dst.write(bands[name], i)
                dst.set_band_description(i, name)
            
            for i, name in enumerate(VEGETATION_INDICES, start=len(SPECTRAL_BANDS) + 1):
                dst.write(indices[name].astype(np.float32), i)
                dst.set_band_description(i, name)


def validate_output(file_path: Path, city_geometry: gpd.GeoDataFrame) -> bool:
    """
    Validiert heruntergeladenes Sentinel-2 GeoTIFF.
    """
    try:
        with rasterio.open(file_path) as src:
            if src.count != EXPECTED_BAND_COUNT:
                return False

            if src.crs is None or src.crs != CRS.from_string(TARGET_CRS):
                return False

            res_x = abs(src.res[0])
            if not (5 < res_x < 15):
                return False

            data = src.read(1)
            
            city_mask = geometry_mask(
                city_geometry.geometry,
                out_shape=(src.height, src.width),
                transform=src.transform,
                invert=True
            )
            
            pixels_in_city = np.sum(city_mask)
            if pixels_in_city == 0:
                return False
            
            has_data = data != 0
            pixels_with_data_in_city = np.sum(city_mask & has_data)
            
            if pixels_with_data_in_city / pixels_in_city < 0.5:
                return False

            return True

    except Exception:
        return False


def download_sentinel2(
    cities: list[str],
    year: int,
    months: list[int],
    output_dir: Path,
    resume: bool = True,
) -> None:
    """
    Lädt Sentinel-2 Monatskompositionen für alle Städte herunter.
    """
    connection = connect_openeo()

    city_bounds = {}
    city_geometries = {}
    for city in cities:
        bbox, geometry = load_city_bounds(city)
        city_bounds[city] = bbox
        city_geometries[city] = geometry

    processed = 0
    failed = []

    for city in cities:
        city_output_dir = output_dir / city.lower()
        city_output_dir.mkdir(parents=True, exist_ok=True)
        city_geom = city_geometries[city]
        city_bbox = city_bounds[city]

        for month in months:
            processed += 1
            output_path = city_output_dir / f"S2_{year}_{month:02d}_median.tif"

            if resume and output_path.exists() and validate_output(output_path, city_geom):
                continue

            print(f"Processing {city} {month:02d}...")
            try:
                with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_file:
                    tmp_download_path = Path(tmp_file.name)

                try:
                    process_monthly_composite(
                        connection=connection,
                        city_name=city,
                        bbox=city_bbox,
                        year=year,
                        month=month,
                        output_path=tmp_download_path,
                    )

                    reproject_and_add_indices(
                        input_path=tmp_download_path,
                        output_path=output_path,
                    )

                finally:
                    if tmp_download_path.exists():
                        tmp_download_path.unlink()

                if not validate_output(output_path, city_geom):
                    failed.append((city, month))
                    print(f"Warning: {city} {month:02d} has <50% valid pixels")
                else:
                    print(f"✓ Completed {city} {month:02d}")

            except Exception as e:
                failed.append((city, month))
                print(f"✗ Failed {city} {month:02d}: {e}")


def parse_month_range(month_str: str) -> list[int]:
    """Parst Monats-Bereichsangabe."""
    if "-" in month_str:
        start, end = month_str.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(month_str)]


def main() -> None:
    """CLI-Einstiegspunkt."""
    parser = argparse.ArgumentParser(
        description="Download Sentinel-2 L2A monthly composites using openEO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download full year for all cities
  python download_sentinel2.py

  # Download specific months for one city
  python download_sentinel2.py --cities Hamburg --months 4-10

  # Download without resume (re-download existing files)
  python download_sentinel2.py --no-resume
        """,
    )

    parser.add_argument(
        "--cities",
        nargs="+",
        default=CITIES,
        choices=CITIES,
        help=f"Cities to process (default: {', '.join(CITIES)})",
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Year to download (default: 2021)",
    )

    parser.add_argument(
        "--months",
        type=str,
        default="1-12",
        help="Month range, e.g. '1-12' or '4-10' (default: 1-12)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=SENTINEL2_DIR,
        help=f"Output directory (default: {SENTINEL2_DIR})",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-download existing files instead of skipping",
    )

    args = parser.parse_args()
    months = parse_month_range(args.months)

    download_sentinel2(
        cities=args.cities,
        year=args.year,
        months=months,
        output_dir=args.output,
        resume=not args.no_resume,
    )

    # Optional: Print summary if failed
    if failed:
        print(f"\nFailed downloads: {failed}")


if __name__ == "__main__":
    main()
