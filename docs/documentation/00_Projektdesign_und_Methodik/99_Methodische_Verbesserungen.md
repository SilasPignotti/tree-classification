# Methodische Verbesserungen - Projektdesign & Methodik

**Status:** Dokumentation ausstehend
**Letzte Aktualisierung:** 21. Januar 2026

---

## 🟢 Dokumentation - Bekannte Limitations

### 1. Klimajahr 2021 Anomalie

**Problem:**
2021 war ein kühl/nasses Jahr → Modelle nur für diese klimatischen Bedingungen validiert.

**Zu dokumentieren in `02_Methodische_Grundlagen.md`:**

- Section "Temporal Generalization Limitation"
- Empfehlung: Multi-Jahr-Retraining für operative Anwendungen
- Verweise auf DWD-Daten 2021 vs. Langzeit-Mittel

**Priorität:** 🟢 NIEDRIG
**Aufwand:** 1 Stunde

---

### 2. Cross-City Confounders

**Problem:**
Berlin/Hamburg vs. Rostock unterscheiden sich nicht nur im Klima, sondern auch in:

- Urbanisierungsgrad
- tree_type (Straßenbaum vs. Anlagenbaum)
- Baum-Alter
- Kataster-Qualität

**Zu dokumentieren in `02_Methodische_Grundlagen.md`:**

- Section "Confounding Factors in Cross-City Transfer"
- Limitation: Nicht alle Confounders kontrolliert
- Vorsichtige Interpretation Transfer-Performance

**Priorität:** 🟢 NIEDRIG
**Aufwand:** 1 Stunde

---

**Version:** 1.0 | **Aktualisiert:** 21. Januar 2026
