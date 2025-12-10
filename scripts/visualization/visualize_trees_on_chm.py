"""
Visualisierung von Baumkataster-Punkten auf Berlin 1m-CHM.

Erstellt zwei Arten von Visualisierungen:
1. Übersichtskarte: 500×500m Ausschnitt mit CHM als Hillshade und Baumkataster als Punkte
2. Detail-Ansichten: 6-8 zufällige Bäume mit 50×50m Zoom, CHM-Detail und Annotationen

Usage:
    uv run python scripts/visualization/visualize_trees_on_chm.py
"""

import sys
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib import patheffects
from rasterio.windows import Window

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import CHM_DIR, TARGET_CRS, TREE_CADASTRES_PROCESSED_DIR

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Overview map parameters
OVERVIEW_CENTER_X = 391000
OVERVIEW_CENTER_Y = 5820000
OVERVIEW_SIZE_M = 500

# Detail map parameters
DETAIL_SIZE_M = 50
NUM_DETAIL_PLOTS = 8
RANDOM_SEED = 42

# Visualization parameters
HILLSHADE_AZIMUTH = 315  # Light source from NW
HILLSHADE_ALTITUDE = 45  # Light angle
TREE_POINT_COLOR = "red"
TREE_POINT_SIZE = 30
TREE_POINT_ALPHA = 0.8

np.random.seed(RANDOM_SEED)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def load_chm(city: str = "Berlin") -> Tuple[np.ndarray, rasterio.Affine, rasterio.CRS]:
    """
    Lädt CHM-Raster für eine Stadt.

    Args:
        city: Stadtname (default: Berlin)

    Returns:
        Tuple mit (CHM-Array, Affine-Transform, CRS)

    Raises:
        FileNotFoundError: Wenn CHM-File nicht existiert
    """
    chm_path = CHM_DIR / "processed" / f"CHM_1m_{city}.tif"

    if not chm_path.exists():
        raise FileNotFoundError(f"CHM file not found: {chm_path}")

    with rasterio.open(chm_path) as src:
        chm = src.read(1)
        transform = src.transform
        crs = src.crs

        # NoData zu NaN konvertieren
        if src.nodata is not None:
            chm = np.where(np.isclose(chm, src.nodata), np.nan, chm).astype(np.float32)

    print(f"✓ CHM geladen: {chm.shape} pixels, CRS: {crs}")
    return chm, transform, crs


def load_trees(city: str = "Berlin") -> gpd.GeoDataFrame:
    """
    Lädt Baumkataster und filtert nach Stadt.

    Args:
        city: Stadtname (default: Berlin)

    Returns:
        GeoDataFrame mit gefilterten Bäumen

    Raises:
        FileNotFoundError: Wenn Baumkataster-File nicht existiert
        ValueError: Wenn keine Bäume für Stadt gefunden
    """
    trees_path = TREE_CADASTRES_PROCESSED_DIR / "trees_filtered_viable_no_edge.gpkg"

    if not trees_path.exists():
        raise FileNotFoundError(f"Tree cadastre file not found: {trees_path}")

    trees = gpd.read_file(trees_path)
    trees_city = trees[trees["city"] == city].copy()

    if len(trees_city) == 0:
        raise ValueError(f"No trees found for city: {city}")

    # CRS prüfen und ggf. reprojecten
    if trees_city.crs.to_string() != TARGET_CRS:
        trees_city = trees_city.to_crs(TARGET_CRS)

    print(f"✓ Baumkataster geladen: {len(trees_city):,} Bäume für {city}")
    return trees_city


def create_hillshade(
    dem: np.ndarray, azimuth: float = 315, altitude: float = 45
) -> np.ndarray:
    """
    Erstellt Hillshade aus DEM/CHM.

    Args:
        dem: Digital Elevation Model (CHM) als 2D-Array
        azimuth: Azimuth des Lichts in Grad (0-360)
        altitude: Höhenwinkel des Lichts in Grad (0-90)

    Returns:
        Hillshade-Array (0-255, uint8)
    """
    # Handle NaN values
    dem_filled = np.nan_to_num(dem, nan=0.0)

    # Convert angles to radians
    azimuth_rad = np.radians(360.0 - azimuth + 90)
    altitude_rad = np.radians(altitude)

    # Calculate gradients
    dy, dx = np.gradient(dem_filled)

    # Calculate slope and aspect
    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dx, dy)

    # Calculate hillshade
    shaded = np.sin(altitude_rad) * np.cos(slope) + np.cos(altitude_rad) * np.sin(
        slope
    ) * np.cos(azimuth_rad - aspect)

    # Normalize to 0-255
    shaded = (shaded + 1) / 2 * 255
    shaded = np.clip(shaded, 0, 255).astype(np.uint8)

    return shaded


