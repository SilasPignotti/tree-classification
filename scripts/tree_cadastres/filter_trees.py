"""
Räumliche Filterung und Gattungs-Viabilitätsbewertung für Baumkataster-Daten.

Wendet zeitliche, räumliche und Gattungs-Filter auf harmonisierte Baumkataster an,
berechnet Abstände zu Nachbargattungen und exportiert zwei Datensatz-Varianten:
1. Ohne Kantenfilterung (maximale Stichprobe)
2. Mit 15m Kantenfilterung (Qualitätsfilterung)
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


# Konstanten
BASE_DIR = Path("data/tree_cadastres")
PROCESSED_DIR = BASE_DIR / "processed"
METADATA_DIR = BASE_DIR / "metadata"
BOUNDARIES_PATH = Path("data/boundaries/city_boundaries.gpkg")

TARGET_CRS = "EPSG:25832"
CHM_REFERENCE_YEAR = 2021
MIN_SAMPLES_PER_CITY = 500
EDGE_DISTANCE_THRESHOLD_M = 15
GRID_CELL_SIZE_M = 1000


def temporal_filter(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Filtert Bäume nach Pflanzjahr (≤ CHM-Referenzjahr).

    Behält Bäume mit plant_year ≤ 2021 oder unbekanntem Pflanzjahr (NaN).

    Args:
        gdf: GeoDataFrame mit harmonisierten Baumdaten

    Returns:
        Tuple aus gefiltertem GeoDataFrame und Loss-Dictionary
    """
    filtered = gdf[
        (gdf["plant_year"].isna()) | (gdf["plant_year"] <= CHM_REFERENCE_YEAR)
    ].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = loss / len(gdf) * 100 if len(gdf) > 0 else 0.0

    print(f"  ✓ Retained: {len(filtered):,} trees")
    print(f"  ✗ Excluded: {loss:,} ({loss_pct:.1f}%)")

    return filtered, {
        "step": "temporal_filter",
        "excluded": int(loss),
        "excluded_pct": float(round(loss_pct, 2)),
    }


