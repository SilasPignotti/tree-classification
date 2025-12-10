"""
CHM-Harmonisierung: Filterung unrealistischer Werte.

Wendet Qualitätsfilter auf CHM-Daten an:
- 0 bis -2m → 0 (leichte Interpolationsfehler auf Boden setzen)
- < -2m → NoData (Wasserflächen, starke Artefakte)
- > 50m → NoData (Hochhäuser, unrealistisch für Bäume)

WARNUNG: Überschreibt die originalen CHM-Dateien!
         Erstelle vorher ein Backup!

Usage:
    uv run python scripts/chm/harmonize_chm.py
"""

import sys
from pathlib import Path

import numpy as np
import rasterio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import CHM_DIR, CITIES

# =============================================================================
# CONFIGURATION
# =============================================================================

CHM_PROCESSED_DIR = CHM_DIR / "processed"
NODATA = -9999.0

# Filter-Schwellwerte
SLIGHTLY_NEGATIVE_MIN = -2.0  # -2m bis 0m → 0 setzen
MAX_REALISTIC_HEIGHT = 50.0  # >50m → NoData


# =============================================================================
# FUNCTIONS
# =============================================================================


def apply_chm_filters(chm: np.ndarray) -> tuple[np.ndarray, dict]:
    """
    Wendet Qualitätsfilter auf CHM an.

    Filter:
    - 0 bis -2m → 0 (leichte Artefakte)
    - < -2m → NoData (Wasser, starke Artefakte)
    - > 50m → NoData (Hochhäuser, unrealistisch)

    Args:
        chm: CHM array (NaN = NoData)

    Returns:
        Tuple (filtered_chm, filter_stats)
    """
    # Kopie erstellen
    chm_filtered = chm.copy()

    # Original-Statistiken
    valid_mask = ~np.isnan(chm)
    original_valid_count = valid_mask.sum()

    # Zähle betroffene Pixel vor Filterung
    slightly_negative = (chm >= SLIGHTLY_NEGATIVE_MIN) & (chm < 0)
    very_negative = chm < SLIGHTLY_NEGATIVE_MIN
    very_high = chm > MAX_REALISTIC_HEIGHT

    slightly_negative_count = int(np.sum(slightly_negative))
    very_negative_count = int(np.sum(very_negative))
    very_high_count = int(np.sum(very_high))

    # FILTER 1: Leicht negative Werte → 0
    chm_filtered[slightly_negative] = 0.0

    # FILTER 2: Stark negative Werte → NoData
    chm_filtered[very_negative] = np.nan

    # FILTER 3: Sehr hohe Werte → NoData
    chm_filtered[very_high] = np.nan

    # Nach-Filter-Statistiken
    valid_mask_filtered = ~np.isnan(chm_filtered)
    filtered_valid_count = valid_mask_filtered.sum()
    removed_count = original_valid_count - filtered_valid_count

    stats = {
        "original_valid_pixels": int(original_valid_count),
        "filtered_valid_pixels": int(filtered_valid_count),
        "removed_pixels": int(removed_count),
        "removed_percent": round(100 * removed_count / original_valid_count, 2),
        "slightly_negative_set_to_zero": slightly_negative_count,
        "very_negative_removed": very_negative_count,
        "very_high_removed": very_high_count,
    }

    return chm_filtered, stats


