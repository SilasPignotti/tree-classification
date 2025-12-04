"""
Lädt Stadtgrenzen für Hamburg, Berlin und Rostock vom BKG WFS-Dienst,
bereinigt die Daten, erstellt 500m Buffer und speichert die Ergebnisse.
"""

import sys
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BKG_WFS_URL,
    BKG_WFS_LAYER,
    BOUNDARIES_DIR,
    BUFFER_DISTANCE_M,
    CITIES,
    TARGET_CRS,
)


def download_city_boundaries(cities: list[str]) -> gpd.GeoDataFrame:
    """
    Lädt Stadtgrenzen vom BKG WFS-Dienst.
    """
    # WFS-Filter für mehrere Städte
    filter_conditions = "".join(
        f"<PropertyIsEqualTo>"
        f"<ValueReference>gen</ValueReference>"
        f"<Literal>{city}</Literal>"
        f"</PropertyIsEqualTo>"
        for city in cities
    )
    filter_xml = f"<Filter><Or>{filter_conditions}</Or></Filter>"

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": BKG_WFS_LAYER,
        "FILTER": filter_xml,
        "OUTPUTFORMAT": "gml3",
    }

    print(f"Downloading boundaries for {', '.join(cities)}...")
    response = requests.get(f"{BKG_WFS_URL}?{urlencode(params)}")
    response.raise_for_status()

    return gpd.read_file(response.content)


def clean_boundaries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Bereinigt Stadtgrenzen-Daten: entfernt Duplikate, behält nur das größte 
    Polygon pro Stadt (entfernt kleine Inseln), und reprojectiert zu EPSG 25832.
    """
    gdf_clean = gdf[["gen", "ags", "geometry"]].drop_duplicates(subset=["gen"])
    
    # Extrahiere größtes Polygon aus MultiPolygons
    gdf_clean["geometry"] = gdf_clean.geometry.apply(
        lambda geom: max(geom.geoms, key=lambda p: p.area) 
        if geom.geom_type == "MultiPolygon" 
        else geom
    )
    
    gdf_clean = gdf_clean.to_crs(TARGET_CRS)
    
    print(f"Cleaned boundaries: {len(gdf_clean)} cities")
    return gdf_clean


def create_buffer(
    gdf: gpd.GeoDataFrame, buffer_distance_m: float
) -> gpd.GeoDataFrame:
    """
    Erstellt Buffer um Stadtgrenzen.
    """
    original_crs = gdf.crs
    gdf_buffered = gdf.to_crs(TARGET_CRS).copy()
    gdf_buffered["geometry"] = gdf_buffered.geometry.buffer(buffer_distance_m)
    gdf_buffered = gdf_buffered.to_crs(original_crs)
    
    print(f"Created {buffer_distance_m}m buffer around boundaries")
    return gdf_buffered


def save_boundaries(
    gdf_original: gpd.GeoDataFrame,
    gdf_buffered: gpd.GeoDataFrame,
    output_dir: Path,
) -> None:
    """
    Speichert Stadtgrenzen und gepufferte Grenzen als GeoPackage.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for gdf, filename in [
        (gdf_original, "city_boundaries.gpkg"),
        (gdf_buffered, "city_boundaries_500m_buffer.gpkg"),
    ]:
        path = output_dir / filename
        gdf.to_file(path, driver="GPKG")
        print(f"Saved {filename} to: {path}")


def main() -> None:
    """Hauptfunktion: Lädt, verarbeitet und speichert Stadtgrenzen."""
    print("=" * 60)
    print("Stadtgrenzen-Download und -Verarbeitung")
    print("=" * 60)

    gdf_raw = download_city_boundaries(CITIES)
    print(f"Original CRS: {gdf_raw.crs}")
    
    gdf_clean = clean_boundaries(gdf_raw)
    gdf_buffered = create_buffer(gdf_clean, BUFFER_DISTANCE_M)
    save_boundaries(gdf_clean, gdf_buffered, BOUNDARIES_DIR)

    print("=" * 60)
    print("Fertig!")
    print("=" * 60)


if __name__ == "__main__":
    main()
