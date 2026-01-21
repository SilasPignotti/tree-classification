"""
Harmonisiert die Baumkataster-Daten von Berlin, Hamburg und Rostock
in ein einheitliches Schema mit EPSG:25832 und normalisierten Gattungs-/Artnamen.

Normalisierung:
- genus_latin: UPPERCASE (z.B. "QUERCUS")
- species_latin: lowercase, ohne Gattungspräfix (z.B. "robur" statt "Quercus robur")
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CITIES,
    TARGET_CRS,
    TREE_CADASTRE_COLUMNS,
    TREE_CADASTRES_PROCESSED_DIR,
    TREE_CADASTRES_RAW_DIR,
)


def load_raw_data() -> dict[str, gpd.GeoDataFrame]:
    """
    Lädt die rohen Baumkataster-Daten.
    """
    print("Loading raw tree cadastre data...")

    result = {}
    for city in CITIES:
        gdf = gpd.read_file(TREE_CADASTRES_RAW_DIR / f"{city.lower()}_trees_raw.gpkg")
        print(f"  {city}: {len(gdf):,} trees, CRS: {gdf.crs}")
        result[city.lower()] = gdf
    return result


def normalize_genus(genus: str | None) -> str | None:
    """
    Normalisiert Gattungsnamen zu Uppercase.
    """
    if not genus or pd.isna(genus) or not str(genus).strip():
        return None
    return str(genus).strip().upper()


def normalize_species(species: str | None) -> str | None:
    """
    Normalisiert Artnamen zu lowercase.
    
    Entfernt Gattungspräfix falls vorhanden (z.B. "Quercus robur" -> "robur").
    """
    if not species or pd.isna(species):
        return None
    
    species_str = str(species).strip()
    if not species_str:
        return None
    
    parts = species_str.split()
    
    # Remove genus prefix (first word) if present and capitalized
    if len(parts) > 1 and parts[0][0].isupper():
        return " ".join(parts[1:]).lower()
    
    return species_str.lower()


def harmonize_berlin(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Berlin-Baumkataster zum Zielschema.
    """
    print("\nHarmonizing Berlin...")

    df = gdf.copy()

    df["tree_id"] = df["gisid"]
    df["city"] = "Berlin"
    df["genus_latin"] = df["gattung"].apply(normalize_genus)
    df["species_latin"] = df["art_bot"].apply(normalize_species)
    df["plant_year"] = pd.to_numeric(df["pflanzjahr"], errors="coerce").astype("Int64")
    df["height_m"] = pd.to_numeric(df["baumhoehe"], errors="coerce")
    
    # Map source_layer to tree_type for Berlin trees
    df["tree_type"] = df["source_layer"].map({
        "baumbestand:anlagenbaeume": "Anlagenbaum",
        "baumbestand:strassenbaeume": "Straßenbaum",
    })

    df = df.to_crs(TARGET_CRS)

    result = gpd.GeoDataFrame(df[TREE_CADASTRE_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")
    print(f"  ✓ Unique species: {result['species_latin'].nunique()}")

    return result


def harmonize_hamburg(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Hamburg-Baumkataster zum Zielschema.
    """
    print("\nHarmonizing Hamburg...")

    df = gdf.copy()
    
    df["tree_id"] = df["baumid"].astype(str)
    df["city"] = "Hamburg"
    df["genus_latin"] = df["gattung_latein"].apply(normalize_genus)
    df["species_latin"] = df["art_latein"].apply(normalize_species)
    df["plant_year"] = pd.to_numeric(df["pflanzjahr_portal"], errors="coerce").astype("Int64")
    df["height_m"] = np.nan
    df["tree_type"] = np.nan
    
    # Convert MultiPoint to Point geometry
    df["geometry"] = df["geometry"].apply(
        lambda geom: (geom.geoms[0] if geom.geom_type == "MultiPoint" and len(geom.geoms) > 0 else geom)
        if geom is not None else None
    )
    
    result = gpd.GeoDataFrame(df[TREE_CADASTRE_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print("  ✓ Geometry converted: MultiPoint → Point")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")
    print(f"  ✓ Unique species: {result['species_latin'].nunique()}")

    return result


def harmonize_rostock(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Harmonisiert Rostock-Baumkataster zum Zielschema.
    """
    print("\nHarmonizing Rostock...")

    df = gdf.copy()
    
    df["tree_id"] = df["uuid"]
    df["city"] = "Rostock"
    df["genus_latin"] = df["gattung_botanisch"].apply(normalize_genus)
    df["species_latin"] = df["art_botanisch"].apply(normalize_species)
    df["plant_year"] = pd.NA
    df["height_m"] = pd.to_numeric(df["hoehe"], errors="coerce")
    df["tree_type"] = np.nan
    
    df = df.to_crs(TARGET_CRS)
    result = gpd.GeoDataFrame(df[TREE_CADASTRE_COLUMNS], crs=TARGET_CRS)

    print(f"  ✓ {len(result):,} trees harmonized")
    print(f"  ✓ CRS: {result.crs}")
    print(f"  ✓ Unique genera: {result['genus_latin'].nunique()}")
    print(f"  ✓ Unique species: {result['species_latin'].nunique()}")

    return result


def validate_harmonized(gdf: gpd.GeoDataFrame) -> bool:
    """
    Validiert das harmonisierte GeoDataFrame.
    """
    print("\nValidating harmonized data...")
    issues = []

    # CRS prüfen
    if str(gdf.crs) != TARGET_CRS:
        issues.append(f"CRS mismatch: {gdf.crs} (expected {TARGET_CRS})")

    # Spalten prüfen
    missing_cols = set(TREE_CADASTRE_COLUMNS) - set(gdf.columns)
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")

    # Geometrie-Typen prüfen
    if not gdf.geometry.type.eq("Point").all():
        issues.append(f"Non-Point geometries found: {gdf.geometry.type.unique()}")

    # Eindeutigkeit prüfen
    duplicate_count = gdf.groupby(["city", "tree_id"]).size().gt(1).sum()
    if duplicate_count > 0:
        issues.append(f"Duplicate (city, tree_id) combinations: {duplicate_count}")

    # Städte prüfen
    if set(gdf["city"].unique()) != set(CITIES):
        issues.append(f"Cities mismatch: {set(gdf['city'].unique())} (expected {set(CITIES)})")

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

    total = len(gdf)
    
    # Pro Stadt
    print("\nTrees per city:")
    for city, count in gdf.groupby("city").size().items():
        print(f"  {city:<10} {count:>10,}")
    print(f"  {'TOTAL':<10} {total:>10,}")

    # Top Gattungen
    print("\nTop 15 genera (genus_latin):")
    for genus, count in gdf["genus_latin"].value_counts().head(15).items():
        print(f"  {genus:<20} {count:>10,} ({count / total * 100:>5.1f}%)")

    # Top Arten
    print("\nTop 15 species (species_latin):")
    for species, count in gdf["species_latin"].value_counts().head(15).items():
        print(f"  {species:<30} {count:>10,} ({count / total * 100:>5.1f}%)")

    # Gesamtstatistiken
    print(f"\nTotal unique genera: {gdf['genus_latin'].nunique()}")
    print(f"Total unique species: {gdf['species_latin'].nunique()}")

    # NA-Anteile
    print("\nNull value percentages:")
    for col in ["genus_latin", "species_latin", "plant_year", "height_m", "tree_type"]:
        print(f"  {col:<25} {gdf[col].isna().sum() / total * 100:>6.1f}%")

    # Geometry stats
    print(f"\nGeometry type: {gdf.geometry.type.iloc[0]}")
    print(f"CRS: {gdf.crs}")


def main() -> None:
    """Hauptfunktion: Harmonisiert alle Baumkataster."""
    print("=" * 80)
    print("Baumkataster-Harmonisierung")
    print("=" * 80)

    # Ausgabeverzeichnis erstellen
    TREE_CADASTRES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Rohdaten laden und harmonisieren
    raw_data = load_raw_data()
    harmonized_gdfs = [
        harmonize_berlin(raw_data["berlin"]),
        harmonize_hamburg(raw_data["hamburg"]),
        harmonize_rostock(raw_data["rostock"]),
    ]

    # Zusammenführen
    print("\nMerging all cities...")
    gdf_all = gpd.GeoDataFrame(
        pd.concat(harmonized_gdfs, ignore_index=True),
        crs=TARGET_CRS,
    )
    print(f"✓ Total: {len(gdf_all):,} trees")

    # Validieren
    validate_harmonized(gdf_all)

    # Zusammenfassung
    print_summary(gdf_all)

    # Speichern
    output_path = TREE_CADASTRES_PROCESSED_DIR / "trees_harmonized.gpkg"
    gdf_all.to_file(output_path, driver="GPKG")
    print(f"\n✓ Saved to: {output_path}")
    print(f"✓ File size: {output_path.stat().st_size / (1024 * 1024):.1f} MB")

    print("\n" + "=" * 80)
    print("✓ Harmonization complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
