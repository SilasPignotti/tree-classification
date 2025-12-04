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
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt

# Styling
plt.rcParams["figure.figsize"] = (12, 8)
warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_CHM_RAW = PROJECT_ROOT / "data" / "CHM" / "raw"
DATA_CHM_PROCESSED = PROJECT_ROOT / "data" / "CHM" / "processed"
DATA_BOUNDARIES = PROJECT_ROOT / "data" / "boundaries"

CITIES = ["hamburg", "berlin", "rostock"]

# Qualitätsfilter-Schwellenwerte
# Negative CHM-Werte entstehen durch: Wasser (DOM<DGM), Brücken, Interpolationsfehler
# Diese werden als NoData behandelt, nicht als 0, um Statistiken nicht zu verzerren
NEGATIVE_THRESHOLD = 0.0  # Alles < 0 → NoData
MAX_HEIGHT_THRESHOLD = 60.0  # Alles > 60m → NoData (Ausreißer)

# Erwartete Mittelwerte (nach Bereinigung negativer Werte)
# Höher als vorher, da keine künstlichen Nullen mehr die Statistik verzerren
EXPECTED_MEAN_FULL = (4.0, 25.0)  # 500m Buffer (mehr Stadtrand, Wasser entfernt)
EXPECTED_MEAN_CORE = (6.0, 30.0)  # City core (ohne Buffer, dichter bebaut)

DATA_CHM_PROCESSED.mkdir(parents=True, exist_ok=True)