def get_window_for_extent(
    center_x: float, center_y: float, size_m: float, transform: rasterio.Affine
) -> Tuple[Window, Tuple[float, float, float, float]]:
    """
    Berechnet rasterio Window für gegebenen räumlichen Ausschnitt.

    Args:
        center_x: X-Koordinate des Zentrums
        center_y: Y-Koordinate des Zentrums
        size_m: Größe des Ausschnitts in Metern (quadratisch)
        transform: Affine-Transform des Rasters

    Returns:
        Tuple mit (Window, extent_tuple)
        extent_tuple: (xmin, xmax, ymin, ymax) für matplotlib
    """
    half_size = size_m / 2

    # Extent berechnen
    xmin = center_x - half_size
    xmax = center_x + half_size
    ymin = center_y - half_size
    ymax = center_y + half_size

    # Pixel-Koordinaten berechnen
    col_off, row_off = ~transform * (xmin, ymax)
    col_off, row_off = int(col_off), int(row_off)

    # Window-Größe in Pixeln (1m Auflösung)
    width = height = int(size_m)

    window = Window(col_off, row_off, width, height)
    extent = (xmin, xmax, ymin, ymax)

    return window, extent


def select_random_trees(trees: gpd.GeoDataFrame, n: int = 8) -> gpd.GeoDataFrame:
    """
    Wählt zufällige Bäume mit vollständigen Attributen aus.

    Args:
        trees: GeoDataFrame mit allen Bäumen
        n: Anzahl der zu wählenden Bäume

    Returns:
        GeoDataFrame mit n zufälligen Bäumen
    """
    # Filter: Nur Bäume mit vollständigen Attributen
    valid_trees = trees[
        trees["genus_latin"].notna()
        & trees["height_m"].notna()
        & (trees["height_m"] > 0)
    ].copy()

    if len(valid_trees) < n:
        print(f"⚠ Warning: Only {len(valid_trees)} valid trees found, using all")
        return valid_trees

    # Zufällige Auswahl
    selected = valid_trees.sample(n=n, random_state=RANDOM_SEED)
    return selected


# =============================================================================
# PLOTTING FUNCTIONS
# =============================================================================


def plot_overview(
    chm: np.ndarray,
    transform: rasterio.Affine,
    trees: gpd.GeoDataFrame,
    center_x: float,
    center_y: float,
    size_m: float,
    output_path: Path,
) -> None:
    """
    Erstellt Übersichtskarte mit CHM-Hillshade und Baumkataster-Punkten.

    Args:
        chm: CHM-Array
        transform: Affine-Transform
        trees: GeoDataFrame mit Bäumen
        center_x: X-Koordinate des Zentrums
        center_y: Y-Koordinate des Zentrums
        size_m: Größe des Ausschnitts in Metern
        output_path: Pfad für Output-File
    """
    # Window und Extent berechnen
    window, extent = get_window_for_extent(center_x, center_y, size_m, transform)

    # CHM-Ausschnitt laden
    chm_subset = chm[
        window.row_off : window.row_off + window.height,
        window.col_off : window.col_off + window.width,
    ]

    # Hillshade erstellen
    hillshade = create_hillshade(chm_subset, HILLSHADE_AZIMUTH, HILLSHADE_ALTITUDE)

    # Bäume im Ausschnitt filtern
    xmin, xmax, ymin, ymax = extent
    trees_subset = trees.cx[xmin:xmax, ymin:ymax]

    # Plot erstellen
    fig, ax = plt.subplots(figsize=(12, 12))

    # Hillshade plotten
    ax.imshow(hillshade, extent=extent, cmap="gray", alpha=0.8)

    # CHM als Farboverlay
    chm_masked = np.ma.masked_invalid(chm_subset)
    im = ax.imshow(chm_masked, extent=extent, cmap="YlGn", alpha=0.5, vmin=0, vmax=30)

    # Bäume plotten
    trees_subset.plot(
        ax=ax,
        color=TREE_POINT_COLOR,
        markersize=TREE_POINT_SIZE,
        alpha=TREE_POINT_ALPHA,
        edgecolor="black",
        linewidth=0.5,
    )

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("CHM Height [m]", fontsize=12)

    # Labels und Titel
    ax.set_xlabel("Easting [m]", fontsize=12)
    ax.set_ylabel("Northing [m]", fontsize=12)
    ax.set_title(
        f"Berlin CHM + Baumkataster\n"
        f"Zentrum: ({center_x}, {center_y}), Größe: {size_m}×{size_m}m\n"
        f"Bäume: {len(trees_subset):,}",
        fontsize=14,
        fontweight="bold",
    )

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Übersichtskarte gespeichert: {output_path}")


