"""Reaktions-/Gleichungstrainer: kuratierte Industrieprozesse + regelbasierte Pruefung.

Der Nutzer schreibt eine Reaktionsgleichung; wir vergleichen die Mengen der Edukte
und Produkte gegen die Referenz. Koeffizienten/Zustandssymbole/Pfeilvarianten werden
normalisiert; verglichen wird die Spezies-Menge (nicht die exakte Schreibweise).
"""
from __future__ import annotations

import re


# Jede Reaktion: benannter Prozess (Prompt) + Edukte/Produkte als Spezies-Listen.
# teil = Pruefungsblock (passt zu _exam_block in main.py).
REACTIONS = [
    # --- Anorganische Chemie ---
    {"id": "haber-bosch", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Haber-Bosch-Synthese (Ammoniak)",
     "equation": "N₂ + 3 H₂ → 2 NH₃",
     "educts": ["N2", "H2"], "products": ["NH3"],
     "conditions": "Fe-Katalysator, ~200–300 bar, ~450 °C",
     "hint": "Stickstoff und Wasserstoff zu Ammoniak."},
    {"id": "ostwald", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Ostwald-Verfahren (Ammoniak-Verbrennung)",
     "equation": "4 NH₃ + 5 O₂ → 4 NO + 6 H₂O",
     "educts": ["NH3", "O2"], "products": ["NO", "H2O"],
     "conditions": "Pt/Rh-Netz, ~900 °C",
     "hint": "Katalytische Oxidation von Ammoniak zu Stickstoffmonoxid."},
    {"id": "no-oxidation", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Oxidation von NO zu NO₂",
     "equation": "2 NO + O₂ → 2 NO₂",
     "educts": ["NO", "O2"], "products": ["NO2"],
     "conditions": "Abkühlen",
     "hint": "Weiterer Schritt der Salpetersäure-Herstellung."},
    {"id": "hno3-bildung", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Salpetersäure aus NO₂ (Disproportionierung)",
     "equation": "3 NO₂ + H₂O → 2 HNO₃ + NO",
     "educts": ["NO2", "H2O"], "products": ["HNO3", "NO"],
     "conditions": "Absorption in Wasser",
     "hint": "NO wird rückgeführt."},
    {"id": "kontakt-so3", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Kontaktverfahren: SO₂ zu SO₃",
     "equation": "2 SO₂ + O₂ → 2 SO₃",
     "educts": ["SO2", "O2"], "products": ["SO3"],
     "conditions": "V₂O₅-Katalysator, ~450 °C",
     "hint": "Schlüsselschritt der Schwefelsäure-Produktion."},
    {"id": "so3-h2so4", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Schwefelsäure aus SO₃",
     "equation": "SO₃ + H₂O → H₂SO₄",
     "educts": ["SO3", "H2O"], "products": ["H2SO4"],
     "conditions": "technisch über Oleum",
     "hint": "Formal Anlagerung von Wasser an SO₃."},
    {"id": "claus", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Claus-Prozess (Schwefelrückgewinnung)",
     "equation": "2 H₂S + SO₂ → 3 S + 2 H₂O",
     "educts": ["H2S", "SO2"], "products": ["S", "H2O"],
     "conditions": "Bauxit-/Al₂O₃-Katalysator",
     "hint": "Elementarer Schwefel aus H₂S und SO₂."},
    {"id": "chloralkali", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Chloralkali-Elektrolyse",
     "equation": "2 NaCl + 2 H₂O → 2 NaOH + H₂ + Cl₂",
     "educts": ["NaCl", "H2O"], "products": ["NaOH", "H2", "Cl2"],
     "conditions": "Membranverfahren, elektrolytisch",
     "hint": "Liefert Natronlauge, Wasserstoff und Chlor."},
    {"id": "soda-zersetzung", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Soda aus Natriumhydrogencarbonat (Solvay)",
     "equation": "2 NaHCO₃ → Na₂CO₃ + H₂O + CO₂",
     "educts": ["NaHCO3"], "products": ["Na2CO3", "H2O", "CO2"],
     "conditions": "Kalzinieren (Erhitzen)",
     "hint": "Thermische Zersetzung zu Soda."},
    {"id": "hochofen", "module": "inorganic", "teil": "Metallurgie",
     "name": "Hochofen: Reduktion von Eisenoxid mit CO",
     "equation": "Fe₂O₃ + 3 CO → 2 Fe + 3 CO₂",
     "educts": ["Fe2O3", "CO"], "products": ["Fe", "CO2"],
     "conditions": "indirekte Reduktion",
     "hint": "Kohlenstoffmonoxid als Reduktionsmittel."},
    {"id": "boudouard", "module": "inorganic", "teil": "Metallurgie",
     "name": "Boudouard-Gleichgewicht",
     "equation": "C + CO₂ → 2 CO",
     "educts": ["C", "CO2"], "products": ["CO"],
     "conditions": "hohe Temperatur begünstigt CO",
     "hint": "Bildung des Reduktionsmittels im Hochofen."},
    {"id": "thermit", "module": "inorganic", "teil": "Metallurgie",
     "name": "Thermit-Reaktion (Aluminothermie)",
     "equation": "2 Al + Fe₂O₃ → 2 Fe + Al₂O₃",
     "educts": ["Al", "Fe2O3"], "products": ["Fe", "Al2O3"],
     "conditions": "stark exotherm",
     "hint": "Aluminium reduziert Eisenoxid."},
    {"id": "al-elektrolyse", "module": "inorganic", "teil": "Metallurgie",
     "name": "Schmelzflusselektrolyse von Aluminiumoxid",
     "equation": "2 Al₂O₃ → 4 Al + 3 O₂",
     "educts": ["Al2O3"], "products": ["Al", "O2"],
     "conditions": "in Kryolith gelöst, elektrolytisch",
     "hint": "Aluminiumgewinnung aus Tonerde."},
    {"id": "roesten-zns", "module": "inorganic", "teil": "Metallurgie",
     "name": "Rösten von Zinkblende",
     "equation": "2 ZnS + 3 O₂ → 2 ZnO + 2 SO₂",
     "educts": ["ZnS", "O2"], "products": ["ZnO", "SO2"],
     "conditions": "Rösten an Luft",
     "hint": "Sulfid zu Oxid, SO₂ wird verwertet."},
    {"id": "kalkbrennen", "module": "inorganic", "teil": "Werkstoffe und Bindemittel",
     "name": "Kalkbrennen (Branntkalk)",
     "equation": "CaCO₃ → CaO + CO₂",
     "educts": ["CaCO3"], "products": ["CaO", "CO2"],
     "conditions": "~900 °C",
     "hint": "Thermische Zersetzung von Kalkstein."},
    {"id": "kalkloeschen", "module": "inorganic", "teil": "Werkstoffe und Bindemittel",
     "name": "Kalklöschen (Löschkalk)",
     "equation": "CaO + H₂O → Ca(OH)₂",
     "educts": ["CaO", "H2O"], "products": ["Ca(OH)2"],
     "conditions": "stark exotherm",
     "hint": "Branntkalk plus Wasser."},
    {"id": "rge-kalk", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Rauchgasentschwefelung mit Kalk",
     "equation": "CaCO₃ + SO₂ + ½ O₂ → CaSO₄ + CO₂",
     "educts": ["CaCO3", "SO2", "O2"], "products": ["CaSO4", "CO2"],
     "conditions": "Produkt: Gips",
     "hint": "Bindet SO₂ als Calciumsulfat."},
    # --- Organische Technologie ---
    {"id": "dampfreformierung", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Dampfreformierung von Methan",
     "equation": "CH₄ + H₂O → CO + 3 H₂",
     "educts": ["CH4", "H2O"], "products": ["CO", "H2"],
     "conditions": "Ni-Katalysator, ~800 °C",
     "hint": "Synthesegas aus Erdgas."},
    {"id": "wassergas-shift", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Wassergas-Shift-Reaktion",
     "equation": "CO + H₂O → CO₂ + H₂",
     "educts": ["CO", "H2O"], "products": ["CO2", "H2"],
     "conditions": "erhöht die H₂-Ausbeute",
     "hint": "Verschiebt CO zu CO₂ und Wasserstoff."},
    {"id": "methanolsynthese", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Methanolsynthese aus Synthesegas",
     "equation": "CO + 2 H₂ → CH₃OH",
     "educts": ["CO", "H2"], "products": ["CH3OH"],
     "conditions": "Cu/ZnO-Katalysator, Druck",
     "hint": "Aus Kohlenstoffmonoxid und Wasserstoff."},
    {"id": "carbid-acetylen", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Acetylen aus Calciumcarbid",
     "equation": "CaC₂ + 2 H₂O → C₂H₂ + Ca(OH)₂",
     "educts": ["CaC2", "H2O"], "products": ["C2H2", "Ca(OH)2"],
     "conditions": "historischer Weg zu Ethin",
     "hint": "Carbid plus Wasser ergibt Ethin."},
    {"id": "methanol-formaldehyd", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "name": "Formaldehyd aus Methanol (Oxidation)",
     "equation": "2 CH₃OH + O₂ → 2 HCHO + 2 H₂O",
     "educts": ["CH3OH", "O2"], "products": ["HCHO", "H2O"],
     "conditions": "Silber-Katalysator",
     "hint": "Partielle Oxidation von Methanol."},
]

