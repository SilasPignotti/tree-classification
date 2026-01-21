# [Titel]: [Komponente/Thema] - Methodik und Dokumentation

**Projektphase:** [z.B. Datenakquise, Feature Engineering, Model Training]  
**Datum:** [Erstellungsdatum]  
**Autor:** Silas Pignotti  
**Notebook/Script:** [z.B. `notebooks/01_processing/example.ipynb` oder `scripts/example.py`] _(optional)_

---

## 1. Übersicht

[Kurze Zusammenfassung des Dokuments: Was wird beschrieben? Warum ist dieser Schritt wichtig?]

### 1.1 Zweck

[Detaillierte Beschreibung des Zwecks dieses Verarbeitungsschritts/dieser Methode:

- Was soll erreicht werden?
- Welches Problem wird gelöst?
- Welche Daten werden transformiert/generiert?]

### 1.2 Zieldaten / Output

**[Output-Datei-Typ] ([Beschreibung]):**

- **Format:** [z.B. GeoPackage (GPKG), GeoTIFF, CSV]
- **Koordinatensystem:** [z.B. EPSG:25832 (ETRS89 / UTM zone 32N)]
- **Auflösung/Dimension:** [z.B. 1m, 10m, oder Anzahl Features/Spalten]
- **Räumliche Abdeckung:** [z.B. Stadtgrenze + 500m Buffer]
- **Datentyp:** [z.B. Float32, Integer]
- **NoData-Wert:** [z.B. -9999, None] _(falls relevant)_
- **Attribute/Features:** [Liste wichtiger Spalten/Features]

### 1.3 Untersuchungsgebiete / Zielstädte

1. **Hamburg** - [Rolle: z.B. Trainingsdaten, ~Fläche]
2. **Berlin** - [Rolle: z.B. Trainingsdaten, ~Fläche]
3. **Rostock** - [Rolle: z.B. Testdaten, ~Fläche]

### 1.4 Workflow-Übersicht / Pipeline

```
[ASCII-Diagramm der Verarbeitungsschritte]
Beispiel:

Input-Daten (Format, Quelle)
    ↓
[Step 1] Beschreibung Schritt 1
    ├── Sub-Operation 1
    ├── Sub-Operation 2
    └── Validierung
    ↓ [Output/Zwischenstand]
[Step 2] Beschreibung Schritt 2
    ├── Sub-Operation 1
    └── Sub-Operation 2
    ↓ [Output/Zwischenstand]
[Step 3] Beschreibung Schritt 3
    ↓
Output-Daten (Format, Anzahl)
```

---

## 2. Theoretische Grundlagen _(optional, bei Bedarf)_

### 2.1 [Konzept/Theorie 1]

[Erklärung der theoretischen/wissenschaftlichen Grundlage:

- Warum wird diese Methode verwendet?
- Welche wissenschaftlichen Prinzipien liegen zugrunde?
- Formel/Gleichungen (in KaTeX formatiert, wenn nötig)]

**Beispiel:**

```
CHM = DOM - DGM

where:
  DOM = Digital Surface Model (Oberfläche inkl. Objekte)
  DGM = Digital Terrain Model (Geländeoberfläche)
  CHM = Canopy Height Model (Vegetationshöhe)
```

### 2.2 [Konzept/Theorie 2]

[Weitere theoretische Grundlagen, falls relevant]

---

## 3. Datenquellen

### 3.1 [Stadt 1 / Quelle 1]

**Quelle:** [Name der Institution/Organisation]  
**Service:** [z.B. Web Feature Service (WFS) 2.0.0, OGC API Features, Direct Download]  
**Layer/Datensatz:** [Name des Layers]  
**URL:** [Download-/Service-URL]  
**Datenformat:** [z.B. GML 3.2, GeoJSON, XYZ ASCII, GeoTIFF]  
**CRS:** [z.B. EPSG:25832, EPSG:25833]

**Datensatz-Details:**

- **Aktualität:** [Datum/Stand der Daten]
- **Geometrie-Typ:** [z.B. Point, Polygon, Raster]
- **Auflösung:** [z.B. 1m, 10m] _(bei Rasterdaten)_
- **Schlüsselattribute:** [Wichtige Spalten/Attribute]
- **Abdeckung:** [Räumliche Abdeckung]