def plot_detail(
    chm: np.ndarray,
    transform: rasterio.Affine,
    tree: gpd.GeoSeries,
    size_m: float,
    output_path: Path,
) -> None:
    """
    Erstellt Detail-Ansicht eines einzelnen Baums.

    Args:
        chm: CHM-Array
        transform: Affine-Transform
        tree: GeoSeries mit Baum-Attributen (einzelne Zeile)
        size_m: Größe des Ausschnitts in Metern
        output_path: Pfad für Output-File
    """
    # Baum-Koordinaten extrahieren
    tree_x = tree.geometry.x
    tree_y = tree.geometry.y

    # Window und Extent berechnen
    window, extent = get_window_for_extent(tree_x, tree_y, size_m, transform)

    # CHM-Ausschnitt laden
    chm_subset = chm[
        window.row_off : window.row_off + window.height,
        window.col_off : window.col_off + window.width,
    ]

    # Hillshade erstellen
    hillshade = create_hillshade(chm_subset, HILLSHADE_AZIMUTH, HILLSHADE_ALTITUDE)

    # Plot erstellen
    fig, ax = plt.subplots(figsize=(10, 10))

    # Hillshade plotten
    ax.imshow(hillshade, extent=extent, cmap="gray", alpha=0.8)

    # CHM als Farboverlay
    chm_masked = np.ma.masked_invalid(chm_subset)
    im = ax.imshow(chm_masked, extent=extent, cmap="YlGn", alpha=0.6, vmin=0, vmax=30)

    # Baum-Punkt plotten
    ax.scatter(
        tree_x,
        tree_y,
        color=TREE_POINT_COLOR,
        s=200,
        alpha=1.0,
        edgecolor="white",
        linewidth=2,
        marker="o",
        zorder=10,
    )

    # Annotation hinzufügen
    tree_id = tree.get("tree_id", "N/A")
    genus = tree.get("genus_latin", "N/A")
    height = tree.get("height_m", np.nan)

    annotation_text = f"ID: {tree_id}\n{genus}\nH: {height:.1f}m"

    # Text mit Outline für bessere Lesbarkeit
    text = ax.text(
        tree_x,
        tree_y + size_m * 0.35,
        annotation_text,
        fontsize=11,
        fontweight="bold",
        ha="center",
        va="center",
        color="white",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="black", alpha=0.7),
        zorder=11,
    )
    text.set_path_effects(
        [patheffects.withStroke(linewidth=3, foreground="black", alpha=0.8)]
    )

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("CHM Height [m]", fontsize=11)

    # Labels und Titel
    ax.set_xlabel("Easting [m]", fontsize=11)
    ax.set_ylabel("Northing [m]", fontsize=11)
    ax.set_title(
        f"Detail-Ansicht: {genus}\nPosition: ({tree_x:.1f}, {tree_y:.1f})",
        fontsize=13,
        fontweight="bold",
    )

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Detail-Ansicht gespeichert: {output_path.name}")


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Hauptfunktion: Erstellt alle Visualisierungen."""
    print("=" * 70)
    print("VISUALISIERUNG: Baumkataster auf Berlin CHM")
    print("=" * 70)

    # Daten laden
    print("\n1. Daten laden...")
    chm, transform, crs = load_chm("Berlin")
    trees = load_trees("Berlin")

    # Übersichtskarte erstellen
    print("\n2. Übersichtskarte erstellen...")
    overview_output = OUTPUT_DIR / "berlin_chm_trees_overview.png"
    plot_overview(
        chm,
        transform,
        trees,
        OVERVIEW_CENTER_X,
        OVERVIEW_CENTER_Y,
        OVERVIEW_SIZE_M,
        overview_output,
    )

    # Zufällige Bäume für Detail-Ansichten auswählen
    print(f"\n3. {NUM_DETAIL_PLOTS} zufällige Bäume für Detail-Ansichten auswählen...")
    selected_trees = select_random_trees(trees, NUM_DETAIL_PLOTS)
    print(f"   Ausgewählte Bäume: {len(selected_trees)}")

    # Detail-Ansichten erstellen
    print(f"\n4. {len(selected_trees)} Detail-Ansichten erstellen...")
    for idx, (_, tree) in enumerate(selected_trees.iterrows(), start=1):
        detail_output = OUTPUT_DIR / f"berlin_chm_trees_detail_{idx}.png"
        plot_detail(chm, transform, tree, DETAIL_SIZE_M, detail_output)

    print("\n" + "=" * 70)
    print("✓ FERTIG: Alle Visualisierungen erstellt!")
    print(f"  Output-Verzeichnis: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
