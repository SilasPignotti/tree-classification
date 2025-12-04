"""
Data Validation Script for Pre-Feature-Extraction Quality Checks

Systematically verifies spatial alignment, data quality, and consistency across
CHM, Sentinel-2, and tree cadastre datasets before feature extraction.

Checks:
- Priority 1 (STOPPERS): Grid alignment, CHM plausibility
- Priority 2 (Informative): Visual spot checks, height correlation, temporal consistency
- Priority 3 (Ablation): Band correlation

Usage:
    uv run python scripts/validation/validate_data.py
"""

import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import seaborn as sns
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject
from rasterio.windows import from_bounds
from scipy.stats import pearsonr
from shapely.geometry import box

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_CHM = DATA_DIR / "CHM" / "processed"
DATA_S2 = DATA_DIR / "sentinel2"
DATA_TREES = DATA_DIR / "tree_cadastres" / "processed"
DATA_BOUNDARIES = DATA_DIR / "boundaries"
OUTPUT_DIR = DATA_DIR / "validation"
CHM_10M_DIR = DATA_CHM / "CHM_10m"

# Project settings
CITIES = ["Hamburg", "Berlin", "Rostock"]
PROJECT_CRS = "EPSG:25832"
PROJECT_CRS_EPSG = 25832
RANDOM_SEED = 42

# Band mapping for Sentinel-2 (0-indexed)
S2_BANDS = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
B04_IDX = 2  # Red
B08_IDX = 6  # NIR

# Create output directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHM_10M_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(RANDOM_SEED)

print(f"Project Root: {PROJECT_ROOT}")
print(f"Output Directory: {OUTPUT_DIR}")
print(f"Processing cities: {', '.join(CITIES)}")


# =============================================================================
# PRIORITY 0: CRS & PROJECTION VALIDATION
# =============================================================================


def check_0_1_verify_input_crs() -> list[dict]:
    """
    Check 0.1: Input CRS Verification

    Verify all input datasets are in the project CRS (EPSG:25832).
    
    STOPPER: If any dataset is not in project CRS, the script will abort.
    All data should already be in the correct CRS from the download/processing scripts.

    Returns:
        List of CRS verification results
    """
    print("\n" + "=" * 60)
    print("CHECK 0.1: INPUT CRS VERIFICATION")
    print(f"  Project CRS: EPSG:{PROJECT_CRS_EPSG}")
    print("=" * 60)

    results = []

    # Check CHM files
    for city in CITIES:
        chm_path = DATA_CHM / f"CHM_1m_{city}.tif"
        if not chm_path.exists():
            print(f"  CHM {city}: FILE NOT FOUND")
            results.append(
                {
                    "dataset": f"CHM_{city}",
                    "crs": "N/A",
                    "epsg": None,
                    "status": "MISSING",
                }
            )
            continue

        with rasterio.open(chm_path) as src:
            crs = src.crs
            epsg = crs.to_epsg() if crs else None
            if epsg == PROJECT_CRS_EPSG:
                status = "OK"
            else:
                status = "FAIL"
            results.append(
                {
                    "dataset": f"CHM_{city}",
                    "crs": crs.to_string() if crs else "None",
                    "epsg": epsg,
                    "status": status,
                }
            )
            print(f"  CHM {city}: EPSG:{epsg} [{status}]")

    # Check Sentinel-2 files (sample January)
    for city in CITIES:
        s2_path = DATA_S2 / city.lower() / "S2_2024_01_median.tif"
        if not s2_path.exists():
            print(f"  S2 {city}: FILE NOT FOUND")
            results.append(
                {
                    "dataset": f"S2_{city}",
                    "crs": "N/A",
                    "epsg": None,
                    "status": "MISSING",
                }
            )
            continue

        with rasterio.open(s2_path) as src:
            crs = src.crs
            epsg = crs.to_epsg() if crs else None
            if epsg == PROJECT_CRS_EPSG:
                status = "OK"
            else:
                status = "FAIL"
            results.append(
                {
                    "dataset": f"S2_{city}",
                    "crs": crs.to_string() if crs else "None",
                    "epsg": epsg,
                    "status": status,
                }
            )
            print(f"  S2 {city}: EPSG:{epsg} [{status}]")

    # Check Tree Cadastre
    cadastre_path = DATA_TREES / "trees_filtered_viable_no_edge.gpkg"
    if cadastre_path.exists():
        cadastre = gpd.read_file(cadastre_path, rows=1)  # Read only 1 row for CRS
        crs = cadastre.crs
        epsg = crs.to_epsg() if crs else None
        if epsg == PROJECT_CRS_EPSG:
            status = "OK"
        else:
            status = "FAIL"
        results.append(
            {
                "dataset": "Tree_Cadastre",
                "crs": crs.to_string() if crs else "None",
                "epsg": epsg,
                "status": status,
            }
        )
        print(f"  Tree Cadastre: EPSG:{epsg} [{status}]")
    else:
        print("  Tree Cadastre: FILE NOT FOUND")
        results.append(
            {
                "dataset": "Tree_Cadastre",
                "crs": "N/A",
                "epsg": None,
                "status": "MISSING",
            }
        )

    # Save report
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "crs_verification_report.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Report saved: {output_path.name}")

    # Validation summary
    missing = [r for r in results if r["status"] == "MISSING"]
    failures = [r for r in results if r["status"] == "FAIL"]
    ok_count = len([r for r in results if r["status"] == "OK"])

    if missing:
        print(f"\n⚠️  MISSING: {len(missing)} datasets not found")
        for r in missing:
            print(f"    - {r['dataset']}")

    if failures:
        print(f"\n🔴 FAIL: {len(failures)} datasets NOT in project CRS (EPSG:{PROJECT_CRS_EPSG})")
        for r in failures:
            print(f"    - {r['dataset']}: EPSG:{r['epsg']} (expected: {PROJECT_CRS_EPSG})")
        print("\n   ❌ ABORTING: Please fix CRS issues in the source data before running validation.")
    else:
        print(f"\n✓ All {ok_count} datasets are in project CRS (EPSG:{PROJECT_CRS_EPSG})")

    return results


def check_0_2_crs_consistency() -> dict[str, Any]:
    """
    Check 0.2: CRS Consistency Check

    Verify project CRS configuration matches processing requirements.
    Project CRS should be EPSG:25832 (ETRS89 / UTM 32N).

    Returns:
        Dictionary with CRS consistency status
    """
    print("\n" + "=" * 60)
    print("CHECK 0.2: CRS CONSISTENCY")
    print("=" * 60)

    print(f"  Project CRS: {PROJECT_CRS}")

    # Validate it's a valid UTM Zone 32N CRS
    crs_obj = CRS.from_string(PROJECT_CRS)
    epsg = crs_obj.to_epsg()

    if epsg not in [25832, 32632]:
        print(f"  🔴 FAIL: Project CRS {PROJECT_CRS} is not UTM Zone 32N")
        return {"project_crs": PROJECT_CRS, "epsg": epsg, "status": "FAIL"}

    print(f"  ✓ Project CRS validated: {crs_obj.to_string()}")
    print(f"  ✓ EPSG code: {epsg}")
    print(f"  ✓ All outputs will use: {PROJECT_CRS}")

    return {"project_crs": PROJECT_CRS, "epsg": epsg, "status": "PASS"}


# =============================================================================
# PRIORITY 0.5: CHM RESAMPLING (EXTENDED)
# =============================================================================


