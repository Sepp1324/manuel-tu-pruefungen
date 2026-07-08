from __future__ import annotations

import json
import re
from pathlib import Path

from contextualize_seed_cards import strip_answer_context, strip_question_context


REPO = Path(__file__).resolve().parents[1]
SEED_PATH = REPO / "app" / "seed_data.json"

SOURCE_NOISE_RE = re.compile(
    r"(?i)\b(systematic review|meta-regression|doi:|trademark|trademarks|"
    r"company overview|company information|internal: confidential|global headquarters|"
    r"regional headquarters|corporate hubs|patent applications|workforce|"
    r"microsoft copilot|marktresearchfuture|guardian|kurier\.at|derstandard|"
    r"welt\.de|copyright|email:|web:|lv-evaluierung|tiss|"
    r"bildquellen?:|bildquelle|wikimedia commons)\b"
)
OCR_NOISE_RE = re.compile(
    r"(?i)\(cid:\d+\)|[\uf0b7\uf0fc\ufffd�]|"
    r"\b(?:elleuqdli\.?\s*b|elleuq|elleu\.\s*q|nelleu\.\s*q|snommo\.\s*c|"
    r"aidemiki\.\s*w|kehtoto\.\s*f|ehcstue\.\s*d)\b"
)
COMPANY_RE = re.compile(
    r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\s+(AG|GmbH|Inc|Ltd|LLC|International)\b"
)
AUTHOR_RE = re.compile(
    r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\s+[A-Z]\.?\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\b"
    r"|\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+,\s+"
    r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\b"
)
META_NOISE_RE = re.compile(
    r"(?i)\b(location|headquarters|corporate hub|source:|notes?:|"
    r"formed from three regional leaders|global organization|global polyolefins platform|"
    r"manufacturing sites|innovation centers|patents?)\b"
)
ANSWER_LINE_NOISE_RE = re.compile(
    r"(?i)\b("
    r"chem\.\s*tech\.|chemische technologie anorganische stoffe|"
    r"raquel\s+de\s+oro|r\.\s*de\s+oro|t\.\s*konegger|raumnummer|"
    r"seite\s+\d+|slide\s+\d+|allgemeine informationen|"
    r"164\.211|164\.221|inhalt unterteilt|lernziele?|"
    r"technologie zu beschreiben|verfahrensprinzipien und prozessbedingungen|"
    r"wichtige vorgaben|pruefungsrelevantes|prüfungsrelevantes|vorausschau|"
    r"regional\s+leaders|regional headquarters|global organization|"
    r"produkt\s+festes\s+eisen|hochofeninfrast|investitionskosten|"
    r"hauptvorteile|hauptnachteile|infrastrukturbedarf|"
    r"diaphragma-\s*amalgam-\s*membran|vorteile\s+anforderungen|"
    r"nachteile\s+geringe|soleaufbereitung|werkstoff\s+masse|"
    r"weltproduktion\s+verschiedener\s+werkstoffe|"
    r"hauptmerkmale\s+vorteile\s+nachteile|vorratsbunker|frischlanze|"
    r"einspulvorr|heizelektroden|verwendung\s+o\s+-?\s*einblasung|"
    r"kaum im einsatz"
    r")"
)
LECTURE_ADMIN_RE = re.compile(
    r"(?i)\b(vor-?\s*(?:&amp;|&|und)\s*nachbereitung|vorlesungseinheiten|"
    r"prüfungsbogen|pruefungsbogen|prüfungsbeginn|pruefungsbeginn|"
    r"prüfungsantritt|pruefungsantritt|angabezettel|antwortzettel|"
    r"abgabe am ende|zugewiesenen sitzplatz|digitale geräte|digitale geraete|"
    r"sammelort|anmeldeformalitäten|anmeldeformalitaeten|"
    r"positive absolvierung|mindestens 50% der punkte|vorlesungsteile|"
    r"raquel\s+de\s+oro|r\.\s*de\s+oro|raumnummer|allgemeine informationen|"
    r"chemische technologie anorganische stoffe|164\.211|164\.221|"
    r"inhalt unterteilt|lernziele?|technologie zu beschreiben|"
    r"verfahrensprinzipien und prozessbedingungen|wichtige vorgaben|"
    r"pruefungsrelevantes|prüfungsrelevantes|vorausschau)\b"
)
ENGLISH_NOISE_RE = re.compile(
    r"(?i)\b("
    r"take-home messages|if we look towards|technology and innovation|ownership of|"
    r"leading innovation|mechanical recycling|chemical recycling|plastics recycling paths|"
    r"dissolving wood pulp|paper pulp|challenge:|circular economy|open hearth furnace|"
    r"basic oxygen furnace|blast furnace|fluidized beds|global organization|"
    r"high-quality|food packaging|medical grades|external use|internal confidential|"
    r"cellulose fibers|degree of polymerization|down the rabbit-hole|"
    r"polyolefins player|assets supporting|would mean|are hydrolyzed|becomes solubilized|"
    r"oxygen depolarized cathode|gas hourly space velocity|phase diagrams|engl\.|"
    r"filtration/degassing|xanthation|dissolution|homogenization|spinning|"
    r"sulfuric acid|aftertreatment|exhaust air recovery|spinbath recovery|"
    r"deauration|wet spinning|"
    r"\b(the|and|with|from|which|between|company|headquarters|manufacturing|"
    r"ownership|innovation|includes|globally|supporting|reliable|supply|"
    r"subsequent|transferring|hydrolyzed|suspended|dissolved|dewatered)\b"
    r")"
)
DOMAIN_KEEP_RE = re.compile(
    r"(?i)\b(haber-bosch|ostwald|bleikammer|claus|solvay|downs|bayer|"
    r"hochofen|zement|ammoniak|salpetersäure|salpetersaeure|"
    r"schwefelsäure|schwefelsaeure|chloralkali|elektrolyse|"
    r"hydrotreatment|cracking|polymerisation|polykondensation)\b"
)


