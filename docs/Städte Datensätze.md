## 1) Übersichtstabelle

| Stadt | Baumkataster Link | Kataster Format | CHM | CHM Jahr / Aufl. | S2 Zeitraum (openEO) | Status | Bemerkungen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Hamburg | https://api.hamburg.de/datasets/v1/strassenbaumkataster | API (WFS/WMS) | DOM & DGM vorhanden | 2021 | April–Okt 2024 | ☐ offen |  |
| Berlin | https://gdi.berlin.de/geonetwork/srv/ger/catalog.search#/metadata/3368004a-d596-336a-8fdf-c4391f3313dd | API (WFS/WMS) | DOM & DGM vorhanden | 2021 | April–Okt 2024 | ☐ offen |  |
| Rostock (Test) | https://www.opendata-hro.de/dataset/baeume | API (WFS/WMS) | DOM & DGM vorhanden | ? | April–Okt 2024 | ☐ offen |  |
| Lübeck (Fallback) | https://opendata.luebeck.de/bereich/5.660/stadtgruen/baumkataster/index.html | CSV |  |  | April–Okt 2024 | ☐ optional |  |
| Schwerin (Fallback, optional) | - | - |  |  | April–Okt 2024 | ☐ optional |  |

---

## 2) Stadtmodule

### Hamburg

#### Baumkataster
- **Link:**  
  https://api.hamburg.de/datasets/v1/strassenbaumkataster/api?f=json
- **Format:** JSON (REST-API)
- **Last Update:**  
  Fortlaufend aktualisiert über das Transparenzportal. Datensätze enthalten individuelle Zeitstempel.
- **Lizenz:** dl-de/by-2-0

#### CHM (Hamburg)

*CHM entsteht aus DOM1 − DGM1.*

**bDOM – Digitales Oberflächenmodell Hamburg**
- **Link (ASCII):**  
  https://daten-hamburg.de/opendata/Digitales_Hoehenmodell_bDOM/dom1_xyz_HH_2021_04_30.zip
- **Metadaten:**  
  https://suche.transparenz.hamburg.de/dataset/digitales-hoehenmodell-hamburg-bdom7
- **Jahr / Auflösung:** 1 m, 2021

**DGM1 – Digitales Geländemodell Hamburg**
- **Link (ASCII):**  
  https://daten-hamburg.de/geographie_geologie_geobasisdaten/Digitales_Hoehenmodell/DGM1/dgm1_2x2km_XYZ_hh_2021_04_01.zip
- **Metadaten:**  
  https://suche.transparenz.hamburg.de/dataset/digitales-hoehenmodell-hamburg-dgm-16
- **Jahr / Auflösung:** 1 m, 2021

---

### Berlin

#### Baumkataster (FIS-Broker)
- **Link:**  
  https://gdi.berlin.de/services/wfs/baumbestand?REQUEST=GetCapabilities&SERVICE=WFS
- **Format:** WFS (GML/XML)
- **Last Update:** Regelmäßig aktualisiert (typisch jährlich oder häufiger).
- **Lizenz:** dl-de/zero-2-0

#### CHM (Berlin)

*CHM entsteht aus DOM1 − DGM1.*

**DOM1 – Digitales Oberflächenmodell Berlin**
- **Link:**  
  https://fbinter.stadt-berlin.de/fb/feed/senstadt/a_dom1
- **Metadaten:**  
  https://www.berlin.de/sen/sbw/stadtdaten/geoinformation/geotopographie-atkis/dom-digitales-oberflaechenmodell/
- **Jahr / Auflösung:** 1 m, Befliegung Feb–Mär 2021

**DGM1 – Digitales Geländemodell Berlin**
- **Link:**  
  https://gdi.berlin.de/data/dgm1/atom
- **Metadaten:**  
  https://www.berlin.de/sen/sbw/stadtdaten/geoinformation/geotopographie-atkis/dgm-digitale-gelaendemodelle/
- **Jahr / Auflösung:** 1 m, Befliegung Q1 2021

---

### Rostock (Teststadt)

#### Baumkataster
- **Link:**  
  https://geo.sv.rostock.de/geodienste/baeume/wfs?service=WFS&version=2.0.0&request=GetCapabilities
- **Format:** WFS (GML/XML)
- **Last Update:** Laufend aktualisiert, Objekte haben Änderungszeitstempel.
- **Lizenz:** dl-de/by-2-0

#### CHM (LAiV MV)

**DOM1 – Digitales Oberflächenmodell MV**
- **Link:**  
  https://www.geodaten-mv.de/dienste/dom_atom
- **Metadaten:**  
  https://www.geoportal-mv.de/portal/Geowebdienste/INSPIRE_Atom_Feeds?feed=https%3A%2F%2Fwww.geodaten-mv.de%2Fdienste%2Fdom_atom#feed=https%3A%2F%2Fwww.geodaten-mv.de%2Fdienste%2Fdom_atom
- **Jahr / Auflösung:** 1 m, regelmäßige Aktualisierung

**DGM1 – Digitales Geländemodell MV**
- **Link:**  
  https://www.geodaten-mv.de/dienste/dgm_atom
- **Metadaten:**  
  https://www.geoportal-mv.de/portal/Geowebdienste/INSPIRE_Atom_Feeds?feed=https%3A%2F%2Fwww.geodaten-mv.de%2Fdienste%2Fdgm_atom#feed=https%3A%2F%2Fwww.geodaten-mv.de%2Fdienste%2Fdgm_atom
- **Jahr / Auflösung:** 1 m, regelmäßige Aktualisierung

---

## 3) openEO – Sentinel-2 Processing Block

**Parameter pro Stadt**
- Zeitraum: April–Oktober 2024
- Cloud Filter: SCL != Wolke (Threshold 20 %)
- Output: Monatliche Mediane
- Resampling: B11/B12 auf 10 m
- Export: Cloud-optimized GeoTIFF

**Status Tracking**

| Stadt | S2 fertig? | QA durchgeführt? | Link zu Output |
| --- | --- | --- | --- |
| Hamburg | ☐ | ☐ |  |
| Berlin | ☐ | ☐ |  |
| Rostock | ☐ | ☐ |  |
| Lübeck | ☐ | ☐ |  |
| Schwerin | ☐ | ☐ |  |

---

## 4) Kontrollliste

- [ ] Baumkataster aller Primärstädte (HH, BE, RO) geladen
- [ ] CHM aller Primärstädte geladen
- [ ] S2 openEO-Processing abgeschlossen
- [ ] CHM-S2 Alignment geprüft
- [ ] Artenliste finalisiert (≥ 500 Samples/Art in Primärstädten)
- [ ] Exportierte Feature-Stacks (107 Features) vollständig
- [ ] Datensatz-Splits (Train/Val/Test) erstellt

---

## 5) Uploadbereich für Dateien

- Hamburg Kataster (GeoJSON/CSV)
- Hamburg CHM (TIFF)
- Berlin Kataster
- Berlin CHM
- Rostock Kataster
- Rostock CHM
- Fallback-Städte (Lübeck, Schwerin)
