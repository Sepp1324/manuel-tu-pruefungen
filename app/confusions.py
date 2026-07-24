"""Verwechslungs-Trainer: haeufig verwechselte Begriffe/Prozesse als A/B-Entscheidung.

Jede Gruppe hat zwei leicht zu verwechselnde Begriffe (a/b) und mehrere Aussagen,
die jeweils genau auf einen der beiden zutreffen. Der Nutzer entscheidet je Aussage,
welcher Begriff gemeint ist. Die Loesung wird serverseitig geprueft (kein Leak).
"""
from __future__ import annotations

import hashlib
import random


CONFUSIONS = [
    # --- Organische Technologie ---
    {"id": "lauge-kraft-sulfit", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "a": "Schwarzlauge (Kraft/Sulfat)", "b": "Sulfitablauge (Sulfit)",
     "explain": "Schwarzlauge = Ablauge des alkalischen Sulfat-/Kraft-Verfahrens (Alkalilignin). "
                "Sulfitablauge = Ablauge des Sulfitaufschlusses und Quelle der Ligninsulfonate.",
     "items": [
         {"statement": "Ablauge des alkalischen Sulfat-/Kraft-Verfahrens, enthält Alkalilignin.", "answer": "a"},
         {"statement": "Quelle der Ligninsulfonate (sulfonierte Lignine), z. B. als Betonverflüssiger.", "answer": "b"},
         {"statement": "Wird eingedampft und verbrannt – liefert Energie und Chemikalienrückgewinnung.", "answer": "a"},
         {"statement": "Fällt beim sauren Sulfitaufschluss an.", "answer": "b"},
     ]},
    {"id": "kraft-sulfit-verfahren", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "a": "Sulfat-/Kraftverfahren", "b": "Sulfitverfahren",
     "explain": "Kraft = alkalischer Aufschluss (NaOH/Na₂S), sehr fester Zellstoff, Chemikalienrückgewinnung. "
                "Sulfit = saurer Aufschluss, liefert gut bleichbaren Zellstoff und Ligninsulfonate.",
     "items": [
         {"statement": "Alkalischer Aufschluss mit Weißlauge (NaOH + Na₂S).", "answer": "a"},
         {"statement": "Saurer Aufschluss; liefert Ligninsulfonate als Nebenprodukt.", "answer": "b"},
         {"statement": "Liefert besonders festen Kraftzellstoff.", "answer": "a"},
     ]},
    {"id": "thermo-duroplast", "module": "organic", "teil": "Polymerchemie",
     "a": "Thermoplast", "b": "Duroplast",
     "explain": "Thermoplaste sind unvernetzt, schmelzbar und umformbar. Duroplaste sind engmaschig "
                "vernetzt, nicht schmelzbar und formstabil.",
     "items": [
         {"statement": "Wird beim Erwärmen weich und ist wieder umformbar.", "answer": "a"},
         {"statement": "Engmaschig vernetzt, zersetzt sich beim Erhitzen statt zu schmelzen.", "answer": "b"},
         {"statement": "Kann aufgeschmolzen und recycelt werden.", "answer": "a"},
     ]},
    {"id": "polymerisation-kondensation", "module": "organic", "teil": "Polymerchemie",
     "a": "Polymerisation", "b": "Polykondensation",
     "explain": "Polymerisation: Kettenwachstum über C=C-Doppelbindungen, ohne Abspaltung. "
                "Polykondensation: Verknüpfung unter Abspaltung kleiner Moleküle (z. B. Wasser).",
     "items": [
         {"statement": "Kettenwachstum über Doppelbindungen, kein Nebenprodukt abgespalten.", "answer": "a"},
         {"statement": "Verknüpfung unter Abspaltung von Wasser (z. B. bei PET).", "answer": "b"},
         {"statement": "Bildung von Polyethylen aus Ethen.", "answer": "a"},
     ]},
    # --- Anorganische Chemie ---
    {"id": "exo-endotherm", "module": "inorganic", "teil": "Grundlagen und Rohstoffe",
     "a": "exotherm", "b": "endotherm",
     "explain": "Exotherm gibt Energie an die Umgebung ab (ΔH < 0), endotherm nimmt Energie auf (ΔH > 0).",
     "items": [
         {"statement": "Reaktion gibt Wärme an die Umgebung ab (ΔH < 0).", "answer": "a"},
         {"statement": "Reaktion nimmt Energie auf, Umgebung kühlt ab (ΔH > 0).", "answer": "b"},
         {"statement": "Kalklöschen (CaO + H₂O) – wird sehr heiß.", "answer": "a"},
         {"statement": "Kalkbrennen (CaCO₃ → CaO + CO₂) – braucht ständige Wärmezufuhr.", "answer": "b"},
     ]},
    {"id": "oxidation-reduktion", "module": "inorganic", "teil": "Metallurgie",
     "a": "Oxidation", "b": "Reduktion",
     "explain": "Oxidation = Elektronenabgabe (Oxidationszahl steigt). Reduktion = Elektronenaufnahme (sinkt).",
     "items": [
         {"statement": "Elektronenabgabe, die Oxidationszahl steigt.", "answer": "a"},
         {"statement": "Elektronenaufnahme, die Oxidationszahl sinkt.", "answer": "b"},
         {"statement": "Fe₂O₃ + CO: Was passiert mit dem Eisen?", "answer": "b"},
     ]},
    {"id": "anode-kathode", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "a": "Anode", "b": "Kathode",
     "explain": "An der Anode läuft die Oxidation ab, an der Kathode die Reduktion.",
     "items": [
         {"statement": "Hier läuft die Oxidation ab.", "answer": "a"},
         {"statement": "Hier läuft die Reduktion ab.", "answer": "b"},
         {"statement": "Chloralkali-Elektrolyse: Wo entsteht Chlor?", "answer": "a"},
         {"statement": "Chloralkali-Elektrolyse: Wo entstehen Wasserstoff und Natronlauge?", "answer": "b"},
     ]},
    {"id": "branntkalk-loeschkalk", "module": "inorganic", "teil": "Werkstoffe und Bindemittel",
     "a": "Branntkalk (CaO)", "b": "Löschkalk (Ca(OH)₂)",
     "explain": "Branntkalk CaO entsteht beim Kalkbrennen; mit Wasser entsteht daraus Löschkalk Ca(OH)₂.",
     "items": [
         {"statement": "Entsteht direkt beim Brennen von Kalkstein (CaCO₃).", "answer": "a"},
         {"statement": "Entsteht aus CaO durch Zugabe von Wasser.", "answer": "b"},
         {"statement": "Formel CaO.", "answer": "a"},
         {"statement": "Formel Ca(OH)₂.", "answer": "b"},
     ]},
    {"id": "haber-ostwald", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "a": "Haber-Bosch", "b": "Ostwald",
     "explain": "Haber-Bosch synthetisiert Ammoniak (N₂ + H₂). Ostwald verbrennt Ammoniak weiter zu Salpetersäure.",
     "items": [
         {"statement": "Synthese von Ammoniak aus N₂ und H₂.", "answer": "a"},
         {"statement": "Katalytische Verbrennung von Ammoniak zu NO (Weg zur Salpetersäure).", "answer": "b"},
         {"statement": "Nutzt einen Eisen-Katalysator bei hohem Druck.", "answer": "a"},
         {"statement": "Nutzt ein Platin/Rhodium-Netz.", "answer": "b"},
     ]},
    {"id": "roheisen-stahl", "module": "inorganic", "teil": "Metallurgie",
     "a": "Roheisen", "b": "Stahl",
     "explain": "Roheisen (aus dem Hochofen) ist kohlenstoffreich und spröde. Stahl entsteht durch Senken des "
                "C-Gehalts (Frischen) und ist schmiedbar.",
     "items": [
         {"statement": "Kommt direkt aus dem Hochofen, hoher Kohlenstoffgehalt, spröde.", "answer": "a"},
         {"statement": "Entsteht durch Frischen (Senken des C-Gehalts), ist schmiedbar.", "answer": "b"},
         {"statement": "Wird im Konverter mit Sauerstoff behandelt.", "answer": "b"},
     ]},
]