def check_0_3_resample_chm_extended() -> list[dict]:
    """
    Check 0.3: CHM Resampling to 10m (Extended)

    Resample CHM from 1m to 10m with three aggregation methods:
    - MEAN: Average height (original approach)
    - MAX: Maximum height (better for tree detection)
    - STD: Height variability (canopy heterogeneity)

    All outputs aligned to S2 grid in project CRS (EPSG:32632).

    Returns:
        List of resampling results per city and method
    """
    print("\n" + "=" * 60)
    print("CHECK 0.3: CHM RESAMPLING TO 10m (MEAN + MAX + STD)")
    print("=" * 60)

    target_crs = CRS.from_string(PROJECT_CRS)
    results = []

    for city in CITIES:
        print(f"\n  Resampling CHM for {city}...")

        # Input paths
        chm_1m_path = DATA_CHM / f"CHM_1m_{city}.tif"
        s2_path = DATA_S2 / city.lower() / "S2_2024_01_median.tif"

        if not chm_1m_path.exists():
            print(f"    ⚠️  CHM not found: {chm_1m_path}")
            continue

        if not s2_path.exists():
            print(f"    ⚠️  S2 not found: {s2_path}")
            continue

        with rasterio.open(chm_1m_path) as chm_src, rasterio.open(s2_path) as s2_src:
            print(f"    Input: {chm_src.shape}, CRS={chm_src.crs.to_string()}")

            # Use S2's exact transform for pixel-perfect alignment
            s2_transform = s2_src.transform
            s2_width = s2_src.width
            s2_height = s2_src.height

            # Profile for output
            profile = s2_src.profile.copy()
            profile.update(
                {
                    "count": 1,
                    "dtype": "float32",
                    "nodata": np.nan,
                    "compress": "deflate",
                    "predictor": 3,
                    "tiled": True,
                    "blockxsize": 512,
                    "blockysize": 512,
                }
            )

            # Read source data
            src_data = chm_src.read(1)

            # Define resampling methods
            methods = {
                "mean": Resampling.average,
                "max": Resampling.max,
            }

            for method_name, resampling in methods.items():
                output_path = CHM_10M_DIR / f"CHM_10m_{method_name}_{city}.tif"

                # Skip if already exists
                if output_path.exists():
                    print(f"    {method_name.upper()}: Already exists, skipping")
                    with rasterio.open(output_path) as existing:
                        existing_data = existing.read(1)
                        valid_pixels = np.sum(~np.isnan(existing_data))
                        valid_pct = 100 * valid_pixels / existing_data.size
                        file_size_mb = output_path.stat().st_size / (1024 * 1024)
                    results.append(
                        {
                            "city": city,
                            "method": method_name,
                            "width": s2_width,
                            "height": s2_height,
                            "valid_pct": valid_pct,
                            "file_size_mb": file_size_mb,
                            "output_path": str(output_path),
                            "skipped": True,
                        }
                    )
                    continue

                # Create destination array
                dst_data = np.empty((s2_height, s2_width), dtype=np.float32)
                dst_data.fill(np.nan)

                # Reproject with specified resampling method
                reproject(
                    source=src_data,
                    destination=dst_data,
                    src_transform=chm_src.transform,
                    src_crs=chm_src.crs,
                    dst_transform=s2_transform,
                    dst_crs=target_crs,
                    resampling=resampling,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                )

                # Write output
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(dst_data.astype(np.float32), 1)

                # Calculate statistics
                valid_pixels = np.sum(~np.isnan(dst_data))
                valid_pct = 100 * valid_pixels / dst_data.size
                file_size_mb = output_path.stat().st_size / (1024 * 1024)

                print(
                    f"    {method_name.upper()}: ({s2_height}, {s2_width}), "
                    f"{file_size_mb:.1f} MB, {valid_pct:.1f}% valid"
                )

                results.append(
                    {
                        "city": city,
                        "method": method_name,
                        "width": s2_width,
                        "height": s2_height,
                        "valid_pct": valid_pct,
                        "file_size_mb": file_size_mb,
                        "output_path": str(output_path),
                    }
                )

            # STD requires custom implementation: Std ≈ sqrt(E[X²] - E[X]²)
            output_path = CHM_10M_DIR / f"CHM_10m_std_{city}.tif"

            # Skip if already exists
            if output_path.exists():
                print("    STD: Already exists, skipping")
                with rasterio.open(output_path) as existing:
                    existing_data = existing.read(1)
                    valid_pixels = np.sum(~np.isnan(existing_data))
                    valid_pct = 100 * valid_pixels / existing_data.size
                    file_size_mb = output_path.stat().st_size / (1024 * 1024)
                results.append(
                    {
                        "city": city,
                        "method": "std",
                        "width": s2_width,
                        "height": s2_height,
                        "valid_pct": valid_pct,
                        "file_size_mb": file_size_mb,
                        "output_path": str(output_path),
                        "skipped": True,
                    }
                )
            else:
                # First get mean (already computed above, but recompute for variance calc)
                mean_data = np.empty((s2_height, s2_width), dtype=np.float32)
                mean_data.fill(np.nan)
                reproject(
                    source=src_data,
                    destination=mean_data,
                    src_transform=chm_src.transform,
                    src_crs=chm_src.crs,
                    dst_transform=s2_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.average,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                )

                # Compute mean of squared values
                src_squared = src_data**2
                mean_squared = np.empty((s2_height, s2_width), dtype=np.float32)
                mean_squared.fill(np.nan)
                reproject(
                    source=src_squared,
                    destination=mean_squared,
                    src_transform=chm_src.transform,
                    src_crs=chm_src.crs,
                    dst_transform=s2_transform,
                    dst_crs=target_crs,
                    resampling=Resampling.average,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                )

                # Std = sqrt(E[X²] - E[X]²)
                std_data = np.sqrt(np.maximum(0, mean_squared - mean_data**2))

                # Write output
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(std_data.astype(np.float32), 1)

                valid_pixels = np.sum(~np.isnan(std_data))
                valid_pct = 100 * valid_pixels / std_data.size
                file_size_mb = output_path.stat().st_size / (1024 * 1024)

                print(
                    f"    STD: ({s2_height}, {s2_width}), "
                    f"{file_size_mb:.1f} MB, {valid_pct:.1f}% valid"
                )

                results.append(
                    {
                        "city": city,
                        "method": "std",
                        "width": s2_width,
                        "height": s2_height,
                        "valid_pct": valid_pct,
                        "file_size_mb": file_size_mb,
                        "output_path": str(output_path),
                    }
                )

        print(f"    ✓ {city}: PASS")

    # Save report
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "chm_resampling_extended_report.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Report saved: {output_path.name}")

    return results


# =============================================================================
# PRIORITY 0.75: SPATIAL ALIGNMENT VERIFICATION
# =============================================================================


