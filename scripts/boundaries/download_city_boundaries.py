"""
Lädt Stadtgrenzen für Hamburg, Berlin und Rostock vom BKG WFS-Dienst,
bereinigt die Daten, erstellt 500m Buffer und speichert die Ergebnisse.
"""

from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import matplotlib.pyplot as plt
import requests


# Konstanten
BASE_URL = "https://sgx.geodatenzentrum.de/wfs_vg250"
LAYER = "vg250:vg250_gem"
CITIES = ["Berlin", "Hamburg", "Rostock"]
OUTPUT_DIR = Path("data/boundaries")
BUFFER_DISTANCE_M = 500


def download_city_boundaries(cities: list[str], temp_file: str = "tmp.gml") -> gpd.GeoDataFrame:
    """
    Lädt Stadtgrenzen vom BKG WFS-Dienst.

    Args:
        cities: Liste der Städtenamen
        temp_file: Temporäre GML-Datei

    Returns:
        GeoDataFrame mit Stadtgrenzen

    Raises:
        requests.HTTPError: Bei Fehlern beim Download
    """
    # WFS-Filter für mehrere Städte
    filter_xml = (
        "<Filter><Or>"
        + "".join(
            f"<PropertyIsEqualTo>"
            f"<ValueReference>gen</ValueReference>"
            f"<Literal>{city}</Literal>"
            f"</PropertyIsEqualTo>"
            for city in cities
        )
        + "</Or></Filter>"
    )

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": LAYER,
        "FILTER": filter_xml,
        "OUTPUTFORMAT": "gml3",
    }

    url = f"{BASE_URL}?{urlencode(params)}"

    print(f"Downloading boundaries for {', '.join(cities)}...")
    response = requests.get(url)
    response.raise_for_status()

    # Temporäre GML-Datei speichern und einlesen
    Path(temp_file).write_bytes(response.content)
    gdf = gpd.read_file(temp_file)

    # Temporäre Datei löschen
    Path(temp_file).unlink()

    return gdf


def clean_boundaries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Bereinigt Stadtgrenzen-Daten und behält nur das größte Polygon pro Stadt.

    Args:
        gdf: Rohe GeoDataFrame vom WFS

    Returns:
        Bereinigte GeoDataFrame mit relevanten Spalten und nur Hauptland-Polygonen
    """
    # Nur relevante Spalten behalten
    wanted_cols = ["gen", "ags", "geometry"]
    gdf_clean = gdf[wanted_cols].copy()

    # Duplikate entfernen (basierend auf Stadtname)
    gdf_clean = gdf_clean.drop_duplicates(subset=["gen"])

    # Nur größtes Polygon pro Stadt behalten (Mainland, ohne kleine Inseln)
    gdf_clean = keep_largest_polygon(gdf_clean)

    print(f"Cleaned boundaries: {len(gdf_clean)} cities")
    return gdf_clean


def keep_largest_polygon(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Behält nur das größte Polygon für jede Stadt (entfernt kleine Inseln).

    Args:
        gdf: GeoDataFrame mit möglicherweise MultiPolygon-Geometrien

    Returns:
        GeoDataFrame mit nur den größten Polygonen pro Stadt
    """
    result_rows = []

    for _, row in gdf.iterrows():
        geom = row.geometry

        # Wenn MultiPolygon, größtes Polygon extrahieren
        if geom.geom_type == "MultiPolygon":
            largest_polygon = max(geom.geoms, key=lambda p: p.area)
            row_copy = row.copy()
            row_copy.geometry = largest_polygon
            result_rows.append(row_copy)
            print(f"  {row['gen']}: Reduced MultiPolygon to largest part")
        else:
            # Wenn bereits Polygon, beibehalten
            result_rows.append(row)

    return gpd.GeoDataFrame(result_rows, crs=gdf.crs)


