"""
Validiert Höhendaten (DOM und DGM) für alle drei Städte.

Überprüfungen:
1. Dateiexistenz und Größe
2. CRS (EPSG:25832)
3. Pixelgröße (1m)
4. Datenbereich und Statistiken
5. NoData-Behandlung
6. DOM > DGM Sanity Check
7. Datenabdeckung (% gültige Pixel INNERHALB Stadtgrenzen)
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import (
    BOUNDARIES_PATH,
    CHM_RAW_DIR,
    CITIES,
    ELEVATION_RESOLUTION_M,
    TARGET_CRS,
)


def validate_elevation_files() -> None:
    """Validiert alle Elevation-Dateien."""
    print("=" * 90)
    print("ELEVATION DATA VALIDATION")
    print("=" * 90)
    print()

    # Lade Stadtgrenzen (OHNE Buffer) für Coverage-Berechnung
    boundaries = gpd.read_file(BOUNDARIES_PATH)

    # CHECK 1: Dateiexistenz
    print("CHECK 1: File Existence and Size")
    print("-" * 90)
    all_exist = True
    files_info = {}

    for city in CITIES:
        dom_path = CHM_RAW_DIR / city.lower() / "dom_1m.tif"
        dgm_path = CHM_RAW_DIR / city.lower() / "dgm_1m.tif"

        for data_type, path in [("DOM", dom_path), ("DGM", dgm_path)]:
            name = f"{city} {data_type}"
            exists = path.exists()
            all_exist = all_exist and exists

            status = "✓" if exists else "✗"
            size_mb = path.stat().st_size / (1024**2) if exists else 0

            try:
                rel_path = path.relative_to(Path.cwd())
            except ValueError:
                rel_path = path
            print(f"  {status} {name:15} {size_mb:8.1f} MB  {rel_path}")
            files_info[name] = (path, exists)

    print()

    # CHECK 2: CRS Validierung
    print("CHECK 2: CRS Validation (Target: EPSG:25832)")
    print("-" * 90)
    for city in CITIES:
        for data_type in ["DOM", "DGM"]:
            path = CHM_RAW_DIR / city.lower() / f"{data_type.lower()}_1m.tif"

            if not path.exists():
                print(f"  ✗ {city} {data_type:3} - File not found")
                continue

            with rasterio.open(path) as src:
                crs_match = str(src.crs) == TARGET_CRS
                status = "✓" if crs_match else "✗"
                crs_str = f"{src.crs}" if crs_match else f"✗ {src.crs} (expected {TARGET_CRS})"

                print(f"  {status} {city:10} {data_type:3}  {crs_str:25}  {src.width}x{src.height} pixels")

    print()

    # CHECK 3: Pixelgröße (1m Auflösung)
    print("CHECK 3: Pixel Size (Expected: 1.0m)")
    print("-" * 90)
    for city in CITIES:
        for data_type in ["DOM", "DGM"]:
            path = CHM_RAW_DIR / city.lower() / f"{data_type.lower()}_1m.tif"

            if not path.exists():
                continue

            with rasterio.open(path) as src:
                # Pixelgröße aus Transform
                pixel_size = abs(src.transform.a)  # X-Pixelgröße
                pixel_size_y = abs(src.transform.e)  # Y-Pixelgröße

                is_1m = abs(pixel_size - ELEVATION_RESOLUTION_M) < 0.01
                is_1m_y = abs(pixel_size_y - ELEVATION_RESOLUTION_M) < 0.01

                status = "✓" if (is_1m and is_1m_y) else "⚠️"

                print(f"  {status} {city:10} {data_type:3}  X={pixel_size:.4f}m  Y={pixel_size_y:.4f}m")

    print()

    # CHECK 4: Datenbereich und Statistiken (innerhalb Stadtgrenzen)
    print("CHECK 4: Data Range and Statistics (within city boundaries)")
    print("-" * 90)
    for city in CITIES:
        city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]
        
        for data_type in ["DOM", "DGM"]:
            path = CHM_RAW_DIR / city.lower() / f"{data_type.lower()}_1m.tif"

            if not path.exists():
                continue

            with rasterio.open(path) as src:
                data = src.read(1)
                nodata = src.nodata
                
                # Maske für Pixel innerhalb der Stadtgrenze
                inside_mask = ~geometry_mask(
                    [city_geom], out_shape=data.shape, transform=src.transform
                )
                
                # NoData zu NaN konvertieren
                if nodata is not None:
                    data = np.where(np.isclose(data, nodata), np.nan, data).astype(np.float32)
                
                # Nur Pixel innerhalb der Stadtgrenze
                data_inside = data[inside_mask]
                valid_values = data_inside[~np.isnan(data_inside)]

                if len(valid_values) == 0:
                    print(f"  ✗ {city} {data_type:3} - No valid data")
                    continue

                # Statistiken
                min_val = float(np.min(valid_values))
                max_val = float(np.max(valid_values))
                mean_val = float(np.mean(valid_values))
                std_val = float(np.std(valid_values))
                median_val = float(np.median(valid_values))

                # Überprüfe auf negative Werte (sollte nicht vorkommen)
                negative_count = int(np.sum(valid_values < 0))
                has_negative = negative_count > 0
                neg_status = f"⚠️ {negative_count:,} NEGATIVES" if has_negative else "✓"

                print(f"  {neg_status}")
                print(f"    {city} {data_type:3}:")
                print(f"      Range:  {min_val:7.2f}m to {max_val:7.2f}m")
                print(f"      Mean:   {mean_val:7.2f}m  Median: {median_val:7.2f}m  (±{std_val:.2f}m)")

    print()

    # CHECK 5: NoData-Behandlung (innerhalb Stadtgrenzen)
    print("CHECK 5: NoData Handling (within city boundaries)")
    print("-" * 90)
    for city in CITIES:
        city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]

        for data_type in ["DOM", "DGM"]:
            path = CHM_RAW_DIR / city.lower() / f"{data_type.lower()}_1m.tif"

            if not path.exists():
                continue

            with rasterio.open(path) as src:
                nodata = src.nodata
                data = src.read(1)

                # Maske für Pixel innerhalb der Stadtgrenze
                inside_mask = ~geometry_mask(
                    [city_geom], out_shape=data.shape, transform=src.transform
                )
                pixels_inside = inside_mask.sum()

                # NoData-Pixel identifizieren
                if nodata is not None:
                    is_nodata = np.isclose(data, nodata)
                else:
                    is_nodata = np.zeros_like(data, dtype=bool)

                valid_inside = np.sum(inside_mask & ~is_nodata)
                valid_pct = (valid_inside / pixels_inside * 100) if pixels_inside > 0 else 0

                status = "✓" if valid_pct > 90 else "⚠️" if valid_pct > 50 else "✗"

                print(
                    f"  {status} {city:10} {data_type:3}  NoData={nodata}  "
                    f"Valid: {valid_pct:.1f}% ({valid_inside:,}/{pixels_inside:,})"
                )

    print()

    # CHECK 6: DOM > DGM Sanity Check (innerhalb Stadtgrenzen)
    print("CHECK 6: DOM >= DGM Sanity Check (within city boundaries)")
    print("-" * 90)
    for city in CITIES:
        city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]
        dom_path = CHM_RAW_DIR / city.lower() / "dom_1m.tif"
        dgm_path = CHM_RAW_DIR / city.lower() / "dgm_1m.tif"

        if not (dom_path.exists() and dgm_path.exists()):
            print(f"  ✗ {city:10} - Files not found")
            continue

        with rasterio.open(dom_path) as dom_src, rasterio.open(dgm_path) as dgm_src:
            dom_data = dom_src.read(1)
            dgm_data = dgm_src.read(1)
            dom_nodata = dom_src.nodata
            dgm_nodata = dgm_src.nodata
            
            # Maske für Pixel innerhalb der Stadtgrenze
            inside_mask = ~geometry_mask(
                [city_geom], out_shape=dom_data.shape, transform=dom_src.transform
            )
            
            # NoData zu NaN konvertieren
            if dom_nodata is not None:
                dom_data = np.where(np.isclose(dom_data, dom_nodata), np.nan, dom_data).astype(np.float32)
            if dgm_nodata is not None:
                dgm_data = np.where(np.isclose(dgm_data, dgm_nodata), np.nan, dgm_data).astype(np.float32)

            # Vergleich nur wo beide gültig UND innerhalb Stadtgrenze
            valid_mask = inside_mask & (~np.isnan(dom_data)) & (~np.isnan(dgm_data))
            valid_count = valid_mask.sum()

            if valid_count > 0:
                diff = dom_data[valid_mask] - dgm_data[valid_mask]

                # DOM sollte >= DGM sein (DOM hat Vegetation/Gebäude)
                dom_lt_dgm_count = int(np.sum(diff < -0.1))  # -0.1m Toleranz
                dom_gte_dgm_pct = (valid_count - dom_lt_dgm_count) / valid_count * 100
                mean_diff = float(np.mean(diff))
                
                # Zusätzliche Statistiken für negative Differenzen
                if dom_lt_dgm_count > 0:
                    neg_diff = diff[diff < -0.1]
                    min_neg_diff = float(np.min(neg_diff))
                    mean_neg_diff = float(np.mean(neg_diff))

                status = "✓" if dom_gte_dgm_pct > 95 else "⚠️" if dom_gte_dgm_pct > 80 else "✗"

                print(f"  {status} {city:10}  DOM-DGM mean={mean_diff:6.2f}m  "
                      f"({dom_gte_dgm_pct:.1f}% DOM >= DGM)")
                if dom_lt_dgm_count > 0:
                    print(f"      → {dom_lt_dgm_count:,} pixels where DOM < DGM "
                          f"(min diff: {min_neg_diff:.2f}m, mean: {mean_neg_diff:.2f}m)")
            else:
                print(f"  ✗ {city:10}  No valid overlapping pixels")

    print()

    # CHECK 7: Datenabdeckung (innerhalb Stadtgrenzen)
    print("CHECK 7: Data Coverage (within city boundaries, no buffer)")
    print("-" * 90)
    coverage_stats = {}

    for city in CITIES:
        print(f"  {city}:")
        city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]
        total_valid = 0
        pixels_inside_total = 0

        for data_type in ["DOM", "DGM"]:
            path = CHM_RAW_DIR / city.lower() / f"{data_type.lower()}_1m.tif"

            if not path.exists():
                continue

            with rasterio.open(path) as src:
                data = src.read(1)
                nodata = src.nodata

                # Maske für Pixel innerhalb der Stadtgrenze
                inside_mask = ~geometry_mask(
                    [city_geom], out_shape=data.shape, transform=src.transform
                )
                pixels_inside = inside_mask.sum()

                # NoData-Pixel identifizieren
                if nodata is not None:
                    is_nodata = np.isclose(data, nodata)
                else:
                    is_nodata = np.zeros_like(data, dtype=bool)

                valid_inside = np.sum(inside_mask & ~is_nodata)
                coverage_pct = (valid_inside / pixels_inside * 100) if pixels_inside > 0 else 0

                status = "✓" if coverage_pct > 90 else "⚠️" if coverage_pct > 50 else "✗"

                print(
                    f"    {status} {data_type:3}  {valid_inside:,} / {pixels_inside:,} "
                    f"pixels ({coverage_pct:.1f}%)"
                )

                total_valid += valid_inside
                pixels_inside_total += pixels_inside

        if pixels_inside_total > 0:
            avg_coverage = total_valid / pixels_inside_total * 100
            coverage_stats[city] = avg_coverage

    print()

    # Zusammenfassung
    print("=" * 90)
    print("VALIDATION SUMMARY")
    print("=" * 90)

    if all_exist:
        print("✓ All 6 files exist")
    else:
        print("✗ Some files missing")

    print()
    print("Data Quality:")
    for city, coverage in coverage_stats.items():
        status = "✓ GOOD" if coverage > 90 else "⚠️ WARNING" if coverage > 70 else "✗ POOR"
        print(f"  {status} {city:10} - Average coverage: {coverage:.1f}%")

    print()
    print("=" * 90)


if __name__ == "__main__":
    validate_elevation_files()