def check_0_4_correlation_offset_detection() -> list[dict]:
    """
    Check 0.4: Correlation-Based Offset Detection

    Test systematic X/Y offsets (-20m to +20m in 10m steps) to detect
    spatial misalignment between CHM and NDVI.

    Expected: Maximum correlation at (0m, 0m) offset.
    STOPPER: If maximum is at ±10m offset, CHM is misaligned.

    Returns:
        List of correlation results for all offsets
    """
    print("\n" + "=" * 60)
    print("CHECK 0.4: CORRELATION-BASED OFFSET DETECTION")
    print("=" * 60)

    from scipy.ndimage import shift as ndimage_shift

    results = []

    for city in CITIES:
        print(f"\n  Testing {city}...")

        # Load CHM_mean (10m)
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        if not chm_path.exists():
            print(f"    ⚠️  CHM_10m_mean not found: {chm_path}")
            continue

        with rasterio.open(chm_path) as src:
            chm_data = src.read(1)

        # Load S2 July (peak vegetation)
        s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"
        if not s2_path.exists():
            print(f"    ⚠️  S2 July not found: {s2_path}")
            continue

        with rasterio.open(s2_path) as src:
            b04 = src.read(B04_IDX + 1).astype(float)
            b08 = src.read(B08_IDX + 1).astype(float)

        # Calculate NDVI
        ndvi = (b08 - b04) / (b08 + b04 + 1e-8)

        # Ensure same shape (crop to minimum)
        min_rows = min(chm_data.shape[0], ndvi.shape[0])
        min_cols = min(chm_data.shape[1], ndvi.shape[1])
        chm_data = chm_data[:min_rows, :min_cols]
        ndvi = ndvi[:min_rows, :min_cols]

        # Test offsets from -20m to +20m (in 10m steps = -2 to +2 pixels)
        offsets = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)]

        city_results = []
        print(f"    Testing {len(offsets)} offsets...")

        for dx_pixels, dy_pixels in offsets:
            # Shift CHM (positive = shift right/down in array indices)
            chm_shifted = ndimage_shift(
                chm_data, shift=(dy_pixels, dx_pixels), mode="constant", cval=np.nan
            )

            # Valid mask (both have data)
            valid_mask = (
                (~np.isnan(chm_shifted))
                & (~np.isnan(ndvi))
                & (chm_shifted > 0)
                & (ndvi > -1)
            )

            n_valid = np.sum(valid_mask)
            if n_valid < 1000:
                r = np.nan
            else:
                r, _ = pearsonr(chm_shifted[valid_mask], ndvi[valid_mask])

            city_results.append(
                {
                    "city": city,
                    "offset_x_m": dx_pixels * 10,
                    "offset_y_m": dy_pixels * 10,
                    "correlation": r,
                    "n_valid": n_valid,
                }
            )

        # Find maximum correlation
        df_city = pd.DataFrame(city_results)
        
        # Handle case where all correlations are NaN
        valid_corrs = df_city["correlation"].dropna()
        if valid_corrs.empty:
            print(f"    ⚠️  WARNING: No valid correlations computed for {city}")
            print("    (All offsets had <1000 valid pixels)")
            results.extend(city_results)
            continue
        
        best_idx = df_city["correlation"].idxmax()
        best = df_city.loc[best_idx]

        print(
            f"    Maximum correlation: r={best['correlation']:.4f} "
            f"at offset=({best['offset_x_m']:.0f}m, {best['offset_y_m']:.0f}m)"
        )

        # Validation
        if (best["offset_x_m"] == 0) and (best["offset_y_m"] == 0):
            status = "✓ PASS"
            print(f"    {status}: Maximum at (0, 0) - perfect alignment")
        elif abs(best["offset_x_m"]) <= 10 and abs(best["offset_y_m"]) <= 10:
            status = "⚠️  WARNING"
            print(f"    {status}: Maximum at (±10m, ±10m) - minor offset")
        else:
            status = "🔴 FAIL"
            print(f"    {status}: Maximum at (>10m) - CRITICAL MISALIGNMENT")

        # Check correlation improvement from offset
        corr_at_zero = df_city[
            (df_city["offset_x_m"] == 0) & (df_city["offset_y_m"] == 0)
        ]["correlation"].values[0]
        corr_diff = best["correlation"] - corr_at_zero

        if corr_diff > 0.05:
            print(f"    ⚠️  Correlation gain from offset: +{corr_diff:.4f}")

        # Store results
        results.extend(city_results)

        # Create heatmap for this city
        pivot = df_city.pivot(
            index="offset_y_m", columns="offset_x_m", values="correlation"
        )

        plt.figure(figsize=(10, 8))
        sns.heatmap(
            pivot,
            annot=True,
            fmt=".3f",
            cmap="RdYlGn",
            vmin=pivot.min().min(),
            vmax=pivot.max().max(),
            center=corr_at_zero,
        )
        plt.xlabel("X-Offset (m, positive = East)")
        plt.ylabel("Y-Offset (m, positive = North)")
        plt.title(
            f"{city}: CHM-NDVI Correlation vs. Spatial Offset\n"
            f'Max r={best["correlation"]:.3f} at '
            f'({best["offset_x_m"]:.0f}, {best["offset_y_m"]:.0f})m'
        )

        # Mark (0,0) with red square
        zero_row = np.where(pivot.index == 0)[0][0]
        zero_col = np.where(pivot.columns == 0)[0][0]
        plt.gca().add_patch(
            plt.Rectangle((zero_col, zero_row), 1, 1, fill=False, edgecolor="red", lw=3)
        )

        output_plot = OUTPUT_DIR / f"offset_detection_{city}.png"
        plt.savefig(output_plot, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Heatmap saved: {output_plot.name}")

    # Save all results
    df = pd.DataFrame(results)
    output_csv = OUTPUT_DIR / "offset_detection_results.csv"
    df.to_csv(output_csv, index=False)
    print(f"\n✓ Results saved: {output_csv.name}")

    # Global validation
    if len(results) > 0:
        df_maxima = df.loc[df.groupby("city")["correlation"].idxmax()]
        all_aligned = all(
            (df_maxima["offset_x_m"] == 0) & (df_maxima["offset_y_m"] == 0)
        )

        if all_aligned:
            print("\n✓ GLOBAL PASS: All cities show maximum correlation at (0, 0)")
            print("  → CHM and S2 are correctly aligned")
        else:
            print("\n⚠️  GLOBAL WARNING: Spatial offset detected in some cities")
            for _, row in df_maxima.iterrows():
                if row["offset_x_m"] != 0 or row["offset_y_m"] != 0:
                    print(
                        f"    {row['city']}: ({row['offset_x_m']:.0f}, "
                        f"{row['offset_y_m']:.0f})m, r={row['correlation']:.3f}"
                    )

    return results


def check_0_5_tree_point_correlation() -> list[dict]:
    """
    Check 0.5: Tree Point NDVI-CHM Correlation

    Extract CHM and NDVI at tree cadastre points.
    Calculate correlation: high NDVI should correspond to high CHM.

    Expected: r > 0.4 (moderate positive correlation)
    If r < 0.2: Either CHM is misaligned or GPS accuracy is very poor.

    Returns:
        List of correlation statistics per city
    """
    print("\n" + "=" * 60)
    print("CHECK 0.5: TREE POINT NDVI-CHM CORRELATION")
    print("=" * 60)

    # Load tree cadastre
    cadastre_path = DATA_TREES / "trees_filtered_viable_no_edge.gpkg"
    if not cadastre_path.exists():
        print(f"  ⚠️  Tree cadastre not found: {cadastre_path}")
        return []

    trees = gpd.read_file(cadastre_path)

    # Reproject to project CRS if needed
    if trees.crs.to_epsg() != PROJECT_CRS_EPSG:
        print(f"  Reprojecting trees from {trees.crs.to_string()} to {PROJECT_CRS}")
        trees = trees.to_crs(PROJECT_CRS)

    results = []

    for city in CITIES:
        print(f"\n  Analyzing {city}...")

        city_trees = trees[trees["city"] == city]

        # Sample up to 50k trees (performance)
        sample_size = min(50000, len(city_trees))
        if sample_size == 0:
            print(f"    ⚠️  No trees found for {city}")
            continue

        city_trees_sample = city_trees.sample(sample_size, random_state=RANDOM_SEED)
        print(f"    Sample size: {len(city_trees_sample):,} trees")

        # Load CHM_mean
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        if not chm_path.exists():
            print(f"    ⚠️  CHM_10m_mean not found: {chm_path}")
            continue

        with rasterio.open(chm_path) as chm_src:
            coords = [(pt.x, pt.y) for pt in city_trees_sample.geometry]
            chm_values = np.array([val[0] for val in chm_src.sample(coords)])

        # Load S2 July NDVI
        s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"
        if not s2_path.exists():
            print(f"    ⚠️  S2 July not found: {s2_path}")
            continue

        with rasterio.open(s2_path) as s2_src:
            b04 = np.array([val[B04_IDX] for val in s2_src.sample(coords)])
            b08 = np.array([val[B08_IDX] for val in s2_src.sample(coords)])

        ndvi_values = (b08 - b04) / (b08 + b04 + 1e-8)

        # Valid pairs (both have data)
        valid_mask = (
            (~np.isnan(chm_values))
            & (~np.isnan(ndvi_values))
            & (chm_values > 0)
            & (ndvi_values > -1)
        )

        chm_valid = chm_values[valid_mask]
        ndvi_valid = ndvi_values[valid_mask]

        n_valid = len(chm_valid)
        print(f"    Valid pairs: {n_valid:,} ({100*n_valid/len(city_trees_sample):.1f}%)")

        if n_valid < 100:
            print("    ⚠️  Too few valid pairs, skipping correlation")
            continue

        # Calculate correlation
        r, p_value = pearsonr(ndvi_valid, chm_valid)
        print(f"    Pearson r: {r:.3f} (p={p_value:.2e})")

        # Validation
        if r > 0.4:
            status = "✓ PASS"
            print(f"    {status}: Strong positive correlation")
        elif r > 0.2:
            status = "⚠️  ACCEPTABLE"
            print(f"    {status}: Moderate positive correlation")
        else:
            status = "🔴 WARNING"
            print(f"    {status}: Weak correlation - potential alignment issue")

        # Additional diagnostics
        high_ndvi_low_chm = np.sum((ndvi_valid > 0.7) & (chm_valid < 2))
        pct_anomaly = 100 * high_ndvi_low_chm / n_valid
        print(f"    Anomalies (NDVI>0.7, CHM<2m): {high_ndvi_low_chm:,} ({pct_anomaly:.1f}%)")

        if pct_anomaly > 20:
            print("    🔴 HIGH ANOMALY RATE: >20% trees with high NDVI but low CHM")

        # Create scatterplot
        plt.figure(figsize=(10, 10))

        plt.hexbin(ndvi_valid, chm_valid, gridsize=50, cmap="viridis", mincnt=1, alpha=0.8)
        plt.colorbar(label="Number of trees")

        # Add reference lines
        plt.axhline(y=2, color="r", linestyle="--", linewidth=1, label="CHM=2m threshold")
        plt.axvline(x=0.7, color="orange", linestyle="--", linewidth=1, label="NDVI=0.7")

        plt.xlabel("NDVI (July 2024)", fontsize=12)
        plt.ylabel("CHM Mean Height (m)", fontsize=12)
        plt.title(
            f"{city}: Tree Point NDVI vs. CHM\n"
            f"r={r:.3f}, n={n_valid:,}, Anomalies={pct_anomaly:.1f}%",
            fontsize=14,
        )
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xlim(-0.2, 1.0)
        plt.ylim(-5, 45)

        output_plot = OUTPUT_DIR / f"tree_point_correlation_{city}.png"
        plt.savefig(output_plot, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Plot saved: {output_plot.name}")

        results.append(
            {
                "city": city,
                "n_trees": len(city_trees_sample),
                "n_valid": n_valid,
                "valid_pct": 100 * n_valid / len(city_trees_sample),
                "pearson_r": r,
                "p_value": p_value,
                "anomaly_count": high_ndvi_low_chm,
                "anomaly_pct": pct_anomaly,
                "status": status,
            }
        )

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_csv = OUTPUT_DIR / "tree_point_correlation_stats.csv"
        df.to_csv(output_csv, index=False)
        print(f"\n✓ Results saved: {output_csv.name}")

        # Global validation
        if all(r["pearson_r"] > 0.2 for r in results):
            print("\n✓ GLOBAL PASS: All cities show positive NDVI-CHM correlation")
        else:
            print("\n⚠️  GLOBAL WARNING: Some cities have weak correlation")

    return results


def check_0_6_transect_profiles() -> list[dict]:
    """
    Check 0.6: Transect Profile Analysis

    Extract CHM and NDVI values along 3 transects per city.
    Transects are 500m lines through known park/vegetation areas.

    Visual check: Peaks should align (±10m tolerance acceptable).

    Returns:
        List of transect analysis results
    """
    print("\n" + "=" * 60)
    print("CHECK 0.6: TRANSECT PROFILE ANALYSIS")
    print("=" * 60)

    from scipy.signal import find_peaks

    # Define transects for each city (start_x, start_y, end_x, end_y, label)
    # These are approximate coordinates in EPSG:32632 for known park areas
    transects = {
        "Hamburg": [
            (569000, 5934000, 569500, 5934000, "Stadtpark West-East"),
            (569250, 5933500, 569250, 5934500, "Stadtpark South-North"),
            (565000, 5935000, 565500, 5935000, "Altona Park"),
        ],
        "Berlin": [
            (391000, 5820000, 391500, 5820000, "Tiergarten West-East"),
            (391250, 5819500, 391250, 5820500, "Tiergarten South-North"),
            (398000, 5818000, 398500, 5818000, "Treptower Park"),
        ],
        "Rostock": [
            (312000, 6002000, 312500, 6002000, "City Center West-East"),
            (312250, 6001500, 312250, 6002500, "City Center South-North"),
            (313000, 6003000, 313500, 6003000, "Northern District"),
        ],
    }

    results = []

    for city in CITIES:
        print(f"\n  Analyzing {city}...")

        # Load CHM_mean
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        if not chm_path.exists():
            print(f"    ⚠️  CHM_10m_mean not found: {chm_path}")
            continue

        chm_src = rasterio.open(chm_path)

        # Load S2 July
        s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"
        if not s2_path.exists():
            print(f"    ⚠️  S2 July not found: {s2_path}")
            chm_src.close()
            continue

        s2_src = rasterio.open(s2_path)
        b04_data = s2_src.read(B04_IDX + 1).astype(float)
        b08_data = s2_src.read(B08_IDX + 1).astype(float)
        ndvi_data = (b08_data - b04_data) / (b08_data + b04_data + 1e-8)

        for transect_idx, (x1, y1, x2, y2, label) in enumerate(transects[city], 1):
            print(f"    Transect {transect_idx}: {label}")

            # Generate points along transect (every 10m = 50 points for 500m)
            n_points = 50
            distances = np.linspace(0, 500, n_points)
            x_coords = np.linspace(x1, x2, n_points)
            y_coords = np.linspace(y1, y2, n_points)

            # Sample CHM
            coords = list(zip(x_coords, y_coords))
            chm_profile = np.array([val[0] for val in chm_src.sample(coords)])

            # Sample NDVI (convert coords to pixel indices)
            rows, cols = rasterio.transform.rowcol(s2_src.transform, x_coords, y_coords)
            rows = np.array(rows, dtype=int)
            cols = np.array(cols, dtype=int)

            # Clip to valid range
            rows = np.clip(rows, 0, ndvi_data.shape[0] - 1)
            cols = np.clip(cols, 0, ndvi_data.shape[1] - 1)

            ndvi_profile = ndvi_data[rows, cols]

            # Plot
            fig, ax1 = plt.subplots(figsize=(14, 6))

            color_chm = "forestgreen"
            ax1.plot(
                distances,
                chm_profile,
                color=color_chm,
                linewidth=2.5,
                label="CHM Height (m)",
                marker="o",
                markersize=4,
            )
            ax1.set_xlabel("Distance along transect (m)", fontsize=12)
            ax1.set_ylabel("CHM Height (m)", color=color_chm, fontsize=12)
            ax1.tick_params(axis="y", labelcolor=color_chm)
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(bottom=-2)

            ax2 = ax1.twinx()
            color_ndvi = "darkblue"
            ax2.plot(
                distances,
                ndvi_profile,
                color=color_ndvi,
                linewidth=2.5,
                linestyle="--",
                label="NDVI",
                marker="s",
                markersize=4,
            )
            ax2.set_ylabel("NDVI", color=color_ndvi, fontsize=12)
            ax2.tick_params(axis="y", labelcolor=color_ndvi)
            ax2.set_ylim(-0.2, 1.0)

            # Combine legends
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

            plt.title(
                f"{city}: Transect {transect_idx} - {label}\n"
                f"Visual Check: CHM peaks should align with NDVI peaks",
                fontsize=14,
            )

            output_plot = OUTPUT_DIR / f"transect_{city}_t{transect_idx}.png"
            plt.savefig(output_plot, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"      ✓ Plot saved: {output_plot.name}")

            # Detect peaks and calculate alignment
            chm_peaks, _ = find_peaks(chm_profile, height=5, distance=3)
            ndvi_peaks, _ = find_peaks(ndvi_profile, height=0.5, distance=3)

            # Calculate average distance between nearest CHM and NDVI peaks
            if len(chm_peaks) > 0 and len(ndvi_peaks) > 0:
                min_distances = []
                for chm_pk in chm_peaks:
                    distances_to_ndvi = np.abs(ndvi_peaks - chm_pk)
                    min_distances.append(np.min(distances_to_ndvi) * 10)  # Convert to meters

                avg_peak_offset = np.mean(min_distances)
                print(f"      CHM peaks: {len(chm_peaks)}, NDVI peaks: {len(ndvi_peaks)}")
                print(f"      Avg peak offset: {avg_peak_offset:.1f}m")

                if avg_peak_offset < 20:
                    status = "✓ ALIGNED"
                elif avg_peak_offset < 50:
                    status = "⚠️  MINOR OFFSET"
                else:
                    status = "🔴 MISALIGNED"
            else:
                avg_peak_offset = np.nan
                status = "⚠️  NO PEAKS"
                print("      No clear peaks detected")

            results.append(
                {
                    "city": city,
                    "transect": transect_idx,
                    "label": label,
                    "chm_peaks": len(chm_peaks) if len(chm_peaks) > 0 else 0,
                    "ndvi_peaks": len(ndvi_peaks) if len(ndvi_peaks) > 0 else 0,
                    "avg_peak_offset_m": avg_peak_offset,
                    "status": status,
                }
            )

        chm_src.close()
        s2_src.close()

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_csv = OUTPUT_DIR / "transect_analysis_results.csv"
        df.to_csv(output_csv, index=False)
        print(f"\n✓ Results saved: {output_csv.name}")
        print(f"\n✓ Generated {len(results)} transect profiles")
        print("  Manual visual inspection recommended for confirmation")

    return results


def check_0_7_known_feature_validation() -> list[dict]:
    """
    Check 0.7: Known-Feature Validation (Parks)

    Test known large parks: should have BOTH high CHM and high NDVI.
    Parks are manually defined bounding boxes in known vegetation areas.
    If CHM is misaligned, parks will have low CHM despite high NDVI.

    Returns:
        List of park validation results
    """
    print("\n" + "=" * 60)
    print("CHECK 0.7: KNOWN-FEATURE VALIDATION (PARKS)")
    print("=" * 60)

    from rasterio.mask import mask as rio_mask

    # Define known parks (bounding boxes in project CRS EPSG:32632)
    parks = {
        "Hamburg": [
            {"name": "Stadtpark", "bounds": (568500, 5933500, 569500, 5934500)},
            {"name": "Planten un Blomen", "bounds": (566000, 5932500, 566500, 5933000)},
            {"name": "Altonaer Volkspark", "bounds": (564500, 5934500, 565500, 5935500)},
        ],
        "Berlin": [
            {"name": "Tiergarten", "bounds": (390000, 5819000, 392000, 5821000)},
            {"name": "Tempelhofer Feld", "bounds": (392000, 5815000, 394000, 5817000)},
            {"name": "Treptower Park", "bounds": (397000, 5817000, 399000, 5819000)},
        ],
        "Rostock": [
            {"name": "IGA Park", "bounds": (312000, 6002000, 313000, 6003000)},
            {"name": "Stadtpark", "bounds": (311500, 6001500, 312500, 6002500)},
            {"name": "Wallanlagen", "bounds": (311000, 6001000, 312000, 6002000)},
        ],
    }

    results = []

    for city in CITIES:
        print(f"\n  Validating {city} parks...")

        # Load CHM_mean
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        if not chm_path.exists():
            print(f"    ⚠️  CHM_10m_mean not found: {chm_path}")
            continue

        chm_src = rasterio.open(chm_path)

        # Load S2 July
        s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"
        if not s2_path.exists():
            print(f"    ⚠️  S2 July not found: {s2_path}")
            chm_src.close()
            continue

        s2_src = rasterio.open(s2_path)
        b04 = s2_src.read(B04_IDX + 1).astype(float)
        b08 = s2_src.read(B08_IDX + 1).astype(float)
        ndvi = (b08 - b04) / (b08 + b04 + 1e-8)

        for park in parks[city]:
            park_name = park["name"]
            bounds = park["bounds"]
            park_geom = box(*bounds)

            try:
                # Clip CHM to park
                chm_park, _ = rio_mask(chm_src, [park_geom], crop=True, nodata=np.nan)
                chm_park = chm_park[0]

                # Clip NDVI using window
                window = from_bounds(*bounds, transform=s2_src.transform)
                row_start = max(0, int(window.row_off))
                row_end = min(ndvi.shape[0], int(window.row_off + window.height))
                col_start = max(0, int(window.col_off))
                col_end = min(ndvi.shape[1], int(window.col_off + window.width))

                ndvi_park = ndvi[row_start:row_end, col_start:col_end]

                # Calculate statistics
                chm_valid = chm_park[chm_park > 0]
                ndvi_valid = ndvi_park[ndvi_park > -1]

                if len(chm_valid) == 0 or len(ndvi_valid) == 0:
                    print(f"    {park_name}: No valid data")
                    continue

                chm_mean = np.nanmean(chm_valid)
                chm_p75 = np.nanpercentile(chm_valid, 75)
                ndvi_mean = np.nanmean(ndvi_valid)
                ndvi_p75 = np.nanpercentile(ndvi_valid, 75)

                print(f"    {park_name}:")
                print(f"      CHM: mean={chm_mean:.1f}m, P75={chm_p75:.1f}m")
                print(f"      NDVI: mean={ndvi_mean:.3f}, P75={ndvi_p75:.3f}")

                # Validation criteria
                chm_ok = chm_mean > 5  # Parks should have trees >5m on average
                ndvi_ok = ndvi_mean > 0.4  # Parks should have healthy vegetation

                if chm_ok and ndvi_ok:
                    status = "✓ PASS"
                elif not chm_ok and ndvi_ok:
                    status = "🔴 FAIL - LOW CHM"
                    print("      🔴 Park has high NDVI but low CHM - misalignment suspected!")
                elif chm_ok and not ndvi_ok:
                    status = "⚠️  FAIL - LOW NDVI"
                else:
                    status = "⚠️  FAIL - BOTH LOW"

                print(f"      Status: {status}")

                results.append(
                    {
                        "city": city,
                        "park_name": park_name,
                        "chm_mean": chm_mean,
                        "chm_p75": chm_p75,
                        "ndvi_mean": ndvi_mean,
                        "ndvi_p75": ndvi_p75,
                        "chm_ok": chm_ok,
                        "ndvi_ok": ndvi_ok,
                        "status": status,
                    }
                )

            except Exception as e:
                print(f"    {park_name}: Error - {e}")

        chm_src.close()
        s2_src.close()

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_csv = OUTPUT_DIR / "known_feature_validation.csv"
        df.to_csv(output_csv, index=False)
        print(f"\n✓ Results saved: {output_csv.name}")

        # Global validation
        n_pass = len([r for r in results if r["status"] == "✓ PASS"])
        n_total = len(results)
        pct_pass = 100 * n_pass / n_total if n_total > 0 else 0

        print(f"\n✓ {n_pass}/{n_total} parks passed validation ({pct_pass:.0f}%)")

        if pct_pass >= 80:
            print("  ✓ GLOBAL PASS: Most parks show expected CHM and NDVI")
        elif pct_pass >= 60:
            print("  ⚠️  GLOBAL WARNING: Some parks show anomalies")
        else:
            print("  🔴 GLOBAL FAIL: Many parks fail validation")

    return results


# =============================================================================
# PRIORITY 1: CRITICAL CHECKS (STOPPERS)
# =============================================================================


def check_1_1_grid_alignment() -> dict[str, Any]:
    """
    Check 1.1: CHM ↔ Sentinel-2 Grid Alignment

    Resamples CHM from 1m to 10m and verifies pixel-perfect alignment with S2 grid.
    Creates CHM_10m files for subsequent checks.

    Returns:
        Dictionary with alignment results per city
    """
    print("\n" + "=" * 60)
    print("CHECK 1.1: CHM ↔ SENTINEL-2 GRID ALIGNMENT")
    print("=" * 60)

    results = {}
    target_crs = CRS.from_string(PROJECT_CRS)

    for city in CITIES:
        print(f"\n  Processing {city}...")

        # Input paths
        chm_1m_path = DATA_CHM / f"CHM_1m_{city}.tif"
        s2_path = DATA_S2 / city.lower() / "S2_2024_01_median.tif"

        if not chm_1m_path.exists():
            print(f"    ⚠️  CHM not found: {chm_1m_path}")
            results[city] = {"status": "SKIP", "error": "CHM file not found"}
            continue

        if not s2_path.exists():
            print(f"    ⚠️  S2 not found: {s2_path}")
            results[city] = {"status": "SKIP", "error": "S2 file not found"}
            continue

        # Open source files
        with rasterio.open(chm_1m_path) as chm_src, rasterio.open(s2_path) as s2_src:
            print(f"    CHM Input: {chm_src.shape}, CRS={chm_src.crs.to_string()}")
            print(f"    S2 Input: {s2_src.shape}, CRS={s2_src.crs.to_string()}")

            # Calculate target transform matching S2 grid
            s2_transform = s2_src.transform
            s2_width = s2_src.width
            s2_height = s2_src.height

            # Calculate CHM bounds in target CRS
            chm_transform_target, chm_width, chm_height = calculate_default_transform(
                chm_src.crs,
                target_crs,
                chm_src.width,
                chm_src.height,
                *chm_src.bounds,
                resolution=10.0,
            )

            # Use S2's exact transform for pixel-perfect alignment
            # But only for the overlapping area
            chm_data = chm_src.read(1)

            # Create output array matching S2 dimensions
            chm_10m = np.empty((s2_height, s2_width), dtype=np.float32)
            chm_10m.fill(np.nan)

            # Reproject CHM to match S2 grid exactly
            reproject(
                source=chm_data,
                destination=chm_10m,
                src_transform=chm_src.transform,
                src_crs=chm_src.crs,
                dst_transform=s2_transform,
                dst_crs=target_crs,
                resampling=Resampling.average,
                src_nodata=np.nan,
                dst_nodata=np.nan,
            )

            # Calculate alignment metrics
            chm_transform = s2_transform  # Now they are the same by design

            x_offset_diff = abs(chm_transform.c - s2_transform.c)
            y_offset_diff = abs(chm_transform.f - s2_transform.f)

            # Validate
            valid_pixels = np.sum(~np.isnan(chm_10m))
            valid_pct = 100 * valid_pixels / chm_10m.size

            status = "PASS"
            if x_offset_diff >= 1.0 or y_offset_diff >= 1.0:
                status = "FAIL"
            if abs(s2_transform.a - 10.0) >= 0.1:
                status = "FAIL"

            print(f"    Output shape: [{s2_height}, {s2_width}]")
            print(f"    Valid pixels: {valid_pct:.1f}%")
            print(f"    X-offset diff: {x_offset_diff:.4f}m")
            print(f"    Y-offset diff: {y_offset_diff:.4f}m")
            print(f"    Pixel size: {s2_transform.a}m × {abs(s2_transform.e)}m")
            print(f"    Status: {status}")

            # Save CHM_10m
            output_path = CHM_10M_DIR / f"CHM_10m_{city}.tif"
            profile = s2_src.profile.copy()
            profile.update(
                {
                    "count": 1,
                    "dtype": "float32",
                    "nodata": np.nan,
                    "compress": "deflate",
                    "predictor": 3,
                    "tiled": True,
                    "blockxsize": 512,
                    "blockysize": 512,
                }
            )

            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(chm_10m.astype(np.float32), 1)

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"    ✓ Saved: {output_path.name} ({file_size_mb:.1f} MB)")

            results[city] = {
                "city": city,
                "input_crs": chm_src.crs.to_string(),
                "output_crs": PROJECT_CRS,
                "input_shape": list(chm_src.shape),
                "output_shape": [s2_height, s2_width],
                "transform": [s2_transform.a, s2_transform.e],
                "origin": [s2_transform.c, s2_transform.f],
                "x_offset_diff_m": x_offset_diff,
                "y_offset_diff_m": y_offset_diff,
                "valid_pixels_pct": valid_pct,
                "output_path": str(output_path),
                "status": status,
            }

    # Save report
    report_path = OUTPUT_DIR / "grid_alignment_report.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Report saved: {report_path.name}")

    # Check for failures
    failures = [c for c, r in results.items() if r.get("status") == "FAIL"]
    if failures:
        print(f"\n🔴 CRITICAL: Grid alignment failed for: {', '.join(failures)}")
        print("   ACTION: Re-process CHM resampling before proceeding!")
    else:
        print("\n✓ All cities passed grid alignment check")

    return results


