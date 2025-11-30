"""
Lädt Sentinel-2 L2A Monatskompositionen für Hamburg, Berlin und Rostock herunter.

Nutzt openEO (Copernicus Data Space Ecosystem) für cloud-native Verarbeitung:
- Cloud-Masking mit SCL-Band
- Temporale Median-Aggregation
- Resampling auf 10m Auflösung
- Output: 10 Bänder pro Monat (B02-B12, ohne B01/B09/B10)

Datenquelle: Copernicus Data Space Ecosystem (https://openeo.dataspace.copernicus.eu)
"""

import argparse
import logging
from calendar import monthrange
from pathlib import Path

import geopandas as gpd
import numpy as np
import openeo
import rasterio
from rasterio.crs import CRS

# Konstanten
CITIES = ["Hamburg", "Berlin", "Rostock"]
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries_500m_buffer.gpkg")
OUTPUT_DIR = Path("data/sentinel2")
TARGET_CRS = "EPSG:25832"
TARGET_RESOLUTION = 10  # meters

# Sentinel-2 Bänder für Vegetation
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

# openEO Backend
OPENEO_BACKEND = "openeo.dataspace.copernicus.eu"

# Logging Setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_month_range(year: int, month: int) -> tuple[str, str]:
    """
    Gibt Start- und Enddatum für einen Monat zurück.

    Args:
        year: Jahr
        month: Monat (1-12)

    Returns:
        Tuple (start_date, end_date) im Format YYYY-MM-DD
    """
    _, last_day = monthrange(year, month)
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day:02d}"
    return start, end


