# Projektübersicht

## Ziel

Entwicklung eines Machine-Learning-Systems zur automatischen **Klassifizierung von Baumarten** in Städten basierend auf Satellitenbildern (Sentinel-2), Höhendaten (CHM) und spektralen Indizes.

**Kernfrage:** Wie gut generalisieren Modelle zwischen verschiedenen Städten? Können in Hamburg/Berlin trainierte Modelle auf Rostock angewendet werden?

## Hintergrund

- Viele Städte haben unvollständige/veraltete Baumkataster
- Manuelle Kartierung von 100k+ Bäumen ist teuer und zeitintensiv
- Automatische Klassifizierung mit offenen Daten (Sentinel-2, öffentliche DHMs) ist kostengünstiger

## Output

- Trainierte Klassifizierungsmodelle
- Vorhersagen für Testbäume (GeoPackage)
- Reproduzierbare Python-Pipeline
- Wissenschaftliche Dokumentation

## Untersuchungsgebiete

- **Hamburg & Berlin:** Trainingsdaten
- **Rostock:** Testdaten (für Generalisierungsprüfung)

## Pipeline-Phasen

1. **Datenverarbeitung:** Harmonisierung Baumkataster, Sentinel-2-Daten, Höhenmodelle
2. **Feature Engineering:** Multitemporale spektrale Features + optionale strukturelle Features
3. **Modelltraining:** Vergleich verschiedener ML-Klassifikationsverfahren
4. **Evaluation:** Cross-City Transfer testen, Generalisierungsfähigkeit bewerten

## Forschungsfrage

**Zentral:** Wie generalisieren ML-Modelle für Baumartenerkennung zwischen verschiedenen Städten derselben Klimazone?

**Unterfragen:**

- Welcher Algorithmus ist am besten geeignet?
- Wie hoch ist der Genauigkeitsverlust beim Transfer Hamburg+Berlin → Rostock?
- Kann lokales Fine-Tuning die Generalisierung verbessern?

## Untersuchungsziele

1. Methodenvergleich verschiedener ML-Ansätze
2. Maximale Genauigkeit innerhalb einer Stadt (Single-City)
3. Generalisierungsverlust quantifizieren (Cross-City Transfer)
4. Fine-Tuning-Potenzial testen

**Relevanz:** Studien zeigen hohe Single-City-Genauigkeiten (>85%), systematische stadtübergreifende Transferstudien fehlen noch.

## Feature-Kategorien

- Multispektrale Zeitserien (Sentinel-2, Vegetationsperiode)
- Vegetation-Indizes (zeitlich aggregiert)
- Strukturelle Höhendaten (optional)

## Erfolgskriterien

✅ **Wissenschaftlich:** Publikationstaugliche Ergebnisse mit valider Evaluation  
✅ **Technisch:** Reproduzierbare, versionierte Pipeline  
✅ **Praktisch:** Modelle auf neue Städte anwendbar

---

**Version:** 1.1 | **Aktualisiert:** 21. Januar 2026