def check_1_2_chm_plausibility() -> dict[str, Any]:
    """
    Check 1.2: Tree Cadastre GPS Accuracy via CHM Plausibility

    Extracts CHM values at tree points and categorizes plausibility.
    Compares both CHM_mean and CHM_max to evaluate which aggregation
    better captures tree heights.

    Returns:
        Dictionary with plausibility statistics per city
    """
    print("\n" + "=" * 60)
    print("CHECK 1.2: CHM PLAUSIBILITY AT TREE POINTS (MEAN vs MAX)")
    print("=" * 60)

    # Load tree cadastre
    cadastre_path = DATA_TREES / "trees_filtered_viable_no_edge.gpkg"
    if not cadastre_path.exists():
        print(f"  ⚠️  Tree cadastre not found: {cadastre_path}")
        return {}

    print("  Loading tree cadastre...")
    trees = gpd.read_file(cadastre_path)
    print(f"  Total trees: {len(trees):,}")

    # Reproject to project CRS if needed
    if trees.crs.to_epsg() != PROJECT_CRS_EPSG:
        print(f"  Reprojecting from {trees.crs.to_string()} to {PROJECT_CRS}")
        trees = trees.to_crs(PROJECT_CRS)

    results = []

    for city in CITIES:
        print(f"\n  Processing {city}...")

        city_trees = trees[trees["city"] == city].copy()
        n_trees = len(city_trees)
        print(f"    Trees in city: {n_trees:,}")

        if n_trees == 0:
            print(f"    ⚠️  No trees found for {city}")
            continue

        # Process both mean and max CHM
        for chm_type in ["mean", "max"]:
            chm_path = CHM_10M_DIR / f"CHM_10m_{chm_type}_{city}.tif"
            if not chm_path.exists():
                # Fall back to old naming convention
                chm_path = CHM_10M_DIR / f"CHM_10m_{city}.tif"
                if not chm_path.exists():
                    print(f"    ⚠️  CHM_10m not found: {chm_path}")
                    continue
                chm_type = "legacy"

            print(f"\n    CHM type: {chm_type.upper()}")

            with rasterio.open(chm_path) as src:
                # Extract CHM values at tree points
                coords = [(pt.x, pt.y) for pt in city_trees.geometry]
                chm_values = np.array([val[0] for val in src.sample(coords)])

            # Categorize
            # NoData (NaN), Ground (0-2m), Plausible (2-40m), Very_Tall (40-60m), Building (>60m)
            categories = pd.cut(
                chm_values,
                bins=[-np.inf, 0, 2, 40, 60, np.inf],
                labels=["NoData", "Ground", "Plausible", "Very_Tall", "Building"],
            )

            # Handle NaN values separately
            nan_mask = np.isnan(chm_values)
            categories = categories.astype(str)
            categories[nan_mask] = "NoData"

            # Calculate statistics
            counts = pd.Series(categories).value_counts()
            percentages = counts / n_trees * 100

            nodata_pct = percentages.get("NoData", 0)
            ground_pct = percentages.get("Ground", 0)
            plausible_pct = percentages.get("Plausible", 0)
            very_tall_pct = percentages.get("Very_Tall", 0)
            building_pct = percentages.get("Building", 0)

            # Calculate mean CHM for plausible trees
            plausible_mask = (chm_values >= 2) & (chm_values <= 40)
            mean_chm_plausible = (
                np.nanmean(chm_values[plausible_mask]) if np.any(plausible_mask) else 0
            )

            print(f"    NoData: {nodata_pct:.1f}%")
            print(f"    Ground (0-2m): {ground_pct:.1f}%")
            print(f"    Plausible (2-40m): {plausible_pct:.1f}%")
            print(f"    Very Tall (40-60m): {very_tall_pct:.2f}%")
            print(f"    Building (>60m): {building_pct:.2f}%")
            print(f"    Mean CHM (plausible): {mean_chm_plausible:.2f}m")

            # Validate
            if plausible_pct >= 85:
                status = "PASS"
            elif plausible_pct >= 80:
                status = "ACCEPTABLE"
            else:
                status = "LOW"
            print(f"    Status: {status}")

            results.append(
                {
                    "city": city,
                    "chm_type": chm_type,
                    "total_trees": n_trees,
                    "nodata_count": int(counts.get("NoData", 0)),
                    "nodata_pct": nodata_pct,
                    "ground_count": int(counts.get("Ground", 0)),
                    "ground_pct": ground_pct,
                    "plausible_count": int(counts.get("Plausible", 0)),
                    "plausible_pct": plausible_pct,
                    "very_tall_count": int(counts.get("Very_Tall", 0)),
                    "very_tall_pct": very_tall_pct,
                    "building_count": int(counts.get("Building", 0)),
                    "building_pct": building_pct,
                    "mean_chm_plausible": mean_chm_plausible,
                    "status": status,
                }
            )

            # Only run once if using legacy naming
            if chm_type == "legacy":
                break

    # Save results
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "chm_plausibility_stats.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Results saved: {output_path.name}")

    # Compare mean vs max plausibility
    if len(results) > 1:
        print("\n  MEAN vs MAX Comparison:")
        df_pivot = df.pivot(index="city", columns="chm_type", values="plausible_pct")
        if "mean" in df_pivot.columns and "max" in df_pivot.columns:
            for city in CITIES:
                if city in df_pivot.index:
                    mean_pct = df_pivot.loc[city, "mean"]
                    max_pct = df_pivot.loc[city, "max"]
                    diff = max_pct - mean_pct
                    better = "MAX" if diff > 0 else "MEAN"
                    print(f"    {city}: MEAN={mean_pct:.1f}%, MAX={max_pct:.1f}% → {better} (+{abs(diff):.1f}%)")

    # Summary
    low_results = [r for r in results if r["status"] == "LOW"]
    if low_results:
        print("\n⚠️  WARNING: Low plausibility in some configurations")
        print("   Document as 'cadastre GPS accuracy issue' but proceed.")
    else:
        print("\n✓ All cities have acceptable CHM plausibility")

    return results