**Besonderheiten:**

- [Wichtige Hinweise zur Datenquelle]
- [Technische Spezifikationen]
- [Limitationen oder Herausforderungen]

### 3.2 [Stadt 2 / Quelle 2]

[Gleiche Struktur wie 3.1]

### 3.3 [Stadt 3 / Quelle 3]

[Gleiche Struktur wie 3.1]

---

## 4. Methodisches Vorgehen

### 4.1 [Schritt 1: Beschreibung]

**Zweck:** [Warum wird dieser Schritt durchgeführt?]

**Methode:**

[Detaillierte Beschreibung der Methode:

- Welche Algorithmen/Techniken werden verwendet?
- Welche Parameter sind wichtig?
- Welche Tools/Bibliotheken werden eingesetzt?]

**Implementierung:**

```python
# Beispiel-Code (falls relevant)
import geopandas as gpd

# Beschreibung der Implementierung
data = gpd.read_file("input.gpkg")
# ...
```

**Parameter:**

| Parameter | Wert   | Beschreibung               | Begründung           |
| --------- | ------ | -------------------------- | -------------------- |
| [param1]  | [wert] | [was macht der Parameter?] | [warum dieser Wert?] |
| [param2]  | [wert] | [was macht der Parameter?] | [warum dieser Wert?] |

**Validierung:**

- [Wie wird die Qualität dieses Schritts überprüft?]
- [Welche Kontrollen werden durchgeführt?]

**Output:**

- [Was ist das Ergebnis dieses Schritts?]
- [Welche Dateien werden generiert?]

### 4.2 [Schritt 2: Beschreibung]

[Gleiche Struktur wie 4.1]

### 4.3 [Schritt 3: Beschreibung]

[Gleiche Struktur wie 4.1]

---

## 5. Datenqualität & Validierung

### 5.1 Qualitätsprüfungen

**[Prüfung 1: Beschreibung]**

- **Methode:** [Wie wird geprüft?]
- **Kriterium:** [Was ist der Erfolgs-/Akzeptanzkriterium?]
- **Ergebnis:** [Was wurde festgestellt?]

**[Prüfung 2: Beschreibung]**

- **Methode:** [Wie wird geprüft?]
- **Kriterium:** [Was ist der Erfolgs-/Akzeptanzkriterium?]
- **Ergebnis:** [Was wurde festgestellt?]

### 5.2 Fehlerbehandlung

**[Fehlertyp 1]:**

- **Problem:** [Beschreibung des Problems]
- **Häufigkeit:** [Wie oft tritt es auf?]
- **Lösung:** [Wie wird damit umgegangen?]

**[Fehlertyp 2]:**

- **Problem:** [Beschreibung des Problems]
- **Häufigkeit:** [Wie oft tritt es auf?]
- **Lösung:** [Wie wird damit umgegangen?]

### 5.3 Datenverluste / Filterung

[Falls Daten gefiltert oder entfernt werden:]

| Filterkriterium | Anzahl entfernt | Prozent | Begründung |
| --------------- | --------------- | ------- | ---------- |
| [Kriterium 1]   | [Anzahl]        | [%]     | [Warum?]   |
| [Kriterium 2]   | [Anzahl]        | [%]     | [Warum?]   |
| **Total**       | [Anzahl]        | [%]     | -          |

---

## 6. Ergebnisse & Statistiken

### 6.1 Output-Übersicht

[Zusammenfassung der generierten Dateien und ihrer Eigenschaften:]

```
output_directory/
├── file_1.ext          ([Anzahl] Einträge, ~Größe)
├── file_2.ext          ([Anzahl] Einträge, ~Größe)
└── metadata/
    ├── summary.json    (Verarbeitungsstatistiken)
    └── report.csv      (Detaillierte Metriken)
```

### 6.2 Deskriptive Statistiken

**[Datensatz/Variable 1]:**

| Metrik             | Wert  | Einheit   | Anmerkung   |
| ------------------ | ----- | --------- | ----------- |
| Anzahl             | [N]   | -         | [Kommentar] |
| Mittelwert         | [μ]   | [Einheit] | [Kommentar] |
| Standardabweichung | [σ]   | [Einheit] | [Kommentar] |
| Minimum            | [min] | [Einheit] | [Kommentar] |
| Maximum            | [max] | [Einheit] | [Kommentar] |

