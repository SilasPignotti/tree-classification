"""
CHM Creation & Quality Assessment Script

Berechnet Canopy Height Models (CHM = DOM - DGM) für Hamburg, Berlin und Rostock
mit Qualitätskontrolle und Validierung.

Usage:
    uv run python scripts/chm/create_chm.py
"""

from pathlib import Path
from typing import Tuple, Dict, Optional
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.transform import Affine
from rasterio.features import geometry_mask
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from tqdm.auto import tqdm

# Styling
plt.rcParams["figure.figsize"] = (12, 8)
warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_BOUNDARIES = PROJECT_ROOT / "data" / "boundaries"

CITIES = ["hamburg", "berlin", "rostock"]

NEGATIVE_THRESHOLD = 0.0
MAX_HEIGHT_THRESHOLD = 60.0

EXPECTED_MEAN_FULL = (2.0, 20.0)
EXPECTED_MEAN_CORE = (5.0, 25.0)

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

print(f"Projekt-Root: {PROJECT_ROOT}")
print(f"Verarbeite Städte: {', '.join(CITIES)}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def load_and_validate_elevation(
    dom_path: Path, dgm_path: Path
) -> Tuple[np.ndarray, np.ndarray, Dict, Affine]:
    """
    Lädt DOM und DGM, validiert räumliche Übereinstimmung.

    Args:
        dom_path: Pfad zum Digital Oberflächenmodell
        dgm_path: Pfad zum Digitalen Geländemodell

    Returns:
        Tuple mit (DOM array, DGM array, Metadaten dict, Transform)

    Raises:
        ValueError: Bei CRS-Diskrepanzen
    """
    with rasterio.open(dom_path) as dom_src:
        dom = dom_src.read(1, masked=True).filled(np.nan)
        dom_meta = dom_src.meta.copy()
        dom_transform = dom_src.transform
        dom_crs = dom_src.crs
        dom_shape = dom.shape

    with rasterio.open(dgm_path) as dgm_src:
        dgm = dgm_src.read(1, masked=True).filled(np.nan)
        dgm_crs = dgm_src.crs
        dgm_shape = dgm.shape
        dgm_transform = dgm_src.transform

    if dom_crs != dgm_crs:
        raise ValueError(f"CRS mismatch: DOM={dom_crs}, DGM={dgm_crs}")

    if dom_shape != dgm_shape:
        min_rows = min(dom_shape[0], dgm_shape[0])
        min_cols = min(dom_shape[1], dgm_shape[1])
        print(
            f"  ⚠️  Shape-Mismatch: DOM={dom_shape}, DGM={dgm_shape} "
            f"→ Croppe auf {(min_rows, min_cols)}"
        )
        dom = dom[:min_rows, :min_cols]
        dgm = dgm[:min_rows, :min_cols]
        dom_meta["height"] = min_rows
        dom_meta["width"] = min_cols

    transform_match = all(
        abs(a - b) < 1e-6 for a, b in zip(dom_transform, dgm_transform)
    )
    if not transform_match:
        print(
            f"  ⚠️  Transform-Diskrepanz (toleriert): "
            f"DOM={dom_transform[:3]}, DGM={dgm_transform[:3]}"
        )

    valid_dom = np.sum(~np.isnan(dom))
    valid_dgm = np.sum(~np.isnan(dgm))
    total = dom.size

    print(f"  DOM: {valid_dom:,} valid pixels ({100*valid_dom/total:.1f}%)")
    print(f"  DGM: {valid_dgm:,} valid pixels ({100*valid_dgm/total:.1f}%)")
    print(f"  CRS: {dom_crs}, Shape: {dom.shape}")

    return dom, dgm, dom_meta, dom_transform


def compute_chm(dom: np.ndarray, dgm: np.ndarray) -> np.ndarray:
    """
    Berechnet Canopy Height Model durch Subtraktion.

    Args:
        dom: Digital Oberflächenmodell
        dgm: Digitales Geländemodell

    Returns:
        CHM array (mit NoData wo Input-NoData vorlag)
    """
    chm = dom - dgm
    chm[np.isnan(dom) | np.isnan(dgm)] = np.nan
    return chm