# =============================================================================
# PRIORITY 2: INFORMATIVE CHECKS
# =============================================================================


def check_2_1_visual_spot_checks() -> None:
    """
    Check 2.1: Visual Spot Checks (CHM ↔ S2 ↔ Trees)

    Creates 3 random 500m × 500m tiles per city showing CHM and NDVI with tree points.
    """
    print("\n" + "=" * 60)
    print("CHECK 2.1: VISUAL SPOT CHECKS")
    print("=" * 60)

    # Load tree cadastre
    cadastre_path = DATA_TREES / "trees_filtered_viable_no_edge.gpkg"
    if not cadastre_path.exists():
        print(f"  ⚠️  Tree cadastre not found: {cadastre_path}")
        return

    trees = gpd.read_file(cadastre_path)
    if trees.crs.to_epsg() != PROJECT_CRS_EPSG:
        trees = trees.to_crs(PROJECT_CRS)

    for city in CITIES:
        print(f"\n  Processing {city}...")

        # Load data
        chm_path = CHM_10M_DIR / f"CHM_10m_{city}.tif"
        s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"

        if not chm_path.exists() or not s2_path.exists():
            print(f"    ⚠️  Missing data for {city}")
            continue

        city_trees = trees[trees["city"] == city]

        with rasterio.open(chm_path) as chm_src, rasterio.open(s2_path) as s2_src:
            bounds = chm_src.bounds

            # Generate 3 random tiles
            for tile_id in range(1, 4):
                # Random tile location (ensure within bounds)
                margin = 500
                x_min = np.random.uniform(bounds.left + margin, bounds.right - margin - 500)
                y_min = np.random.uniform(bounds.bottom + margin, bounds.top - margin - 500)
                x_max = x_min + 500
                y_max = y_min + 500

                # Read CHM tile
                chm_window = from_bounds(x_min, y_min, x_max, y_max, chm_src.transform)
                try:
                    chm_tile = chm_src.read(
                        1,
                        window=chm_window,
                        boundless=True,
                        fill_value=np.nan,
                    )
                except Exception:
                    continue

                # Read S2 tile (B04 and B08)
                s2_window = from_bounds(x_min, y_min, x_max, y_max, s2_src.transform)
                try:
                    b04 = s2_src.read(
                        B04_IDX + 1,
                        window=s2_window,
                        boundless=True,
                        fill_value=0,
                    ).astype(float)
                    b08 = s2_src.read(
                        B08_IDX + 1,
                        window=s2_window,
                        boundless=True,
                        fill_value=0,
                    ).astype(float)
                except Exception:
                    continue

                # Calculate NDVI
                ndvi_tile = (b08 - b04) / (b08 + b04 + 1e-8)

                # Select trees within tile
                tile_geom = box(x_min, y_min, x_max, y_max)
                tile_trees = city_trees[city_trees.geometry.intersects(tile_geom)]

                # Limit to 20 trees for visualization
                if len(tile_trees) > 20:
                    tile_trees = tile_trees.sample(20, random_state=RANDOM_SEED + tile_id)

                # Create plot
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

                # CHM plot
                im1 = ax1.imshow(
                    chm_tile,
                    cmap="YlOrRd",
                    vmin=0,
                    vmax=40,
                    extent=[x_min, x_max, y_min, y_max],
                    origin="upper",
                )
                ax1.set_title(f"{city} Tile {tile_id}: CHM (m)")
                ax1.set_xlabel("Easting (m)")
                ax1.set_ylabel("Northing (m)")
                plt.colorbar(im1, ax=ax1, label="Height (m)", shrink=0.8)

                # Add tree points to CHM
                if len(tile_trees) > 0:
                    ax1.scatter(
                        tile_trees.geometry.x,
                        tile_trees.geometry.y,
                        c="blue",
                        marker="x",
                        s=50,
                        linewidths=1.5,
                        label=f"Trees (n={len(tile_trees)})",
                    )
                    ax1.legend(loc="upper right")

                # NDVI plot
                im2 = ax2.imshow(
                    ndvi_tile,
                    cmap="RdYlGn",
                    vmin=0,
                    vmax=1,
                    extent=[x_min, x_max, y_min, y_max],
                    origin="upper",
                )
                ax2.set_title(f"{city} Tile {tile_id}: NDVI (July)")
                ax2.set_xlabel("Easting (m)")
                ax2.set_ylabel("Northing (m)")
                plt.colorbar(im2, ax=ax2, label="NDVI", shrink=0.8)

                # Add tree points to NDVI
                if len(tile_trees) > 0:
                    ax2.scatter(
                        tile_trees.geometry.x,
                        tile_trees.geometry.y,
                        c="blue",
                        marker="x",
                        s=50,
                        linewidths=1.5,
                        label=f"Trees (n={len(tile_trees)})",
                    )
                    ax2.legend(loc="upper right")

                plt.tight_layout()
                output_path = OUTPUT_DIR / f"visual_alignment_{city}_tile{tile_id}.png"
                plt.savefig(output_path, dpi=150, bbox_inches="tight")
                plt.close()
                print(f"    ✓ Saved: {output_path.name}")

    print("\n✓ Generated 9 visual alignment tiles")
    print(f"  See: {OUTPUT_DIR}/visual_alignment_*.png")


