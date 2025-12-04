"""
Räumliche Filterung und Gattungs-Viabilitätsbewertung für Baumkataster-Daten.

Wendet zeitliche, räumliche und Gattungs-Filter auf harmonisierte Baumkataster an,
berechnet Abstände zu Nachbargattungen und exportiert mehrere Datensatz-Varianten:
1. Ohne Kantenfilterung (maximale Stichprobe)
2. Mit 15m/20m/30m Kantenfilterung (verschiedene Qualitätsstufen)

Bäume ohne Gattungsangabe (NaN) werden in separaten Dateien für potenzielle
spätere Nutzung exportiert.
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BOUNDARIES_PATH,
    CHM_REFERENCE_YEAR,
    CITIES,
    EDGE_DISTANCE_THRESHOLDS_M,
    GRID_CELL_SIZE_M,
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
    Clippt Bäume auf Stadtgrenzen (ohne 500m-Puffer).
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


def calculate_edge_distances(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Berechnet für jeden Baum den Abstand zum nächsten Baum einer anderen Gattung.

    Verwendet KD-Tree für effiziente O(n log n) Performance.
    
    WICHTIG: Bäume ohne Gattung (NaN) werden als potenzielle Kontaminationsquellen
    behandelt - sie zählen als "fremde" Bäume für alle bekannten Gattungen.
    """
    print("\n  Calculating edge distances (KD-Tree per genus)...")
    print("  ℹ️  NaN-genus trees are treated as contamination sources")

    gdf = gdf.copy()
    gdf["min_dist_other_genus"] = np.nan

    # Trennung: mit/ohne Gattung
    has_genus = gdf["genus_latin"].notna()
    gdf_with_genus = gdf[has_genus]
    gdf_nan_genus = gdf[~has_genus]
    
    print(f"  ℹ️  Trees with genus: {len(gdf_with_genus):,}")
    print(f"  ℹ️  Trees without genus (as contamination): {len(gdf_nan_genus):,}")

    # Prepare coordinates once
    nan_coords = np.column_stack([gdf_nan_genus.geometry.x, gdf_nan_genus.geometry.y]) if len(gdf_nan_genus) > 0 else None
    genera_list = gdf_with_genus["genus_latin"].unique()
    total_genera = len(genera_list)

    for i, genus in enumerate(genera_list, 1):
        # Bäume dieser Gattung
        genus_idx = gdf_with_genus["genus_latin"] == genus
        genus_trees = gdf_with_genus[genus_idx]
        genus_indices = gdf_with_genus.index[genus_idx]

        # "Fremde" Bäume = andere bekannte Gattungen + NaN-Bäume
        other_known = gdf_with_genus[~genus_idx]
        
        if len(other_known) == 0 and (nan_coords is None or len(nan_coords) == 0):
            gdf.loc[genus_indices, "min_dist_other_genus"] = np.inf
            continue

        # Combine coordinates
        coords_list = [np.column_stack([other_known.geometry.x, other_known.geometry.y])]
        if nan_coords is not None and len(nan_coords) > 0:
            coords_list.append(nan_coords)
        
        coords_other = np.vstack(coords_list) if len(coords_list) > 1 else coords_list[0]
        tree = cKDTree(coords_other)

        # Query distances
        coords_same = np.column_stack([genus_trees.geometry.x, genus_trees.geometry.y])
        distances, _ = tree.query(coords_same, k=1)

        gdf.loc[genus_indices, "min_dist_other_genus"] = distances

        if i % 10 == 0 or i == total_genera:
            print(f"    ✓ Processed {i}/{total_genera} genera")

    return gdf


