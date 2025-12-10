"""
CHM Resampling Script

Resampelt die 1m CHM auf das exakte Sentinel-2 Grid (10m).
Die 1m CHM bleiben erhalten für eventuelle Baumkataster-Korrekturen.

Usage:
    uv run python scripts/chm/resample_chm.py
"""

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from rasterio.features import geometry_mask
import geopandas as gpd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import CHM_DIR, CITIES, SENTINEL2_DIR, BOUNDARIES_DIR

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_DIR = CHM_DIR / "processed"
OUTPUT_DIR = CHM_DIR / "processed" / "CHM_10m"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NODATA = -9999.0

# Referenz-Monat für Sentinel-2 Grid (Juli hat beste Vegetationsabdeckung)
REFERENCE_MONTH = "07"


# =============================================================================
# FUNCTIONS
# =============================================================================


def get_sentinel_reference(city: str) -> tuple[tuple, rasterio.Affine, rasterio.CRS]:
    """
    Lädt Grid-Eigenschaften vom Sentinel-2 Referenzbild.

    Args:
        city: Stadtname

    Returns:
        Tuple mit (shape, transform, crs)
    """
    # Suche Sentinel-2 Referenzbild
    s2_dir = SENTINEL2_DIR / city.lower()
    reference_file = s2_dir / f"S2_2021_{REFERENCE_MONTH}_median.tif"

    if not reference_file.exists():
        # Fallback: erstes verfügbares Bild
        s2_files = list(s2_dir.glob("S2_*.tif"))
        if not s2_files:
            raise FileNotFoundError(f"Keine Sentinel-2 Daten gefunden für {city}")
        reference_file = s2_files[0]

    with rasterio.open(reference_file) as src:
        return (src.height, src.width), src.transform, src.crs


def resample_chm_aggregation(
    src_data: np.ndarray,
    src_transform: rasterio.Affine,
    src_crs: rasterio.CRS,
    dst_shape: tuple,
    dst_transform: rasterio.Affine,
    dst_crs: rasterio.CRS,
    agg_method: str = "mean",
) -> np.ndarray:
    """
    Resampelt CHM mit verschiedenen Aggregationsmethoden via rasterio reproject.

    Args:
        src_data: Quell-Daten (1m)
        src_transform: Quell-Transform
        src_crs: Quell-CRS
        dst_shape: Ziel-Shape (height, width)
        dst_transform: Ziel-Transform
        dst_crs: Ziel-CRS
        agg_method: 'mean', 'max', oder 'std'

    Returns:
        Resampeltes Array
    """
    dst_data = np.full(dst_shape, np.nan, dtype=np.float32)

    # Wähle Resampling-Methode
    if agg_method == "mean":
        resampling_method = Resampling.average
    elif agg_method == "max":
        resampling_method = Resampling.max
    elif agg_method == "std":
        # rasterio hat keinen std, daher nutzen wir average als Fallback
        resampling_method = Resampling.average
    else:
        raise ValueError(f"Unbekannte Aggregationsmethode: {agg_method}")

    # Für std: nutze block_reduce Alternative mit scipy
    if agg_method == "std":
        # Berechne Blockgröße basierend auf den Transforms
        src_pixel_size = src_transform.a
        dst_pixel_size = dst_transform.a
        block_size = int(dst_pixel_size / src_pixel_size)

        print(f"    Block-Größe: {block_size}x{block_size}")
        print(f"    Nutze scipy-basierte Block-Aggregation...")

        # Berechne Std via Manual Loop über Blöcke (mit numpy vectorization wo möglich)
        dst_height, dst_width = dst_shape
        dst_data = np.full(dst_shape, np.nan, dtype=np.float32)

        for i in range(0, dst_height):
            for j in range(0, dst_width):
                y_start = i * block_size
                y_end = min(y_start + block_size, src_data.shape[0])
                x_start = j * block_size
                x_end = min(x_start + block_size, src_data.shape[1])

                block = src_data[y_start:y_end, x_start:x_end]
                valid_values = block[~np.isnan(block)]

                if len(valid_values) > 1:
                    dst_data[i, j] = np.std(valid_values)
                elif len(valid_values) == 1:
                    dst_data[i, j] = 0.0  # Std von einem Wert ist 0

    else:
        # Für mean und max: nutze rasterio reproject
        reproject(
            source=src_data.astype(np.float32),
            destination=dst_data,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=resampling_method,
        )

    return dst_data