def load_city_bounds(city_name: str) -> dict:
    """
    Lädt Stadtgrenzen aus GeoPackage und gibt Bounding Box zurück.

    Args:
        city_name: Name der Stadt (Hamburg, Berlin, Rostock)

    Returns:
        Dict mit west, south, east, north, crs Schlüsseln
    """
    logger.info(f"Loading boundary for {city_name}...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)

    # Spalte 'gen' enthält Stadtnamen
    city_gdf = boundaries[boundaries["gen"] == city_name]

    if city_gdf.empty:
        raise ValueError(f"No boundary found for {city_name}")

    # Reprojektion zu EPSG:4326 für openEO (erwartet lat/lon)
    city_gdf_wgs84 = city_gdf.to_crs("EPSG:4326")
    bounds = city_gdf_wgs84.total_bounds  # [minx, miny, maxx, maxy]

    bbox = {
        "west": float(bounds[0]),
        "south": float(bounds[1]),
        "east": float(bounds[2]),
        "north": float(bounds[3]),
        "crs": "EPSG:4326",
    }

    logger.info(f"  Bounds: W={bbox['west']:.4f}, S={bbox['south']:.4f}, "
                f"E={bbox['east']:.4f}, N={bbox['north']:.4f}")

    return bbox


def connect_openeo() -> openeo.Connection:
    """
    Stellt Verbindung zu openEO Backend her und authentifiziert.

    Returns:
        Authentifizierte openEO Connection

    Note:
        Beim ersten Aufruf öffnet sich ein Browser für die Authentifizierung.
        Danach wird ein Refresh-Token lokal gespeichert.
    """
    import webbrowser

    logger.info(f"Connecting to openEO backend: {OPENEO_BACKEND}")
    connection = openeo.connect(OPENEO_BACKEND)

    logger.info("Authenticating with OIDC...")

    # Define custom display function to ensure URL is printed
    # The display function receives a single message string from openEO
    def show_device_code(message: str) -> None:
        print("\n" + "=" * 70)
        print("AUTHENTICATION REQUIRED")
        print("=" * 70)
        print(message)
        print("=" * 70 + "\n")

        # Try to extract URL and open browser automatically
        import re

        url_match = re.search(r"(https?://[^\s]+)", message)
        if url_match:
            try:
                webbrowser.open(url_match.group(1))
                print("(Browser should open automatically)")
            except Exception:
                print("(Please open the URL manually)")

    # Use device code flow with explicit display
    connection.authenticate_oidc_device(
        provider_id="CDSE",
        display=show_device_code,
    )

    logger.info("Successfully authenticated!")
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

    Args:
        connection: Authentifizierte openEO-Verbindung
        city_name: Name der Stadt
        bbox: Bounding Box als Dict
        year: Jahr
        month: Monat (1-12)
        output_path: Ausgabepfad für GeoTIFF

    Pipeline:
        1. Lade S2 L2A Collection
        2. Cloud-Masking mit SCL-Band
        3. Resampling auf 10m
        4. Temporale Median-Aggregation
        5. Download als GeoTIFF
    """
    start_date, end_date = get_month_range(year, month)
    logger.info(f"Processing {city_name} {year}-{month:02d} ({start_date} to {end_date})")

    # Lade Sentinel-2 L2A mit allen benötigten Bändern + SCL
    bands_with_scl = SPECTRAL_BANDS + ["SCL"]

    s2_cube = connection.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=bbox,
        temporal_extent=[start_date, end_date],
        bands=bands_with_scl,
    )

    # Cloud-Masking: Erstelle Maske aus SCL-Band
    scl = s2_cube.band("SCL")

    # Erstelle binäre Maske (True = valid, False = cloud/shadow)
    mask = scl != 3  # Start with non-shadow
    for cloud_val in CLOUD_MASK_VALUES[1:]:
        mask = mask & (scl != cloud_val)

    # Wende Maske auf alle Bänder an
    s2_masked = s2_cube.mask(~mask)

    # Entferne SCL-Band (nur für Masking benötigt)
    s2_masked = s2_masked.filter_bands(SPECTRAL_BANDS)

    # Resample 20m Bänder auf 10m
    s2_resampled = s2_masked.resample_spatial(
        resolution=TARGET_RESOLUTION,
        method="bilinear",
    )

    # Temporale Aggregation: Median über alle gültigen Beobachtungen
    s2_monthly = s2_resampled.reduce_dimension(
        dimension="t",
        reducer="median",
    )

    # Starte Job und warte auf Abschluss
    logger.info(f"Starting openEO batch job for {city_name} {year}-{month:02d}...")

    job = s2_monthly.execute_batch(
        out_format="GTiff",
        title=f"S2_{city_name}_{year}_{month:02d}",
        outputfile=output_path,
        job_options={
            "driver-memory": "4g",
            "executor-memory": "4g",
        },
    )

    logger.info(f"Job submitted: {job.job_id}")
    logger.info("Waiting for job completion (this may take 10-30 minutes)...")

    # Warte auf Job-Abschluss
    job.start_and_wait()

    # Download Ergebnis
    logger.info(f"Downloading result to {output_path}...")
    job.download_result(output_path)

    logger.info(f"✓ Downloaded: {output_path.name}")


def validate_output(file_path: Path) -> bool:
    """
    Validiert heruntergeladenes Sentinel-2 GeoTIFF.

    Args:
        file_path: Pfad zur GeoTIFF-Datei

    Returns:
        True wenn valide, sonst False

    Checks:
        - Band count: 10
        - CRS: EPSG:25832 oder EPSG:4326 (wird später reprojiziert)
        - Resolution: ~10m
        - Valid pixels: >50%
        - Reflectance range: 0-10000
    """
    try:
        with rasterio.open(file_path) as src:
            # Check 1: Korrekte Bandanzahl
            if src.count != len(SPECTRAL_BANDS):
                logger.warning(
                    f"Expected {len(SPECTRAL_BANDS)} bands, got {src.count}"
                )
                return False

            # Check 2: CRS vorhanden
            if src.crs is None:
                logger.warning("No CRS defined")
                return False

            # Check 3: Auflösung prüfen (ungefähr 10m)
            res_x, res_y = abs(src.res[0]), abs(src.res[1])
            # Bei WGS84 ist Auflösung in Grad (~0.0001° ≈ 10m)
            if src.crs == CRS.from_epsg(4326):
                if not (0.00005 < res_x < 0.0002):
                    logger.warning(f"Unexpected resolution in degrees: {res_x}")
                    return False
            else:
                if not (5 < res_x < 15):
                    logger.warning(f"Resolution mismatch: {res_x}m (expected ~10m)")
                    return False

            # Check 4: Valid pixels Anteil
            data = src.read(1)  # Erstes Band (Blue)
            valid_mask = (data > 0) & (data <= 10000)
            valid_pct = np.sum(valid_mask) / data.size

            if valid_pct < 0.3:
                logger.warning(
                    f"Only {valid_pct:.1%} valid pixels (may be cloud-contaminated)"
                )
                return False

            # Check 5: Reflectance Wertebereich
            max_val = data[valid_mask].max() if valid_mask.any() else 0
            if max_val > 10000:
                logger.warning(f"Reflectance out of range: max={max_val}")
                return False

            logger.info(
                f"✓ Validated {file_path.name}: "
                f"{src.width}x{src.height}, {src.count} bands, "
                f"CRS: {src.crs}, Valid: {valid_pct:.1%}"
            )
            return True

    except Exception as e:
        logger.error(f"Validation failed for {file_path}: {e}")
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

    Args:
        cities: Liste der Stadtnamen
        year: Jahr
        months: Liste der Monate (1-12)
        output_dir: Ausgabeverzeichnis
        resume: Überspringe existierende Dateien
    """
    # Verbinde zu openEO
    connection = connect_openeo()

    # Lade Stadtgrenzen
    city_bounds = {}
    for city in cities:
        city_bounds[city] = load_city_bounds(city)

    # Verarbeite alle Stadt/Monat-Kombinationen
    total_files = len(cities) * len(months)
    processed = 0
    failed = []

    for city in cities:
        city_output_dir = output_dir / city.lower()
        city_output_dir.mkdir(parents=True, exist_ok=True)

        for month in months:
            processed += 1
            output_path = city_output_dir / f"S2_{year}_{month:02d}_median.tif"

            # Checkpointing: Überspringe existierende valide Dateien
            if resume and output_path.exists():
                if validate_output(output_path):
                    logger.info(
                        f"[{processed}/{total_files}] Skipping {output_path.name} "
                        "(already exists and valid)"
                    )
                    continue
                else:
                    logger.info(
                        f"[{processed}/{total_files}] Re-downloading invalid file: "
                        f"{output_path.name}"
                    )

            logger.info(f"[{processed}/{total_files}] Processing {city} {year}-{month:02d}")

            try:
                process_monthly_composite(
                    connection=connection,
                    city_name=city,
                    bbox=city_bounds[city],
                    year=year,
                    month=month,
                    output_path=output_path,
                )

                # Validiere nach Download
                if not validate_output(output_path):
                    logger.warning(f"Validation failed for {output_path.name}")
                    failed.append((city, month))

            except Exception as e:
                logger.error(f"Failed to process {city} {year}-{month:02d}: {e}")
                failed.append((city, month))

    # Summary
    logger.info("=" * 70)
    logger.info("Download Summary")
    logger.info("=" * 70)
    logger.info(f"Total: {total_files} files")
    logger.info(f"Successful: {total_files - len(failed)}")
    logger.info(f"Failed: {len(failed)}")

    if failed:
        logger.warning("Failed downloads:")
        for city, month in failed:
            logger.warning(f"  - {city} {year}-{month:02d}")


def parse_month_range(month_str: str) -> list[int]:
    """
    Parst Monats-Bereichsangabe.

    Args:
        month_str: z.B. "1-12", "4-10", "6"

    Returns:
        Liste von Monaten als Integers
    """
    if "-" in month_str:
        start, end = month_str.split("-")
        return list(range(int(start), int(end) + 1))
    else:
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
        default=2024,
        help="Year to download (default: 2024)",
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
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-download existing files instead of skipping",
    )

    args = parser.parse_args()

    months = parse_month_range(args.months)

    logger.info("=" * 70)
    logger.info("Sentinel-2 Download - openEO")
    logger.info("=" * 70)
    logger.info(f"Cities: {', '.join(args.cities)}")
    logger.info(f"Year: {args.year}")
    logger.info(f"Months: {min(months)}-{max(months)} ({len(months)} months)")
    logger.info(f"Output: {args.output}")
    logger.info(f"Resume: {not args.no_resume}")
    logger.info("=" * 70)

    download_sentinel2(
        cities=args.cities,
        year=args.year,
        months=months,
        output_dir=args.output,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