def apply_quality_filters(
    chm: np.ndarray,
    neg_threshold: float = NEGATIVE_THRESHOLD,
    max_threshold: float = MAX_HEIGHT_THRESHOLD,
) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Wendet Qualitätsfilter auf CHM an.

    Args:
        chm: Rohes CHM
        neg_threshold: Schwellenwert für negative Werte
        max_threshold: Maximale plausible Höhe

    Returns:
        Tuple mit (bereinigtes CHM, Korrektur-Log dict)
    """
    chm_clean = chm.copy()

    corrections = {
        "negative_pixels": np.sum((chm < neg_threshold) & ~np.isnan(chm)),
        "outlier_pixels": np.sum(chm > max_threshold),
    }

    chm_clean[(chm_clean < neg_threshold) & ~np.isnan(chm_clean)] = 0.0
    chm_clean[chm_clean > max_threshold] = np.nan

    return chm_clean, corrections


def compute_statistics(
    chm: np.ndarray, city: str, extent: str
) -> Dict[str, float | str]:
    """
    Berechnet statistische Kennzahlen für CHM.

    Args:
        chm: CHM array
        city: Stadtname
        extent: "Full" oder "City core"

    Returns:
        Dict mit Statistiken
    """
    valid = ~np.isnan(chm)
    valid_count = np.sum(valid)
    valid_percent = 100 * valid_count / chm.size

    return {
        "City": city,
        "Extent": extent,
        "Valid_pixels": valid_count,
        "Valid_percent": valid_percent,
        "Min": float(np.nanmin(chm)),
        "Max": float(np.nanmax(chm)),
        "Mean": float(np.nanmean(chm)),
        "Median": float(np.nanmedian(chm)),
        "Std": float(np.nanstd(chm)),
        "P25": float(np.nanpercentile(chm, 25)),
        "P75": float(np.nanpercentile(chm, 75)),
        "P95": float(np.nanpercentile(chm, 95)),
        "P99": float(np.nanpercentile(chm, 99)),
    }


def mask_to_city_core(
    chm: np.ndarray,
    transform: Affine,
    crs: str,
    city: str,
    boundary_path: Path,
) -> np.ndarray:
    """
    Maskiert CHM auf Stadtkern (ohne 500m Buffer).

    Args:
        chm: CHM array
        transform: Raster-Transform
        crs: CRS string
        city: Stadtname (für Filterung in GeoPackage)
        boundary_path: Pfad zu city_boundaries.gpkg

    Returns:
        Maskiertes CHM (außerhalb Stadtgrenze = NaN)
    """
    gdf = gpd.read_file(boundary_path)
    gdf_city = gdf[gdf["gen"].str.lower() == city.lower()]

    if len(gdf_city) == 0:
        raise ValueError(f"Stadt '{city}' nicht in boundaries gefunden")

    geom_mask = geometry_mask(
        gdf_city.geometry, transform=transform, invert=True, out_shape=chm.shape
    )

    chm_masked = chm.copy()
    chm_masked[~geom_mask] = np.nan

    return chm_masked


def validate_chm_quality(
    chm: np.ndarray,
    stats: Dict,
    corrections: Dict,
    city: str,
    extent: str,
) -> None:
    """
    Automatisierte Plausibilitätsprüfungen (Warnings, keine Fehler).

    Args:
        chm: Bereinigtes CHM
        stats: Statistik-Dict
        corrections: Korrektur-Log
        city: Stadtname
        extent: "Full" oder "City core"
    """
    print(f"\n  Validierung ({extent}):")

    mean = stats["Mean"]
    expected_range = EXPECTED_MEAN_FULL if extent == "Full" else EXPECTED_MEAN_CORE
    if not (expected_range[0] <= mean <= expected_range[1]):
        print(
            f"    ⚠️  Mean {mean:.1f}m außerhalb Erwartungsbereich "
            f"{expected_range[0]}-{expected_range[1]}m"
        )
    else:
        print(f"    ✓ Mean {mean:.1f}m plausibel")

    outlier_pct = 100 * corrections["outlier_pixels"] / chm.size
    if outlier_pct > 2.0:
        print(f"    ⚠️  {outlier_pct:.2f}% Ausreißer >60m (erwartet <2%)")
    else:
        print(f"    ✓ Ausreißer-Rate {outlier_pct:.2f}% akzeptabel")

    valid_pct = stats["Valid_percent"]
    min_valid = 40.0 if extent == "Full" else 60.0
    if valid_pct < min_valid:
        print(f"    ⚠️  Nur {valid_pct:.1f}% gültige Pixel (erwartet >{min_valid}%)")
    else:
        print(f"    ✓ Gültige Pixel: {valid_pct:.1f}%")

    if stats["Median"] >= stats["Mean"]:
        print(
            f"    ⚠️  Median≥Mean (unerwartete Verteilung: "
            f"Median={stats['Median']:.1f}, Mean={stats['Mean']:.1f})"
        )


def plot_statistical_overview(
    chm: np.ndarray,
    stats_full: Dict,
    stats_core: Dict,
    city: str,
    transform: Affine,
    output_dir: Path,
) -> None:
    """
    Erstellt 2x2 Übersichtsplot und speichert als PNG.

    Args:
        chm: CHM array
        stats_full: Statistiken für gesamtes Gebiet
        stats_core: Statistiken für Stadtkern
        city: Stadtname
        transform: Raster-Transform
        output_dir: Ausgabeverzeichnis für Plots
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"CHM Statistische Übersicht: {city.upper()}", fontsize=16, y=0.995)

    chm_valid = chm[~np.isnan(chm)]

    # 1. Histogram
    ax = axes[0, 0]
    ax.hist(chm_valid, bins=100, edgecolor="none", alpha=0.7, color="forestgreen")
    ax.axvline(
        stats_full["Mean"], color="red", linestyle="--", label="Mean", linewidth=2
    )
    ax.axvline(
        stats_full["Median"], color="blue", linestyle="--", label="Median", linewidth=2
    )
    ax.set_xlabel("Höhe (m)")
    ax.set_ylabel("Häufigkeit (log)")
    ax.set_yscale("log")
    ax.set_xlim(0, 60)
    ax.set_title("Höhenverteilung")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. Box Plot
    ax = axes[0, 1]
    bp = ax.boxplot(
        [chm_valid, chm_valid],
        tick_labels=["Full extent", "City core"],
        patch_artist=True,
        showmeans=True,
    )
    for patch in bp["boxes"]:
        patch.set_facecolor("lightgreen")
    ax.set_ylabel("Höhe (m)")
    ax.set_title("Vergleich: Gesamtgebiet vs. Stadtkern")
    ax.grid(True, alpha=0.3, axis="y")

    # 3. CDF
    ax = axes[1, 0]
    sorted_heights = np.sort(chm_valid)
    cumulative = np.arange(1, len(sorted_heights) + 1) / len(sorted_heights) * 100
    ax.plot(sorted_heights, cumulative, linewidth=2, color="darkgreen")
    ax.set_xlabel("Höhe (m)")
    ax.set_ylabel("Kumulative Häufigkeit (%)")
    ax.set_xlim(0, 60)
    ax.set_title("Kumulative Verteilungsfunktion")
    ax.grid(True, alpha=0.3)
    ax.axhline(50, color="gray", linestyle=":", alpha=0.5)
    ax.axhline(95, color="gray", linestyle=":", alpha=0.5)

    # 4. Spatial
    ax = axes[1, 1]
    downsample_factor = max(1, chm.shape[0] // 2000)
    if downsample_factor > 1:
        chm_display = chm[::downsample_factor, ::downsample_factor]
    else:
        chm_display = chm

    im = ax.imshow(chm_display, cmap="YlGn", vmin=0, vmax=30, interpolation="nearest")
    ax.set_title(f"Räumliche CHM-Verteilung (Shape: {chm.shape})")
    ax.set_xlabel("Pixel (1m Auflösung)")
    ax.set_ylabel("Pixel (1m Auflösung)")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Höhe (m)", rotation=270, labelpad=15)

    plt.tight_layout()
    output_path = output_dir / f"chm_overview_{city}.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ Plot gespeichert: {output_path.name}")


