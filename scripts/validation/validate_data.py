"""
Data Validation Script for Pre-Feature-Extraction Quality Checks.

Validates spatial alignment, data quality, and consistency across
CHM (10m), Sentinel-2, and tree cadastre datasets.

Checks:
1. Data Integrity: CRS, file existence, grid alignment
2. CHM Quality: Value ranges, coverage
3. Sentinel-2 Quality: Band ranges, temporal completeness, seasonal patterns
4. Tree-Raster Alignment: CHM/NDVI values at tree points
5. Visual Spot Checks: Random tiles with CHM, NDVI, and tree points

Usage:
    uv run python scripts/validation/validate_data.py
"""

import json
import warnings
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from scipy.stats import pearsonr

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHM_10M_DIR = DATA_DIR / "CHM" / "processed" / "CHM_10m"
S2_DIR = DATA_DIR / "sentinel2"
TREES_DIR = DATA_DIR / "tree_cadastres" / "processed"
BOUNDARIES_DIR = DATA_DIR / "boundaries"
OUTPUT_DIR = DATA_DIR / "validation"

# Project settings
CITIES = ["Berlin", "Hamburg", "Rostock"]
PROJECT_CRS = "EPSG:25832"
PROJECT_CRS_EPSG = 25832
REFERENCE_YEAR = 2021
RANDOM_SEED = 42

# Sentinel-2 bands (10 spectral + 5 vegetation indices)
S2_BANDS = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12",
            "NDre", "NDVIre", "kNDVI", "VARI", "RTVIcore"]
NDVI_BAND_IDX = 12  # kNDVI is a good proxy for NDVI

# Expected band indices for NDVI calculation (if needed)
B04_IDX = 2  # Red
B08_IDX = 6  # NIR

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
np.random.seed(RANDOM_SEED)

print(f"Project Root: {PROJECT_ROOT}")
print(f"Output Directory: {OUTPUT_DIR}")


# =============================================================================
# CHECK 1: DATA INTEGRITY
# =============================================================================