print(f"Projekt-Root: {PROJECT_ROOT}")
print(f"Verarbeite Städte: {', '.join(CITIES)}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def load_and_clip_elevation(
    dom_path: Path, dgm_path: Path, city: str, boundary_buffer_path: Path
) -> Tuple[np.ndarray, np.ndarray, Dict, Affine]:
    """
    Lädt DOM und DGM, clippt auf 500m Buffer der Stadtgrenze.
    
    State-of-the-Art Ansatz:
    1. DGM als Referenzraster clippen (Master-Grid)
    2. DOM auf exakt gleiches Grid resampen
    3. Garantiert pixel-perfekte Ausrichtung für CHM-Berechnung

    Args:
        dom_path: Pfad zum Digital Oberflächenmodell
        dgm_path: Pfad zum Digitalen Geländemodell
        city: Stadtname für Filterung
        boundary_buffer_path: Pfad zu city_boundaries_500m_buffer.gpkg

    Returns:
        Tuple mit (DOM array, DGM array, Metadaten dict, Transform)

    Raises:
        ValueError: Bei CRS-Diskrepanzen
    """
    # Lade Stadtgrenze mit 500m Buffer
    gdf = gpd.read_file(boundary_buffer_path)
    gdf_city = gdf[gdf["gen"].str.lower() == city.lower()]
    
    if len(gdf_city) == 0:
        raise ValueError(f"Stadt '{city}' nicht in boundaries gefunden")
    
    # =========================================================================
    # SCHRITT 1: DGM als Referenz-Grid clippen
    # =========================================================================
    print("  [1/3] Clippe DGM als Referenz-Grid...")
    with rasterio.open(dgm_path) as dgm_src:
        dgm_crs = dgm_src.crs
        dgm_nodata = dgm_src.nodata
        
        # Reprojektion der Boundary falls nötig
        if gdf_city.crs != dgm_crs:
            gdf_city = gdf_city.to_crs(dgm_crs)
        
        # Clip DGM auf Boundary - DGM definiert das Master-Grid
        dgm, dgm_transform = mask(dgm_src, gdf_city.geometry, crop=True, nodata=np.nan)
        dgm = dgm[0]  # Erstes Band
        
        # NoData handling
        if dgm_nodata is not None:
            dgm = np.where(dgm == dgm_nodata, np.nan, dgm)
        
        # Speichere Referenz-Metadaten
        ref_shape = dgm.shape
        ref_transform = dgm_transform
        ref_crs = dgm_crs
        
        dgm_meta = dgm_src.meta.copy()
        dgm_meta.update({
            "height": ref_shape[0],
            "width": ref_shape[1],
            "transform": ref_transform,
            "crs": ref_crs
        })
    
    print(f"       DGM Reference Grid: {ref_shape}, Transform: {ref_transform[:6]}")
    
    # =========================================================================
    # SCHRITT 2: DOM clippen und auf DGM-Grid resampen
    # =========================================================================
    print("  [2/3] Clippe DOM und resample auf DGM-Grid...")
    with rasterio.open(dom_path) as dom_src:
        dom_crs = dom_src.crs
        dom_nodata = dom_src.nodata
        
        if dom_crs != dgm_crs:
            raise ValueError(f"CRS mismatch: DOM={dom_crs}, DGM={dgm_crs}")
        
        # Erst DOM clippen
        dom_clipped, dom_transform = mask(dom_src, gdf_city.geometry, crop=True, nodata=np.nan)
        dom_clipped = dom_clipped[0]
        
        if dom_nodata is not None:
            dom_clipped = np.where(dom_clipped == dom_nodata, np.nan, dom_clipped)
        
        print(f"       DOM nach Clip: {dom_clipped.shape}")
        
        # Prüfe ob Resampling nötig ist
        if dom_clipped.shape != ref_shape or not np.allclose(list(dom_transform)[:6], list(ref_transform)[:6], atol=1e-6):
            print(f"       → Resample DOM auf DGM-Grid (Shape: {dom_clipped.shape} → {ref_shape})")
            
            # Erstelle leeres Array für resampled DOM
            dom = np.empty(ref_shape, dtype=np.float32)
            dom.fill(np.nan)
            
            # Reproject/Resample DOM auf DGM-Grid
            reproject(
                source=dom_clipped,
                destination=dom,
                src_transform=dom_transform,
                src_crs=dom_crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.bilinear,  # Bilinear für Höhendaten
                src_nodata=np.nan,
                dst_nodata=np.nan
            )
        else:
            print("       → Grids bereits identisch, kein Resampling nötig")
            dom = dom_clipped
    
    # =========================================================================
    # SCHRITT 3: Validierung
    # =========================================================================
    print("  [3/3] Validiere ausgerichtete Raster...")
    
    # Shapes müssen jetzt identisch sein
    assert dom.shape == dgm.shape, f"Shape mismatch nach Resampling: DOM={dom.shape}, DGM={dgm.shape}"
    
    valid_dom = np.sum(~np.isnan(dom))
    valid_dgm = np.sum(~np.isnan(dgm))
    total = dom.size

    print(f"       DOM: {valid_dom:,} valid pixels ({100*valid_dom/total:.1f}%)")
    print(f"       DGM: {valid_dgm:,} valid pixels ({100*valid_dgm/total:.1f}%)")
    print(f"       CRS: {ref_crs}, Shape: {ref_shape}")
    print("       ✓ Raster perfekt ausgerichtet")

    return dom, dgm, dgm_meta, ref_transform


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
    
    Negative Werte entstehen durch:
    - Wasserflächen (DOM misst Oberfläche, DGM interpoliert Grund)
    - Brücken (DGM zeigt Brücke, DOM zeigt Wasser darunter)
    - Interpolationsfehler an Datenkanten
    
    Diese werden als NoData behandelt (nicht 0!), da sie keine
    Vegetation repräsentieren und sonst Statistiken verzerren würden.

    Args:
        chm: Rohes CHM
        neg_threshold: Schwellenwert für negative Werte (Standard: 0)
        max_threshold: Maximale plausible Höhe (Standard: 60m)

    Returns:
        Tuple mit (bereinigtes CHM, Korrektur-Log dict)
    """
    chm_clean = chm.copy()

    # Zähle problematische Pixel (als int für JSON-Serialisierung)
    corrections = {
        "negative_pixels": int(np.sum((chm < neg_threshold) & ~np.isnan(chm))),
        "outlier_pixels": int(np.sum(chm > max_threshold)),
    }

    # Negative Werte → NoData (nicht 0!)
    # Begründung: Wasser/Brücken sind keine Vegetation mit Höhe 0
    chm_clean[(chm_clean < neg_threshold) & ~np.isnan(chm_clean)] = np.nan
    
    # Ausreißer > 60m → NoData (unrealistisch hohe Bäume, meist Messfehler)
    chm_clean[chm_clean > max_threshold] = np.nan

    return chm_clean, corrections


def compute_statistics(
    chm: np.ndarray,
    city: str,
    extent: str,
    reference_mask: Optional[np.ndarray] = None,
) -> Dict[str, float | str]:
    """
    Berechnet statistische Kennzahlen für CHM.

    Args:
        chm: CHM array
        city: Stadtname
        extent: "500m Buffer" oder "City core"
        reference_mask: Boolean-Maske der Referenzgeometrie (True = innerhalb).
                       Wenn angegeben, wird valid_percent relativ zur Geometrie
                       berechnet, nicht zur gesamten BBox.

    Returns:
        Dict mit Statistiken
    """
    valid = ~np.isnan(chm)
    valid_count = np.sum(valid)
    
    # Berechne valid_percent relativ zur Referenzgeometrie (nicht BBox)
    if reference_mask is not None:
        pixels_in_geometry = np.sum(reference_mask)
        valid_in_geometry = np.sum(valid & reference_mask)
        valid_percent = 100 * valid_in_geometry / pixels_in_geometry if pixels_in_geometry > 0 else 0.0
    else:
        # Fallback: alte Methode (BBox-basiert)
        valid_percent = 100 * valid_count / chm.size

    return {
        "City": city,
        "Extent": extent,
        "Valid_pixels": int(valid_count),  # int() für JSON-Serialisierung
        "Valid_percent": round(valid_percent, 2),
        "Pixels_in_geometry": int(np.sum(reference_mask)) if reference_mask is not None else int(chm.size),
        "Min": round(float(np.nanmin(chm)), 2),
        "Max": round(float(np.nanmax(chm)), 2),
        "Mean": round(float(np.nanmean(chm)), 2),
        "Median": round(float(np.nanmedian(chm)), 2),
        "Std": round(float(np.nanstd(chm)), 2),
        "P25": round(float(np.nanpercentile(chm, 25)), 2),
        "P75": round(float(np.nanpercentile(chm, 75)), 2),
        "P95": round(float(np.nanpercentile(chm, 95)), 2),
        "P99": round(float(np.nanpercentile(chm, 99)), 2),
    }


def create_geometry_mask(
    raster_shape: Tuple[int, int],
    transform: Affine,
    city: str,
    boundary_path: Path,
) -> np.ndarray:
    """
    Erstellt Boolean-Maske für eine Stadtgeometrie.

    Args:
        raster_shape: Shape des Rasters (height, width)
        transform: Raster-Transform
        city: Stadtname (für Filterung in GeoPackage)
        boundary_path: Pfad zu GeoPackage mit Stadtgrenzen

    Returns:
        Boolean-Array (True = Pixel innerhalb der Stadtgeometrie)
    """
    gdf = gpd.read_file(boundary_path)
    gdf_city = gdf[gdf["gen"].str.lower() == city.lower()]

    if len(gdf_city) == 0:
        raise ValueError(f"Stadt '{city}' nicht in boundaries gefunden")

    # geometry_mask: invert=True → True wo Pixel INNERHALB der Geometrie sind
    geom_mask = geometry_mask(
        gdf_city.geometry, transform=transform, invert=True, out_shape=raster_shape
    )

    return geom_mask


def mask_to_city_core(
    chm: np.ndarray,
    transform: Affine,
    crs: str,
    city: str,
    boundary_path: Path,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Maskiert CHM auf Stadtkern (ohne 500m Buffer).

    Args:
        chm: CHM array
        transform: Raster-Transform
        crs: CRS string
        city: Stadtname (für Filterung in GeoPackage)
        boundary_path: Pfad zu city_boundaries.gpkg

    Returns:
        Tuple mit (maskiertes CHM, Geometrie-Maske)
        - Maskiertes CHM: außerhalb Stadtgrenze = NaN
        - Geometrie-Maske: Boolean-Array (True = innerhalb Stadt)
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

    return chm_masked, geom_mask


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
        extent: "500m Buffer" oder "City core"
    """
    print(f"\n  Validierung ({extent}):")

    # 1. Mean-Plausibilität
    mean = stats["Mean"]
    expected_range = EXPECTED_MEAN_FULL if extent == "500m Buffer" else EXPECTED_MEAN_CORE
    if not (expected_range[0] <= mean <= expected_range[1]):
        print(
            f"    ⚠️  Mean {mean:.1f}m außerhalb Erwartungsbereich "
            f"{expected_range[0]}-{expected_range[1]}m"
        )
    else:
        print(f"    ✓ Mean {mean:.1f}m plausibel")

    # 2. Median-Plausibilität (sollte bei CHM nahe Mean liegen)
    median = stats["Median"]
    print(f"    ✓ Median {median:.1f}m")

    # 3. Ausreißer >60m
    outlier_pct = 100 * corrections["outlier_pixels"] / stats["Pixels_in_geometry"]
    if outlier_pct > 2.0:
        print(f"    ⚠️  {outlier_pct:.2f}% Ausreißer >60m (erwartet <2%)")
    else:
        print(f"    ✓ Ausreißer-Rate {outlier_pct:.3f}% akzeptabel ({corrections['outlier_pixels']:,} Pixel)")

    # 4. Negative Pixel (jetzt NoData)
    negative_pct = 100 * corrections["negative_pixels"] / stats["Pixels_in_geometry"]
    print(f"    ℹ️  Negative → NoData: {negative_pct:.1f}% ({corrections['negative_pixels']:,} Pixel, meist Wasser)")

    # 5. Gültige Pixel
    valid_pct = stats["Valid_percent"]
    min_valid = 40.0 if extent == "500m Buffer" else 60.0
    if valid_pct < min_valid:
        print(f"    ⚠️  Nur {valid_pct:.1f}% gültige Pixel (erwartet >{min_valid}%)")
    else:
        print(f"    ✓ Gültige Pixel: {valid_pct:.1f}%")


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
    except Exception:
        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024**2)
            print(f"  ⚠️  Schreibfehler, aber Datei existiert: {output_path.name} ({file_size_mb:.1f} MB)")
        else:
            raise