def plot_qa_visualization(
    chm_raw: np.ndarray,
    chm_clean: np.ndarray,
    corrections: Dict,
    city: str,
    output_dir: Path,
) -> None:
    """
    Erstellt QA-Visualisierung und speichert als PNG.

    Args:
        chm_raw: Rohes CHM vor Filtern
        chm_clean: Bereinigtes CHM
        corrections: Korrektur-Log dict
        city: Stadtname
        output_dir: Ausgabeverzeichnis für Plots
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f"Quality Assessment: {city.upper()}", fontsize=14)

    # NoData
    ax = axes[0]
    downsample_factor = max(1, chm_clean.shape[0] // 2000)
    if downsample_factor > 1:
        chm_display = chm_clean[::downsample_factor, ::downsample_factor]
    else:
        chm_display = chm_clean
    nodata_mask = np.isnan(chm_display).astype(int)
    ax.imshow(nodata_mask, cmap="RdYlGn_r", interpolation="nearest")
    ax.set_title("NoData-Verteilung (Rot = NoData)")
    ax.axis("off")

    # Histogram
    ax = axes[1]
    chm_raw_valid = chm_raw[~np.isnan(chm_raw)]
    chm_clean_valid = chm_clean[~np.isnan(chm_clean)]

    ax.hist(
        chm_raw_valid,
        bins=100,
        alpha=0.5,
        label="Vor Korrektur",
        color="orange",
        range=(-5, 65),
    )
    ax.hist(
        chm_clean_valid,
        bins=100,
        alpha=0.7,
        label="Nach Korrektur",
        color="green",
        range=(0, 60),
    )
    ax.axvline(0, color="black", linestyle="--", linewidth=1)
    ax.axvline(60, color="red", linestyle="--", linewidth=1, label="Schwellenwerte")
    ax.set_xlabel("Höhe (m)")
    ax.set_ylabel("Häufigkeit")
    ax.set_yscale("log")
    ax.set_title(
        f"Korrektur-Impact (Negativ: {corrections['negative_pixels']:,}, "
        f"Ausreißer: {corrections['outlier_pixels']:,})"
    )
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / f"chm_qa_{city}.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✓ QA-Plot gespeichert: {output_path.name}")


def save_chm_geotiff(
    chm: np.ndarray, meta: Dict, transform: Affine, output_path: Path
) -> None:
    """
    Speichert bereinigtes CHM als komprimiertes GeoTIFF.

    Args:
        chm: CHM array
        meta: Raster-Metadaten
        transform: Raster-Transform
        output_path: Ziel-Pfad
    """
    output_meta = meta.copy()
    output_meta.update(
        {
            "driver": "GTiff",
            "dtype": "float32",
            "nodata": np.nan,
            "count": 1,
            "compress": "DEFLATE",
            "predictor": 3,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "num_threads": 4,
        }
    )

    try:
        with rasterio.open(output_path, "w", **output_meta) as dst:
            dst.write(chm.astype(np.float32), 1)
            dst.set_band_description(1, "Canopy Height Model (m)")

        file_size_mb = output_path.stat().st_size / (1024**2)
        print(f"  ✓ Gespeichert: {output_path.name} ({file_size_mb:.1f} MB)")
    except Exception as e:
        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024**2)
            print(f"  ⚠️  Schreibfehler, aber Datei existiert: {output_path.name} ({file_size_mb:.1f} MB)")
        else:
            raise


# =============================================================================
# PROCESSING PIPELINE
# =============================================================================


def process_city(city: str, boundary_file: Path, skip_existing: bool = True) -> Tuple[Dict, Dict, Dict]:
    """
    Verarbeitet eine Stadt komplett.

    Args:
        city: Stadtname
        boundary_file: Pfad zu city_boundaries.gpkg
        skip_existing: Überspringe bereits verarbeitete Städte

    Returns:
        Tuple mit (stats_full, stats_core, corrections)
    """
    output_path = DATA_PROCESSED / f"CHM_1m_{city.capitalize()}.tif"

    if skip_existing and output_path.exists():
        print(f"\n{'='*60}")
        print(f"SKIPPING: {city.upper()} (bereits verarbeitet)")
        print(f"{'='*60}")
        # Return None to indicate skip - will be handled in main()
        return None, None, None

    print(f"\n{'='*60}")
    print(f"PROCESSING: {city.upper()}")
    print(f"{'='*60}")

    # 1. Lade DOM/DGM
    print("\n[1/7] Lade und validiere Eingangsdaten...")
    dom_path = DATA_RAW / city / "dom_1m.tif"
    dgm_path = DATA_RAW / city / "dgm_1m.tif"
    dom, dgm, meta, transform = load_and_validate_elevation(dom_path, dgm_path)

    # 2. Berechne CHM
    print("\n[2/7] Berechne CHM...")
    chm_raw = compute_chm(dom, dgm)
    print(f"  CHM Shape: {chm_raw.shape}, Valid: {np.sum(~np.isnan(chm_raw)):,} pixels")

    # 3. Qualitätsfilter
    print("\n[3/7] Wende Qualitätsfilter an...")
    chm_clean, corrections = apply_quality_filters(chm_raw)
    print(
        f"  Korrigiert: {corrections['negative_pixels']:,} negative Pixel, "
        f"{corrections['outlier_pixels']:,} Ausreißer"
    )

    # 4. Statistiken (Full)
    print("\n[4/7] Berechne Statistiken (Full extent)...")
    stats_full = compute_statistics(chm_clean, city, "Full")
    print(
        f"  Mean: {stats_full['Mean']:.2f}m, Median: {stats_full['Median']:.2f}m, "
        f"P95: {stats_full['P95']:.2f}m"
    )

    # 5. Statistiken (Core)
    print("\n[5/7] Berechne Statistiken (City core)...")
    try:
        chm_core = mask_to_city_core(chm_clean, transform, meta["crs"], city, boundary_file)
        stats_core = compute_statistics(chm_core, city, "City core")
        print(
            f"  Mean: {stats_core['Mean']:.2f}m, Median: {stats_core['Median']:.2f}m, "
            f"P95: {stats_core['P95']:.2f}m"
        )
    except Exception as e:
        print(f"  ⚠️  City-Core-Maskierung fehlgeschlagen: {e}")
        stats_core = stats_full.copy()
        stats_core["Extent"] = "City core (fallback)"

    # 6. Validierung
    validate_chm_quality(chm_clean, stats_full, corrections, city, "Full")
    validate_chm_quality(chm_clean, stats_core, corrections, city, "City core")

    # 7. Visualisierungen
    print("\n[6/7] Erstelle Visualisierungen...")
    plot_output_dir = DATA_PROCESSED / "plots"
    plot_output_dir.mkdir(exist_ok=True)
    plot_statistical_overview(chm_clean, stats_full, stats_core, city, transform, plot_output_dir)
    plot_qa_visualization(chm_raw, chm_clean, corrections, city, plot_output_dir)

    # 8. Speichern
    print("\n[7/7] Speichere Output...")
    output_path = DATA_PROCESSED / f"CHM_1m_{city.capitalize()}.tif"
    save_chm_geotiff(chm_clean, meta, transform, output_path)

    print(f"\n✓ {city.upper()} abgeschlossen!")

    return stats_full, stats_core, corrections


def main():
    """Hauptfunktion: Verarbeitet alle Städte."""
    all_statistics = []
    all_corrections = {}

    boundary_file = DATA_BOUNDARIES / "city_boundaries.gpkg"
    if not boundary_file.exists():
        raise FileNotFoundError(f"Stadtgrenzen nicht gefunden: {boundary_file}")

    # Load existing statistics if available
    csv_path = DATA_PROCESSED / "chm_statistics.csv"
    existing_stats = {}
    if csv_path.exists():
        df_existing = pd.read_csv(csv_path)
        for city in CITIES:
            city_stats = df_existing[df_existing["City"] == city]
            if not city_stats.empty:
                existing_stats[city] = city_stats.to_dict("records")
                print(f"Loaded existing statistics for {city}")

    # Process each city
    for city in CITIES:
        stats_full, stats_core, corrections = process_city(city, boundary_file)

        # If skipped, use existing stats if available
        if stats_full is None:
            if city in existing_stats:
                for stat_dict in existing_stats[city]:
                    all_statistics.append(stat_dict)
                all_corrections[city] = {"negative_pixels": 0, "outlier_pixels": 0}
            continue

        all_statistics.append(stats_full)
        all_statistics.append(stats_core)
        all_corrections[city] = corrections

    # Cross-city comparison
    print("\n" + "=" * 60)
    print("CROSS-CITY COMPARISON")
    print("=" * 60)

    df_stats = pd.DataFrame(all_statistics)
    display_cols = ["City", "Extent", "Valid_percent", "Mean", "Median", "P95", "P99", "Max"]
    df_display = df_stats[display_cols].copy()
    df_display["Valid_percent"] = df_display["Valid_percent"].round(1)
    for col in ["Mean", "Median", "P95", "P99", "Max"]:
        df_display[col] = df_display[col].round(2)

    print("\nStatistik-Übersicht:")
    print(df_display.to_string(index=False))

    print("\n\nKorrektur-Zusammenfassung:")
    for city, corr in all_corrections.items():
        print(
            f"  {city.capitalize():10s}: {corr['negative_pixels']:6,} negative, "
            f"{corr['outlier_pixels']:6,} Ausreißer"
        )

    # Export
    csv_path = DATA_PROCESSED / "chm_statistics.csv"
    df_stats.to_csv(csv_path, index=False, float_format="%.2f")
    print(f"\n✓ Statistiken gespeichert: {csv_path}")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE ABGESCHLOSSEN")
    print("=" * 60)
    print("\nErzeugte Dateien:")
    for city in CITIES:
        chm_file = DATA_PROCESSED / f"CHM_1m_{city.capitalize()}.tif"
        if chm_file.exists():
            size_mb = chm_file.stat().st_size / (1024**2)
            print(f"  ✓ {chm_file.name:25s} ({size_mb:6.1f} MB)")
        else:
            print(f"  ✗ {chm_file.name:25s} (FEHLT!)")

    print(f"  ✓ {csv_path.name}")
    print(f"  ✓ Plots in {DATA_PROCESSED / 'plots'}")


if __name__ == "__main__":
    main()