def create_buffer(
    gdf: gpd.GeoDataFrame, buffer_distance_m: float
) -> gpd.GeoDataFrame:
    """
    Erstellt Buffer um Stadtgrenzen.

    Args:
        gdf: GeoDataFrame mit Stadtgrenzen
        buffer_distance_m: Buffer-Distanz in Metern

    Returns:
        GeoDataFrame mit gepufferten Geometrien
    """
    # In metrisches CRS transformieren für korrekte Buffer-Berechnung
    gdf_metric = gdf.to_crs(epsg=25832)  # ETRS89 / UTM zone 32N (Deutschland)

    # Buffer erstellen
    gdf_buffered = gdf_metric.copy()
    gdf_buffered["geometry"] = gdf_metric.geometry.buffer(buffer_distance_m)

    # Zurück ins Original-CRS
    gdf_buffered = gdf_buffered.to_crs(gdf.crs)

    print(f"Created {buffer_distance_m}m buffer around boundaries")
    return gdf_buffered


def save_boundaries(
    gdf_original: gpd.GeoDataFrame,
    gdf_buffered: gpd.GeoDataFrame,
    output_dir: Path,
) -> None:
    """
    Speichert Stadtgrenzen und gepufferte Grenzen als GeoPackage.

    Args:
        gdf_original: Original-Stadtgrenzen
        gdf_buffered: Gepufferte Stadtgrenzen
        output_dir: Ausgabeverzeichnis
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    original_path = output_dir / "city_boundaries.gpkg"
    buffered_path = output_dir / "city_boundaries_500m_buffer.gpkg"

    gdf_original.to_file(original_path, driver="GPKG")
    gdf_buffered.to_file(buffered_path, driver="GPKG")

    print(f"Saved original boundaries to: {original_path}")
    print(f"Saved buffered boundaries to: {buffered_path}")


def visualize_boundaries(
    gdf_original: gpd.GeoDataFrame,
    gdf_buffered: gpd.GeoDataFrame,
    output_dir: Path,
) -> None:
    """
    Visualisiert Original- und gepufferte Stadtgrenzen.

    Args:
        gdf_original: Original-Stadtgrenzen
        gdf_buffered: Gepufferte Stadtgrenzen
        output_dir: Ausgabeverzeichnis für Plot
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Original-Grenzen
    gdf_original.plot(ax=axes[0], color="lightblue", edgecolor="black", alpha=0.7)
    axes[0].set_title("Original Stadtgrenzen", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Längengrad")
    axes[0].set_ylabel("Breitengrad")

    # Annotate city names
    for idx, row in gdf_original.iterrows():
        centroid = row.geometry.centroid
        axes[0].annotate(
            row["gen"],
            xy=(centroid.x, centroid.y),
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    # Gepufferte Grenzen
    gdf_buffered.plot(ax=axes[1], color="coral", edgecolor="black", alpha=0.5)
    gdf_original.plot(ax=axes[1], color="lightblue", edgecolor="black", alpha=0.7)
    axes[1].set_title(
        "Stadtgrenzen mit 500m Buffer", fontsize=14, fontweight="bold"
    )
    axes[1].set_xlabel("Längengrad")
    axes[1].set_ylabel("Breitengrad")

    # Annotate city names
    for idx, row in gdf_original.iterrows():
        centroid = row.geometry.centroid
        axes[1].annotate(
            row["gen"],
            xy=(centroid.x, centroid.y),
            ha="center",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()

    # Speichern
    output_path = output_dir / "city_boundaries_visualization.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved visualization to: {output_path}")

    # Close figure to prevent interactive display
    plt.close(fig)


def main() -> None:
    """Hauptfunktion: Lädt, verarbeitet und visualisiert Stadtgrenzen."""
    print("=" * 60)
    print("Stadtgrenzen-Download und -Verarbeitung")
    print("=" * 60)

    # 1. Download
    gdf_raw = download_city_boundaries(CITIES)
    print(f"Original CRS: {gdf_raw.crs}")

    # 2. Bereinigen
    gdf_clean = clean_boundaries(gdf_raw)

    # 3. Buffer erstellen
    gdf_buffered = create_buffer(gdf_clean, BUFFER_DISTANCE_M)

    # 4. Speichern
    save_boundaries(gdf_clean, gdf_buffered, OUTPUT_DIR)

    # 5. Visualisieren
    visualize_boundaries(gdf_clean, gdf_buffered, OUTPUT_DIR)

    print("=" * 60)
    print("Fertig!")
    print("=" * 60)


if __name__ == "__main__":
    main()
