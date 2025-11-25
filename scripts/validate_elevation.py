"""Validate elevation data files."""
import rasterio
import numpy as np
from pathlib import Path

files = {
    "Hamburg DOM": Path("data/raw/hamburg/dom_1m.tif"),
    "Hamburg DGM": Path("data/raw/hamburg/dgm_1m.tif"),
    "Berlin DOM": Path("data/raw/berlin/dom_1m.tif"),
    "Berlin DGM": Path("data/raw/berlin/dgm_1m.tif"),
    "Rostock DOM": Path("data/raw/rostock/dom_1m.tif"),
    "Rostock DGM": Path("data/raw/rostock/dgm_1m.tif"),
}

print("=" * 80)
print("ELEVATION DATA VALIDATION")
print("=" * 80)
print()

# Check 1: File existence
print("✓ CHECK 1: All 6 files exist")
for name, path in files.items():
    exists = "✓" if path.exists() else "✗"
    size_mb = path.stat().st_size / (1024**2) if path.exists() else 0
    print(f"  {exists} {name:20} {size_mb:8.1f} MB")
print()

# Check 2: CRS validation
print("✓ CHECK 2: CRS is EPSG:25832")
for name, path in files.items():
    if not path.exists():
        continue
    with rasterio.open(path) as src:
        crs_ok = "✓" if str(src.crs) == "EPSG:25832" else f"✗ {src.crs}"
        print(f"  {crs_ok} {name:20} {src.width}x{src.height} pixels")
print()

# Check 3: Data statistics
print("✓ CHECK 3: Data ranges and statistics")
for name, path in files.items():
    if not path.exists():
        continue
    with rasterio.open(path) as src:
        # Sample data (read first 1000x1000 pixels)
        window = ((0, min(1000, src.height)), (0, min(1000, src.width)))
        data = src.read(1, window=window, masked=True)
        data_copy = np.array(data, copy=True)  # Make writable copy

        min_val = float(np.nanmin(data_copy))
        max_val = float(np.nanmax(data_copy))
        mean_val = float(np.nanmean(data_copy))

        has_negative = "⚠️  HAS NEGATIVES" if min_val < 0 else ""

        print(f"  {name:20} min={min_val:7.2f}  max={max_val:7.2f}  mean={mean_val:7.2f}  {has_negative}")
print()

# Check 4: DOM > DGM sanity check
print("✓ CHECK 4: DOM > DGM (sanity check)")
cities = ["hamburg", "berlin", "rostock"]
for city in cities:
    dom_path = Path(f"data/raw/{city}/dom_1m.tif")
    dgm_path = Path(f"data/raw/{city}/dgm_1m.tif")

    if not (dom_path.exists() and dgm_path.exists()):
        continue

    with rasterio.open(dom_path) as dom_src, rasterio.open(dgm_path) as dgm_src:
        # Sample 1000x1000 window
        window = ((0, min(1000, dom_src.height)), (0, min(1000, dom_src.width)))
        dom_data = dom_src.read(1, window=window, masked=True)
        dgm_data = dgm_src.read(1, window=window, masked=True)

        # Check if DOM > DGM in most places
        diff = np.array(dom_data - dgm_data, copy=True)
        positive_pct = (diff > 0).sum() / diff.size * 100

        status = "✓" if positive_pct > 50 else "⚠️"
        mean_diff = float(np.nanmean(diff))

        print(f"  {status} {city.capitalize():10} DOM-DGM mean={mean_diff:6.2f}m  ({positive_pct:.1f}% positive)")

print()
print("=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
