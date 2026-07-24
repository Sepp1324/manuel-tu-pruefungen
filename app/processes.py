"""Prozess-Schema-Trainer: benannte Industrieprozesse, deren Schritte in die
richtige Reihenfolge gebracht werden muessen.

Die Schritte werden dem Client GEMISCHT und mit stabilen, nicht die Reihenfolge
verratenden IDs (Hash) ausgeliefert; die korrekte Reihenfolge bleibt serverseitig.
"""
from __future__ import annotations

import hashlib
import random


# Jeder Prozess: benannter Ablauf + Schritte in KORREKTER Reihenfolge.
# teil = Pruefungsblock (passt zu _exam_block in main.py).
PROCESSES = [
    {"id": "kontaktverfahren", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Kontaktverfahren (Schwefelsäure)",
     "note": "Von Schwefel zu H₂SO₄.",
     "steps": [
         "Schwefel bzw. Schwefelkies zu SO₂ verbrennen",
         "SO₂-Gas reinigen und trocknen",
         "Katalytische Oxidation SO₂ → SO₃ am V₂O₅-Kontakt",
         "SO₃ in konzentrierter Schwefelsäure absorbieren (Oleum)",
         "Oleum mit Wasser zu Schwefelsäure verdünnen",
     ]},
    {"id": "ostwald", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Ostwald-Verfahren (Salpetersäure)",
     "note": "Von Ammoniak zu HNO₃.",
     "steps": [
         "Ammoniak katalytisch zu NO verbrennen (Pt/Rh-Netz)",
         "NO mit Luftsauerstoff zu NO₂ oxidieren (abkühlen)",
         "NO₂ in Wasser absorbieren → Salpetersäure",
         "Entstehendes NO in den Prozess zurückführen",
     ]},
    {"id": "solvay", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Solvay-Verfahren (Soda)",
     "note": "Ammoniak-Soda-Prozess.",
     "steps": [
         "NaCl-Sole mit Ammoniak sättigen",
         "CO₂ einleiten → schwerlösliches NaHCO₃ fällt aus",
         "NaHCO₃ abfiltrieren",
         "NaHCO₃ kalzinieren → Na₂CO₃ (Soda)",
         "Ammoniak aus der Mutterlauge zurückgewinnen",
     ]},
    {"id": "hochofen", "module": "inorganic", "teil": "Metallurgie",
     "name": "Hochofenprozess (Roheisen)",
     "note": "Reduktion von Eisenerz.",
     "steps": [
         "Möller (Erz, Koks, Zuschlag) von oben chargieren",
         "Heißwind einblasen → Koks verbrennt zu CO",
         "CO reduziert die Eisenoxide zu Eisen",
         "Gangart mit dem Zuschlag zu Schlacke verschmelzen",
         "Roheisen und Schlacke getrennt abstechen",
     ]},
    {"id": "chloralkali", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Chloralkali-Elektrolyse (Membranverfahren)",
     "note": "NaCl-Sole elektrolysieren.",
     "steps": [
         "NaCl-Sole reinigen (Ca²⁺/Mg²⁺ entfernen)",
         "Sole in die Membranzelle leiten und Spannung anlegen",
         "An der Anode entsteht Chlor",
         "An der Kathode entstehen Wasserstoff und Natronlauge",
         "Produkte trennen und aufkonzentrieren",
     ]},
    {"id": "aluminium", "module": "inorganic", "teil": "Metallurgie",
     "name": "Aluminiumgewinnung (Bayer + Schmelzflusselektrolyse)",
     "note": "Von Bauxit zu Aluminium.",
     "steps": [
         "Bauxit mit Natronlauge aufschließen (Bayer-Prozess)",
         "Al(OH)₃ ausfällen und abtrennen",
         "Al(OH)₃ zu reinem Al₂O₃ kalzinieren",
         "Al₂O₃ in geschmolzenem Kryolith lösen",
         "Schmelzflusselektrolyse → flüssiges Aluminium",
     ]},
    {"id": "kraftverfahren", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "name": "Sulfat-/Kraftverfahren (Zellstoff)",
     "note": "Chemischer Holzaufschluss mit Chemikalienrückgewinnung.",
     "steps": [
         "Holz zu Hackschnitzeln zerkleinern",
         "Mit Weißlauge (NaOH + Na₂S) kochen → Lignin herauslösen",
         "Zellstofffasern von der Schwarzlauge trennen",
         "Schwarzlauge eindampfen und verbrennen (Energie + Schmelze)",
         "Chemikalien zurückgewinnen: Grünlauge → Kaustifizieren → Weißlauge",
     ]},
    {"id": "steamcracking", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Steamcracking (Olefine)",
     "note": "Thermische Spaltung zu Ethen/Propen.",
     "steps": [
         "Naphtha oder Gasöl mit Wasserdampf mischen",
         "Im Röhrenofen sehr kurz stark erhitzen (~850 °C)",
         "Produktgemisch sofort abschrecken (Quench)",
         "Gemisch durch Destillation auftrennen",
         "Ethen und Propen als Hauptprodukte abtrennen",
     ]},
    {"id": "raffinerie", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Erdölraffinerie (Grundschema)",
     "note": "Vom Rohöl zu Produkten.",
     "steps": [
         "Rohöl entsalzen und vorwärmen",
         "Atmosphärische Destillation in Fraktionen trennen",
         "Schweren Rückstand im Vakuum weiter destillieren",
         "Konversion: Cracken/Reforming schwerer Fraktionen",
         "Produkte veredeln und zu Endprodukten blenden",
     ]},
]

PROCESSES_BY_ID = {p["id"]: p for p in PROCESSES}


def _sid(process_id: str, text: str) -> str:
    """Stabile, die Reihenfolge NICHT verratende Schritt-ID."""
    return hashlib.sha1(f"{process_id}|{text}".encode("utf-8")).hexdigest()[:10]


def correct_order(process: dict) -> list[str]:
    return [_sid(process["id"], s) for s in process["steps"]]


def shuffled_steps(process: dict) -> list[dict]:
    steps = [{"sid": _sid(process["id"], s), "text": s} for s in process["steps"]]
    order = correct_order(process)
    # So lange mischen, bis die Reihenfolge nicht zufaellig schon korrekt ist
    for _ in range(8):
        random.shuffle(steps)
        if [s["sid"] for s in steps] != order or len(steps) <= 1:
            break
    return steps


def public_list(module: str) -> list[dict]:
    """Prozesse fuers Ueben - Schritte gemischt, korrekte Reihenfolge NICHT enthalten."""
    return [
        {"id": p["id"], "module": p["module"], "teil": p["teil"], "name": p["name"],
         "note": p.get("note", ""), "steps": shuffled_steps(p)}
        for p in PROCESSES if p["module"] == module
    ]


def check(process: dict, order: list[str]) -> dict:
    """Vergleicht die vom Nutzer gewaehlte Reihenfolge (Liste von sids) mit der korrekten."""
    correct = correct_order(process)
    order = list(order or [])
    positions_ok = [i < len(order) and order[i] == correct[i] for i in range(len(correct))]
    all_ok = order == correct
    return {
        "correct": all_ok,
        "positions_ok": positions_ok,
        "correct_steps": process["steps"],  # in richtiger Reihenfolge (nach dem Pruefen zeigen)
        "n_correct": sum(1 for ok in positions_ok if ok),
        "n_total": len(correct),
        "name": process["name"],
    }