REACTIONS_BY_ID = {r["id"]: r for r in REACTIONS}

_SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_ARROW_RE = re.compile(r"→|⟶|⇌|⇋|<=>|<->|-->|->|=>|=")
_STATE_RE = re.compile(r"\((?:g|l|s|aq|fl|gasf|fest|solv)\)", re.IGNORECASE)
_LEADING_COEFF_RE = re.compile(r"^\s*(?:\d+\s*/\s*\d+|\d+[.,]?\d*|½|¼|¾)\s*")


def normalize_species(token: str) -> str:
    """Eine Spezies auf eine vergleichbare Form bringen (ohne Koeffizient/Zustand/Leerzeichen)."""
    s = token.translate(_SUBSCRIPT).strip()
    s = _STATE_RE.sub("", s)
    s = _LEADING_COEFF_RE.sub("", s)
    s = s.replace(" ", "").replace("·", "").strip()
    # Multiplikationszeichen / mittelstrich-varianten vereinheitlichen
    s = s.replace("−", "-")
    return s.lower()


def parse_equation(text: str):
    """(edukt_menge, produkt_menge) als Frozensets normalisierter Spezies, oder None bei Formfehler."""
    if not text or not _ARROW_RE.search(text):
        return None
    parts = _ARROW_RE.split(text, maxsplit=1)
    if len(parts) != 2:
        return None
    def side(chunk):
        out = set()
        for tok in chunk.split("+"):
            sp = normalize_species(tok)
            if sp:
                out.add(sp)
        return frozenset(out)
    return side(parts[0]), side(parts[1])


