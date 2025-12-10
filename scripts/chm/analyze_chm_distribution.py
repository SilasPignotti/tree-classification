"""
CHM-Verteilungsanalyse: Negative und sehr hohe Werte.

Analysiert die Verteilung von negativen (<0m) und sehr hohen (>50m) CHM-Werten
innerhalb der Stadtgrenzen für alle drei Städte.

Usage:
    uv run python scripts/chm/analyze_chm_distribution.py
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import BOUNDARIES_PATH, CHM_DIR, CITIES

# =============================================================================
# CONFIGURATION
# =============================================================================

CHM_PROCESSED_DIR = CHM_DIR / "processed"
OUTPUT_DIR = CHM_DIR / "analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# FUNCTIONS
# =============================================================================


def load_chm_and_boundary(city: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Lädt CHM und erstellt Stadtgrenzen-Maske.

    Args:
        city: Stadtname

    Returns:
        Tuple (chm_array, city_mask)
    """
    chm_path = CHM_PROCESSED_DIR / f"CHM_1m_{city}.tif"

    with rasterio.open(chm_path) as src:
        chm = src.read(1)
        transform = src.transform

        # NoData zu NaN
        if src.nodata is not None:
            chm = np.where(np.isclose(chm, src.nodata), np.nan, chm).astype(np.float32)

    # Stadtgrenzen-Maske
    boundaries = gpd.read_file(BOUNDARIES_PATH)
    city_geom = boundaries[boundaries["gen"] == city].geometry.iloc[0]
    city_mask = ~geometry_mask([city_geom], out_shape=chm.shape, transform=transform)

    return chm, city_mask


def analyze_chm_distribution(chm: np.ndarray, city_mask: np.ndarray, city: str) -> dict:
    """
    Analysiert CHM-Verteilung innerhalb Stadtgrenzen.

    Args:
        chm: CHM array
        city_mask: Boolean-Maske (True = innerhalb Stadtgrenze)
        city: Stadtname

    Returns:
        Dict mit Statistiken
    """
    # Nur Pixel innerhalb Stadtgrenze
    chm_city = chm[city_mask]
    valid_mask = ~np.isnan(chm_city)
    valid_values = chm_city[valid_mask]

    total_valid = len(valid_values)

    # Negative Werte analysieren
    negative_mask = valid_values < 0
    negative_values = valid_values[negative_mask]

    # Kategorisierung negativer Werte
    very_negative = negative_values < -5  # Starke Artefakte
    moderate_negative = (negative_values >= -5) & (negative_values < -2)
    slightly_negative = (negative_values >= -2) & (negative_values < 0)

    # Hohe Werte analysieren
    high_mask = valid_values > 50
    high_values = valid_values[high_mask]

    very_high_mask = valid_values > 60
    very_high_values = valid_values[very_high_mask]

    # Normale Werte (0-50m)
    normal_mask = (valid_values >= 0) & (valid_values <= 50)
    normal_values = valid_values[normal_mask]

    stats = {
        "city": city,
        # Gesamt
        "total_pixels_in_boundary": int(city_mask.sum()),
        "valid_pixels": int(total_valid),
        "coverage_percent": round(100 * total_valid / city_mask.sum(), 2),
        # Alle gültigen Werte
        "all_min": round(float(np.min(valid_values)), 2),
        "all_max": round(float(np.max(valid_values)), 2),
        "all_mean": round(float(np.mean(valid_values)), 2),
        "all_median": round(float(np.median(valid_values)), 2),
        "all_std": round(float(np.std(valid_values)), 2),
        # Negative Werte
        "negative_total": int(negative_mask.sum()),
        "negative_percent": round(100 * negative_mask.sum() / total_valid, 2),
        "negative_min": round(float(np.min(negative_values)), 2) if len(negative_values) > 0 else None,
        "negative_mean": round(float(np.mean(negative_values)), 2) if len(negative_values) > 0 else None,
        "negative_median": round(float(np.median(negative_values)), 2) if len(negative_values) > 0 else None,
        # Kategorien negativer Werte
        "very_negative_lt_minus5": int(very_negative.sum()),
        "very_negative_percent": round(100 * very_negative.sum() / total_valid, 2),
        "moderate_negative_minus5_to_minus2": int(moderate_negative.sum()),
        "moderate_negative_percent": round(100 * moderate_negative.sum() / total_valid, 2),
        "slightly_negative_minus2_to_0": int(slightly_negative.sum()),
        "slightly_negative_percent": round(100 * slightly_negative.sum() / total_valid, 2),
        # Hohe Werte
        "high_gt_50m": int(high_mask.sum()),
        "high_gt_50m_percent": round(100 * high_mask.sum() / total_valid, 2),
        "high_mean": round(float(np.mean(high_values)), 2) if len(high_values) > 0 else None,
        "high_max": round(float(np.max(high_values)), 2) if len(high_values) > 0 else None,
        # Sehr hohe Werte
        "very_high_gt_60m": int(very_high_mask.sum()),
        "very_high_gt_60m_percent": round(100 * very_high_mask.sum() / total_valid, 2),
        "very_high_max": round(float(np.max(very_high_values)), 2) if len(very_high_values) > 0 else None,
        # Normale Werte (0-50m) - "saubere" Vegetation
        "normal_0_to_50m": int(normal_mask.sum()),
        "normal_percent": round(100 * normal_mask.sum() / total_valid, 2),
        "normal_mean": round(float(np.mean(normal_values)), 2) if len(normal_values) > 0 else None,
        "normal_median": round(float(np.median(normal_values)), 2) if len(normal_values) > 0 else None,
    }

    return stats