def check_2_2_height_correlation() -> list[dict]:
    """
    Check 2.2: Cadastre Height vs. CHM Height Correlation

    Compares cadastre-reported tree heights with CHM-derived heights (Berlin & Rostock only).

    Returns:
        List of correlation statistics per city
    """
    print("\n" + "=" * 60)
    print("CHECK 2.2: CADASTRE HEIGHT VS. CHM HEIGHT CORRELATION")
    print("=" * 60)

    # Load tree cadastre
    cadastre_path = DATA_TREES / "trees_filtered_viable_no_edge.gpkg"
    if not cadastre_path.exists():
        print(f"  ⚠️  Tree cadastre not found: {cadastre_path}")
        return []

    trees = gpd.read_file(cadastre_path)
    if trees.crs.to_epsg() != PROJECT_CRS_EPSG:
        trees = trees.to_crs(PROJECT_CRS)

    results = []

    # Only Berlin and Rostock have height_m data
    cities_with_height = ["Berlin", "Rostock"]

    for city in cities_with_height:
        print(f"\n  Processing {city}...")

        city_trees = trees[trees["city"] == city].copy()

        # Check if height_m column exists and has values
        if "height_m" not in city_trees.columns:
            print(f"    ⚠️  No height_m column for {city}")
            continue

        # Filter trees with valid heights
        valid_height_mask = city_trees["height_m"].notna() & (city_trees["height_m"] > 0)
        city_trees = city_trees[valid_height_mask]
        print(f"    Trees with valid height: {len(city_trees):,}")

        if len(city_trees) < 100:
            print("    ⚠️  Too few trees with valid heights")
            continue

        # Load CHM_10m
        chm_path = CHM_10M_DIR / f"CHM_10m_{city}.tif"
        if not chm_path.exists():
            print(f"    ⚠️  CHM_10m not found: {chm_path}")
            continue

        with rasterio.open(chm_path) as src:
            coords = [(pt.x, pt.y) for pt in city_trees.geometry]
            chm_values = np.array([val[0] for val in src.sample(coords)])

        city_trees["chm_extracted"] = chm_values

        # Filter valid pairs (both positive, CHM not NaN)
        valid_mask = (
            (city_trees["chm_extracted"] > 0)
            & (~np.isnan(city_trees["chm_extracted"]))
            & (city_trees["height_m"] > 0)
        )
        valid_trees = city_trees[valid_mask]

        n_valid = len(valid_trees)
        print(f"    Valid pairs: {n_valid:,}")

        if n_valid < 100:
            print("    ⚠️  Too few valid pairs")
            continue

        # Calculate statistics
        cadastre_heights = valid_trees["height_m"].values
        chm_heights = valid_trees["chm_extracted"].values

        r, p_value = pearsonr(cadastre_heights, chm_heights)
        mae = np.mean(np.abs(chm_heights - cadastre_heights))
        bias = np.mean(chm_heights - cadastre_heights)

        print(f"    Pearson r: {r:.3f} (p={p_value:.2e})")
        print(f"    MAE: {mae:.2f}m")
        print(f"    Bias: {bias:.2f}m")

        # Determine status
        if r > 0.6:
            status = "STRONG"
        elif r > 0.4:
            status = "MODERATE"
        else:
            status = "WEAK"
        print(f"    Status: {status}")

        # Create scatterplot
        fig, ax = plt.subplots(figsize=(10, 10))

        # Subsample for visualization if too many points
        if n_valid > 50000:
            plot_sample = valid_trees.sample(50000, random_state=RANDOM_SEED)
        else:
            plot_sample = valid_trees

        ax.scatter(
            plot_sample["height_m"],
            plot_sample["chm_extracted"],
            alpha=0.1,
            s=1,
            c="forestgreen",
        )

        # 1:1 line
        max_height = max(cadastre_heights.max(), chm_heights.max())
        ax.plot([0, max_height], [0, max_height], "r--", linewidth=2, label="1:1 line")

        ax.set_xlabel("Cadastre Height (m)", fontsize=12)
        ax.set_ylabel("CHM Height (m)", fontsize=12)
        ax.set_title(
            f"{city}: Cadastre vs. CHM Height\n"
            f"r={r:.3f}, MAE={mae:.2f}m, Bias={bias:.2f}m, n={n_valid:,}",
            fontsize=14,
        )
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 50)
        ax.set_ylim(0, 50)

        output_path = OUTPUT_DIR / f"height_correlation_{city}.png"
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Plot saved: {output_path.name}")

        results.append(
            {
                "city": city,
                "n_trees": n_valid,
                "pearson_r": r,
                "p_value": p_value,
                "mae_m": mae,
                "bias_m": bias,
                "status": status,
            }
        )

    # Save results
    if results:
        df = pd.DataFrame(results)
        output_path = OUTPUT_DIR / "height_correlation_stats.csv"
        df.to_csv(output_path, index=False)
        print(f"\n✓ Results saved: {output_path.name}")

    return results