def clip_to_city_core(
    gdf: gpd.GeoDataFrame, boundaries_path: Path
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Clippt Bäume auf Stadtgrenzen (ohne 500m-Puffer).

    Args:
        gdf: GeoDataFrame mit Baumdaten
        boundaries_path: Pfad zur city_boundaries.gpkg

    Returns:
        Tuple aus geclipptem GeoDataFrame und Loss-Dictionary
    """
    # Grenzen laden (ohne Buffer)
    boundaries = gpd.read_file(boundaries_path)

    # CRS angleichen falls nötig
    if gdf.crs != boundaries.crs:
        boundaries = boundaries.to_crs(gdf.crs)

    # Spatial Join: nur Bäume innerhalb der Grenzen behalten
    gdf_clipped = gpd.sjoin(
        gdf,
        boundaries[["gen", "geometry"]],
        how="inner",
        predicate="within",
    )

    # Join-Artefakte bereinigen
    gdf_clipped = gdf_clipped.drop(columns=["index_right"], errors="ignore")
    gdf_clipped = gdf_clipped.drop(columns=["gen"], errors="ignore")

    # Duplikate entfernen (sollte nicht vorkommen)
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

    Args:
        gdf: GeoDataFrame mit Baumdaten

    Returns:
        GeoDataFrame mit neuer Spalte 'min_dist_other_genus'
    """
    print("\n  Calculating edge distances (KD-Tree per genus)...")

    gdf = gdf.copy()
    gdf["min_dist_other_genus"] = np.nan

    genera = gdf["genus_latin"].dropna().unique()
    total_genera = len(genera)

    for i, genus in enumerate(genera, 1):
        # Bäume dieser Gattung
        same_genus_mask = gdf["genus_latin"] == genus
        same_genus = gdf[same_genus_mask]

        # Bäume anderer Gattungen
        other_genus = gdf[~same_genus_mask & gdf["genus_latin"].notna()]

        if len(other_genus) == 0:
            # Keine anderen Gattungen in der Nähe (unwahrscheinlich)
            gdf.loc[same_genus.index, "min_dist_other_genus"] = np.inf
            continue

        # KD-Tree für schnelle Nearest-Neighbor-Suche
        coords_other = np.column_stack([other_genus.geometry.x, other_genus.geometry.y])
        tree = cKDTree(coords_other)

        # Query: Abstand zum nächsten "fremden" Baum
        coords_same = np.column_stack([same_genus.geometry.x, same_genus.geometry.y])
        distances, _ = tree.query(coords_same, k=1)

        gdf.loc[same_genus.index, "min_dist_other_genus"] = distances

        # Fortschritt alle 10 Gattungen
        if i % 10 == 0 or i == total_genera:
            print(f"    ✓ Processed {i}/{total_genera} genera")

    return gdf


def apply_edge_filter(
    gdf: gpd.GeoDataFrame, min_distance_m: float = EDGE_DISTANCE_THRESHOLD_M
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Behält nur Bäume mit ≥ min_distance_m Abstand zu anderen Gattungen.

    Args:
        gdf: GeoDataFrame mit 'min_dist_other_genus' Spalte
        min_distance_m: Minimaler Abstandsschwellenwert (Standard: 15m)

    Returns:
        Tuple aus gefiltertem GeoDataFrame und Loss-Dictionary
    """
    filtered = gdf[gdf["min_dist_other_genus"] >= min_distance_m].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = loss / len(gdf) * 100 if len(gdf) > 0 else 0.0

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

    Args:
        gdf: GeoDataFrame mit Baumdaten
        min_samples: Minimum Stichproben pro Stadt (Standard: 500)

    Returns:
        Tuple aus:
        - Liste vieler Gattungen
        - DataFrame mit Statistiken für viable Gattungen
        - DataFrame mit allen Gattungszählungen
    """
    # Zählung pro Stadt × Gattung (rows=cities, cols=genera nach unstack)
    counts_raw = gdf.groupby(["city", "genus_latin"]).size().unstack(fill_value=0)

    # Transponieren: rows=genera, cols=cities
    counts = counts_raw.T

    # Viable = erfüllt Schwellenwert in ALLEN Städten
    expected_cities = ["Berlin", "Hamburg", "Rostock"]
    available_cities = [c for c in expected_cities if c in counts.columns]

    viable_mask = (counts[available_cities] >= min_samples).all(axis=1)
    viable_genera = sorted(counts[viable_mask].index.tolist())

    # Statistiken für viable Gattungen
    if len(viable_genera) > 0:
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

    if len(viable_stats) > 0:
        print("\n  Sample counts:")
        display_cols = available_cities + ["total", "min_city"]
        print(viable_stats[display_cols].to_string())

    return viable_genera, viable_stats, counts

    return viable_genera, viable_stats, counts


def filter_viable_genera(
    gdf: gpd.GeoDataFrame, viable_genera: list[str]
) -> tuple[gpd.GeoDataFrame, dict]:
    """
    Behält nur Bäume der viablen Gattungen.

    Args:
        gdf: GeoDataFrame mit Baumdaten
        viable_genera: Liste der viablen Gattungsnamen

    Returns:
        Tuple aus gefiltertem GeoDataFrame und Loss-Dictionary
    """
    filtered = gdf[gdf["genus_latin"].isin(viable_genera)].copy()

    loss = len(gdf) - len(filtered)
    loss_pct = loss / len(gdf) * 100 if len(gdf) > 0 else 0.0

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

    Args:
        gdf: GeoDataFrame mit Baumdaten
        cell_size_m: Gitterzellengröße in Metern (Standard: 1000 = 1km × 1km)

    Returns:
        GeoDataFrame mit neuen Spalten 'grid_x', 'grid_y', 'grid_id'
    """
    gdf = gdf.copy()
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
    for city in sorted(gdf["city"].unique()):
        city_data = gdf[gdf["city"] == city]
        city_cells = city_data["grid_id"].nunique()
        city_avg = len(city_data) / city_cells if city_cells > 0 else 0
        print(f"    {city}: {city_cells:,} cells, {city_avg:.1f} trees/cell")

    return gdf


def export_filtered_dataset(
    gdf: gpd.GeoDataFrame, variant_name: str, output_dir: Path = PROCESSED_DIR
) -> Path:
    """
    Exportiert gefilterten Datensatz als GeoPackage.

    Args:
        gdf: GeoDataFrame mit gefilterten Baumdaten
        variant_name: 'no_edge' oder 'edge_15m'
        output_dir: Ausgabeverzeichnis

    Returns:
        Pfad zur exportierten Datei
    """
    output_path = output_dir / f"trees_filtered_viable_{variant_name}.gpkg"
    output_dir.mkdir(parents=True, exist_ok=True)

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

    gdf_export = gdf[columns].copy()

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

    Args:
        viable_stats: Statistiken für viable Gattungen
        all_genus_counts: Zählungen für alle Gattungen
        filtering_losses: Liste der Loss-Dictionaries pro Filterschritt
        variant_name: 'no_edge' oder 'edge_15m'
    """
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Viable Genera Statistiken
    viable_path = METADATA_DIR / f"genus_viability_{variant_name}.csv"
    viable_stats.to_csv(viable_path)
    print(f"  ✓ Viable genera stats: {viable_path}")

    # 2. Alle Gattungszählungen (Dokumentation)
    all_genera_path = METADATA_DIR / f"all_genera_counts_{variant_name}.csv"
    all_genus_counts.to_csv(all_genera_path)
    print(f"  ✓ All genera counts: {all_genera_path}")

    # 3. Filtering Losses
    losses_df = pd.DataFrame(filtering_losses)
    losses_df["variant"] = variant_name
    losses_path = METADATA_DIR / f"filtering_losses_{variant_name}.csv"
    losses_df.to_csv(losses_path, index=False)
    print(f"  ✓ Filtering losses: {losses_path}")

    # 4. Summary JSON
    summary = {
        "variant": variant_name,
        "viable_genera": viable_stats.index.tolist() if len(viable_stats) > 0 else [],
        "viable_genera_count": len(viable_stats),
        "total_trees": int(viable_stats["total"].sum()) if len(viable_stats) > 0 else 0,
        "per_city": {},
        "filtering_steps": filtering_losses,
    }

    if len(viable_stats) > 0:
        for city in ["Hamburg", "Berlin", "Rostock"]:
            if city in viable_stats.columns:
                summary["per_city"][city] = int(viable_stats[city].sum())

    summary_path = PROCESSED_DIR / f"filtering_report_{variant_name}.json"
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
    input_path = PROCESSED_DIR / "trees_harmonized.gpkg"
    gdf = gpd.read_file(input_path)
    print(f"  ✓ Loaded: {len(gdf):,} trees")

    # Temporal Filter (für beide Varianten gleich)
    print("\n[2/7] Applying temporal filter (plant_year ≤ 2021)...")
    gdf_temporal, loss_temporal = temporal_filter(gdf)

    # City Boundary Clipping (für beide Varianten gleich)
    print("\n[3/7] Clipping to city core (remove 500m buffer)...")
    gdf_clipped, loss_clip = clip_to_city_core(gdf_temporal, BOUNDARIES_PATH)

    # Edge Distances berechnen (für beide Varianten)
    print("\n[4/7] Calculating edge distances...")
    gdf_with_distances = calculate_edge_distances(gdf_clipped)

    # Gemeinsame Losses speichern
    shared_losses = [loss_temporal, loss_clip]

    # ========================================================================
    # VARIANTE A: Ohne Edge Filter
    # ========================================================================
    print("\n" + "=" * 80)
    print("VARIANT A: NO EDGE FILTER")
    print("=" * 80)

    gdf_no_edge = gdf_with_distances.copy()
    losses_no_edge = shared_losses.copy()

    # Kein Edge Filtering
    print("\n[5/7] Skipping edge filter...")
    print("  ✓ No edge filtering applied")

    # Genus Viability Check
    print("\n[6/7] Checking genus viability (≥500 per city)...")
    viable_genera_no_edge, viable_stats_no_edge, all_counts_no_edge = (
        check_genus_viability(gdf_no_edge)
    )

    gdf_no_edge, loss_genus_no_edge = filter_viable_genera(
        gdf_no_edge, viable_genera_no_edge
    )
    losses_no_edge.append(loss_genus_no_edge)

    # Spatial Grid Assignment
    print("\n[7/7] Assigning spatial grid (1km cells)...")
    gdf_no_edge = create_spatial_grid(gdf_no_edge, cell_size_m=GRID_CELL_SIZE_M)

    # Export
    print("\nExporting dataset...")
    export_filtered_dataset(gdf_no_edge, "no_edge")

    print("\nExporting metadata...")
    export_metadata(viable_stats_no_edge, all_counts_no_edge, losses_no_edge, "no_edge")

    # ========================================================================
    # VARIANTE B: 15m Edge Filter
    # ========================================================================
    print("\n" + "=" * 80)
    print("VARIANT B: 15M EDGE FILTER")
    print("=" * 80)

    gdf_edge = gdf_with_distances.copy()
    losses_edge = shared_losses.copy()

    # Edge Filtering anwenden
    print("\n[5/7] Applying 15m edge filter...")
    gdf_edge, loss_edge = apply_edge_filter(
        gdf_edge, min_distance_m=EDGE_DISTANCE_THRESHOLD_M
    )
    losses_edge.append(loss_edge)

    # Genus Viability Check
    print("\n[6/7] Checking genus viability (≥500 per city)...")
    viable_genera_edge, viable_stats_edge, all_counts_edge = check_genus_viability(
        gdf_edge
    )

    gdf_edge, loss_genus_edge = filter_viable_genera(gdf_edge, viable_genera_edge)
    losses_edge.append(loss_genus_edge)

    # Spatial Grid Assignment
    print("\n[7/7] Assigning spatial grid (1km cells)...")
    gdf_edge = create_spatial_grid(gdf_edge, cell_size_m=GRID_CELL_SIZE_M)

    # Export
    print("\nExporting dataset...")
    export_filtered_dataset(gdf_edge, "edge_15m")

    print("\nExporting metadata...")
    export_metadata(viable_stats_edge, all_counts_edge, losses_edge, "edge_15m")

    # ========================================================================
    # Zusammenfassung
    # ========================================================================
    print("\n" + "=" * 80)
    print("✓ PIPELINE COMPLETE")
    print("=" * 80)

    print("\nVariant A (no_edge):")
    print(f"  Trees: {len(gdf_no_edge):,}")
    print(f"  Genera: {len(viable_genera_no_edge)}")
    if viable_genera_no_edge:
        print(f"  → {', '.join(sorted(viable_genera_no_edge))}")

    print("\nVariant B (edge_15m):")
    print(f"  Trees: {len(gdf_edge):,}")
    print(f"  Genera: {len(viable_genera_edge)}")
    if viable_genera_edge:
        print(f"  → {', '.join(sorted(viable_genera_edge))}")

    # Vergleich: Gattungen die durch Edge Filter verloren gehen
    only_in_no_edge = set(viable_genera_no_edge) - set(viable_genera_edge)
    if only_in_no_edge:
        print(
            f"\n⚠️  Genera lost due to edge filtering: {', '.join(sorted(only_in_no_edge))}"
        )


if __name__ == "__main__":
    main()