def resample_chm(
    input_path: Path,
    output_path: Path,
    dst_shape: tuple,
    dst_transform: rasterio.Affine,
    dst_crs: rasterio.CRS,
    agg_method: str = "mean",
    city: str = None,
) -> dict:
    """
    Resampelt CHM auf Ziel-Grid mit angegebener Aggregationsmethode.
    Coverage wird nur für Stadtgrenzen berechnet.

    Args:
        input_path: Pfad zur 1m CHM
        output_path: Pfad für 10m CHM
        dst_shape: Ziel-Shape (height, width)
        dst_transform: Ziel-Transform
        dst_crs: Ziel-CRS
        agg_method: 'mean', 'max', oder 'std'
        city: Stadtname für Grenzen-basierte Coverage

    Returns:
        Dict mit Statistiken
    """
    with rasterio.open(input_path) as src:
        src_data = src.read(1)
        src_nodata = src.nodata
        src_transform = src.transform
        src_crs = src.crs

        # NoData zu NaN für Resampling
        if src_nodata is not None:
            src_data = np.where(np.isclose(src_data, src_nodata), np.nan, src_data)

        src_shape = src.shape
        src_height = src.height
        src_width = src.width

    # Resample mit angegebener Methode
    dst_data = resample_chm_aggregation(
        src_data, src_transform, src_crs, dst_shape, dst_transform, dst_crs, agg_method
    )

    # NaN zurück zu NoData
    dst_output = np.where(np.isnan(dst_data), NODATA, dst_data).astype(np.float32)

    # Speichern
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": dst_shape[1],
        "height": dst_shape[0],
        "count": 1,
        "crs": dst_crs,
        "transform": dst_transform,
        "nodata": NODATA,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(dst_output, 1)

    # Statistiken berechnen mit Stadtgrenzen-basiertem Coverage
    valid_pixels = np.sum(~np.isnan(dst_data))
    total_pixels = dst_data.size
    
    # Default: Coverage über gesamtes Grid
    coverage_percent = round(100 * valid_pixels / total_pixels, 2)
    
    # Berechne Coverage basierend auf Stadtgrenzen
    if city:
        boundary_file = BOUNDARIES_DIR / "city_boundaries.gpkg"
        if boundary_file.exists():
            try:
                gdf = gpd.read_file(boundary_file)
                
                # Finde die richtige Stadt über den Namen in der 'gen' Spalte
                city_boundary = None
                city_lower = city.lower()
                
                for i, row in gdf.iterrows():
                    gen = str(row.get('gen', '')).lower()
                    if city_lower in gen:
                        city_boundary = gdf.iloc[[i]]
                        break
                
                if city_boundary is not None and not city_boundary.empty:
                    # Erstelle Maske für Stadtgrenzen mit korrektem Parameter
                    city_mask = geometry_mask(
                        city_boundary.geometry,
                        out_shape=dst_shape,  # korrekter Parameter-Name
                        transform=dst_transform,
                        all_touched=True,
                    )
                    # city_mask: True = außerhalb, False = innerhalb
                    data_in_city = dst_data.copy()
                    data_in_city[city_mask] = np.nan
                    
                    # Coverage: Gültige Pixel / Gesamtpixel in der Stadt
                    valid_in_city = np.sum(~np.isnan(data_in_city))
                    total_in_city = np.sum(~city_mask)  # Alle Pixel in der Stadt
                    
                    if total_in_city > 0:
                        coverage_percent = round(100 * valid_in_city / total_in_city, 2)
            except Exception as e:
                pass  # Fallback zu globalem Coverage bei Fehler

    stats = {
        "input_shape": (src_height, src_width),
        "output_shape": dst_shape,
        "valid_pixels": int(valid_pixels),
        "total_pixels": int(total_pixels),
        "coverage_percent": coverage_percent,
        "agg_method": agg_method,
    }

    if valid_pixels > 0:
        valid_values = dst_data[~np.isnan(dst_data)]
        stats["min"] = round(float(np.min(valid_values)), 2)
        stats["max"] = round(float(np.max(valid_values)), 2)
        stats["mean"] = round(float(np.mean(valid_values)), 2)
        stats["std"] = round(float(np.std(valid_values)), 2)

    # NaN zurück zu NoData
    dst_output = np.where(np.isnan(dst_data), NODATA, dst_data).astype(np.float32)

    # Speichern
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": dst_shape[1],
        "height": dst_shape[0],
        "count": 1,
        "crs": dst_crs,
        "transform": dst_transform,
        "nodata": NODATA,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(dst_output, 1)

    return stats