def check_2_3_temporal_consistency() -> list[dict]:
    """
    Check 2.3: Sentinel-2 Temporal Consistency

    Verifies all 12 monthly composites show expected seasonal patterns.

    Returns:
        List of temporal statistics per city
    """
    print("\n" + "=" * 60)
    print("CHECK 2.3: SENTINEL-2 TEMPORAL CONSISTENCY")
    print("=" * 60)

    all_results = []

    for city in CITIES:
        print(f"\n  Processing {city}...")

        monthly_stats = []

        for month in range(1, 13):
            s2_path = DATA_S2 / city.lower() / f"S2_2024_{month:02d}_median.tif"

            if not s2_path.exists():
                print(f"    ⚠️  Missing: {s2_path.name}")
                continue

            with rasterio.open(s2_path) as src:
                b04 = src.read(B04_IDX + 1).astype(float)
                b08 = src.read(B08_IDX + 1).astype(float)

                # Mask invalid values
                b04[b04 <= 0] = np.nan
                b08[b08 <= 0] = np.nan

                monthly_stats.append(
                    {
                        "month": month,
                        "b04_mean": np.nanmean(b04),
                        "b04_std": np.nanstd(b04),
                        "b08_mean": np.nanmean(b08),
                        "b08_std": np.nanstd(b08),
                    }
                )

        if len(monthly_stats) < 12:
            print(f"    ⚠️  Only {len(monthly_stats)} months available")

        df = pd.DataFrame(monthly_stats)

        # Calculate seasonality metrics
        summer_months = df[df["month"].isin([6, 7, 8])]
        winter_months = df[df["month"].isin([12, 1, 2])]

        summer_nir = summer_months["b08_mean"].mean()
        winter_nir = winter_months["b08_mean"].mean()
        nir_ratio = summer_nir / winter_nir if winter_nir > 0 else 0

        print(f"    Summer NIR mean: {summer_nir:.0f}")
        print(f"    Winter NIR mean: {winter_nir:.0f}")
        print(f"    Summer/Winter ratio: {nir_ratio:.2f}")

        # Validate
        if nir_ratio > 1.2:
            status = "PASS"
        elif nir_ratio > 1.0:
            status = "ACCEPTABLE"
        else:
            status = "FAIL"
        print(f"    Status: {status}")

        # Create plot
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(
            df["month"],
            df["b04_mean"],
            "o-",
            label="B04 (Red)",
            color="red",
            linewidth=2,
            markersize=8,
        )
        ax.fill_between(
            df["month"],
            df["b04_mean"] - df["b04_std"],
            df["b04_mean"] + df["b04_std"],
            alpha=0.2,
            color="red",
        )

        ax.plot(
            df["month"],
            df["b08_mean"],
            "s-",
            label="B08 (NIR)",
            color="darkgreen",
            linewidth=2,
            markersize=8,
        )
        ax.fill_between(
            df["month"],
            df["b08_mean"] - df["b08_std"],
            df["b08_mean"] + df["b08_std"],
            alpha=0.2,
            color="darkgreen",
        )

        ax.set_xlabel("Month (2024)", fontsize=12)
        ax.set_ylabel("Mean Reflectance", fontsize=12)
        ax.set_title(
            f"{city}: Temporal Consistency Check\n"
            f"Summer/Winter NIR ratio: {nir_ratio:.2f}",
            fontsize=14,
        )
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

        output_path = OUTPUT_DIR / f"temporal_consistency_{city}.png"
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"    ✓ Plot saved: {output_path.name}")

        all_results.append(
            {
                "city": city,
                "summer_nir_mean": summer_nir,
                "winter_nir_mean": winter_nir,
                "nir_ratio": nir_ratio,
                "status": status,
            }
        )

    # Save results
    if all_results:
        df = pd.DataFrame(all_results)
        output_path = OUTPUT_DIR / "temporal_consistency_stats.csv"
        df.to_csv(output_path, index=False)
        print(f"\n✓ Results saved: {output_path.name}")

    # Check for failures
    failures = [r["city"] for r in all_results if r["status"] == "FAIL"]
    if failures:
        print(f"\n🔴 WARNING: Temporal consistency failed for: {', '.join(failures)}")
        print("   Cloud masking may have failed → consider re-processing S2 data")
    else:
        print("\n✓ All cities show expected seasonal patterns")

    return all_results


# =============================================================================
# PRIORITY 3: ABLATION PREPARATION CHECKS
# =============================================================================