def apply_edge_filter(
    gdf: gpd.GeoDataFrame, min_distance_m: float
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Behält nur Bäume mit ≥ min_distance_m Abstand zu anderen Gattungen.
    """
    mask = gdf["min_dist_other_genus"] >= min_distance_m
    filtered = gdf[mask].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = (loss / len(gdf) * 100) if len(gdf) > 0 else 0.0

    print(f"  ✓ Retained: {len(filtered):,} trees")
    print(f"  ✗ Excluded: {loss:,} ({loss_pct:.1f}%)")

    return filtered, {
        "step": f"edge_filter_{int(min_distance_m)}m",
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


def create_spatial_grid(
    gdf: gpd.GeoDataFrame, cell_size_m: int = GRID_CELL_SIZE_M
) -> gpd.GeoDataFrame:
    """
    Weist jeden Baum einer Gitterzelle zu für späteres räumliches Sampling.
    """
    gdf = gdf.copy()
    
    # Vectorized grid assignment
    gdf["grid_x"] = (gdf.geometry.x // cell_size_m).astype(int)
    gdf["grid_y"] = (gdf.geometry.y // cell_size_m).astype(int)
    gdf["grid_id"] = gdf["grid_x"].astype(str) + "_" + gdf["grid_y"].astype(str)

    # Gitter-Statistiken
    n_cells = gdf["grid_id"].nunique()
    avg_trees_per_cell = len(gdf) / n_cells if n_cells > 0 else 0

    print("\n  ✓ Grid assignment complete:")
    print(f"    Grid cells: {n_cells:,}")
    print(f"    Avg trees/cell: {avg_trees_per_cell:.1f}")

    # Pro-Stadt Statistiken
    for city in gdf["city"].unique():
        city_data = gdf[gdf["city"] == city]
        city_cells = city_data["grid_id"].nunique()
        city_avg = len(city_data) / city_cells if city_cells > 0 else 0
        print(f"    {city}: {city_cells:,} cells, {city_avg:.1f} trees/cell")

    return gdf


def export_filtered_dataset(
    gdf: gpd.GeoDataFrame, variant_name: str
) -> Path:
    """
    Exportiert gefilterten Datensatz als GeoPackage.
    """
    output_path = TREE_CADASTRES_PROCESSED_DIR / f"trees_filtered_viable_{variant_name}.gpkg"
    TREE_CADASTRES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Finale Spalten auswählen
    columns = [
        "tree_id",
        "city",
        "genus_latin",
        "species_latin",
        "plant_year",
        "height_m",
        "crown_diameter_m",
        "stem_circumference_cm",
        "source_layer",
        "min_dist_other_genus",
        "grid_x",
        "grid_y",
        "grid_id",
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
    variant_name: str,
) -> None:
    """
    Exportiert Metadaten-CSVs und JSON-Bericht.
    """
    TREE_CADASTRES_METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # Export CSVs
    viable_path = TREE_CADASTRES_METADATA_DIR / f"genus_viability_{variant_name}.csv"
    viable_stats.to_csv(viable_path)
    print(f"  ✓ Viable genera stats: {viable_path}")

    all_genera_path = TREE_CADASTRES_METADATA_DIR / f"all_genera_counts_{variant_name}.csv"
    all_genus_counts.to_csv(all_genera_path)
    print(f"  ✓ All genera counts: {all_genera_path}")

    losses_df = pd.DataFrame(filtering_losses)
    losses_df["variant"] = variant_name
    losses_path = TREE_CADASTRES_METADATA_DIR / f"filtering_losses_{variant_name}.csv"
    losses_df.to_csv(losses_path, index=False)
    print(f"  ✓ Filtering losses: {losses_path}")

    # Build summary
    is_empty = len(viable_stats) == 0
    total_trees = int(viable_stats["total"].sum()) if not is_empty else 0
    
    summary = {
        "variant": variant_name,
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
    summary_path = TREE_CADASTRES_PROCESSED_DIR / f"filtering_report_{variant_name}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Summary report: {summary_path}")


def main() -> None:
    """Hauptfunktion: Führt die komplette Filterpipeline aus."""
    print("=" * 80)
    print("TREE CADASTRE SPATIAL FILTERING & GENUS VIABILITY")
    print("=" * 80)

    # Harmonisierte Daten laden
    print("\n[1/7] Loading harmonized data...")
    input_path = TREE_CADASTRES_PROCESSED_DIR / "trees_harmonized.gpkg"
    gdf = gpd.read_file(input_path)
    print(f"  ✓ Loaded: {len(gdf):,} trees")
    print(f"  ✓ Trees with genus: {gdf['genus_latin'].notna().sum():,}")
    print(f"  ✓ Trees without genus (NaN): {gdf['genus_latin'].isna().sum():,}")

    # Temporal Filter (für alle Varianten gleich)
    print("\n[2/7] Applying temporal filter (plant_year ≤ 2021)...")
    gdf_temporal, loss_temporal = temporal_filter(gdf)

    # City Boundary Clipping (für alle Varianten gleich)
    print("\n[3/7] Clipping to city core (remove 500m buffer)...")
    gdf_clipped, loss_clip = clip_to_city_core(gdf_temporal)

    # Edge Distances berechnen (NaN-Bäume werden als Kontaminationsquellen berücksichtigt)
    print("\n[4/7] Calculating edge distances...")
    gdf_with_distances = calculate_edge_distances(gdf_clipped)

    shared_losses = [loss_temporal, loss_clip]
    results_summary = {}

    # Helper function to process variants
    def process_variant(gdf_input, edge_threshold=None):
        """Process a single variant and return results."""
        if edge_threshold is None:
            variant_name = "no_edge"
            print("\n" + "=" * 80)
            print("VARIANT A: NO EDGE FILTER")
            print("=" * 80)
            print("\n[5/7] Skipping edge filter...")
            print("  ✓ No edge filtering applied")
            losses = shared_losses.copy()
        else:
            variant_name = f"edge_{edge_threshold}m"
            print("\n" + "=" * 80)
            print(f"VARIANT: {edge_threshold}M EDGE FILTER")
            print("=" * 80)
            print(f"\n[5/7] Applying {edge_threshold}m edge filter...")
            gdf_input, loss_edge = apply_edge_filter(gdf_input, min_distance_m=edge_threshold)
            losses = shared_losses + [loss_edge]

        # Genus Viability Check
        print("\n[6/7] Checking genus viability (≥500 per city)...")
        viable_genera, viable_stats, all_counts = check_genus_viability(gdf_input)

        gdf_filtered, loss_genus = filter_viable_genera(gdf_input, viable_genera)
        losses.append(loss_genus)

        # Spatial Grid Assignment
        print("\n[7/7] Assigning spatial grid (1km cells)...")
        gdf_filtered = create_spatial_grid(gdf_filtered, cell_size_m=GRID_CELL_SIZE_M)

        # Export
        print("\nExporting dataset...")
        export_filtered_dataset(gdf_filtered, variant_name)

        print("\nExporting metadata...")
        export_metadata(viable_stats, all_counts, losses, variant_name)

        return len(gdf_filtered), viable_genera

    # Process no-edge variant
    tree_count, genera = process_variant(gdf_with_distances.copy())
    results_summary["no_edge"] = {"trees": tree_count, "genera": genera}

    # Process edge filter variants
    for edge_threshold in EDGE_DISTANCE_THRESHOLDS_M:
        tree_count, genera = process_variant(gdf_with_distances.copy(), edge_threshold)
        results_summary[f"edge_{edge_threshold}m"] = {"trees": tree_count, "genera": genera}

    # ========================================================================
    # Zusammenfassung
    # ========================================================================
    print("\n" + "=" * 80)
    print("✓ PIPELINE COMPLETE")
    print("=" * 80)

    print("\n📊 Summary of all variants:")
    print("-" * 60)
    
    for variant, data in results_summary.items():
        print(f"\n{variant}:")
        print(f"  Trees: {data['trees']:,}")
        print(f"  Genera: {len(data['genera'])}")
        if data['genera']:
            print(f"  → {', '.join(sorted(data['genera']))}")

    # Vergleich: Gattungen die durch verschiedene Edge Filter verloren gehen
    print("\n" + "-" * 60)
    print("📉 Genera lost per edge filter threshold:")
    
    base_genera = set(results_summary["no_edge"]["genera"])
    for edge_threshold in EDGE_DISTANCE_THRESHOLDS_M:
        variant_name = f"edge_{edge_threshold}m"
        edge_genera = set(results_summary[variant_name]["genera"])
        lost = base_genera - edge_genera
        print(f"\n  {variant_name}: {', '.join(sorted(lost)) if lost else '(none)'}")


if __name__ == "__main__":
    main()