_flat: list[dict] = []
ITEMS_BY_ID: dict[str, dict] = {}
for _g in CONFUSIONS:
    for _it in _g["items"]:
        _id = hashlib.sha1(f"{_g['id']}|{_it['statement']}".encode("utf-8")).hexdigest()[:10]
        _rec = {
            "item_id": _id, "group": _g["id"], "module": _g["module"], "teil": _g["teil"],
            "statement": _it["statement"], "answer": _it["answer"],
            "a": _g["a"], "b": _g["b"], "explain": _g.get("explain", ""),
        }
        _flat.append(_rec)
        ITEMS_BY_ID[_id] = _rec


def public_list(module: str) -> list[dict]:
    """Fragen fuers Ueben - je Aussage die zwei Begriffe (Reihenfolge gemischt), OHNE Antwort."""
    out = []
    for rec in _flat:
        if rec["module"] != module:
            continue
        opts = [{"key": "a", "label": rec["a"]}, {"key": "b", "label": rec["b"]}]
        random.shuffle(opts)
        out.append({
            "item_id": rec["item_id"], "teil": rec["teil"],
            "statement": rec["statement"], "options": opts,
        })
    random.shuffle(out)
    return out


def check(item_id: str, choice: str) -> dict | None:
    rec = ITEMS_BY_ID.get(item_id)
    if not rec:
        return None
    correct = choice == rec["answer"]
    return {
        "correct": correct,
        "correct_key": rec["answer"],
        "correct_label": rec["a"] if rec["answer"] == "a" else rec["b"],
        "explain": rec["explain"],
    }