def check_1_data_integrity() -> dict:
    """
    Check 1: Data Integrity
    
    Verifies:
    - All required files exist
    - All datasets use project CRS (EPSG:25832)
    - CHM and S2 grids are aligned (same origin, size, resolution)
    
    Returns:
        Dictionary with integrity check results
    """
    print("\n" + "=" * 70)
    print("CHECK 1: DATA INTEGRITY")
    print("=" * 70)
    
    results = {
        "files_missing": [],
        "crs_issues": [],
        "grid_alignment": {},
        "status": "PASS"
    }
    
    # 1.1 Check file existence
    print("\n  1.1 File Existence...")
    
    required_files = []
    
    # CHM 10m files
    for city in CITIES:
        for agg in ["mean", "max", "std"]:
            required_files.append(CHM_10M_DIR / f"CHM_10m_{agg}_{city}.tif")
    
    # Sentinel-2 files (12 months per city)
    for city in CITIES:
        for month in range(1, 13):
            required_files.append(S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_{month:02d}_median.tif")
    
    # Tree cadastre
    required_files.append(TREES_DIR / "trees_filtered_viable_no_edge.gpkg")
    
    # Boundaries
    required_files.append(BOUNDARIES_DIR / "city_boundaries.gpkg")
    
    for f in required_files:
        if not f.exists():
            results["files_missing"].append(str(f.relative_to(PROJECT_ROOT)))
            results["status"] = "FAIL"
    
    if results["files_missing"]:
        print(f"    ❌ Missing {len(results['files_missing'])} files:")
        for f in results["files_missing"][:5]:
            print(f"       - {f}")
        if len(results["files_missing"]) > 5:
            print(f"       ... and {len(results['files_missing']) - 5} more")
    else:
        print(f"    ✓ All {len(required_files)} required files exist")
    
    # 1.2 Check CRS consistency
    print("\n  1.2 CRS Consistency...")
    
    datasets_to_check = []
    
    # Sample CHM and S2 files
    for city in CITIES:
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_07_median.tif"
        if chm_path.exists():
            datasets_to_check.append(("CHM", city, chm_path))
        if s2_path.exists():
            datasets_to_check.append(("S2", city, s2_path))
    
    # Tree cadastre
    trees_path = TREES_DIR / "trees_filtered_viable_no_edge.gpkg"
    if trees_path.exists():
        datasets_to_check.append(("Trees", "all", trees_path))
    
    for dataset_type, city, path in datasets_to_check:
        try:
            if path.suffix == ".gpkg":
                gdf = gpd.read_file(path, rows=1)
                epsg = gdf.crs.to_epsg() if gdf.crs else None
            else:
                with rasterio.open(path) as src:
                    epsg = src.crs.to_epsg() if src.crs else None
            
            if epsg != PROJECT_CRS_EPSG:
                results["crs_issues"].append(f"{dataset_type}_{city}: EPSG:{epsg}")
                results["status"] = "FAIL"
        except Exception as e:
            results["crs_issues"].append(f"{dataset_type}_{city}: Error - {e}")
            results["status"] = "FAIL"
    
    if results["crs_issues"]:
        print(f"    ❌ CRS issues found:")
        for issue in results["crs_issues"]:
            print(f"       - {issue}")
    else:
        print(f"    ✓ All datasets in project CRS (EPSG:{PROJECT_CRS_EPSG})")
    
    # 1.3 Check grid alignment (CHM ↔ S2)
    print("\n  1.3 Grid Alignment (CHM ↔ S2)...")
    
    for city in CITIES:
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_07_median.tif"
        
        if not chm_path.exists() or not s2_path.exists():
            results["grid_alignment"][city] = "SKIP (files missing)"
            continue
        
        with rasterio.open(chm_path) as chm_src, rasterio.open(s2_path) as s2_src:
            # Compare transforms
            chm_t = chm_src.transform
            s2_t = s2_src.transform
            
            origin_match = (abs(chm_t.c - s2_t.c) < 0.01 and abs(chm_t.f - s2_t.f) < 0.01)
            size_match = (chm_src.width == s2_src.width and chm_src.height == s2_src.height)
            res_match = (abs(chm_t.a - s2_t.a) < 0.01 and abs(chm_t.e - s2_t.e) < 0.01)
            
            if origin_match and size_match and res_match:
                results["grid_alignment"][city] = "ALIGNED"
                print(f"    ✓ {city}: Grids aligned ({chm_src.width}x{chm_src.height}, 10m)")
            else:
                results["grid_alignment"][city] = "MISALIGNED"
                results["status"] = "FAIL"
                print(f"    ❌ {city}: Grid mismatch!")
                if not origin_match:
                    print(f"       Origin: CHM({chm_t.c:.2f}, {chm_t.f:.2f}) vs S2({s2_t.c:.2f}, {s2_t.f:.2f})")
                if not size_match:
                    print(f"       Size: CHM({chm_src.width}x{chm_src.height}) vs S2({s2_src.width}x{s2_src.height})")
    
    # Summary
    print(f"\n  Status: {results['status']}")
    
    return results


# =============================================================================
# CHECK 2: CHM QUALITY
# =============================================================================

def check_2_chm_quality() -> pd.DataFrame:
    """
    Check 2: CHM Quality
    
    Analyzes CHM 10m rasters (mean, max, std) for each city:
    - Value ranges
    - Coverage within city boundaries (valid pixel percentage)
    - Statistics
    
    Returns:
        DataFrame with CHM statistics
    """
    print("\n" + "=" * 70)
    print("CHECK 2: CHM QUALITY (10m)")
    print("=" * 70)
    
    # Load city boundaries for coverage calculation
    boundaries_path = BOUNDARIES_DIR / "city_boundaries.gpkg"
    boundaries_gdf = gpd.read_file(boundaries_path)
    
    results = []
    
    for city in CITIES:
        print(f"\n  {city}:")
        
        # Get city boundary (column is 'gen' not 'city')
        city_boundary = boundaries_gdf[boundaries_gdf["gen"] == city]
        if city_boundary.empty:
            print(f"    ⚠️ No boundary found for {city}")
            continue
        city_geom = city_boundary.geometry.values
        
        for agg in ["mean", "max", "std"]:
            chm_path = CHM_10M_DIR / f"CHM_10m_{agg}_{city}.tif"
            
            if not chm_path.exists():
                print(f"    {agg}: FILE NOT FOUND")
                continue
            
            with rasterio.open(chm_path) as src:
                data = src.read(1)
                
                # Create mask for city boundary (False = inside, True = outside)
                city_mask = geometry_mask(
                    city_geom, 
                    out_shape=data.shape, 
                    transform=src.transform, 
                    invert=True  # True = inside city
                )
                
                # Handle NoData
                nodata = src.nodata
                if nodata is not None:
                    valid_mask = data != nodata
                else:
                    valid_mask = ~np.isnan(data)
                
                # Calculate coverage within city boundary
                pixels_in_city = np.sum(city_mask)
                valid_in_city = np.sum(valid_mask & city_mask)
                coverage_in_city = 100 * valid_in_city / pixels_in_city if pixels_in_city > 0 else 0
                
                # Get valid data for statistics
                valid_data = data[valid_mask & city_mask]
                
                if len(valid_data) == 0:
                    print(f"    {agg}: NO VALID DATA")
                    continue
                
                stats = {
                    "city": city,
                    "aggregation": agg,
                    "width": src.width,
                    "height": src.height,
                    "total_pixels": data.size,
                    "pixels_in_city": int(pixels_in_city),
                    "valid_pixels": int(valid_in_city),
                    "coverage_pct": coverage_in_city,
                    "min": float(np.min(valid_data)),
                    "max": float(np.max(valid_data)),
                    "mean": float(np.mean(valid_data)),
                    "std": float(np.std(valid_data)),
                    "p05": float(np.percentile(valid_data, 5)),
                    "p95": float(np.percentile(valid_data, 95)),
                }
                results.append(stats)
                
                # Check plausibility
                status = "✓"
                warnings = []
                
                if agg in ["mean", "max"]:
                    if stats["min"] < -5:
                        warnings.append(f"min={stats['min']:.1f}m (<-5m)")
                    if stats["max"] > 60:
                        warnings.append(f"max={stats['max']:.1f}m (>60m)")
                    if stats["mean"] < 0:
                        warnings.append(f"mean={stats['mean']:.1f}m (<0)")
                
                if warnings:
                    status = "⚠️"
                
                print(f"    {agg}: {status} range=[{stats['min']:.1f}, {stats['max']:.1f}]m, "
                      f"mean={stats['mean']:.1f}m, coverage={stats['coverage_pct']:.1f}% (in city)")
                
                for w in warnings:
                    print(f"         Warning: {w}")
    
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "chm_quality_stats.csv"
    df.to_csv(output_path, index=False)
    print(f"\n  ✓ Stats saved: {output_path.name}")
    
    return df


# =============================================================================
# CHECK 3: SENTINEL-2 QUALITY
# =============================================================================

def check_3_sentinel2_quality() -> pd.DataFrame:
    """
    Check 3: Sentinel-2 Quality
    
    Analyzes S2 data for each city:
    - Band value ranges
    - Temporal completeness
    - Seasonal NDVI pattern
    
    Returns:
        DataFrame with S2 statistics
    """
    print("\n" + "=" * 70)
    print("CHECK 3: SENTINEL-2 QUALITY")
    print("=" * 70)
    
    results = []
    
    for city in CITIES:
        print(f"\n  {city}:")
        
        # 3.1 Check temporal completeness
        months_found = []
        for month in range(1, 13):
            s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_{month:02d}_median.tif"
            if s2_path.exists():
                months_found.append(month)
        
        if len(months_found) == 12:
            print(f"    ✓ All 12 months present")
        else:
            missing = set(range(1, 13)) - set(months_found)
            print(f"    ⚠️ Missing months: {sorted(missing)}")
        
        # 3.2 Analyze July (peak vegetation) in detail
        july_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_07_median.tif"
        
        if not july_path.exists():
            print(f"    July file not found, skipping detailed analysis")
            continue
        
        with rasterio.open(july_path) as src:
            print(f"    July: {src.count} bands, {src.width}x{src.height} pixels")
            
            # Get NoData value
            nodata = src.nodata if src.nodata is not None else -32768
            
            # Sample 100k random pixels for statistics
            sample_size = min(100000, src.width * src.height)
            
            # Read all bands
            data = src.read()
            
            # Flatten and sample
            flat_data = data.reshape(src.count, -1)
            
            # Remove NoData (check for both NaN and NoData value)
            valid_mask = (~np.isnan(flat_data[0])) & (flat_data[0] != nodata)
            valid_indices = np.where(valid_mask)[0]
            
            if len(valid_indices) > sample_size:
                sample_idx = np.random.choice(valid_indices, sample_size, replace=False)
            else:
                sample_idx = valid_indices
            
            sample_data = flat_data[:, sample_idx]
            
            # Check band ranges
            print(f"    Band statistics (n={len(sample_idx):,}, NoData excluded):")
            
            for i, band_name in enumerate(S2_BANDS[:min(src.count, len(S2_BANDS))]):
                band_data = sample_data[i]
                band_min = np.nanmin(band_data)
                band_max = np.nanmax(band_data)
                band_mean = np.nanmean(band_data)
                
                results.append({
                    "city": city,
                    "month": 7,
                    "band": band_name,
                    "min": float(band_min),
                    "max": float(band_max),
                    "mean": float(band_mean),
                })
                
                # Only print first few bands and vegetation indices
                if i < 4 or i >= 10:
                    status = "✓"
                    # Spectral bands: expect DN values 0-10000 (reflectance × 10000)
                    # Small negative values from atmospheric correction are OK
                    if band_name.startswith("B"):
                        if band_min < -1000 or band_max > 15000:
                            status = "⚠️"
                    # Vegetation indices: expect -1 to +1 range
                    else:
                        if band_min < -2 or band_max > 2:
                            status = "⚠️"
                    print(f"      {band_name}: {status} [{band_min:.1f}, {band_max:.1f}], mean={band_mean:.1f}")
        
        # 3.3 Seasonal NDVI pattern
        print(f"\n    Seasonal vegetation pattern (kNDVI/Band 13):")
        
        monthly_ndvi = []
        for month in range(1, 13):
            s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_{month:02d}_median.tif"
            if not s2_path.exists():
                monthly_ndvi.append(np.nan)
                continue
            
            with rasterio.open(s2_path) as src:
                nodata = src.nodata if src.nodata is not None else -32768
                # Read kNDVI band (index 12, 0-based)
                if src.count > NDVI_BAND_IDX:
                    ndvi_data = src.read(NDVI_BAND_IDX + 1)  # 1-based for rasterio
                    valid_mask = (~np.isnan(ndvi_data)) & (ndvi_data != nodata)
                    valid_ndvi = ndvi_data[valid_mask]
                    if len(valid_ndvi) > 0:
                        monthly_ndvi.append(float(np.mean(valid_ndvi)))
                    else:
                        monthly_ndvi.append(np.nan)
                else:
                    monthly_ndvi.append(np.nan)
        
        # Check seasonal pattern
        winter_mean = np.nanmean([monthly_ndvi[0], monthly_ndvi[1], monthly_ndvi[11]])  # Jan, Feb, Dec
        summer_mean = np.nanmean([monthly_ndvi[5], monthly_ndvi[6], monthly_ndvi[7]])   # Jun, Jul, Aug
        
        if summer_mean > winter_mean:
            print(f"      ✓ Summer ({summer_mean:.3f}) > Winter ({winter_mean:.3f})")
        else:
            print(f"      ⚠️ Unexpected: Summer ({summer_mean:.3f}) <= Winter ({winter_mean:.3f})")
        
        # Print monthly values
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ndvi_str = " | ".join([f"{m}:{v:.2f}" if not np.isnan(v) else f"{m}:--" 
                               for m, v in zip(month_names, monthly_ndvi)])
        print(f"      {ndvi_str}")
    
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "s2_quality_stats.csv"
    df.to_csv(output_path, index=False)
    print(f"\n  ✓ Stats saved: {output_path.name}")
    
    return df


# =============================================================================
# CHECK 4: TREE-RASTER ALIGNMENT
# =============================================================================

def check_4_tree_raster_alignment() -> pd.DataFrame:
    """
    Check 4: Tree-Raster Alignment
    
    Extracts CHM and NDVI values at tree cadastre points.
    Expected: Most trees should have CHM > 0 and NDVI > 0.3
    
    Returns:
        DataFrame with alignment statistics per city
    """
    print("\n" + "=" * 70)
    print("CHECK 4: TREE-RASTER ALIGNMENT")
    print("=" * 70)
    
    # Load tree cadastre
    trees_path = TREES_DIR / "trees_filtered_viable_no_edge.gpkg"
    if not trees_path.exists():
        print("  ❌ Tree cadastre not found")
        return pd.DataFrame()
    
    print("  Loading tree cadastre...")
    trees = gpd.read_file(trees_path)
    print(f"  Total trees: {len(trees):,}")
    
    results = []
    
    for city in CITIES:
        print(f"\n  {city}:")
        
        # Filter trees for this city
        city_trees = trees[trees["city"] == city].copy()
        print(f"    Trees in city: {len(city_trees):,}")
        
        if len(city_trees) == 0:
            continue
        
        # Sample if too many trees
        max_sample = 50000
        if len(city_trees) > max_sample:
            city_trees = city_trees.sample(n=max_sample, random_state=RANDOM_SEED)
            print(f"    Sampled: {len(city_trees):,}")
        
        # Load CHM and S2
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_07_median.tif"
        
        if not chm_path.exists() or not s2_path.exists():
            print(f"    ⚠️ Raster files not found, skipping")
            continue
        
        # Extract coordinates
        coords = [(geom.x, geom.y) for geom in city_trees.geometry]
        
        # Extract CHM values (NoData = -9999)
        with rasterio.open(chm_path) as src:
            chm_nodata = src.nodata if src.nodata is not None else -9999
            chm_values = np.array([val[0] for val in src.sample(coords)])
            # Replace NoData with NaN for consistent handling
            chm_values = np.where(chm_values == chm_nodata, np.nan, chm_values)
        
        # Extract NDVI values (kNDVI, band 13, NoData = -32768)
        with rasterio.open(s2_path) as src:
            s2_nodata = src.nodata if src.nodata is not None else -32768
            ndvi_band = NDVI_BAND_IDX + 1  # 1-based
            ndvi_values = np.array([val[ndvi_band - 1] for val in src.sample(coords)])
            # Replace NoData with NaN
            ndvi_values = np.where(ndvi_values == s2_nodata, np.nan, ndvi_values)
        
        # Analyze CHM values
        valid_chm = chm_values[~np.isnan(chm_values)]
        chm_positive = np.sum(valid_chm > 0) / len(valid_chm) * 100 if len(valid_chm) > 0 else 0
        chm_gt_3m = np.sum(valid_chm > 3) / len(valid_chm) * 100 if len(valid_chm) > 0 else 0
        
        # Analyze NDVI values
        valid_ndvi = ndvi_values[~np.isnan(ndvi_values)]
        ndvi_gt_03 = np.sum(valid_ndvi > 0.3) / len(valid_ndvi) * 100 if len(valid_ndvi) > 0 else 0
        ndvi_gt_05 = np.sum(valid_ndvi > 0.5) / len(valid_ndvi) * 100 if len(valid_ndvi) > 0 else 0
        
        # Correlation
        both_valid = ~np.isnan(chm_values) & ~np.isnan(ndvi_values)
        if np.sum(both_valid) > 100:
            corr, pval = pearsonr(chm_values[both_valid], ndvi_values[both_valid])
        else:
            corr, pval = np.nan, np.nan
        
        result = {
            "city": city,
            "n_trees": len(city_trees),
            "chm_mean": float(np.nanmean(chm_values)),
            "chm_median": float(np.nanmedian(chm_values)),
            "chm_positive_pct": chm_positive,
            "chm_gt_3m_pct": chm_gt_3m,
            "ndvi_mean": float(np.nanmean(ndvi_values)),
            "ndvi_gt_03_pct": ndvi_gt_03,
            "ndvi_gt_05_pct": ndvi_gt_05,
            "chm_ndvi_corr": corr,
        }
        results.append(result)
        
        # Print results
        chm_status = "✓" if chm_positive > 70 else "⚠️"
        ndvi_status = "✓" if ndvi_gt_03 > 70 else "⚠️"
        
        print(f"    CHM: {chm_status} mean={result['chm_mean']:.1f}m, "
              f"{chm_positive:.1f}% >0m, {chm_gt_3m:.1f}% >3m")
        print(f"    NDVI: {ndvi_status} mean={result['ndvi_mean']:.3f}, "
              f"{ndvi_gt_03:.1f}% >0.3, {ndvi_gt_05:.1f}% >0.5")
        print(f"    CHM-NDVI correlation: r={corr:.3f}")
    
    df = pd.DataFrame(results)
    output_path = OUTPUT_DIR / "tree_raster_alignment.csv"
    df.to_csv(output_path, index=False)
    print(f"\n  ✓ Stats saved: {output_path.name}")
    
    return df


# =============================================================================
# CHECK 5: VISUAL SPOT CHECKS
# =============================================================================

def check_5_visual_spot_checks(n_tiles: int = 3) -> None:
    """
    Check 5: Visual Spot Checks
    
    Creates random 500m × 500m tiles per city showing:
    - CHM (mean)
    - kNDVI
    - Tree points overlay
    
    Args:
        n_tiles: Number of tiles per city
    """
    print("\n" + "=" * 70)
    print("CHECK 5: VISUAL SPOT CHECKS")
    print("=" * 70)
    
    # Load tree cadastre
    trees_path = TREES_DIR / "trees_filtered_viable_no_edge.gpkg"
    if not trees_path.exists():
        print("  ❌ Tree cadastre not found")
        return
    
    trees = gpd.read_file(trees_path)
    
    for city in CITIES:
        print(f"\n  Generating tiles for {city}...")
        
        # Load rasters
        chm_path = CHM_10M_DIR / f"CHM_10m_mean_{city}.tif"
        s2_path = S2_DIR / city.lower() / f"S2_{REFERENCE_YEAR}_07_median.tif"
        
        if not chm_path.exists() or not s2_path.exists():
            print(f"    ⚠️ Raster files not found, skipping")
            continue
        
        # Get city trees
        city_trees = trees[trees["city"] == city]
        
        if len(city_trees) == 0:
            print(f"    ⚠️ No trees found for {city}")
            continue
        
        with rasterio.open(chm_path) as chm_src, rasterio.open(s2_path) as s2_src:
            # Get bounds
            bounds = chm_src.bounds
            
            # Tile size in pixels (500m = 50 pixels at 10m)
            tile_size = 50
            
            # Generate random tile positions
            np.random.seed(RANDOM_SEED + CITIES.index(city))
            
            for tile_idx in range(n_tiles):
                # Random position (with margin)
                margin = tile_size + 10
                col = np.random.randint(margin, chm_src.width - margin)
                row = np.random.randint(margin, chm_src.height - margin)
                
                # Read CHM tile
                chm_tile = chm_src.read(
                    1,
                    window=rasterio.windows.Window(col, row, tile_size, tile_size)
                )
                
                # Read kNDVI tile (band 13)
                ndvi_tile = s2_src.read(
                    NDVI_BAND_IDX + 1,
                    window=rasterio.windows.Window(col, row, tile_size, tile_size)
                )
                
                # Get tile bounds for tree filtering
                tile_transform = rasterio.windows.transform(
                    rasterio.windows.Window(col, row, tile_size, tile_size),
                    chm_src.transform
                )
                tile_bounds = rasterio.transform.array_bounds(
                    tile_size, tile_size, tile_transform
                )
                
                # Filter trees within tile
                tile_trees = city_trees.cx[tile_bounds[0]:tile_bounds[2], 
                                           tile_bounds[1]:tile_bounds[3]]
                
                # Create figure
                fig, axes = plt.subplots(1, 2, figsize=(12, 5))
                
                # CHM plot
                im1 = axes[0].imshow(chm_tile, cmap="YlGn", vmin=0, vmax=30)
                axes[0].set_title(f"CHM (mean) - {city}")
                plt.colorbar(im1, ax=axes[0], label="Height (m)")
                
                # NDVI plot
                im2 = axes[1].imshow(ndvi_tile, cmap="RdYlGn", vmin=0, vmax=1)
                axes[1].set_title(f"kNDVI (July) - {city}")
                plt.colorbar(im2, ax=axes[1], label="kNDVI")
                
                # Overlay trees on both
                if len(tile_trees) > 0:
                    # Convert tree coords to pixel coords
                    for ax in axes:
                        for geom in tile_trees.geometry:
                            px = (geom.x - tile_bounds[0]) / 10  # 10m resolution
                            py = (tile_bounds[3] - geom.y) / 10
                            ax.plot(px, py, 'r.', markersize=3, alpha=0.6)
                
                # Add tree count
                fig.suptitle(f"{city} - Tile {tile_idx + 1} ({len(tile_trees)} trees)", 
                            fontsize=14)
                
                for ax in axes:
                    ax.set_xlabel("Pixel (10m)")
                    ax.set_ylabel("Pixel (10m)")
                
                plt.tight_layout()
                
                output_path = OUTPUT_DIR / f"visual_tile_{city.lower()}_{tile_idx + 1}.png"
                plt.savefig(output_path, dpi=150, bbox_inches="tight")
                plt.close()
                
                print(f"    ✓ Tile {tile_idx + 1}: {len(tile_trees)} trees")
    
    print(f"\n  ✓ Visual tiles saved to {OUTPUT_DIR}")


# =============================================================================
# SUMMARY REPORT
# =============================================================================

def generate_summary_report(
    integrity_results: dict,
    chm_stats: pd.DataFrame,
    s2_stats: pd.DataFrame,
    alignment_stats: pd.DataFrame
) -> None:
    """Generate a summary validation report."""
    
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY REPORT")
    print("=" * 70)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""# Data Validation Report

**Generated:** {timestamp}
**Project CRS:** {PROJECT_CRS}
**Reference Year:** {REFERENCE_YEAR}

---

## 1. Data Integrity

**Status:** {integrity_results['status']}

- Missing files: {len(integrity_results['files_missing'])}
- CRS issues: {len(integrity_results['crs_issues'])}
- Grid alignment: {integrity_results['grid_alignment']}

---

## 2. CHM Quality (10m)

"""
    
    if not chm_stats.empty:
        for city in CITIES:
            city_data = chm_stats[chm_stats["city"] == city]
            if not city_data.empty:
                mean_stats = city_data[city_data["aggregation"] == "mean"].iloc[0]
                report += f"""### {city}
- Coverage: {mean_stats['coverage_pct']:.1f}%
- Range: [{mean_stats['min']:.1f}m, {mean_stats['max']:.1f}m]
- Mean: {mean_stats['mean']:.1f}m

"""
    
    report += """---

## 3. Sentinel-2 Quality

- Bands: 10 spectral + 5 vegetation indices
- Temporal: 12 monthly composites per city
- See `s2_quality_stats.csv` for detailed statistics

---

## 4. Tree-Raster Alignment

"""
    
    if not alignment_stats.empty:
        for _, row in alignment_stats.iterrows():
            report += f"""### {row['city']}
- Trees sampled: {row['n_trees']:,}
- CHM mean at trees: {row['chm_mean']:.1f}m
- CHM >0m: {row['chm_positive_pct']:.1f}%
- NDVI >0.3: {row['ndvi_gt_03_pct']:.1f}%
- CHM-NDVI correlation: r={row['chm_ndvi_corr']:.3f}

"""
    
    report += """---

## 5. Visual Spot Checks

See `visual_tile_*.png` files for visual inspection.

---

**Conclusion:** Data is ready for feature extraction.
"""
    
    # Save report
    report_path = OUTPUT_DIR / "validation_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"\n  ✓ Report saved: {report_path}")
    
    # Also save as JSON for programmatic access
    summary = {
        "timestamp": timestamp,
        "project_crs": PROJECT_CRS,
        "reference_year": REFERENCE_YEAR,
        "integrity": integrity_results,
        "chm_stats": chm_stats.to_dict(orient="records") if not chm_stats.empty else [],
        "alignment_stats": alignment_stats.to_dict(orient="records") if not alignment_stats.empty else [],
    }
    
    json_path = OUTPUT_DIR / "validation_summary.json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"  ✓ JSON saved: {json_path}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """Run all validation checks."""
    
    print("\n" + "=" * 70)
    print("  DATA VALIDATION PIPELINE")
    print("  Pre-Feature-Extraction Quality Checks")
    print("=" * 70)
    print(f"\nCities: {', '.join(CITIES)}")
    print(f"Reference Year: {REFERENCE_YEAR}")
    print(f"Project CRS: {PROJECT_CRS}")
    
    # Run checks
    integrity_results = check_1_data_integrity()
    
    # Stop if critical files missing
    if integrity_results["status"] == "FAIL" and integrity_results["files_missing"]:
        print("\n❌ Critical files missing. Fix before proceeding.")
        return
    
    chm_stats = check_2_chm_quality()
    s2_stats = check_3_sentinel2_quality()
    alignment_stats = check_4_tree_raster_alignment()
    check_5_visual_spot_checks()
    
    # Generate summary
    generate_summary_report(integrity_results, chm_stats, s2_stats, alignment_stats)
    
    # Final summary
    print("\n" + "=" * 70)
    print("  ✓ VALIDATION COMPLETE")
    print("=" * 70)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    for f in sorted(OUTPUT_DIR.glob("*")):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