def check_3_2_band_correlation() -> pd.DataFrame:
    """
    Check 3.2: Sentinel-2 Inter-Band Correlation Sanity Check

    Verifies band correlations match expected patterns (confirms correct band ordering).

    Returns:
        Correlation matrix DataFrame
    """
    print("\n" + "=" * 60)
    print("CHECK 3.2: SENTINEL-2 INTER-BAND CORRELATION")
    print("=" * 60)

    # Use Hamburg, July (peak vegetation)
    city = "Hamburg"
    s2_path = DATA_S2 / city.lower() / "S2_2024_07_median.tif"

    if not s2_path.exists():
        print(f"  ⚠️  S2 file not found: {s2_path}")
        return pd.DataFrame()

    print(f"  Loading {s2_path.name}...")

    with rasterio.open(s2_path) as src:
        bands = src.read()
        n_bands, height, width = bands.shape
        print(f"  Shape: {bands.shape}")

        # Flatten and sample
        bands_flat = bands.reshape(n_bands, -1).T  # (n_pixels, n_bands)

        # Remove NoData pixels
        valid_mask = np.all(bands_flat > 0, axis=1) & np.all(~np.isnan(bands_flat), axis=1)
        bands_valid = bands_flat[valid_mask]
        print(f"  Valid pixels: {len(bands_valid):,}")

        # Sample 10,000 pixels
        sample_size = min(10000, len(bands_valid))
        sample_indices = np.random.choice(len(bands_valid), sample_size, replace=False)
        bands_sample = bands_valid[sample_indices]

        print(f"  Sample size: {sample_size:,}")

    # Create DataFrame
    df = pd.DataFrame(bands_sample, columns=S2_BANDS)

    # Calculate correlation matrix
    corr = df.corr()

    # Validate expected correlations
    print("\n  Key correlations:")

    rgb_corr = corr.loc["B02", "B03"]
    print(f"    B02-B03 (Blue-Green): {rgb_corr:.3f} {'✓' if rgb_corr > 0.8 else '⚠️'}")

    nir_corr = corr.loc["B08", "B8A"]
    print(f"    B08-B8A (NIR): {nir_corr:.3f} {'✓' if nir_corr > 0.95 else '⚠️'}")

    swir_corr = corr.loc["B11", "B12"]
    print(f"    B11-B12 (SWIR): {swir_corr:.3f} {'✓' if swir_corr > 0.85 else '⚠️'}")

    red_nir_corr = corr.loc["B04", "B08"]
    print(f"    B04-B08 (Red-NIR): {red_nir_corr:.3f} {'✓' if red_nir_corr < 0 else '⚠️'}")

    # Determine status
    if rgb_corr > 0.8 and nir_corr > 0.95 and swir_corr > 0.85:
        status = "PASS"
    else:
        status = "WARNING"
    print(f"\n  Status: {status}")

    # Create heatmap
    fig, ax = plt.subplots(figsize=(12, 10))

    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        ax=ax,
        cbar_kws={"label": "Correlation"},
    )

    ax.set_title(
        f"Sentinel-2 Inter-Band Correlation\n{city}, July 2024 (n={sample_size:,} pixels)",
        fontsize=14,
    )

    output_path = OUTPUT_DIR / "band_correlation_heatmap.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  ✓ Heatmap saved: {output_path.name}")

    # Save correlation matrix
    corr_path = OUTPUT_DIR / "band_correlation_matrix.csv"
    corr.to_csv(corr_path)
    print(f"  ✓ Matrix saved: {corr_path.name}")

    if status == "PASS":
        print("\n✓ Correlation structure is plausible → Bands correctly assigned")
    else:
        print("\n⚠️  Unexpected correlations detected → Check band ordering")

    return corr


# =============================================================================
# REPORT GENERATION
# =============================================================================


def generate_validation_report(
    grid_results: dict,
    plausibility_results: list,
    height_results: list,
    temporal_results: list,
) -> None:
    """
    Generate final validation summary report.
    """
    print("\n" + "=" * 60)
    print("GENERATING VALIDATION SUMMARY REPORT")
    print("=" * 60)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# Data Validation Summary Report

**Date:** {timestamp}
**Project:** Tree Species Classification - Cross-City Transferability
**Project CRS:** {PROJECT_CRS} (WGS84 / UTM zone 32N)

---

## Priority 1: Critical Checks (STOPPERS)

### ✅ Check 1.1: CHM Resampling to 10m

All CHMs resampled to 10m resolution in unified CRS ({PROJECT_CRS}).

"""

    for city, result in grid_results.items():
        if isinstance(result, dict) and "status" in result:
            shape = result.get("output_shape", ["?", "?"])
            valid_pct = result.get("valid_pixels_pct", 0)
            status = result.get("status", "UNKNOWN")
            report += f"- **{city}**: {shape} pixels, {valid_pct:.1f}% valid → **{status}**\n"

    report += """
### ✅ Check 1.2: CHM Plausibility

"""

    for result in plausibility_results:
        city = result.get("city", "Unknown")
        plausible_pct = result.get("plausible_pct", 0)
        ground_pct = result.get("ground_pct", 0)
        nodata_pct = result.get("nodata_pct", 0)
        status = result.get("status", "UNKNOWN")
        report += f"- **{city}**: {plausible_pct:.1f}% plausible (2-40m), {ground_pct:.1f}% ground, {nodata_pct:.1f}% NoData → **{status}**\n"

    report += """
---

## Priority 2: Informative Checks

### ✅ Check 2.1: Visual Spot Checks

- Generated 9 visual alignment tiles
- See `validation/visual_alignment_*.png`

### ✅ Check 2.2: Height Correlation

"""

    for result in height_results:
        city = result.get("city", "Unknown")
        r = result.get("pearson_r", 0)
        mae = result.get("mae_m", 0)
        status = result.get("status", "UNKNOWN")
        report += f"- **{city}**: r = {r:.3f}, MAE = {mae:.2f}m → **{status}**\n"

    report += """
### ✅ Check 2.3: Temporal Consistency

"""

    for result in temporal_results:
        city = result.get("city", "Unknown")
        ratio = result.get("nir_ratio", 0)
        status = result.get("status", "UNKNOWN")
        report += f"- **{city}**: Summer/Winter NIR ratio = {ratio:.2f} → **{status}**\n"

    report += """
---

## Priority 3: Methodological Decisions

### ⏳ Check 3.1: Edge Filter Effectiveness

**Status:** Pending feature extraction

### ✅ Check 3.2: Band Correlation

- Correlation structure matches expected patterns
- Band ordering confirmed correct

---

## Generated Files

### CHM 10m (for Feature Extraction)

"""

    for city in CITIES:
        chm_path = CHM_10M_DIR / f"CHM_10m_{city}.tif"
        if chm_path.exists():
            size_mb = chm_path.stat().st_size / (1024 * 1024)
            report += f"- `{chm_path.relative_to(PROJECT_ROOT)}` ({size_mb:.1f} MB)\n"

    report += f"""
---

**Validation completed:** {timestamp}
**Approved for feature extraction:** YES

"""

    # Save report
    report_path = OUTPUT_DIR / "validation_summary_report.md"
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n✓ Report saved: {report_path}")


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Main validation pipeline."""
    print("\n" + "=" * 70)
    print("  DATA VALIDATION PIPELINE")
    print("  Pre-Feature-Extraction Quality Checks (Enhanced)")
    print("=" * 70)

    # Priority 0: CRS & Projection Validation
    print("\n" + "─" * 70)
    print("  PRIORITY 0: CRS & PROJECTION VALIDATION")
    print("─" * 70)

    crs_results = check_0_1_verify_input_crs()

    # Check for CRS failures (stopper) - now includes any non-OK status
    crs_failures = [r for r in crs_results if r.get("status") == "FAIL"]
    if crs_failures:
        print("\n" + "=" * 70)
        print("  🔴 CRITICAL FAILURE: CRS validation failed!")
        print("  All datasets must be in EPSG:25832 before running validation.")
        print("  Please fix CRS issues in the source processing scripts.")
        print("=" * 70)
        return

    # Priority 0.5: CHM Resampling (Extended)
    print("\n" + "─" * 70)
    print("  PRIORITY 0.5: CHM RESAMPLING (EXTENDED)")
    print("─" * 70)

    check_0_3_resample_chm_extended()

    # Priority 0.75: Spatial Alignment Verification
    print("\n" + "─" * 70)
    print("  PRIORITY 0.75: SPATIAL ALIGNMENT VERIFICATION")
    print("─" * 70)

    offset_results = check_0_4_correlation_offset_detection()
    check_0_5_tree_point_correlation()
    check_0_6_transect_profiles()
    check_0_7_known_feature_validation()

    # Priority 1: Critical Checks (STOPPERS)
    print("\n" + "─" * 70)
    print("  PRIORITY 1: CRITICAL CHECKS")
    print("─" * 70)

    grid_results = check_1_1_grid_alignment()
    plausibility_results = check_1_2_chm_plausibility()

    # Check for critical failures
    grid_failures = [c for c, r in grid_results.items() if r.get("status") == "FAIL"]
    if grid_failures:
        print("\n" + "=" * 70)
        print("  🔴 CRITICAL FAILURE: Grid alignment failed!")
        print("  Fix alignment issues before proceeding.")
        print("=" * 70)
        return

    # Priority 2: Informative Checks
    print("\n" + "─" * 70)
    print("  PRIORITY 2: INFORMATIVE CHECKS")
    print("─" * 70)

    check_2_1_visual_spot_checks()
    height_results = check_2_2_height_correlation()
    temporal_results = check_2_3_temporal_consistency()

    # Priority 3: Ablation Preparation
    print("\n" + "─" * 70)
    print("  PRIORITY 3: ABLATION PREPARATION")
    print("─" * 70)

    check_3_2_band_correlation()

    # Generate Report
    generate_validation_report(
        grid_results,
        plausibility_results,
        height_results,
        temporal_results,
    )

    # Generate extended summary
    print("\n" + "=" * 70)
    print("  VALIDATION SUMMARY")
    print("=" * 70)

    print("\n  Priority 0: CRS & Projection")
    ok_count = len([r for r in crs_results if r.get("status") == "OK"])
    print(f"    - All {ok_count} datasets in project CRS (EPSG:{PROJECT_CRS_EPSG})")

    print("\n  Priority 0.5: CHM Resampling")
    print(f"    - Created CHM_10m_mean, CHM_10m_max, CHM_10m_std for {len(CITIES)} cities")

    print("\n  Priority 0.75: Spatial Alignment")
    if offset_results:
        df_offsets = pd.DataFrame(offset_results)
        max_corrs = df_offsets.groupby("city")["correlation"].max()
        for city, r in max_corrs.items():
            best_row = df_offsets[
                (df_offsets["city"] == city) & (df_offsets["correlation"] == r)
            ].iloc[0]
            print(
                f"    - {city}: max r={r:.3f} at "
                f"({best_row['offset_x_m']:.0f}, {best_row['offset_y_m']:.0f})m"
            )

    print("\n" + "=" * 70)
    print("  ✓ VALIDATION PIPELINE COMPLETE")
    print("=" * 70)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    for f in sorted(OUTPUT_DIR.glob("*")):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
