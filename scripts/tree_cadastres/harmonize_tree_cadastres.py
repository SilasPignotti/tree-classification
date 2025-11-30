"""
Harmonisiert die Baumkataster-Daten von Berlin, Hamburg und Rostock
in ein einheitliches Schema mit EPSG:25832 und normalisierten Gattungsnamen.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# Konstanten
BASE_DIR = Path("data/tree_cadastres")
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
METADATA_DIR = BASE_DIR / "metadata"

TARGET_CRS = "EPSG:25832"

# Zielschema
TARGET_COLUMNS = [
    "tree_id",
    "city",
    "genus_latin",
    "species_latin",
    "plant_year",
    "height_m",
    "crown_diameter_m",
    "stem_circumference_cm",
    "source_layer",
    "geometry",
]


def load_raw_data() -> dict[str, gpd.GeoDataFrame]:
    """
    Lädt die rohen Baumkataster-Daten.

    Returns:
        Dictionary mit Stadt-Namen als Keys und GeoDataFrames als Values
    """
    print("Loading raw tree cadastre data...")

    data = {}
    for city in ["berlin", "hamburg", "rostock"]:
        path = RAW_DIR / f"{city}_trees_raw.gpkg"
        gdf = gpd.read_file(path)
        data[city] = gdf
        print(f"  {city.capitalize()}: {len(gdf):,} trees, CRS: {gdf.crs}")

    return data


def normalize_genus(genus: str | None) -> str | None:
    """
    Normalisiert Gattungsnamen zu Uppercase.

    Args:
        genus: Roher Gattungsname

    Returns:
        Normalisierter Gattungsname (Uppercase) oder None
    """
    if pd.isna(genus) or genus is None or str(genus).strip() == "":
        return None
    return str(genus).strip().upper()


def harmonize_berlin(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Berlin-Baumkataster zum Zielschema.

    Args:
        gdf: Rohe Berlin-Daten

    Returns:
        Harmonisierte GeoDataFrame
    """
    print("\nHarmonizing Berlin...")

    # Kopie erstellen
    df = gdf.copy()

    # ID
    df["tree_id"] = df["gisid"]

    # Stadt
    df["city"] = "Berlin"

    # Gattung normalisieren (bereits Uppercase in Berlin)
    df["genus_latin"] = df["gattung"].apply(normalize_genus)

    # Art (lateinisch)
    df["species_latin"] = df["art_bot"]

    # Pflanzjahr (String → Int)
    df["plant_year"] = pd.to_numeric(df["pflanzjahr"], errors="coerce")
    df["plant_year"] = df["plant_year"].astype("Int64")  # Nullable Integer

    # Maße
    df["height_m"] = pd.to_numeric(df["baumhoehe"], errors="coerce")
    df["crown_diameter_m"] = pd.to_numeric(df["kronedurch"], errors="coerce")
    df["stem_circumference_cm"] = pd.to_numeric(df["stammumfg"], errors="coerce")

    # Source Layer (bereits vorhanden)
    # df["source_layer"] bleibt

    # CRS transformieren (25833 → 25832)
    df = df.to_crs(TARGET_CRS)

    # Auf Zielschema reduzieren
    result = gpd.GeoDataFrame(df[TARGET_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")

    return result


def harmonize_hamburg(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Hamburg-Baumkataster zum Zielschema.

    Args:
        gdf: Rohe Hamburg-Daten

    Returns:
        Harmonisierte GeoDataFrame
    """
    print("\nHarmonizing Hamburg...")

    # Kopie erstellen
    df = gdf.copy()

    # ID
    df["tree_id"] = df["baumid"].astype(str)

    # Stadt
    df["city"] = "Hamburg"

    # Gattung normalisieren
    df["genus_latin"] = df["gattung_latein"].apply(normalize_genus)

    # Art (lateinisch)
    df["species_latin"] = df["art_latein"]

    # Pflanzjahr (Float → Int)
    df["plant_year"] = pd.to_numeric(df["pflanzjahr_portal"], errors="coerce")
    df["plant_year"] = df["plant_year"].astype("Int64")  # Nullable Integer

    # Maße (Hamburg hat keine Höhe)
    df["height_m"] = np.nan
    df["crown_diameter_m"] = pd.to_numeric(df["kronendurchmesser"], errors="coerce")
    df["stem_circumference_cm"] = pd.to_numeric(df["stammumfang"], errors="coerce")

    # Source Layer (Hamburg hat keines)
    df["source_layer"] = None

    # MultiPoint → Point (nimm ersten Punkt)
    def multipoint_to_point(geom):
        if geom is None:
            return None
        if geom.geom_type == "MultiPoint":
            # Nimm den ersten Punkt aus dem MultiPoint
            return geom.geoms[0] if len(geom.geoms) > 0 else None
        return geom

    df["geometry"] = df["geometry"].apply(multipoint_to_point)

    # CRS ist bereits 25832
    df = df.set_crs(TARGET_CRS, allow_override=True)

    # Auf Zielschema reduzieren
    result = gpd.GeoDataFrame(df[TARGET_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print(f"  ✓ Geometry converted: MultiPoint → Point")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")

    return result


def harmonize_rostock(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Rostock-Baumkataster zum Zielschema.

    Args:
        gdf: Rohe Rostock-Daten

    Returns:
        Harmonisierte GeoDataFrame
    """
    print("\nHarmonizing Rostock...")

    # Kopie erstellen
    df = gdf.copy()

    # ID
    df["tree_id"] = df["uuid"]

    # Stadt
    df["city"] = "Rostock"

    # Gattung normalisieren
    df["genus_latin"] = df["gattung_botanisch"].apply(normalize_genus)

    # Art (lateinisch)
    df["species_latin"] = df["art_botanisch"]

    # Pflanzjahr (Rostock hat keines)
    df["plant_year"] = pd.NA

    # Maße
    df["height_m"] = pd.to_numeric(df["hoehe"], errors="coerce")
    df["crown_diameter_m"] = pd.to_numeric(df["kronendurchmesser"], errors="coerce")
    df["stem_circumference_cm"] = pd.to_numeric(df["stammumfang"], errors="coerce")

    # Source Layer (bereits vorhanden)
    # df["source_layer"] bleibt

    # CRS transformieren (25833 → 25832)
    df = df.to_crs(TARGET_CRS)

    # Auf Zielschema reduzieren
    result = gpd.GeoDataFrame(df[TARGET_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")

    return result


def validate_harmonized(gdf: gpd.GeoDataFrame) -> bool:
    """
    Validiert das harmonisierte GeoDataFrame.

    Args:
        gdf: Harmonisierte Daten

    Returns:
        True wenn Validierung erfolgreich
    """
    print("\nValidating harmonized data...")
    issues = []

    # CRS prüfen
    if str(gdf.crs) != TARGET_CRS:
        issues.append(f"CRS mismatch: {gdf.crs} (expected {TARGET_CRS})")

    # Spalten prüfen
    missing_cols = set(TARGET_COLUMNS) - set(gdf.columns)
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")

    # Geometrie-Typen prüfen
    geom_types = gdf.geometry.type.unique()
    if not all(gt == "Point" for gt in geom_types):
        issues.append(f"Non-Point geometries found: {geom_types}")

    # Eindeutigkeit prüfen
    duplicates = gdf.groupby(["city", "tree_id"]).size()
    duplicate_count = (duplicates > 1).sum()
    if duplicate_count > 0:
        issues.append(f"Duplicate (city, tree_id) combinations: {duplicate_count}")

    # Städte prüfen
    cities = set(gdf["city"].unique())
    expected_cities = {"Berlin", "Hamburg", "Rostock"}
    if cities != expected_cities:
        issues.append(f"Cities mismatch: {cities} (expected {expected_cities})")

    if issues:
        print("⚠ Validation warnings:")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print("✓ All validations passed")
    return True


def print_summary(gdf: gpd.GeoDataFrame) -> None:
    """Gibt Zusammenfassung der harmonisierten Daten aus."""
    print("\n" + "=" * 80)
    print("HARMONIZATION SUMMARY")
    print("=" * 80)

    # Pro Stadt
    print("\nTrees per city:")
    city_counts = gdf.groupby("city").size()
    for city, count in city_counts.items():
        print(f"  {city:<10} {count:>10,}")
    print(f"  {'TOTAL':<10} {len(gdf):>10,}")

    # Top Gattungen
    print("\nTop 15 genera (genus_latin):")
    genus_counts = gdf["genus_latin"].value_counts().head(15)
    for genus, count in genus_counts.items():
        pct = count / len(gdf) * 100
        print(f"  {genus:<20} {count:>10,} ({pct:>5.1f}%)")

    # NA-Anteile
    print("\nNull value percentages:")
    for col in ["genus_latin", "species_latin", "plant_year", "height_m", "source_layer"]:
        null_pct = gdf[col].isna().sum() / len(gdf) * 100
        print(f"  {col:<25} {null_pct:>6.1f}%")

    # Geometry stats
    print(f"\nGeometry type: {gdf.geometry.type.unique()[0]}")
    print(f"CRS: {gdf.crs}")


def main() -> None:
    """Hauptfunktion: Harmonisiert alle Baumkataster."""
    print("=" * 80)
    print("Baumkataster-Harmonisierung")
    print("=" * 80)

    # Ausgabeverzeichnis erstellen
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Rohdaten laden
    raw_data = load_raw_data()

    # Städte harmonisieren
    berlin_harmonized = harmonize_berlin(raw_data["berlin"])
    hamburg_harmonized = harmonize_hamburg(raw_data["hamburg"])
    rostock_harmonized = harmonize_rostock(raw_data["rostock"])

    # Zusammenführen
    print("\nMerging all cities...")
    gdf_all = gpd.GeoDataFrame(
        pd.concat([berlin_harmonized, hamburg_harmonized, rostock_harmonized], ignore_index=True),
        crs=TARGET_CRS,
    )
    print(f"✓ Total: {len(gdf_all):,} trees")

    # Validieren
    validate_harmonized(gdf_all)

    # Zusammenfassung
    print_summary(gdf_all)

    # Speichern
    output_path = PROCESSED_DIR / "trees_harmonized.gpkg"
    gdf_all.to_file(output_path, driver="GPKG")
    print(f"\n✓ Saved to: {output_path}")

    # Dateigröße
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"✓ File size: {size_mb:.1f} MB")

    print("\n" + "=" * 80)
    print("✓ Harmonization complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
