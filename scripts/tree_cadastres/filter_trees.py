"""
Filterung und Genus-Viabilitätsbewertung für harmonisierte Baumkataster-Daten.

Wendet zeitliche, räumliche und Gattungs-Filter auf harmonisierte Baumkataster an:
1. Temporale Filterung: plant_year ≤ 2021 (oder NaN)
2. Räumliche Filterung: Clipping auf Stadtgrenzen
3. Gattungs-Viabilitätsprüfung: ≥500 Bäume pro Gattung in ALLEN Städten
4. Spatial Grid Assignment: 1km Rasterzellen für späteres Sampling

Edge-Distance-Berechnung erfolgt NACH der Positionskorrektur basierend auf CHM.
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BOUNDARIES_PATH,
    CHM_REFERENCE_YEAR,
    CITIES,
    MIN_SAMPLES_PER_CITY,
    TREE_CADASTRES_METADATA_DIR,
    TREE_CADASTRES_PROCESSED_DIR,
)


def temporal_filter(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Filtert Bäume nach Pflanzjahr (≤ CHM-Referenzjahr).

    Behält Bäume mit plant_year ≤ 2021 oder unbekanntem Pflanzjahr (NaN).
    """
    mask = gdf["plant_year"].isna() | (gdf["plant_year"] <= CHM_REFERENCE_YEAR)
    filtered = gdf[mask].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = (loss / len(gdf) * 100) if len(gdf) > 0 else 0.0

    print(f"  ✓ Retained: {len(filtered):,} trees")
    print(f"  ✗ Excluded: {loss:,} ({loss_pct:.1f}%)")

    return filtered, {
        "step": "temporal_filter",
        "excluded": int(loss),
        "excluded_pct": float(round(loss_pct, 2)),
    }


def clip_to_city_core(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Clippt Bäume auf Stadtgrenzen (ohne Puffer).
    """
    boundaries = gpd.read_file(BOUNDARIES_PATH)

    gdf_clipped = gpd.sjoin(
        gdf,
        boundaries[["geometry"]],
        how="inner",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")
    
    gdf_clipped = gdf_clipped.drop_duplicates(subset=["tree_id"])

    loss = len(gdf) - len(gdf_clipped)
    loss_pct = loss / len(gdf) * 100 if len(gdf) > 0 else 0.0

    print(f"  ✓ Retained: {len(gdf_clipped):,} trees")
    print(f"  ✗ Excluded: {loss:,} ({loss_pct:.1f}%)")

    return gdf_clipped, {
        "step": "city_boundary_clipping",
        "excluded": int(loss),
        "excluded_pct": float(round(loss_pct, 2)),
    }




def check_genus_viability(
    gdf: gpd.GeoDataFrame, min_samples: int = MIN_SAMPLES_PER_CITY
) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    """
    Ermittelt Gattungen mit ≥ min_samples in ALLEN drei Städten.
    """
    # Zählung pro Stadt × Gattung, transponiert zu rows=genera, cols=cities
    counts = gdf.groupby(["city", "genus_latin"]).size().unstack(fill_value=0).T

    # Filter zu verfügbaren Städten
    available_cities = [c for c in CITIES if c in counts.columns]

    # Viable = erfüllt Schwellenwert in ALLEN Städten
    viable_mask = (counts[available_cities] >= min_samples).all(axis=1)
    viable_genera = sorted(counts[viable_mask].index.tolist())

    # Statistiken für viable Gattungen
    if viable_genera:
        viable_stats = counts.loc[viable_genera].copy()
        viable_stats["total"] = viable_stats[available_cities].sum(axis=1)
        viable_stats["min_city"] = viable_stats[available_cities].min(axis=1)
        viable_stats["max_city"] = viable_stats[available_cities].max(axis=1)
        viable_stats = viable_stats.sort_values("total", ascending=False)
    else:
        viable_stats = pd.DataFrame()

    print(f"\n  ✓ Viable genera (≥{min_samples} per city): {len(viable_genera)}")
    if viable_genera:
        print(f"    → {', '.join(viable_genera)}")
    if not viable_stats.empty:
        print("\n  Sample counts:")
        print(viable_stats[available_cities + ["total", "min_city"]].to_string())

    return viable_genera, viable_stats, counts


def filter_viable_genera(
    gdf: gpd.GeoDataFrame, viable_genera: list[str]
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Behält nur Bäume der viablen Gattungen.
    """
    mask = gdf["genus_latin"].isin(viable_genera)
    filtered = gdf[mask].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = (loss / len(gdf) * 100) if len(gdf) > 0 else 0.0

    print(f"\n  ✓ Retained: {len(filtered):,} trees ({len(viable_genera)} genera)")
    print(f"  ✗ Excluded: {loss:,} trees ({loss_pct:.1f}%)")

    return filtered, {
        "step": "genus_viability_filter",
        "excluded": int(loss),
        "excluded_pct": float(round(loss_pct, 2)),
        "viable_genera_count": len(viable_genera),
    }




def export_filtered_dataset(gdf: gpd.GeoDataFrame) -> Path:
    """
    Exportiert gefilterten Datensatz als GeoPackage.
    """
    output_path = TREE_CADASTRES_PROCESSED_DIR / "trees_filtered_viable.gpkg"
    TREE_CADASTRES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Spalten in Reihenfolge
    columns = [
        "tree_id",
        "city",
        "genus_latin",
        "species_latin",
        "plant_year",
        "height_m",
        "tree_type",
        "geometry",
    ]

    gdf_export = gdf[columns]

    # Speichern
    gdf_export.to_file(output_path, driver="GPKG")

    # Dateigröße
    file_size_mb = output_path.stat().st_size / 1e6

    print(f"\n  ✓ Saved: {output_path}")
    print(f"    Size: {file_size_mb:.1f} MB")
    print(f"    Records: {len(gdf_export):,}")
    print(f"    Genera: {gdf_export['genus_latin'].nunique()}")

    return output_path


def export_metadata(
    viable_stats: pd.DataFrame,
    all_genus_counts: pd.DataFrame,
    filtering_losses: list[dict],
) -> None:
    """
    Exportiert Metadaten-CSVs und JSON-Bericht.
    """
    TREE_CADASTRES_METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # Export CSVs
    viable_path = TREE_CADASTRES_METADATA_DIR / "genus_viability.csv"
    viable_stats.to_csv(viable_path)
    print(f"  ✓ Viable genera stats: {viable_path}")

    all_genera_path = TREE_CADASTRES_METADATA_DIR / "all_genera_counts.csv"
    all_genus_counts.to_csv(all_genera_path)
    print(f"  ✓ All genera counts: {all_genera_path}")

    losses_df = pd.DataFrame(filtering_losses)
    losses_path = TREE_CADASTRES_METADATA_DIR / "filtering_losses.csv"
    losses_df.to_csv(losses_path, index=False)
    print(f"  ✓ Filtering losses: {losses_path}")

    # Build summary
    is_empty = len(viable_stats) == 0
    total_trees = int(viable_stats["total"].sum()) if not is_empty else 0
    
    summary = {
        "viable_genera": viable_stats.index.tolist() if not is_empty else [],
        "viable_genera_count": len(viable_stats),
        "total_trees": total_trees,
        "per_city": {
            city: int(viable_stats[city].sum())
            for city in ["Hamburg", "Berlin", "Rostock"]
            if city in viable_stats.columns
        },
        "filtering_steps": filtering_losses,
    }

    # Export JSON
    summary_path = TREE_CADASTRES_METADATA_DIR / "filtering_report.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Summary report: {summary_path}")