def check(reaction: dict, user_input: str) -> dict:
    """Vergleicht die Nutzereingabe gegen die Referenz-Reaktion."""
    ref_ed_map = {normalize_species(s): s for s in reaction["educts"]}
    ref_pr_map = {normalize_species(s): s for s in reaction["products"]}
    ref_ed = frozenset(ref_ed_map)
    ref_pr = frozenset(ref_pr_map)
    parsed = parse_equation(user_input or "")
    if parsed is None:
        return {
            "ok": False, "correct": False, "form_error": True,
            "message": "Bitte eine Gleichung mit einem Reaktionspfeil (→ oder ->) eingeben.",
            "reference": reaction["equation"],
        }
    u_ed, u_pr = parsed
    ed_ok = u_ed == ref_ed
    pr_ok = u_pr == ref_pr
    correct = ed_ok and pr_ok
    return {
        "ok": True,
        "correct": correct,
        "educts_ok": ed_ok,
        "products_ok": pr_ok,
        "missing_educts": [ref_ed_map[s] for s in sorted(ref_ed - u_ed)],
        "extra_educts": sorted(u_ed - ref_ed),
        "missing_products": [ref_pr_map[s] for s in sorted(ref_pr - u_pr)],
        "extra_products": sorted(u_pr - ref_pr),
        "reference": reaction["equation"],
        "conditions": reaction.get("conditions", ""),
    }


def public_list(module: str) -> list[dict]:
    """Reaktionen fuer die Uebung - OHNE Loesung (Edukte/Produkte werden nicht mitgeliefert)."""
    return [
        {"id": r["id"], "module": r["module"], "teil": r["teil"],
         "name": r["name"], "conditions": r.get("conditions", ""), "hint": r.get("hint", "")}
        for r in REACTIONS if r["module"] == module
    ]
