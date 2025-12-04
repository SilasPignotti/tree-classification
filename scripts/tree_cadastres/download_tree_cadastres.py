"""
Lädt Baumkataster-Daten für Hamburg, Berlin und Rostock herunter
und extrahiert Schema-Metadaten für die weitere Datenaufbereitung.

Hamburg: OGC API Features (nicht WFS)
Berlin: WFS mit zwei Layern (Anlagen- und Straßenbäume)
Rostock: WFS
"""

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from owslib.wfs import WebFeatureService

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CITIES,
    TARGET_CRS,
    TREE_CADASTRE_CONFIG,
    TREE_CADASTRES_METADATA_DIR,
    TREE_CADASTRES_RAW_DIR,
)


def download_ogc_api_features(
    city_name: str, base_url: str, output_path: Path
) -> gpd.GeoDataFrame:
    """
    Lädt Daten über OGC API Features (Hamburg).
    """
    print(f"\n{'=' * 60}")
    print(f"Downloading: {city_name} (OGC API Features)")
    print(f"{'=' * 60}")

    all_features: list[dict] = []
    limit = 10000
    offset = 0
    crs_param = "http://www.opengis.net/def/crs/EPSG/0/25832"

    # Pagination durch alle Features
    while True:
        url = f"{base_url}?f=json&limit={limit}&offset={offset}&crs={crs_param}"
        print(f"Fetching offset={offset}...")

        response = requests.get(url, timeout=300)
        response.raise_for_status()

        features = response.json().get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += limit

        if len(features) < limit:
            break

    print(f"Total features fetched: {len(all_features):,}")

    # GeoJSON zu GeoDataFrame konvertieren
    gdf = gpd.GeoDataFrame.from_features(
        {"type": "FeatureCollection", "features": all_features}, crs=TARGET_CRS
    )

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
        gdf["source_layer"] = layer_name
        gdfs.append(gdf)
        print(f"  ✓ {len(gdf):,} features from {layer_name}")

    # Alle Layer zusammenführen
    if not gdfs:
        raise ValueError(f"No layers could be downloaded for {city_name}")
    
    gdf_combined = gdfs[0] if len(gdfs) == 1 else gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
    
    if len(gdfs) > 1:
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
    """
    download_func = {
        "ogc_api_features": lambda: download_ogc_api_features(
            city_name, config["url"], output_path
        ),
        "wfs": lambda: download_wfs(
            city_name, config["url"], config.get("layers"), output_path
        ),
    }
    
    download_type = config["type"]
    if download_type not in download_func:
        raise ValueError(f"Unknown download type: {download_type}")
    
    return download_func[download_type]()


def extract_schema(gdf: gpd.GeoDataFrame, city_name: str) -> dict:
    """
    Extrahiert vollständiges Spalten-Schema mit Metadaten.
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

    total_rows = len(gdf)

    for col in gdf.columns:
        if col == "geometry":
            continue

        null_count = gdf[col].isnull().sum()
        
        col_info = {
            "name": col,
            "dtype": str(gdf[col].dtype),
            "total_values": total_rows,
            "non_null_count": int(total_rows - null_count),
            "null_count": int(null_count),
            "null_percentage": round(null_count / total_rows * 100, 2),
            "unique_count": int(gdf[col].nunique()),
            "sample_values": [],
        }

        # Beispielwerte (erste 10 nicht-null eindeutige Werte)
        non_null = gdf[col].dropna()
        if len(non_null) > 0:
            sample_values = []
            for x in non_null.unique()[:10]:
                if isinstance(x, (np.integer, np.floating, np.ndarray, bool, np.bool_)):
                    sample_values.append(str(x))
                else:
                    sample_values.append(x)
            col_info["sample_values"] = sample_values

        schema["columns"].append(col_info)

    return schema


def generate_summary_report(schemas: dict, output_path: Path) -> pd.DataFrame:
    """
    Erstellt stadtübergreifende Spalten-Vergleichstabelle.
    """
    # Alle eindeutigen Spaltennamen über alle Städte sammeln
    all_columns = {col["name"] for schema in schemas.values() for col in schema["columns"]}

    # Vergleichsmatrix aufbauen
    comparison = []
    for col_name in sorted(all_columns):
        row = {"column_name": col_name}

        for city, schema in schemas.items():
            col_data = next(
                (c for c in schema["columns"] if c["name"] == col_name),
                None,
            )

            if col_data:
                row[f"{city}_dtype"] = col_data["dtype"]
                row[f"{city}_null%"] = col_data["null_percentage"]
                row[f"{city}_unique"] = col_data["unique_count"]
            else:
                row[f"{city}_dtype"] = row[f"{city}_null%"] = row[f"{city}_unique"] = "N/A"

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

    header = f"{'Column Name':<35} {'Type':<12} {'Nulls%':<8} {'Unique':<10} {'Sample Values'}"
    print(header)
    print(f"{'-' * 80}")

    for col in schema["columns"]:
        sample_preview = f"{str(col['sample_values'][:3])}..."[:38]
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
    """
    issues = []

    # Mindestanzahl Bäume prüfen
    if len(gdf) < 10000:
        issues.append(f"Low record count: {len(gdf):,} (expected >10,000)")

    # CRS prüfen
    if gdf.crs is None:
        issues.append("Missing CRS")

    # Geometrie-Spalte und Geometrie-Typen prüfen
    if "geometry" not in gdf.columns:
        issues.append("Missing geometry column")
    elif not gdf.geometry.type.isin(["Point", "MultiPoint"]).all():
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

    TREE_CADASTRES_METADATA_DIR.mkdir(parents=True, exist_ok=True)

    schemas: dict[str, dict] = {}

    # Download und Schema-Extraktion für jede Stadt
    for city in CITIES:
        config = TREE_CADASTRE_CONFIG.get(city)
        if not config:
            print(f"⚠ No config found for {city}")
            continue
            
        try:
            # Download
            output_file = TREE_CADASTRES_RAW_DIR / f"{city.lower()}_trees_raw.gpkg"
            gdf = download_tree_cadastre(city, config, output_file)

            # Validierung
            validate_download(gdf, city)

            # Schema extrahieren
            schema = extract_schema(gdf, city)
            schemas[city] = schema

            # Einzelnes Schema-JSON speichern
            schema_file = TREE_CADASTRES_METADATA_DIR / f"{city.lower()}_schema.json"
            schema_file.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"✓ Schema saved: {schema_file}")

            # Auf Konsole ausgeben
            print_schema_summary(schema)

        except Exception as e:
            print(f"✗ Error processing {city}: {e}")

    # Stadtübergreifenden Vergleich generieren
    if schemas:
        summary_file = TREE_CADASTRES_METADATA_DIR / "schema_summary.csv"
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
