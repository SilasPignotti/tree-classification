"""
Harmonisiert DOM und DGM Daten für alle Städte.

Löst zwei kritische Probleme:
1. Grid-Alignment: DOM und DGM auf identische Dimensionen bringen
2. NoData-Harmonisierung: Einheitlicher NoData-Wert (-9999)

Analyse der Ausgangssituation (Stand 09.12.2025):
- Berlin: NoData=0.0, min Höhe=~20m → 0 ist KORREKT als NoData (keine validen 0m-Werte!)
- Hamburg DOM: NoData=None → muss auf -9999 gesetzt werden
- Hamburg DGM: NoData=-32768 → konvertieren zu -9999
- Rostock: NoData=-9999 → bereits korrekt

Coverage INNERHALB Stadtgrenzen:
- Berlin: ~95% (Rest sind echte Lücken)
- Hamburg DOM: 100%, DGM: 89% (echte Lücken)
- Rostock: >99%

WICHTIG: Dieses Skript überschreibt die Originaldateien!
         Stelle sicher, dass ein Backup existiert.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config import CHM_RAW_DIR, CITIES

# Ziel-NoData Wert
TARGET_NODATA = -9999.0


def harmonize_nodata_berlin(src_path: Path, dst_path: Path, data_type: str) -> dict:
    """
    Berlin: NoData=0.0 → -9999.0

    Berlin verwendet 0.0 als NoData. Die minimale echte Höhe liegt bei ~20m,
    daher gibt es keine validen 0m-Werte. Wir konvertieren 0 → -9999.
    """
    with rasterio.open(src_path) as src:
        data = src.read(1)
        profile = src.profile.copy()

        original_nodata = src.nodata

        # Zähle NoData-Pixel (Wert == 0)
        nodata_mask = data == 0
        valid_before = (~nodata_mask).sum()

        # Konvertiere 0 → -9999
        output_data = np.where(nodata_mask, TARGET_NODATA, data).astype(np.float32)
        valid_after = (output_data != TARGET_NODATA).sum()

        profile.update(
            dtype=rasterio.float32,
            nodata=TARGET_NODATA,
            compress="lzw",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )

        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(output_data, 1)

    return {
        "original_nodata": original_nodata,
        "new_nodata": TARGET_NODATA,
        "valid_before": int(valid_before),
        "valid_after": int(valid_after),
    }


def harmonize_nodata_hamburg(src_path: Path, dst_path: Path, data_type: str) -> dict:
    """
    Hamburg: DOM NoData=None, DGM NoData=-32768 → beide auf -9999

    Hamburg DOM hat kein NoData definiert (alle Pixel gelten als valid).
    Hamburg DGM hat NoData=-32768.
    """
    with rasterio.open(src_path) as src:
        data = src.read(1)
        profile = src.profile.copy()

        original_nodata = src.nodata
        total_pixels = data.size

        if original_nodata is None:
            # DOM: Kein NoData definiert, alle Pixel sind valid
            # Setze NoData-Wert für Konsistenz, aber ändere keine Daten
            output_data = data.astype(np.float32)
            valid_before = total_pixels
            valid_after = total_pixels
        elif np.isclose(original_nodata, -32768):
            # DGM: NoData=-32768, konvertiere zu -9999
            nodata_mask = np.isclose(data, original_nodata)
            valid_before = (~nodata_mask).sum()
            output_data = np.where(nodata_mask, TARGET_NODATA, data).astype(np.float32)
            valid_after = (output_data != TARGET_NODATA).sum()
        else:
            # Unerwarteter NoData-Wert
            output_data = data.astype(np.float32)
            valid_before = total_pixels
            valid_after = total_pixels

        profile.update(
            dtype=rasterio.float32,
            nodata=TARGET_NODATA,
            compress="lzw",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )

        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(output_data, 1)

    return {
        "original_nodata": original_nodata,
        "new_nodata": TARGET_NODATA,
        "valid_before": int(valid_before),
        "valid_after": int(valid_after),
    }


def harmonize_nodata_rostock(src_path: Path, dst_path: Path, data_type: str) -> dict:
    """
    Rostock: NoData bereits -9999, nur Profil-Update und Copy.
    """
    with rasterio.open(src_path) as src:
        data = src.read(1)
        profile = src.profile.copy()

        original_nodata = src.nodata

        # Zähle NoData-Pixel
        if original_nodata is not None:
            nodata_mask = np.isclose(data, original_nodata)
            valid_before = (~nodata_mask).sum()
        else:
            valid_before = data.size

        output_data = data.astype(np.float32)
        valid_after = (output_data != TARGET_NODATA).sum()

        profile.update(
            dtype=rasterio.float32,
            nodata=TARGET_NODATA,
            compress="lzw",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )

        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(output_data, 1)

    return {
        "original_nodata": original_nodata,
        "new_nodata": TARGET_NODATA,
        "valid_before": int(valid_before),
        "valid_after": int(valid_after),
    }


def align_dgm_to_dom(dom_path: Path, dgm_path: Path, output_path: Path) -> dict:
    """
    Aligniert DGM auf DOM-Grid mit bilinearem Resampling.

    DOM dient als Referenz (bessere Coverage).
    DGM wird auf exakt gleiche Dimensionen, Transform und CRS gebracht.
    """
    with rasterio.open(dom_path) as dom_src:
        dom_shape = (dom_src.height, dom_src.width)
        dom_transform = dom_src.transform
        dom_crs = dom_src.crs
        dom_bounds = dom_src.bounds

    with rasterio.open(dgm_path) as dgm_src:
        dgm_data = dgm_src.read(1)
        dgm_shape_before = (dgm_src.height, dgm_src.width)
        dgm_nodata = dgm_src.nodata

        # Erstelle Output-Array mit NoData gefüllt
        output_data = np.full(dom_shape, TARGET_NODATA, dtype=np.float32)

        # Reproject DGM auf DOM-Grid
        reproject(
            source=dgm_data,
            destination=output_data,
            src_transform=dgm_src.transform,
            src_crs=dgm_src.crs,
            src_nodata=dgm_nodata,
            dst_transform=dom_transform,
            dst_crs=dom_crs,
            dst_nodata=TARGET_NODATA,
            resampling=Resampling.bilinear,
        )

    # Schreibe aligniertes DGM
    profile = {
        "driver": "GTiff",
        "dtype": rasterio.float32,
        "width": dom_shape[1],
        "height": dom_shape[0],
        "count": 1,
        "crs": dom_crs,
        "transform": dom_transform,
        "nodata": TARGET_NODATA,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(output_data, 1)

    return {
        "dgm_shape_before": dgm_shape_before,
        "dgm_shape_after": dom_shape,
        "dom_shape": dom_shape,
        "dom_bounds": dom_bounds,
    }


def harmonize_city(city: str) -> dict:
    """Harmonisiert DOM und DGM für eine Stadt."""
    city_dir = CHM_RAW_DIR / city.lower()
    dom_path = city_dir / "dom_1m.tif"
    dgm_path = city_dir / "dgm_1m.tif"

    print(f"\n{'=' * 60}")
    print(f"Harmonisiere {city}")
    print(f"{'=' * 60}")

    results = {"city": city}

    # Wähle stadt-spezifische NoData-Funktion
    nodata_funcs = {
        "Berlin": harmonize_nodata_berlin,
        "Hamburg": harmonize_nodata_hamburg,
        "Rostock": harmonize_nodata_rostock,
    }
    nodata_func = nodata_funcs[city]

    # Schritt 1: NoData-Harmonisierung (in temporäre Dateien)
    print(f"\n[1/2] NoData-Harmonisierung für {city}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        dom_tmp = tmpdir_path / "dom_harmonized.tif"
        dgm_tmp = tmpdir_path / "dgm_harmonized.tif"

        # DOM NoData harmonisieren
        print(f"  Processing DOM...")
        dom_nodata_result = nodata_func(dom_path, dom_tmp, "DOM")
        results["dom_nodata"] = dom_nodata_result
        print(f"    NoData: {dom_nodata_result['original_nodata']} → {dom_nodata_result['new_nodata']}")
        print(f"    Valid pixels: {dom_nodata_result['valid_before']:,} → {dom_nodata_result['valid_after']:,}")

        # DGM NoData harmonisieren
        print(f"  Processing DGM...")
        dgm_nodata_result = nodata_func(dgm_path, dgm_tmp, "DGM")
        results["dgm_nodata"] = dgm_nodata_result
        print(f"    NoData: {dgm_nodata_result['original_nodata']} → {dgm_nodata_result['new_nodata']}")
        print(f"    Valid pixels: {dgm_nodata_result['valid_before']:,} → {dgm_nodata_result['valid_after']:,}")

        # Schritt 2: Grid-Alignment (DGM auf DOM-Grid)
        print(f"\n[2/2] Grid-Alignment für {city}...")

        # Kopiere DOM direkt (ist die Referenz)
        print(f"  DOM als Referenz kopieren...")
        shutil.copy2(dom_tmp, dom_path)

        # Aligniere DGM auf DOM
        dgm_aligned_tmp = tmpdir_path / "dgm_aligned.tif"
        print(f"  DGM auf DOM-Grid alignieren...")
        alignment_result = align_dgm_to_dom(dom_tmp, dgm_tmp, dgm_aligned_tmp)
        results["alignment"] = alignment_result

        print(f"    DGM Shape: {alignment_result['dgm_shape_before']} → {alignment_result['dgm_shape_after']}")
        print(f"    DOM Shape: {alignment_result['dom_shape']}")

        # Kopiere aligniertes DGM zurück
        shutil.copy2(dgm_aligned_tmp, dgm_path)

    # Verifiziere Ergebnis
    print(f"\n  Verifizierung...")
    with rasterio.open(dom_path) as dom_src, rasterio.open(dgm_path) as dgm_src:
        shapes_match = (dom_src.height, dom_src.width) == (dgm_src.height, dgm_src.width)
        nodata_match = dom_src.nodata == dgm_src.nodata == TARGET_NODATA

        results["verification"] = {
            "shapes_match": shapes_match,
            "nodata_match": nodata_match,
            "final_shape": (dom_src.height, dom_src.width),
            "final_nodata": TARGET_NODATA,
        }

        status = "✓" if shapes_match and nodata_match else "✗"
        print(f"  {status} Shapes identisch: {shapes_match}")
        print(f"  {status} NoData identisch: {nodata_match}")
        print(f"  Final Shape: {dom_src.height} × {dom_src.width}")

    return results


def main():
    """Hauptfunktion: Harmonisiert alle Städte."""
    print("=" * 70)
    print("DOM/DGM HARMONISIERUNG")
    print("=" * 70)
    print()
    print("WARNUNG: Dieses Skript überschreibt die Originaldateien!")
    print("         Stelle sicher, dass ein Backup existiert.")
    print()

    all_results = {}

    for city in CITIES:
        try:
            results = harmonize_city(city)
            all_results[city] = results
        except Exception as e:
            print(f"\n✗ FEHLER bei {city}: {e}")
            all_results[city] = {"error": str(e)}

    # Zusammenfassung
    print("\n")
    print("=" * 70)
    print("ZUSAMMENFASSUNG")
    print("=" * 70)

    for city, results in all_results.items():
        if "error" in results:
            print(f"✗ {city}: FEHLER - {results['error']}")
        else:
            verification = results.get("verification", {})
            if verification.get("shapes_match") and verification.get("nodata_match"):
                print(f"✓ {city}: Erfolgreich harmonisiert")
                print(f"    Shape: {verification['final_shape']}")
            else:
                print(f"⚠ {city}: Teilweise harmonisiert (Verifizierung prüfen)")

    print()
    print("Führe jetzt 'validate_elevation.py' aus, um die Ergebnisse zu prüfen.")


if __name__ == "__main__":
    main()
