"""
Sentinel-2 Coverage Validation Script

Erstellt eine CSV mit Qualitätsmetriken für alle Sentinel-2 Dateien.
Enthält Cloud-Free-Coverage, Bandanzahl, Dateigröße etc.

Usage:
    uv run python scripts/sentinel2/validate_coverage.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BOUNDARIES_BUFFERED_PATH,
    CITIES,
    SENTINEL2_DIR,
)

OUTPUT_CSV = SENTINEL2_DIR / "coverage_report.csv"
MONTHS = [f"{m:02d}" for m in range(1, 13)]


def analyze_sentinel2_file(file_path: Path, city_geometry) -> dict:
    """
    Analysiert eine Sentinel-2 GeoTIFF Datei.
    """
    result = {
        "file": file_path.name,
        "city": file_path.parent.name,
        "month": None,
        "exists": file_path.exists(),
        "file_size_mb": None,
        "bands": None,
        "width": None,
        "height": None,
        "resolution_x": None,
        "resolution_y": None,
        "crs": None,
        "dtype": None,
        "nodata": None,
        "pixels_total": None,
        "pixels_in_city": None,
        "pixels_with_data": None,
        "coverage_percent": None,
        "min_value": None,
        "max_value": None,
        "mean_value": None,
    }
    
    # Extrahiere Monat aus Dateiname
    try:
        result["month"] = file_path.stem.split("_")[2]
    except (IndexError, AttributeError):
        pass
    
    if not file_path.exists():
        return result
    
    result["file_size_mb"] = round(file_path.stat().st_size / (1024 * 1024), 2)
    
    try:
        with rasterio.open(file_path) as src:
            result["bands"] = src.count
            result["width"] = src.width
            result["height"] = src.height
            result["resolution_x"] = abs(src.transform.a)
            result["resolution_y"] = abs(src.transform.e)
            result["crs"] = str(src.crs)
            result["dtype"] = str(src.dtypes[0])
            result["nodata"] = src.nodata
            result["pixels_total"] = src.width * src.height
            
            city_mask = geometry_mask(
                [city_geometry],
                out_shape=(src.height, src.width),
                transform=src.transform,
                invert=True
            )
            pixels_in_city = np.sum(city_mask)
            result["pixels_in_city"] = int(pixels_in_city)
            
            data = src.read(1)
            valid_mask = (data != src.nodata) & (data != 0) & ~np.isnan(data) if src.nodata is not None else (data != 0) & ~np.isnan(data)
            
            pixels_with_data_in_city = np.sum(valid_mask & city_mask)
            result["pixels_with_data"] = int(pixels_with_data_in_city)
            
            if pixels_in_city > 0:
                result["coverage_percent"] = round(100 * pixels_with_data_in_city / pixels_in_city, 1)
            
            valid_data = data[valid_mask]
            if len(valid_data) > 0:
                result["min_value"] = round(float(np.min(valid_data)), 4)
                result["max_value"] = round(float(np.max(valid_data)), 4)
                result["mean_value"] = round(float(np.mean(valid_data)), 4)
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    """Hauptfunktion: Analysiert alle Sentinel-2 Dateien."""
    
    print("=" * 60)
    print("SENTINEL-2 COVERAGE VALIDATION")
    print("=" * 60)
    
    # Lade Stadtgrenzen (500m Buffer für konsistente Vergleichsbasis)
    if not BOUNDARIES_BUFFERED_PATH.exists():
        print(f"❌ Stadtgrenzen nicht gefunden: {BOUNDARIES_BUFFERED_PATH}")
        return
    
    boundaries = gpd.read_file(BOUNDARIES_BUFFERED_PATH)
    city_geometries = {row["gen"]: row.geometry for _, row in boundaries.iterrows()}
    
    results = []
    
    for city in CITIES:
        if city not in city_geometries:
            print(f"\n📍 {city}")
            print("  ⚠️  Stadt nicht in Boundaries gefunden")
            continue
        
        city_lower = city.lower()
        print(f"\n📍 {city}")
        
        city_dir = SENTINEL2_DIR / city_lower
        if not city_dir.exists():
            print(f"  ⚠️  Verzeichnis nicht gefunden: {city_dir}")
            continue
        
        city_geom = city_geometries[city]
        
        # Analysiere alle Monate
        for month in MONTHS:
            file_path = city_dir / f"S2_2021_{month}_median.tif"
            result = analyze_sentinel2_file(file_path, city_geom)
            results.append(result)
            
            if result["exists"]:
                print(f"  {month}: Coverage={result.get('coverage_percent', 'N/A')}%, "
                      f"Bands={result.get('bands', 'N/A')}, Size={result.get('file_size_mb', 'N/A')}MB")
            else:
                print(f"  {month}: ❌ Nicht vorhanden")
    
    # Erstelle DataFrame und speichere CSV
    df = pd.DataFrame(results).sort_values(["city", "month"])
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Report gespeichert: {OUTPUT_CSV}")
    
    # Zusammenfassung
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    
    existing = df[df["exists"]]
    if len(existing) == 0:
        print("\nKeine Dateien vorhanden!")
        print("Fertig!")
        return
    
    print(f"\nVorhandene Dateien: {len(existing)} / {len(df)}")
    
    # Coverage-Statistik pro Stadt
    print("\nCoverage nach Stadt:")
    for city in CITIES:
        city_data = existing[existing["city"] == city.lower()]
        if len(city_data) > 0:
            cov = city_data["coverage_percent"]
            print(f"  {city:10s}: Mean={cov.mean():.1f}%, Min={cov.min():.1f}%, Max={cov.max():.1f}%")
    
    # Problematische Monate (Coverage < 50%)
    low_coverage = existing[existing["coverage_percent"] < 50]
    if len(low_coverage) > 0:
        print("\n⚠️  Monate mit Coverage < 50%:")
        for _, row in low_coverage.iterrows():
            print(f"  {row['city']}/{row['month']}: {row['coverage_percent']}%")
    
    print("\nFertig!")


if __name__ == "__main__":
    main()