def process_city(city: str) -> dict:
    """Verarbeitet eine Stadt und berechnet mean, max, std."""
    print(f"\n{'=' * 60}")
    print(f"Resample CHM für {city}")
    print(f"{'=' * 60}")

    # 1. Lade Sentinel-2 Referenz-Grid
    print("\n[1/4] Lade Sentinel-2 Referenz-Grid...")
    dst_shape, dst_transform, dst_crs = get_sentinel_reference(city)
    print(f"  Ziel-Shape: {dst_shape[0]} x {dst_shape[1]} (10m)")
    print(f"  Ziel-CRS: {dst_crs}")

    input_path = INPUT_DIR / f"CHM_1m_{city}.tif"
    if not input_path.exists():
        raise FileNotFoundError(f"CHM nicht gefunden: {input_path}")

    # 2. Berechne die drei Aggregationsmethoden
    print("\n[2/4] Berechne CHM-Aggregationen (1m → 10m)...")
    methods = ["mean", "max", "std"]
    all_stats = {}

    for method in methods:
        print(f"\n  [{method.upper()}] Aggregationsmethode...")
        output_path = OUTPUT_DIR / f"CHM_10m_{method}_{city}.tif"
        
        stats = resample_chm(input_path, output_path, dst_shape, dst_transform, dst_crs, method, city=city)
        all_stats[method] = stats

        file_size_mb = output_path.stat().st_size / (1024**2)
        print(f"    Input:    {stats['input_shape'][0]} x {stats['input_shape'][1]} (1m)")
        print(f"    Output:   {stats['output_shape'][0]} x {stats['output_shape'][1]} (10m)")
        print(f"    Coverage: {stats['coverage_percent']:.1f}%")
        print(f"    Range:    {stats['min']:.2f}m - {stats['max']:.2f}m")
        print(f"    Mittel:   {stats['mean']:.2f}m")
        if method == "std":
            print(f"    Std.abw: {stats['std']:.2f}m")
        print(f"    Datei:    {output_path.name} ({file_size_mb:.1f} MB)")

    # 3. Verifizierung
    print("\n[3/4] Verifiziere Grid-Alignment...")
    with rasterio.open(OUTPUT_DIR / f"CHM_10m_mean_{city}.tif") as chm_src:
        chm_transform = chm_src.transform
        chm_shape = (chm_src.height, chm_src.width)

    transform_match = np.allclose(
        [dst_transform.a, dst_transform.b, dst_transform.c,
         dst_transform.d, dst_transform.e, dst_transform.f],
        [chm_transform.a, chm_transform.b, chm_transform.c,
         chm_transform.d, chm_transform.e, chm_transform.f],
        atol=1e-6
    )
    shape_match = chm_shape == dst_shape

    if transform_match and shape_match:
        print("  ✓ Grid exakt identisch mit Sentinel-2")
    else:
        print("  ⚠ Grid-Abweichung!")
        if not shape_match:
            print(f"    Shape: CHM={chm_shape}, S2={dst_shape}")
        if not transform_match:
            print(f"    Transform unterschiedlich")

    # 4. Plausibilitätsprüfung
    print("\n[4/4] Plausibilitätsprüfung...")
    mean_stats = all_stats["mean"]
    max_stats = all_stats["max"]
    std_stats = all_stats["std"]

    checks = [
        ("Mean < Max", mean_stats["mean"] < max_stats["mean"], True),
        ("Max Min >= Mean Min", max_stats["min"] >= mean_stats["min"], True),
        ("Std >= 0", std_stats["min"] >= 0, True),
        ("CHM_std Max plausibel", std_stats["max"] < 20, True),  # Std sollte nicht zu groß sein
    ]

    for check_name, condition, expected in checks:
        status = "✓" if condition == expected else "✗"
        print(f"  {status} {check_name}: {condition}")

    return {
        "city": city,
        "mean": mean_stats,
        "max": max_stats,
        "std": std_stats,
    }


def main():
    """Hauptfunktion: Resampelt CHM für alle Städte."""
    print("=" * 70)
    print("CHM RESAMPLING (1m → 10m Sentinel-2 Grid)")
    print("=" * 70)
    print()
    print("Resampling-Methoden: mean (Average), max (Maximum), std (Standardabweichung)")
    print("Die 1m CHM bleiben erhalten.")
    print()

    all_results = []

    for city in CITIES:
        try:
            result = process_city(city)
            all_results.append(result)
        except Exception as e:
            print(f"\n✗ FEHLER bei {city}: {e}")
            import traceback
            traceback.print_exc()

    # Zusammenfassung
    print("\n")
    print("=" * 70)
    print("ZUSAMMENFASSUNG")
    print("=" * 70)
    print()

    for method in ["mean", "max", "std"]:
        print(f"\n{'─' * 70}")
        print(f"CHM_10m_{method.upper()}")
        print(f"{'─' * 70}")
        print(f"{'Stadt':<12} {'Coverage':>10} {'Min':>8} {'Mean':>8} {'Max':>8}")
        print("-" * 50)

        for result in all_results:
            stats = result[method]
            print(
                f"{result['city']:<12} "
                f"{stats['coverage_percent']:>9.1f}% "
                f"{stats['min']:>7.2f}m "
                f"{stats['mean']:>7.2f}m "
                f"{stats['max']:>7.2f}m"
            )

    print()
    print("=" * 70)
    print("Ausgabeverzeichnis:", OUTPUT_DIR)
    print("=" * 70)
    print()
    print("Erzeugte Dateien:")
    for city in CITIES:
        print(f"  • CHM_10m_mean_{city}.tif")
        print(f"  • CHM_10m_max_{city}.tif")
        print(f"  • CHM_10m_std_{city}.tif")
    print()
    print("=" * 70)
    print("✓ CHM-Resampling abgeschlossen")
    print("=" * 70)


if __name__ == "__main__":
    main()