def main():
    """Hauptfunktion: Analysiert CHM-Verteilung für alle Städte."""
    print("=" * 80)
    print("CHM DISTRIBUTION ANALYSIS")
    print("=" * 80)
    print()
    print("Analysiert negative (<0m) und sehr hohe (>50m) CHM-Werte")
    print("innerhalb der Stadtgrenzen (ohne Buffer)")
    print()

    all_stats = []

    for city in CITIES:
        print(f"\n{'=' * 80}")
        print(f"Analysiere {city}")
        print(f"{'=' * 80}")

        # 1. Lade Daten
        print("\n[1/2] Lade CHM und Stadtgrenzen...")
        chm, city_mask = load_chm_and_boundary(city)
        print(f"  CHM Shape: {chm.shape}")
        print(f"  Pixel in Stadtgrenze: {city_mask.sum():,}")

        # 2. Analysiere Verteilung
        print("\n[2/2] Analysiere CHM-Verteilung...")
        stats = analyze_chm_distribution(chm, city_mask, city)
        all_stats.append(stats)

        print(f"\n  Ergebnisse für {city}:")
        print(f"    Gültige Pixel: {stats['valid_pixels']:,} ({stats['coverage_percent']:.1f}%)")
        print(f"    Wertebereich: {stats['all_min']:.2f}m bis {stats['all_max']:.2f}m")
        print(f"    Mean: {stats['all_mean']:.2f}m | Median: {stats['all_median']:.2f}m")
        print(f"\n  Negative Werte (<0m):")
        print(f"    Gesamt:        {stats['negative_total']:>12,} ({stats['negative_percent']:>5.1f}%)")
        print(
            f"    <-5m:          {stats['very_negative_lt_minus5']:>12,} "
            f"({stats['very_negative_percent']:>5.1f}%)"
        )
        print(
            f"    -5m to -2m:    {stats['moderate_negative_minus5_to_minus2']:>12,} "
            f"({stats['moderate_negative_percent']:>5.1f}%)"
        )
        print(
            f"    -2m to 0m:     {stats['slightly_negative_minus2_to_0']:>12,} "
            f"({stats['slightly_negative_percent']:>5.1f}%)"
        )
        if stats['negative_mean'] is not None:
            print(f"    Mean negativ:  {stats['negative_mean']:>12.2f}m")
        print(f"\n  Hohe Werte:")
        print(f"    >50m:          {stats['high_gt_50m']:>12,} ({stats['high_gt_50m_percent']:>5.1f}%)")
        print(
            f"    >60m:          {stats['very_high_gt_60m']:>12,} "
            f"({stats['very_high_gt_60m_percent']:>5.1f}%)"
        )
        if stats['very_high_max'] is not None:
            print(f"    Max Wert:      {stats['very_high_max']:>12.2f}m")
        print(f"\n  Normale Werte (0-50m):")
        print(f"    Anzahl:        {stats['normal_0_to_50m']:>12,} ({stats['normal_percent']:>5.1f}%)")
        if stats['normal_mean'] is not None:
            print(f"    Mean:          {stats['normal_mean']:>12.2f}m")
            print(f"    Median:        {stats['normal_median']:>12.2f}m")

    # Zusammenfassung
    print("\n")
    print("=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print()

    # Tabelle
    df = pd.DataFrame(all_stats)
    summary_cols = [
        "city",
        "negative_percent",
        "very_negative_percent",
        "moderate_negative_percent",
        "slightly_negative_percent",
        "high_gt_50m_percent",
        "very_high_gt_60m_percent",
        "normal_percent",
    ]
    summary_df = df[summary_cols].copy()
    summary_df.columns = [
        "Stadt",
        "Negativ %",
        "<-5m %",
        "-5 to -2m %",
        "-2 to 0m %",
        ">50m %",
        ">60m %",
        "0-50m %",
    ]

    print(summary_df.to_string(index=False))

    # Speichern
    print("\n")
    print("=" * 80)
    print("SPEICHERN")
    print("=" * 80)
    print()

    # JSON
    json_path = OUTPUT_DIR / "chm_distribution_analysis.json"
    with open(json_path, "w") as f:
        json.dump(all_stats, f, indent=2)
    print(f"✓ JSON gespeichert: {json_path}")

    # CSV
    csv_path = OUTPUT_DIR / "chm_distribution_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"✓ CSV gespeichert: {csv_path}")

    # Empfehlungen
    print("\n")
    print("=" * 80)
    print("INTERPRETATION")
    print("=" * 80)
    print()

    for stats in all_stats:
        city = stats["city"]
        neg_pct = stats["negative_percent"]
        very_neg_pct = stats["very_negative_percent"]
        high_pct = stats["high_gt_50m_percent"]
        very_high_pct = stats["very_high_gt_60m_percent"]

        print(f"{city}:")

        # Negative Werte
        if neg_pct > 20:
            print(f"  ⚠️  Hoher Anteil negativer Werte ({neg_pct:.1f}%)")
            if very_neg_pct > 5:
                print(f"      → {very_neg_pct:.1f}% stark negativ (<-5m) - vermutlich Wasserflächen")
            else:
                print(f"      → Meist leicht negativ - Interpolationsfehler oder Brücken")
        elif neg_pct > 10:
            print(f"  ⚠️  Moderater Anteil negativer Werte ({neg_pct:.1f}%)")
        else:
            print(f"  ✓  Wenige negative Werte ({neg_pct:.1f}%)")

        # Hohe Werte
        if very_high_pct > 0.1:
            print(f"  ⚠️  Viele Ausreißer >60m ({very_high_pct:.2f}%) - Hochhäuser/Messfehler")
        elif high_pct > 1:
            print(f"  ⚠️  Einige hohe Werte >50m ({high_pct:.2f}%) - Gebäude/hohe Bäume")
        else:
            print(f"  ✓  Wenige hohe Werte >50m ({high_pct:.2f}%)")

        print()

    print("=" * 80)
    print("NÄCHSTE SCHRITTE")
    print("=" * 80)
    print()
    print("Basierend auf den Ergebnissen:")
    print("1. Entscheiden: Filter für negative Werte anwenden?")
    print("   - Option A: <-5m → NoData (entfernt Wasserflächen)")
    print("   - Option B: <-2m → NoData (konservativer)")
    print("   - Option C: Alle negativen → NoData (aggressiv)")
    print("   - Option D: Keine Filterung, nur dokumentieren")
    print()
    print("2. Entscheiden: Filter für hohe Werte anwenden?")
    print("   - Option A: >60m → NoData (Hochhäuser/Ausreißer)")
    print("   - Option B: >50m → NoData (alle Gebäude)")
    print("   - Option C: Keine Filterung")
    print()
    print("3. create_chm.py anpassen mit gewählten Filtern")
    print("4. Dokumentation aktualisieren")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
