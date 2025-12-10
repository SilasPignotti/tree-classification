"""
CHM Creation Script

Berechnet Canopy Height Models (CHM = DOM - DGM) für Hamburg, Berlin und Rostock.
Voraussetzung: DOM und DGM sind bereits harmonisiert (gleiche Dimensionen, NoData=-9999).

Usage:
    uv run python scripts/chm/create_chm.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import BOUNDARIES_PATH, CHM_DIR, CHM_RAW_DIR, CITIES

# =============================================================================
# CONFIGURATION
# =============================================================================

OUTPUT_DIR = CHM_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NODATA = -9999.0


# =============================================================================
# FUNCTIONS
# =============================================================================


def load_raster(path: Path) -> tuple[np.ndarray, dict]:
    """Lädt Raster und gibt Daten + Profil zurück."""
    with rasterio.open(path) as src:
        data = src.read(1)
        profile = src.profile.copy()

        # NoData zu NaN konvertieren für Berechnungen
        if src.nodata is not None:
            data = np.where(np.isclose(data, src.nodata), np.nan, data).astype(np.float32)

    return data, profile


def compute_chm(dom: np.ndarray, dgm: np.ndarray) -> np.ndarray:
    """Berechnet CHM = DOM - DGM."""
    chm = dom - dgm
    # NaN wo entweder DOM oder DGM NaN ist
    chm[np.isnan(dom) | np.isnan(dgm)] = np.nan
    return chm


def compute_statistics(chm: np.ndarray, city_mask: np.ndarray, city: str) -> dict:
    """
    Berechnet Statistiken für CHM innerhalb der Stadtgrenzen (ohne Buffer).

    Args:
        chm: CHM array
        city_mask: Boolean-Maske (True = innerhalb Stadtgrenze)
        city: Stadtname

    Returns:
        Dict mit Statistiken
    """
    # Nur Pixel innerhalb der Stadtgrenze
    chm_city = chm[city_mask]
    valid_mask = ~np.isnan(chm_city)
    valid_values = chm_city[valid_mask]

    pixels_total = city_mask.sum()
    pixels_valid = valid_mask.sum()
    coverage_pct = 100 * pixels_valid / pixels_total if pixels_total > 0 else 0

    # Statistiken
    stats = {
        "city": city,
        "pixels_in_boundary": int(pixels_total),
        "pixels_valid": int(pixels_valid),
        "coverage_percent": round(coverage_pct, 2),
        "min": round(float(np.min(valid_values)), 2) if len(valid_values) > 0 else None,
        "max": round(float(np.max(valid_values)), 2) if len(valid_values) > 0 else None,
        "mean": round(float(np.mean(valid_values)), 2) if len(valid_values) > 0 else None,
        "median": round(float(np.median(valid_values)), 2) if len(valid_values) > 0 else None,
        "std": round(float(np.std(valid_values)), 2) if len(valid_values) > 0 else None,
        "p25": (
            round(float(np.percentile(valid_values, 25)), 2) if len(valid_values) > 0 else None
        ),
        "p75": (
            round(float(np.percentile(valid_values, 75)), 2) if len(valid_values) > 0 else None
        ),
        "p95": (
            round(float(np.percentile(valid_values, 95)), 2) if len(valid_values) > 0 else None
        ),
        "negative_pixels": int(np.sum(valid_values < 0)) if len(valid_values) > 0 else 0,
        "pixels_above_60m": int(np.sum(valid_values > 60)) if len(valid_values) > 0 else 0,
    }

    return stats


def save_chm(chm: np.ndarray, profile: dict, output_path: Path) -> None:
    """Speichert CHM als GeoTIFF."""
    # NaN zurück zu NoData konvertieren
    chm_output = np.where(np.isnan(chm), NODATA, chm).astype(np.float32)

    profile.update(
        dtype=rasterio.float32,
        nodata=NODATA,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(chm_output, 1)


def process_city(city: str) -> dict | None:
    """Verarbeitet eine Stadt und gibt Statistiken zurück. Skippt bereits verarbeitete Städte."""
    print(f"\n{'=' * 60}")
    print(f"Verarbeite {city}")
    print(f"{'=' * 60}")

    city_lower = city.lower()
    dom_path = CHM_RAW_DIR / city_lower / "dom_1m.tif"
    dgm_path = CHM_RAW_DIR / city_lower / "dgm_1m.tif"
    chm_output_path = OUTPUT_DIR / f"CHM_1m_{city}.tif"
    stats_path = OUTPUT_DIR / f"stats_{city_lower}.json"

    # Prüfe ob CHM und Stats bereits vorhanden sind
    if chm_output_path.exists() and stats_path.exists():
        print(f"✓ {city} bereits verarbeitet (CHM und Stats existieren)")
        try:
            with open(stats_path, "r") as f:
                stats = json.load(f)
            return stats
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der Stats: {e}. Neu berechnen...")

    # Falls Stats fehlen aber CHM existiert: Lade CHM und berechne nur Stats
    if chm_output_path.exists() and not stats_path.exists():
        print(f"✓ CHM existiert bereits")
        print("\n[1/2] Lade CHM...")
        try:
            chm, _ = load_raster(chm_output_path)
        except Exception as e:
            print(f"⚠️ CHM-Datei beschädigt ({e}). Lösche und erstelle neu...")
            try:
                chm_output_path.unlink()
            except Exception:
                pass
            # Fortfahren zur vollständigen Neuerstellung
            chm = None
        
        if chm is not None:
            print("\n[2/2] Erstelle Stadtgrenzen-Maske und berechne Statistiken...")
            boundaries = gpd.read_file(BOUNDARIES_PATH)
            city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]
            
            with rasterio.open(chm_output_path) as src:
                city_mask = ~geometry_mask([city_geom], out_shape=chm.shape, transform=src.transform)
            
            stats = compute_statistics(chm, city_mask, city)
            
            print(f"\n  Ergebnis für {city}:")
            print(f"    Coverage: {stats['coverage_percent']:.1f}%")
            print(f"    Mean: {stats['mean']:.2f}m")
            print(f"    Median: {stats['median']:.2f}m")
            print(f"    Min/Max: {stats['min']:.2f}m / {stats['max']:.2f}m")
            print(f"    Negative Pixel: {stats['negative_pixels']:,}")
            print(f"    Pixel >60m: {stats['pixels_above_60m']:,}")
            
            # Speichere Statistiken
            with open(stats_path, "w") as f:
                json.dump(stats, f, indent=2)
            print(f"\n  ✓ Statistiken gespeichert: {stats_path.name}")
            
            return stats

    # 1. Lade DOM und DGM
    print("\n[1/4] Lade DOM und DGM...")
    dom, dom_profile = load_raster(dom_path)
    dgm, dgm_profile = load_raster(dgm_path)

    # Prüfe ob Dimensionen übereinstimmen (sollten nach Harmonisierung identisch sein)
    if dom.shape != dgm.shape:
        raise ValueError(
            f"Shape mismatch: DOM {dom.shape} vs DGM {dgm.shape}. "
            "Bitte zuerst harmonize_elevation.py ausführen!"
        )

    print(f"  Shape: {dom.shape[0]} x {dom.shape[1]}")
    print(f"  DOM valid: {np.sum(~np.isnan(dom)):,} pixels")
    print(f"  DGM valid: {np.sum(~np.isnan(dgm)):,} pixels")

    # 2. Berechne CHM
    print("\n[2/4] Berechne CHM (DOM - DGM)...")
    chm = compute_chm(dom, dgm)
    valid_chm = np.sum(~np.isnan(chm))
    print(f"  CHM valid: {valid_chm:,} pixels")

    # 3. Erstelle Stadtgrenzen-Maske (ohne Buffer)
    print("\n[3/4] Erstelle Stadtgrenzen-Maske...")
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]

    with rasterio.open(dom_path) as src:
        city_mask = ~geometry_mask([city_geom], out_shape=dom.shape, transform=src.transform)

    print(f"  Pixel innerhalb Stadtgrenze: {city_mask.sum():,}")

    # 4. Berechne Statistiken (nur innerhalb Stadtgrenze)
    print("\n[4/4] Berechne Statistiken...")
    stats = compute_statistics(chm, city_mask, city)

    print(f"\n  Ergebnis für {city}:")
    print(f"    Coverage: {stats['coverage_percent']:.1f}%")
    print(f"    Mean: {stats['mean']:.2f}m")
    print(f"    Median: {stats['median']:.2f}m")
    print(f"    Min/Max: {stats['min']:.2f}m / {stats['max']:.2f}m")
    print(f"    Negative Pixel: {stats['negative_pixels']:,}")
    print(f"    Pixel >60m: {stats['pixels_above_60m']:,}")

    # 5. Speichere CHM
    output_path = OUTPUT_DIR / f"CHM_1m_{city}.tif"
    print(f"\n  Speichere CHM: {output_path.name}")
    save_chm(chm, dom_profile, output_path)

    file_size_mb = output_path.stat().st_size / (1024**2)
    print(f"  ✓ Gespeichert ({file_size_mb:.1f} MB)")

    # Speichere Statistiken als JSON
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  ✓ Statistiken gespeichert: {stats_path.name}")

    return stats


def main():
    """Hauptfunktion: Verarbeitet alle Städte."""
    print("=" * 70)
    print("CHM CREATION")
    print("=" * 70)
    print()
    print("Voraussetzung: DOM/DGM müssen harmonisiert sein!")
    print("  → Gleiche Dimensionen")
    print("  → NoData = -9999")
    print()

    all_stats = []

    for city in CITIES:
        stats = process_city(city)
        if stats is not None:  # Nur nicht-übersprungene Städte zur Zusammenfassung hinzufügen
            all_stats.append(stats)

    # Zusammenfassung
    print("\n")
    print("=" * 70)
    print("ZUSAMMENFASSUNG")
    print("=" * 70)
    print()
    print(f"{'Stadt':<12} {'Coverage':>10} {'Mean':>8} {'Median':>8} {'Neg.':>10} {'>60m':>10}")
    print("-" * 70)

    for stats in all_stats:
        print(
            f"{stats['city']:<12} "
            f"{stats['coverage_percent']:>9.1f}% "
            f"{stats['mean']:>7.2f}m "
            f"{stats['median']:>7.2f}m "
            f"{stats['negative_pixels']:>10,} "
            f"{stats['pixels_above_60m']:>10,}"
        )

    print()
    print("=" * 70)
    print("✓ CHM-Erstellung abgeschlossen")
    print("=" * 70)


if __name__ == "__main__":
    main()