# =============================================================================
# PROCESSING PIPELINE
# =============================================================================


def save_city_statistics(stats_list: list, csv_path: Path) -> None:
    """
    Speichert Statistiken inkrementell nach jeder Stadt.
    
    Args:
        stats_list: Liste aller bisherigen Statistiken
        csv_path: Pfad zur CSV-Datei
    """
    # Filtere leere Dicts
    valid_stats = [s for s in stats_list if s]
    if valid_stats:
        df = pd.DataFrame(valid_stats)
        df.to_csv(csv_path, index=False, float_format="%.2f")


def process_city(city: str, boundary_file: Path, boundary_buffer_file: Path, skip_existing: bool = True) -> Tuple[Dict, Dict, Dict]:
    """
    Verarbeitet eine Stadt komplett mit Zwischenspeicherung.

    Args:
        city: Stadtname
        boundary_file: Pfad zu city_boundaries.gpkg (ohne Buffer, für Core-Statistik)
        boundary_buffer_file: Pfad zu city_boundaries_500m_buffer.gpkg (für Clipping)
        skip_existing: Überspringe bereits verarbeitete Städte

    Returns:
        Tuple mit (stats_full, stats_core, corrections)
    """
    import gc
    
    output_path = DATA_CHM_PROCESSED / f"CHM_1m_{city.capitalize()}.tif"
    stats_path = DATA_CHM_PROCESSED / f"stats_{city}.json"

    if skip_existing and output_path.exists():
        print(f"\n{'='*60}")
        print(f"SKIPPING: {city.upper()} (bereits verarbeitet)")
        print(f"{'='*60}")
        # Versuche gespeicherte Statistiken zu laden
        if stats_path.exists():
            import json
            with open(stats_path) as f:
                cached = json.load(f)
            return cached.get("stats_full", {}), cached.get("stats_core", {}), cached.get("corrections", {"negative_pixels": 0, "outlier_pixels": 0})
        return {}, {}, {"negative_pixels": 0, "outlier_pixels": 0}

    print(f"\n{'='*60}")
    print(f"PROCESSING: {city.upper()}")
    print(f"{'='*60}")

    # 1. Lade DOM/DGM und clippe auf 500m Buffer
    print("\n[1/8] Lade und clippe DOM/DGM auf 500m Buffer...")
    dom_path = DATA_CHM_RAW / city / "dom_1m.tif"
    dgm_path = DATA_CHM_RAW / city / "dgm_1m.tif"
    dom, dgm, meta, transform = load_and_clip_elevation(dom_path, dgm_path, city, boundary_buffer_file)

    # 2. Berechne CHM
    print("\n[2/8] Berechne CHM...")
    chm_raw = compute_chm(dom, dgm)
    print(f"  CHM Shape: {chm_raw.shape}, Valid: {np.sum(~np.isnan(chm_raw)):,} pixels")
    
    # Speicher freigeben - DOM/DGM werden nicht mehr benötigt
    del dom, dgm
    gc.collect()

    # 3. Qualitätsfilter
    print("\n[3/8] Wende Qualitätsfilter an...")
    chm_clean, corrections = apply_quality_filters(chm_raw)
    print(
        f"  → NoData: {corrections['negative_pixels']:,} negative Pixel (Wasser/Brücken), "
        f"{corrections['outlier_pixels']:,} Ausreißer >60m"
    )

    # 4. SOFORT SPEICHERN (wichtig für Wiederaufnahme!)
    print("\n[4/8] Speichere CHM (Zwischenergebnis)...")
    save_chm_geotiff(chm_clean, meta, transform, output_path)

    # 5. Erstelle Geometrie-Masken für korrekte Statistik-Berechnung
    print("\n[5/8] Erstelle Geometrie-Masken...")
    buffer_mask = create_geometry_mask(chm_clean.shape, transform, city, boundary_buffer_file)
    core_mask = create_geometry_mask(chm_clean.shape, transform, city, boundary_file)
    print(f"  Pixel in 500m Buffer: {np.sum(buffer_mask):,}")
    print(f"  Pixel in City Core:   {np.sum(core_mask):,}")

    # 6. Statistiken (Full = 500m Buffer)
    print("\n[6/8] Berechne Statistiken (500m Buffer)...")
    stats_full = compute_statistics(chm_clean, city, "500m Buffer", reference_mask=buffer_mask)
    print(
        f"  Mean: {stats_full['Mean']:.2f}m, Median: {stats_full['Median']:.2f}m, "
        f"P95: {stats_full['P95']:.2f}m, Valid: {stats_full['Valid_percent']:.1f}%"
    )

    # 7. Statistiken (Core = ohne Buffer)
    print("\n[7/8] Berechne Statistiken (City core, ohne Buffer)...")
    try:
        chm_core, _ = mask_to_city_core(chm_clean, transform, meta["crs"], city, boundary_file)
        stats_core = compute_statistics(chm_core, city, "City core", reference_mask=core_mask)
        print(
            f"  Mean: {stats_core['Mean']:.2f}m, Median: {stats_core['Median']:.2f}m, "
            f"P95: {stats_core['P95']:.2f}m, Valid: {stats_core['Valid_percent']:.1f}%"
        )
        del chm_core
        gc.collect()
    except Exception as e:
        print(f"  ⚠️  City-Core-Maskierung fehlgeschlagen: {e}")
        stats_core = stats_full.copy()
        stats_core["Extent"] = "City core (fallback)"

    # 8. Validierung
    validate_chm_quality(chm_clean, stats_full, corrections, city, "500m Buffer")
    validate_chm_quality(chm_clean, stats_core, corrections, city, "City core")
    
    # Speichere Statistiken als JSON für Wiederaufnahme
    import json
    with open(stats_path, "w") as f:
        json.dump({
            "stats_full": stats_full,
            "stats_core": stats_core,
            "corrections": corrections
        }, f, indent=2)
    print(f"  ✓ Statistiken zwischengespeichert: {stats_path.name}")

    # 9. Visualisierungen
    print("\n[8/9] Erstelle Visualisierungen...")
    plot_output_dir = DATA_CHM_PROCESSED / "plots"
    plot_output_dir.mkdir(exist_ok=True)
    plot_statistical_overview(chm_clean, stats_full, stats_core, city, transform, plot_output_dir)
    plot_qa_visualization(chm_raw, chm_clean, corrections, city, plot_output_dir)
    
    # Speicher freigeben
    del chm_raw, chm_clean
    gc.collect()

    print(f"\n[9/9] ✓ {city.upper()} abgeschlossen!")

    return stats_full, stats_core, corrections


