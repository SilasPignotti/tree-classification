# Data Validation Report

**Generated:** 2025-12-10 02:11:41
**Project CRS:** EPSG:25832
**Reference Year:** 2021

---

## 1. Data Integrity

**Status:** PASS

- Missing files: 0
- CRS issues: 0
- Grid alignment: {'Berlin': 'ALIGNED', 'Hamburg': 'ALIGNED', 'Rostock': 'ALIGNED'}

---

## 2. CHM Quality (10m)

### Berlin
- Coverage: 99.5%
- Range: [0.0m, 49.9m]
- Mean: 6.5m

### Hamburg
- Coverage: 97.1%
- Range: [0.0m, 50.0m]
- Mean: 4.0m

### Rostock
- Coverage: 99.7%
- Range: [0.0m, 49.6m]
- Mean: 5.0m

---

## 3. Sentinel-2 Quality

- Bands: 10 spectral + 5 vegetation indices
- Temporal: 12 monthly composites per city
- See `s2_quality_stats.csv` for detailed statistics

---

## 4. Tree-Raster Alignment

### Berlin
- Trees sampled: 50,000
- CHM mean at trees: 8.2m
- CHM >0m: 100.0%
- NDVI >0.3: 70.7%
- CHM-NDVI correlation: r=0.582

### Hamburg
- Trees sampled: 50,000
- CHM mean at trees: 6.0m
- CHM >0m: 99.9%
- NDVI >0.3: 49.4%
- CHM-NDVI correlation: r=0.368

### Rostock
- Trees sampled: 50,000
- CHM mean at trees: 5.7m
- CHM >0m: 99.7%
- NDVI >0.3: 70.6%
- CHM-NDVI correlation: r=0.481

---

## 5. Visual Spot Checks

See `visual_tile_*.png` files for visual inspection.

---

**Conclusion:** Data is ready for feature extraction.