def plain(card: dict) -> str:
    q = strip_question_context(str(card.get("q", "")))
    a = strip_answer_context(str(card.get("a", "")))
    a = re.sub(r"<br><br><span class='source'>.*?</span>\s*$", "", a, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", f"{q} {a}")
    return re.sub(r"\s+", " ", text).strip()


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_answer_line(line: str) -> str:
    line = re.sub(r"\((?:engl\.|english)\s+[^)]*\)", "", line, flags=re.I)
    line = re.sub(r"(?i)\b(?:bildquellen?|bildquelle|quelle|quellen):?.*$", "", line)
    line = re.sub(r"(?i)\b(?:wikimedia commons|quelle\s*\(unbekannt\)).*$", "", line)
    line = re.sub(r"(?i)\b(?:haubner|hummel).*$", "", line)
    line = re.sub(r"(?i)\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß-]+(?:\s+und\s+[a-zäöüß.]+){0,2},\s*20\d{2},\s*p\d+\b.*$", "", line)
    line = re.sub(r"^\s*(?:[•▪◦‣■●]+\s*)+", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip(" -;:>")


def noisy_answer_line(line: str) -> bool:
    text = strip_html(clean_answer_line(line))
    if OCR_NOISE_RE.search(text):
        return True
    if ANSWER_LINE_NOISE_RE.search(text) or SOURCE_NOISE_RE.search(text) or ENGLISH_NOISE_RE.search(text):
        return True
    if text.count("/") >= 4 or text.count("|") > 0:
        return True
    if len(text) < 12:
        return True
    return False


def sanitize_answer(card: dict) -> dict | None:
    answer = str(card.get("a", ""))
    items = re.findall(r"<li>(.*?)</li>", answer, flags=re.S | re.I)
    if not items:
        return card
    kept = []
    for item in items:
        cleaned = clean_answer_line(item)
        if cleaned and not noisy_answer_line(cleaned):
            kept.append(cleaned)
    if len(kept) < 2:
        return None
    cleaned = re.sub(
        r"<ul>.*?</ul>",
        "<ul>" + "".join(f"<li>{item}</li>" for item in kept[:7]) + "</ul>",
        answer,
        count=1,
        flags=re.S | re.I,
    )
    out = dict(card)
    out["a"] = cleaned
    return out


def irrelevant(card: dict) -> bool:
    text = plain(card)
    question = strip_question_context(str(card.get("q", "")))
    lower = text.lower()
    if DOMAIN_KEEP_RE.search(text) and not (SOURCE_NOISE_RE.search(text) or LECTURE_ADMIN_RE.search(text)):
        return False
    if SOURCE_NOISE_RE.search(text):
        return True
    if OCR_NOISE_RE.search(text):
        return True
    if ANSWER_LINE_NOISE_RE.search(question):
        return True
    if ENGLISH_NOISE_RE.search(text):
        return True
    if COMPANY_RE.search(text):
        return True
    if AUTHOR_RE.search(text) and re.search(r"(?i)\b(review|meta-regression|study|journal|doi)\b", text):
        return True
    if META_NOISE_RE.search(text):
        return True
    if LECTURE_ADMIN_RE.search(text):
        return True
    if any(x in lower for x in ["generated by", "for external use"]):
        return True
    return False


def main() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    keep = []
    removed = []
    for card in payload.get("cards", []):
        if irrelevant(card):
            removed.append(card)
        else:
            sanitized = sanitize_answer(card)
            if sanitized is None or irrelevant(sanitized):
                removed.append(card)
            else:
                keep.append(sanitized)
    payload["cards"] = keep
    SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"removed {len(removed)} irrelevant cards, kept {len(keep)}")
    for card in removed[:30]:
        print(f"- {card.get('id')}: {plain(card)[:160]}")


if __name__ == "__main__":
    main()