**[Datensatz/Variable 2]:**

[Gleiche Struktur]

### 6.3 Visualisierungen _(optional)_

[Hinweise auf Grafiken, Karten oder Plots:]

- **[Abbildung 1]:** [Beschreibung]
- **[Abbildung 2]:** [Beschreibung]

---

## 7. Herausforderungen & Lösungen

### 7.1 [Herausforderung 1: Titel]

**Problem:** [Detaillierte Beschreibung des Problems]

**Kontext:** [Wann/wo trat das Problem auf?]

**Lösung:** [Wie wurde das Problem gelöst?]

**Lessons Learned:** [Was wurde gelernt?]

### 7.2 [Herausforderung 2: Titel]

[Gleiche Struktur wie 7.1]

---

## 8. Designentscheidungen & Begründungen

### 8.1 [Entscheidung 1: Titel]

**Entscheidung:** [Was wurde entschieden?]

**Alternativen:** [Welche anderen Optionen wurden erwogen?]

**Begründung:** [Warum wurde diese Option gewählt?]

**Implikationen:** [Welche Konsequenzen hat diese Entscheidung?]

### 8.2 [Entscheidung 2: Titel]

[Gleiche Struktur wie 8.1]

---

## 9. Verwendete Tools & Bibliotheken

### 9.1 Software-Stack

| Tool/Bibliothek | Version | Verwendung         |
| --------------- | ------- | ------------------ |
| Python          | [x.x]   | [Hauptsprache]     |
| [library1]      | [x.x]   | [Wofür verwendet?] |
| [library2]      | [x.x]   | [Wofür verwendet?] |
| [library3]      | [x.x]   | [Wofür verwendet?] |

### 9.2 Externe Tools _(optional)_

- **[Tool 1]:** [Beschreibung der Verwendung]
- **[Tool 2]:** [Beschreibung der Verwendung]

---

## 10. Reproduzierbarkeit

### 10.1 Ausführung

**Script/Notebook:** [Pfad zum ausführbaren Code]

**Kommandozeile:**

```bash
# Beispiel für Script-Ausführung
python scripts/example/script_name.py
```

**Notebook:**

```bash
# Beispiel für Notebook-Ausführung
jupyter notebook notebooks/example.ipynb
```

### 10.2 Runtime & Ressourcen

- **Geschätzte Laufzeit:** [z.B. 45 Minuten]
- **RAM-Bedarf:** [z.B. ~8 GB]
- **CPU-Auslastung:** [z.B. 4 Cores (parallele Verarbeitung)]
- **Disk Space:** [z.B. ~2.5 GB Output]

### 10.3 Abhängigkeiten

**Input-Dateien (Prerequisites):**

- [Input 1]: [Pfad oder Beschreibung]
- [Input 2]: [Pfad oder Beschreibung]

**Output-Dateien (Generated):**

- [Output 1]: [Pfad oder Beschreibung]
- [Output 2]: [Pfad oder Beschreibung]

---

## 11. Limitationen & Offene Fragen

### 11.1 Bekannte Limitationen

1. **[Limitation 1]:** [Beschreibung der Einschränkung]
2. **[Limitation 2]:** [Beschreibung der Einschränkung]

### 11.2 Offene Fragen / Future Work

1. **[Frage 1]:** [Was könnte noch untersucht werden?]
2. **[Frage 2]:** [Welche Verbesserungen sind denkbar?]

---

## 12. Referenzen _(optional)_

[Falls wissenschaftliche Literatur, Standards oder externe Dokumentation referenziert wird:]

1. [Autor, Jahr]: [Titel]. [Publikation]. [URL/DOI]
2. [Standard-Name]: [Beschreibung]. [URL]

---

## Appendix _(optional)_

### A. [Zusätzliche Tabellen / Detailanalysen]

[Ergänzende Informationen, die für das Hauptdokument zu detailliert sind]

### B. [Code-Snippets]

[Längere Code-Beispiele oder Hilfs-Funktionen]

### C. [Konfigurationsdateien]

[Beispiele für Config-Files, YAML, JSON, etc.]

---

**Dokumentversion:** 1.0  
**Letzte Aktualisierung:** [Datum]
