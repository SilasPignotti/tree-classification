"""
Lädt Baumkataster-Daten für Hamburg, Berlin und Rostock herunter
und extrahiert Schema-Metadaten für die weitere Datenaufbereitung.

Hamburg: OGC API Features (nicht WFS)
Berlin: WFS mit zwei Layern (Anlagen- und Straßenbäume)
Rostock: WFS
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from owslib.wfs import WebFeatureService


# Konstanten
BASE_DIR = Path("data/tree_cadastres")
RAW_DIR = BASE_DIR / "raw"
METADATA_DIR = BASE_DIR / "metadata"

# Konfiguration pro Stadt
CITY_CONFIG = {
    "Hamburg": {
        "type": "ogc_api_features",
        "url": "https://api.hamburg.de/datasets/v1/strassenbaumkataster/collections/strassenbaumkataster_hh/items",
        "crs": "EPSG:25832",
    },
    "Berlin": {
        "type": "wfs",
        "url": "https://gdi.berlin.de/services/wfs/baumbestand",
        "layers": ["baumbestand:anlagenbaeume", "baumbestand:strassenbaeume"],
    },
    "Rostock": {
        "type": "wfs",
        "url": "https://geo.sv.rostock.de/geodienste/baeume/wfs",
        "layers": None,  # Alle Layer verwenden
    },
}


def download_ogc_api_features(
    city_name: str, base_url: str, output_path: Path, crs: str = "EPSG:25832"
) -> gpd.GeoDataFrame:
    """
    Lädt Daten über OGC API Features (Hamburg).

    Args:
        city_name: Stadtname
        base_url: OGC API Features Items-Endpunkt
        output_path: Ausgabepfad für GeoPackage
        crs: Ziel-CRS für die Daten

    Returns:
        GeoDataFrame mit Baumkatasterdaten
    """
    print(f"\n{'=' * 60}")
    print(f"Downloading: {city_name} (OGC API Features)")
    print(f"{'=' * 60}")

    all_features: list[dict] = []
    limit = 10000  # Maximale Features pro Request
    offset = 0

    # Pagination durch alle Features
    while True:
        url = f"{base_url}?f=json&limit={limit}&offset={offset}&crs=http://www.opengis.net/def/crs/EPSG/0/25832"
        print(f"Fetching offset={offset}...")

        response = requests.get(url, timeout=300)
        response.raise_for_status()

        data = response.json()
        features = data.get("features", [])

        if not features:
            break

        all_features.extend(features)
        offset += limit

        # Abbruch wenn weniger als limit Features zurückkommen
        if len(features) < limit:
            break

    print(f"Total features fetched: {len(all_features):,}")

    # GeoJSON zu GeoDataFrame konvertieren
    geojson = {"type": "FeatureCollection", "features": all_features}
    gdf = gpd.GeoDataFrame.from_features(geojson, crs=crs)

    # Speichern
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GPKG")

    print(f"✓ Downloaded: {len(gdf):,} trees")
    print(f"✓ Saved to: {output_path}")

    return gdf


def download_wfs(
    city_name: str, wfs_url: str, layers: list[str] | None, output_path: Path
) -> gpd.GeoDataFrame:
    """
    Lädt Baumkataster über WFS GetFeature herunter.

    Args:
        city_name: Stadtname
        wfs_url: WFS-Service-Endpunkt
        layers: Liste der Layer-Namen oder None für ersten Layer
        output_path: Ausgabepfad für GeoPackage

    Returns:
        GeoDataFrame mit Baumkatasterdaten
    """
    print(f"\n{'=' * 60}")
    print(f"Downloading: {city_name} (WFS)")
    print(f"{'=' * 60}")

    # WFS-Verbindung aufbauen
    print(f"Connecting to WFS: {wfs_url}")
    wfs = WebFeatureService(url=wfs_url, version="2.0.0")

    # Verfügbare Layer auflisten
    available_layers = list(wfs.contents.keys())
    print(f"Available layers: {available_layers}")

    # Layer bestimmen
    if layers is None:
        layers = [available_layers[0]]

    gdfs: list[gpd.GeoDataFrame] = []

    for layer_name in layers:
        if layer_name not in available_layers:
            print(f"⚠ Layer not found: {layer_name}")
            continue

        print(f"Downloading layer: {layer_name}...")
        response = wfs.getfeature(
            typename=layer_name, outputFormat="application/gml+xml; version=3.2"
        )
        gdf = gpd.read_file(response)
        gdf["source_layer"] = layer_name  # Herkunft merken
        gdfs.append(gdf)
        print(f"  ✓ {len(gdf):,} features from {layer_name}")

    # Alle Layer zusammenführen
    if len(gdfs) == 0:
        raise ValueError(f"No layers could be downloaded for {city_name}")
    elif len(gdfs) == 1:
        gdf_combined = gdfs[0]
    else:
        gdf_combined = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
        print(f"✓ Combined {len(gdfs)} layers: {len(gdf_combined):,} total features")

    # Speichern
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf_combined.to_file(output_path, driver="GPKG")

    print(f"✓ Downloaded: {len(gdf_combined):,} trees")
    print(f"✓ Saved to: {output_path}")

    return gdf_combined


def download_tree_cadastre(city_name: str, config: dict, output_path: Path) -> gpd.GeoDataFrame:
    """
    Lädt Baumkataster basierend auf Stadtkonfiguration.

    Args:
        city_name: Stadtname
        config: Konfiguration mit type, url, etc.
        output_path: Ausgabepfad für GeoPackage

    Returns:
        GeoDataFrame mit Baumkatasterdaten
    """
    if config["type"] == "ogc_api_features":
        return download_ogc_api_features(
            city_name, config["url"], output_path, config.get("crs", "EPSG:25832")
        )
    elif config["type"] == "wfs":
        return download_wfs(city_name, config["url"], config.get("layers"), output_path)
    else:
        raise ValueError(f"Unknown download type: {config['type']}")


def extract_schema(gdf: gpd.GeoDataFrame, city_name: str) -> dict:
    """
    Extrahiert vollständiges Spalten-Schema mit Metadaten.

    Args:
        gdf: GeoDataFrame mit Baumkatasterdaten
        city_name: Stadtname

    Returns:
        Schema-Dictionary mit Datentypen, Beispielwerten, Null-Counts
    """
    schema = {
        "city": city_name,
        "total_records": len(gdf),
        "total_columns": len(gdf.columns),
        "crs": str(gdf.crs) if gdf.crs else "Unknown",
        "geometry_type": gdf.geometry.type.unique().tolist() if "geometry" in gdf.columns else [],
        "bounds": gdf.total_bounds.tolist() if "geometry" in gdf.columns else [],
        "columns": [],
    }

    for col in gdf.columns:
        if col == "geometry":
            continue

        col_info = {
            "name": col,
            "dtype": str(gdf[col].dtype),
            "total_values": len(gdf),
            "non_null_count": int(gdf[col].count()),
            "null_count": int(gdf[col].isnull().sum()),
            "null_percentage": round(gdf[col].isnull().sum() / len(gdf) * 100, 2),
            "unique_count": int(gdf[col].nunique()),
            "sample_values": [],
        }

        # Beispielwerte (erste 10 nicht-null eindeutige Werte)
        non_null = gdf[col].dropna()
        if len(non_null) > 0:
            unique_samples = non_null.unique()[:10]
            # NumPy-Typen und booleans in native Python-Typen konvertieren für JSON
            sample_values = []
            for x in unique_samples:
                if isinstance(x, (np.integer, np.floating, np.ndarray)):
                    sample_values.append(str(x))
                elif isinstance(x, (bool, np.bool_)):
                    sample_values.append(str(x))
                else:
                    sample_values.append(x)
            col_info["sample_values"] = sample_values

        schema["columns"].append(col_info)

    return schema


def generate_summary_report(schemas: dict, output_path: Path) -> pd.DataFrame:
    """
    Erstellt stadtübergreifende Spalten-Vergleichstabelle.

    Args:
        schemas: Dictionary {city_name: schema_dict}
        output_path: CSV-Ausgabepfad

    Returns:
        DataFrame mit Spaltenvergleich
    """
    # Alle eindeutigen Spaltennamen über alle Städte sammeln
    all_columns: set[str] = set()
    for schema in schemas.values():
        all_columns.update([col["name"] for col in schema["columns"]])

    # Vergleichsmatrix aufbauen
    comparison = []
    for col_name in sorted(all_columns):
        row = {"column_name": col_name}

        for city, schema in schemas.items():
            # Spalte in dieser Stadt suchen
            col_data = next(
                (c for c in schema["columns"] if c["name"] == col_name),
                None,
            )

            if col_data:
                row[f"{city}_dtype"] = col_data["dtype"]
                row[f"{city}_null%"] = col_data["null_percentage"]
                row[f"{city}_unique"] = col_data["unique_count"]
            else:
                row[f"{city}_dtype"] = "N/A"
                row[f"{city}_null%"] = "N/A"
                row[f"{city}_unique"] = "N/A"

        comparison.append(row)

    df = pd.DataFrame(comparison)
    df.to_csv(output_path, index=False)

    print(f"\n✓ Summary report saved: {output_path}")

    return df


def print_schema_summary(schema: dict) -> None:
    """Gibt lesbare Schema-Zusammenfassung auf der Konsole aus."""
    print(f"\n{'=' * 80}")
    print(f"SCHEMA SUMMARY: {schema['city']}")
    print(f"{'=' * 80}")
    print(f"Total records:    {schema['total_records']:,}")
    print(f"Total columns:    {schema['total_columns']}")
    print(f"CRS:              {schema['crs']}")
    print(f"Geometry type:    {', '.join(schema['geometry_type'])}")
    print(f"Bounds (EPSG):    {[round(b, 1) for b in schema['bounds']]}")

    print(f"\n{'-' * 80}")
    print(f"COLUMNS ({len(schema['columns'])} total):")
    print(f"{'-' * 80}")

    # Tabellenkopf
    header = f"{'Column Name':<35} {'Type':<12} {'Nulls%':<8} {'Unique':<10} {'Sample Values'}"
    print(header)
    print(f"{'-' * 80}")

    for col in schema["columns"]:
        sample_preview = str(col["sample_values"][:3])[:35] + "..."
        print(
            f"{col['name']:<35} "
            f"{col['dtype']:<12} "
            f"{col['null_percentage']:<8.1f} "
            f"{col['unique_count']:<10} "
            f"{sample_preview}"
        )


def validate_download(gdf: gpd.GeoDataFrame, city_name: str) -> bool:
    """
    Validiert heruntergeladene Daten.

    Args:
        gdf: GeoDataFrame mit Baumkatasterdaten
        city_name: Stadtname

    Returns:
        True wenn Validierung erfolgreich
    """
    issues = []

    # Mindestanzahl Bäume prüfen
    if len(gdf) < 10000:
        issues.append(f"Low record count: {len(gdf):,} (expected >10,000)")

    # CRS prüfen
    if gdf.crs is None:
        issues.append("Missing CRS")

    # Geometrie-Spalte prüfen
    if "geometry" not in gdf.columns:
        issues.append("Missing geometry column")
    elif not all(gdf.geometry.type.isin(["Point", "MultiPoint"])):
        issues.append(f"Unexpected geometry types: {gdf.geometry.type.unique().tolist()}")

    if issues:
        print(f"⚠ Validation warnings for {city_name}:")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print(f"✓ Validation passed for {city_name}")
    return True


def main() -> None:
    """Hauptfunktion: Lädt Baumkataster und extrahiert Schemas."""
    print("=" * 60)
    print("Baumkataster-Download und Schema-Extraktion")
    print("=" * 60)

    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    schemas: dict[str, dict] = {}

    # Download und Schema-Extraktion für jede Stadt
    for city, config in CITY_CONFIG.items():
        try:
            # Download
            output_file = RAW_DIR / f"{city.lower()}_trees_raw.gpkg"
            gdf = download_tree_cadastre(city, config, output_file)

            # Validierung
            validate_download(gdf, city)

            # Schema extrahieren
            schema = extract_schema(gdf, city)
            schemas[city] = schema

            # Einzelnes Schema-JSON speichern
            schema_file = METADATA_DIR / f"{city.lower()}_schema.json"
            with open(schema_file, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2, ensure_ascii=False)

            print(f"✓ Schema saved: {schema_file}")

            # Auf Konsole ausgeben
            print_schema_summary(schema)

        except Exception as e:
            print(f"✗ Error processing {city}: {e}")
            continue

    # Stadtübergreifenden Vergleich generieren
    if schemas:
        summary_file = METADATA_DIR / "schema_summary.csv"
        generate_summary_report(schemas, summary_file)

        # Zusammenfassungsstatistiken ausgeben
        print(f"\n{'=' * 80}")
        print("CROSS-CITY SUMMARY")
        print(f"{'=' * 80}")
        for city, schema in schemas.items():
            print(f"{city:<15} {schema['total_records']:>10,} trees, {schema['total_columns']:>3} columns")

    print(f"\n{'=' * 80}")
    print("✓ All downloads and schema extractions complete")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