def main() -> None:
    """Hauptfunktion: Führt die komplette Filterpipeline aus."""
    print("=" * 80)
    print("TREE CADASTRE FILTERING & GENUS VIABILITY")
    print("=" * 80)

    # Harmonisierte Daten laden
    print("\n[1/4] Loading harmonized data...")
    input_path = TREE_CADASTRES_PROCESSED_DIR / "trees_harmonized.gpkg"
    gdf = gpd.read_file(input_path)
    print(f"  ✓ Loaded: {len(gdf):,} trees")
    print(f"  ✓ Trees with genus: {gdf['genus_latin'].notna().sum():,}")
    print(f"  ✓ Trees without genus (NaN): {gdf['genus_latin'].isna().sum():,}")

    # Temporal Filter
    print("\n[2/4] Applying temporal filter (plant_year ≤ 2021)...")
    gdf_temporal, loss_temporal = temporal_filter(gdf)

    # City Boundary Clipping
    print("\n[3/4] Clipping to city core...")
    gdf_clipped, loss_clip = clip_to_city_core(gdf_temporal)

    # Genus Viability Check
    print("\n[4/4] Checking genus viability (≥500 per city)...")
    viable_genera, viable_stats, all_counts = check_genus_viability(gdf_clipped)

    gdf_filtered, loss_genus = filter_viable_genera(gdf_clipped, viable_genera)

    # Collect losses
    losses = [loss_temporal, loss_clip, loss_genus]

    # Export
    print("\nExporting dataset...")
    export_filtered_dataset(gdf_filtered)

    print("\nExporting metadata...")
    export_metadata(viable_stats, all_counts, losses)

    # ========================================================================
    # Zusammenfassung
    # ========================================================================
    print("\n" + "=" * 80)
    print("✓ FILTERING COMPLETE")
    print("=" * 80)

    print(f"\n📊 Final dataset summary:")
    print(f"  Total trees: {len(gdf_filtered):,}")
    print(f"  Viable genera: {len(viable_genera)}")
    print(f"  → {', '.join(sorted(viable_genera))}")
    
    print(f"\nTrees per city:")
    for city, count in gdf_filtered.groupby("city").size().items():
        print(f"  {city}: {count:,}")

    print(f"\nTrees per tree_type:")
    tree_type_counts = gdf_filtered.groupby("tree_type", dropna=False).size()
    for tree_type, count in tree_type_counts.items():
        tree_type_str = str(tree_type) if pd.notna(tree_type) else "(NaN)"
        print(f"  {tree_type_str}: {count:,}")


if __name__ == "__main__":
    main()