def harmonize_city(city: str) -> dict:
    """
    Harmonisiert CHM für eine Stadt.

    Args:
        city: Stadtname

    Returns:
        Dict mit Statistiken
    """
    chm_path = CHM_PROCESSED_DIR / f"CHM_1m_{city}.tif"

    print(f"\n{'=' * 70}")
    print(f"Harmonisiere {city}")
    print(f"{'=' * 70}")

    # 1. Lade CHM
    print("\n[1/3] Lade CHM...")
    with rasterio.open(chm_path) as src:
        chm = src.read(1)
        profile = src.profile.copy()

        # NoData zu NaN
        if src.nodata is not None:
            chm = np.where(np.isclose(chm, src.nodata), np.nan, chm).astype(np.float32)

    print(f"  Shape: {chm.shape}")
    print(f"  Original gültige Pixel: {np.sum(~np.isnan(chm)):,}")

    # 2. Wende Filter an
    print("\n[2/3] Wende Filter an...")
    print(f"  Filter 1: {SLIGHTLY_NEGATIVE_MIN:.1f}m bis 0m → 0")
    print(f"  Filter 2: <{SLIGHTLY_NEGATIVE_MIN:.1f}m → NoData")
    print(f"  Filter 3: >{MAX_REALISTIC_HEIGHT:.1f}m → NoData")

    chm_filtered, stats = apply_chm_filters(chm)

    print(f"\n  Ergebnis:")
    print(f"    Auf 0 gesetzt:        {stats['slightly_negative_set_to_zero']:>10,}")
    print(f"    Entfernt (negativ):   {stats['very_negative_removed']:>10,}")
    print(f"    Entfernt (sehr hoch): {stats['very_high_removed']:>10,}")
    print(f"    Gesamt entfernt:      {stats['removed_pixels']:>10,} ({stats['removed_percent']:.2f}%)")
    print(f"    Verbleibend gültig:   {stats['filtered_valid_pixels']:>10,}")

    # 3. Speichere harmonisierten CHM (überschreibt Original!)
    print("\n[3/3] Speichere harmonisierten CHM...")

    # NaN zurück zu NoData
    chm_output = np.where(np.isnan(chm_filtered), NODATA, chm_filtered).astype(np.float32)

    profile.update(
        dtype=rasterio.float32,
        nodata=NODATA,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )

    with rasterio.open(chm_path, "w", **profile) as dst:
        dst.write(chm_output, 1)

    file_size_mb = chm_path.stat().st_size / (1024**2)
    print(f"  ✓ Gespeichert: {chm_path.name} ({file_size_mb:.1f} MB)")

    stats["city"] = city
    return stats


def main():
    """Hauptfunktion: Harmonisiert alle CHMs."""
    print("=" * 70)
    print("CHM HARMONIZATION")
    print("=" * 70)
    print()
    print("⚠️  WARNUNG: Dieses Script überschreibt die originalen CHM-Dateien!")
    print("    Stelle sicher, dass du ein Backup erstellt hast.")
    print()
    print("Filter-Regeln:")
    print(f"  1. {SLIGHTLY_NEGATIVE_MIN:.1f}m bis 0m → 0 (leichte Artefakte auf Boden)")
    print(f"  2. <{SLIGHTLY_NEGATIVE_MIN:.1f}m → NoData (Wasser, starke Artefakte)")
    print(f"  3. >{MAX_REALISTIC_HEIGHT:.1f}m → NoData (Hochhäuser, unrealistisch für Bäume)")
    print()
    print("Basierend auf Verteilungsanalyse:")
    print("  - Berlin:   7.0% negativ (fast alle -2m bis 0m)")
    print("  - Hamburg: 18.0% negativ (14.5% zwischen -2m bis 0m)")
    print("  - Rostock: 27.0% negativ (27.0% zwischen -2m bis 0m)")
    print()

    # Bestätigung
    response = input("Fortfahren? (ja/nein): ").strip().lower()
    if response not in ["ja", "j", "yes", "y"]:
        print("\nAbgebrochen.")
        return

    all_stats = []

    for city in CITIES:
        stats = harmonize_city(city)
        all_stats.append(stats)

    # Zusammenfassung
    print("\n")
    print("=" * 70)
    print("ZUSAMMENFASSUNG")
    print("=" * 70)
    print()
    print(f"{'Stadt':<12} {'Auf 0':>12} {'Entfernt':>12} {'Entfernt %':>12} {'Verbleibend':>14}")
    print("-" * 70)

    for stats in all_stats:
        print(
            f"{stats['city']:<12} "
            f"{stats['slightly_negative_set_to_zero']:>12,} "
            f"{stats['removed_pixels']:>12,} "
            f"{stats['removed_percent']:>11.2f}% "
            f"{stats['filtered_valid_pixels']:>14,}"
        )

    print()
    print("=" * 70)
    print("✓ CHM-Harmonisierung abgeschlossen")
    print("=" * 70)
    print()
    print("Nächste Schritte:")
    print("  1. Neue Statistiken berechnen:")
    print("     uv run python scripts/chm/create_chm.py")
    print("  2. Verteilung prüfen:")
    print("     uv run python scripts/chm/analyze_chm_distribution.py")
    print()


if __name__ == "__main__":
    main()