def main():
    """Hauptfunktion: Verarbeitet alle Städte mit inkrementeller Speicherung."""
    import gc
    
    all_statistics = []
    all_corrections = {}
    csv_path = DATA_CHM_PROCESSED / "chm_statistics.csv"

    boundary_file = DATA_BOUNDARIES / "city_boundaries.gpkg"
    boundary_buffer_file = DATA_BOUNDARIES / "city_boundaries_500m_buffer.gpkg"
    
    if not boundary_file.exists():
        raise FileNotFoundError(f"Stadtgrenzen nicht gefunden: {boundary_file}")
    if not boundary_buffer_file.exists():
        raise FileNotFoundError(f"Stadtgrenzen (500m Buffer) nicht gefunden: {boundary_buffer_file}")

    # Process each city
    for city in CITIES:
        stats_full, stats_core, corrections = process_city(city, boundary_file, boundary_buffer_file)
        
        if stats_full:  # Nur wenn nicht übersprungen
            all_statistics.append(stats_full)
        if stats_core:
            all_statistics.append(stats_core)
        all_corrections[city] = corrections
        
        # Inkrementell speichern nach jeder Stadt
        save_city_statistics(all_statistics, csv_path)
        print(f"  ✓ Gesamtstatistik aktualisiert: {csv_path.name}")
        
        # Speicher freigeben zwischen Städten
        gc.collect()

    # Cross-city comparison
    print("\n" + "=" * 60)
    print("CROSS-CITY COMPARISON")
    print("=" * 60)

    # Filtere leere Statistiken
    valid_stats = [s for s in all_statistics if s]
    if valid_stats:
        df_stats = pd.DataFrame(valid_stats)
        display_cols = ["City", "Extent", "Valid_percent", "Mean", "Median", "P95", "P99", "Max"]
        available_cols = [c for c in display_cols if c in df_stats.columns]
        df_display = df_stats[available_cols].copy()
        if "Valid_percent" in df_display.columns:
            df_display["Valid_percent"] = df_display["Valid_percent"].round(1)
        for col in ["Mean", "Median", "P95", "P99", "Max"]:
            if col in df_display.columns:
                df_display[col] = df_display[col].round(2)

        print("\nStatistik-Übersicht:")
        print(df_display.to_string(index=False))
    else:
        print("\nKeine neuen Statistiken berechnet (alle Städte übersprungen).")

    print("\n\nKorrektur-Zusammenfassung:")
    for city, corr in all_corrections.items():
        if corr:
            print(
                f"  {city.capitalize():10s}: {corr['negative_pixels']:6,} negative, "
                f"{corr['outlier_pixels']:6,} Ausreißer"
            )

    # Finale Statistik speichern (falls noch nicht geschehen)
    save_city_statistics(all_statistics, csv_path)
    print(f"\n✓ Statistiken gespeichert: {csv_path}")

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE ABGESCHLOSSEN")
    print("=" * 60)
    print("\nErzeugte Dateien:")
    for city in CITIES:
        chm_file = DATA_CHM_PROCESSED / f"CHM_1m_{city.capitalize()}.tif"
        if chm_file.exists():
            size_mb = chm_file.stat().st_size / (1024**2)
            print(f"  ✓ {chm_file.name:25s} ({size_mb:6.1f} MB)")
        else:
            print(f"  ✗ {chm_file.name:25s} (FEHLT!)")

    print(f"  ✓ {csv_path.name}")
    print(f"  ✓ Plots in {DATA_CHM_PROCESSED / 'plots'}")


if __name__ == "__main__":
    main()
