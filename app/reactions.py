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

    # --- Ergaenzungen: Fossile Rohstoffe / Raffinerie ---
    {"id": "methan-verbrennung", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Vollstaendige Verbrennung von Methan",
     "equation": "CH₄ + 2 O₂ → CO₂ + 2 H₂O",
     "educts": ["CH4", "O2"], "products": ["CO2", "H2O"],
     "conditions": "stark exotherm", "hint": "Methan mit Sauerstoff."},
    {"id": "kohlevergasung-wassergas", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Kohlevergasung (Wassergas-Reaktion)",
     "equation": "C + H₂O → CO + H₂",
     "educts": ["C", "H2O"], "products": ["CO", "H2"],
     "conditions": "endotherm, ~1000 °C", "hint": "Gluehender Kohlenstoff + Wasserdampf."},
    {"id": "boudouard-c", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Boudouard-Reaktion (Kohlevergasung)",
     "equation": "C + CO₂ → 2 CO",
     "educts": ["C", "CO2"], "products": ["CO"],
     "conditions": "endotherm, hohe Temperatur", "hint": "Kohlenstoff + Kohlendioxid."},
    {"id": "methanisierung", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Methanisierung (SNG aus Synthesegas)",
     "equation": "CO + 3 H₂ → CH₄ + H₂O",
     "educts": ["CO", "H2"], "products": ["CH4", "H2O"],
     "conditions": "Ni-Katalysator", "hint": "Synthetisches Erdgas aus CO und H₂."},
    {"id": "steamcracking-ethan", "module": "organic", "teil": "Fossile Rohstoffe und Raffinerie",
     "name": "Steamcracking von Ethan zu Ethen",
     "equation": "C₂H₆ → C₂H₄ + H₂",
     "educts": ["C2H6"], "products": ["C2H4", "H2"],
     "conditions": "~850 °C, Wasserdampf", "hint": "Dehydrierung/Cracken zum Olefin."},

    # --- Ergaenzungen: Nachwachsende Rohstoffe ---
    {"id": "alkoholische-gaerung", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "name": "Alkoholische Gaerung von Glucose",
     "equation": "C₆H₁₂O₆ → 2 C₂H₅OH + 2 CO₂",
     "educts": ["C6H12O6"], "products": ["C2H5OH", "CO2"],
     "conditions": "Hefe/Zymase, anaerob", "hint": "Zucker zu Ethanol und Kohlendioxid."},
    {"id": "photosynthese", "module": "organic", "teil": "Nachwachsende Rohstoffe",
     "name": "Photosynthese (Bruttogleichung)",
     "equation": "6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂",
     "educts": ["CO2", "H2O"], "products": ["C6H12O6", "O2"],
     "conditions": "Licht, Chlorophyll", "hint": "Aufbau von Glucose aus CO₂ und Wasser."},

    # --- Ergaenzungen: Polymerchemie (Monomer-Route PVC) ---
    {"id": "ethen-chlorierung", "module": "organic", "teil": "Polymerchemie",
     "name": "1,2-Dichlorethan aus Ethen (PVC-Route)",
     "equation": "C₂H₄ + Cl₂ → C₂H₄Cl₂",
     "educts": ["C2H4", "Cl2"], "products": ["C2H4Cl2"],
     "conditions": "FeCl₃-Katalysator", "hint": "Addition von Chlor an Ethen."},
    {"id": "vcm-pyrolyse", "module": "organic", "teil": "Polymerchemie",
     "name": "Vinylchlorid (VCM) aus 1,2-Dichlorethan",
     "equation": "C₂H₄Cl₂ → C₂H₃Cl + HCl",
     "educts": ["C2H4Cl2"], "products": ["C2H3Cl", "HCl"],
     "conditions": "Pyrolyse ~500 °C", "hint": "HCl-Abspaltung zum PVC-Monomer."},

    # --- Ergaenzungen: Metallurgie (Hochofen-Stufenreduktion, Roesten) ---
    {"id": "hochofen-stufe1", "module": "inorganic", "teil": "Metallurgie",
     "name": "Hochofen: Reduktion Haematit zu Magnetit",
     "equation": "3 Fe₂O₃ + CO → 2 Fe₃O₄ + CO₂",
     "educts": ["Fe2O3", "CO"], "products": ["Fe3O4", "CO2"],
     "conditions": "indirekte Reduktion, ~500 °C", "hint": "Erste Stufe der CO-Reduktion."},
    {"id": "hochofen-stufe2", "module": "inorganic", "teil": "Metallurgie",
     "name": "Hochofen: Magnetit zu Wuestit",
     "equation": "Fe₃O₄ + CO → 3 FeO + CO₂",
     "educts": ["Fe3O4", "CO"], "products": ["FeO", "CO2"],
     "conditions": "indirekte Reduktion", "hint": "Zweite Stufe der CO-Reduktion."},
    {"id": "hochofen-stufe3", "module": "inorganic", "teil": "Metallurgie",
     "name": "Hochofen: Wuestit zu Eisen",
     "equation": "FeO + CO → Fe + CO₂",
     "educts": ["FeO", "CO"], "products": ["Fe", "CO2"],
     "conditions": "indirekte Reduktion", "hint": "Dritte Stufe zu metallischem Eisen."},
    {"id": "koks-verbrennung-co2", "module": "inorganic", "teil": "Metallurgie",
     "name": "Koksverbrennung vor den Duesen",
     "equation": "C + O₂ → CO₂",
     "educts": ["C", "O2"], "products": ["CO2"],
     "conditions": "liefert Prozesswaerme", "hint": "Vollstaendige Verbrennung des Kokses."},
    {"id": "schlackenbildung", "module": "inorganic", "teil": "Metallurgie",
     "name": "Schlackenbildung im Hochofen",
     "equation": "CaO + SiO₂ → CaSiO₃",
     "educts": ["CaO", "SiO2"], "products": ["CaSiO3"],
     "conditions": "Kalk bindet die Gangart", "hint": "Calciumoxid + Kieselsaeure zu Silikat-Schlacke."},
    {"id": "pyrit-roesten", "module": "inorganic", "teil": "Metallurgie",
     "name": "Roesten von Pyrit (Schwefelkies)",
     "equation": "4 FeS₂ + 11 O₂ → 2 Fe₂O₃ + 8 SO₂",
     "educts": ["FeS2", "O2"], "products": ["Fe2O3", "SO2"],
     "conditions": "oxidierendes Roesten", "hint": "Sulfid zu Oxid, SO₂ frei."},
    {"id": "kupfer-reaktionsarbeit", "module": "inorganic", "teil": "Metallurgie",
     "name": "Kupfererzeugung (Reaktionsarbeit im Konverter)",
     "equation": "Cu₂S + O₂ → 2 Cu + SO₂",
     "educts": ["Cu2S", "O2"], "products": ["Cu", "SO2"],
     "conditions": "Peirce-Smith-Konverter", "hint": "Kupferstein zu Rohkupfer."},

    # --- Ergaenzungen: Anorganische Grosschemie ---
    {"id": "harnstoffsynthese", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Harnstoffsynthese (aus Ammoniak und CO₂)",
     "equation": "2 NH₃ + CO₂ → CO(NH₂)₂ + H₂O",
     "educts": ["NH3", "CO2"], "products": ["CO(NH2)2", "H2O"],
     "conditions": "Hochdruck, ueber Ammoniumcarbamat", "hint": "Wichtigster Stickstoffduenger."},
    {"id": "hcl-synthese", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Chlorwasserstoff-Synthese",
     "equation": "H₂ + Cl₂ → 2 HCl",
     "educts": ["H2", "Cl2"], "products": ["HCl"],
     "conditions": "Chlorknallgas, exotherm", "hint": "Aus den Elektrolyse-Produkten H₂ und Cl₂."},
    {"id": "schwefel-verbrennung", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Schwefelverbrennung (SO₂-Erzeugung)",
     "equation": "S + O₂ → SO₂",
     "educts": ["S", "O2"], "products": ["SO2"],
     "conditions": "Start der Schwefelsaeure-Kette", "hint": "Elementarer Schwefel zu SO₂."},
    {"id": "solvay-faellung", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Solvay: Faellung von Natriumhydrogencarbonat",
     "equation": "NaCl + NH₃ + CO₂ + H₂O → NaHCO₃ + NH₄Cl",
     "educts": ["NaCl", "NH3", "CO2", "H2O"], "products": ["NaHCO3", "NH4Cl"],
     "conditions": "in Ammoniaksole", "hint": "Schwerloesliches NaHCO₃ faellt aus."},
    {"id": "frank-caro", "module": "inorganic", "teil": "Anorganische Grosschemie",
     "name": "Frank-Caro-Prozess (Kalkstickstoff)",
     "equation": "CaC₂ + N₂ → CaCN₂ + C",
     "educts": ["CaC2", "N2"], "products": ["CaCN2", "C"],
     "conditions": "~1000 °C", "hint": "Historische Stickstoff-Fixierung."},

    # --- Ergaenzungen: Werkstoffe und Bindemittel ---
    {"id": "alit-bildung", "module": "inorganic", "teil": "Werkstoffe und Bindemittel",
     "name": "Klinkerphase Alit (C₃S) beim Zementbrand",
     "equation": "3 CaO + SiO₂ → Ca₃SiO₅",
     "educts": ["CaO", "SiO2"], "products": ["Ca3SiO5"],
     "conditions": "Sinterzone ~1450 °C", "hint": "Wichtigste festigkeitsbildende Klinkerphase."},
    {"id": "glas-natriumsilikat", "module": "inorganic", "teil": "Werkstoffe und Bindemittel",
     "name": "Glasschmelze: Natriumsilikat-Bildung",
     "equation": "Na₂CO₃ + SiO₂ → Na₂SiO₃ + CO₂",
     "educts": ["Na2CO3", "SiO2"], "products": ["Na2SiO3", "CO2"],
     "conditions": "Soda als Flussmittel", "hint": "CO₂ entweicht beim Aufschmelzen."},
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
