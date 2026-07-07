from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(os.environ.get("INORG_SOURCE_DIR", "/private/tmp/anorganik_sources_clean"))
SEED_PATH = REPO / "app" / "seed_data.json"
RAW_OUT = REPO / "app" / "source_text_index.json"

TARGET_CARDS = 760

CHAPTERS = {
    1: "Einheit 01 Einfuehrung",
    2: "Einheit 02 Rohstoffe",
    3: "Einheit 03 Einleitung Metallurgie",
    4: "Einheit 04 Tools der Metallurgie",
    5: "Einheit 05 Eisen und Stahl",
    6: "Einheit 06 Kupfer und Aluminium",
    7: "Einheit 07 Grosschemie Stickstoff",
    8: "Einheit 08 Grosschemie NaCl, Chlor, NaOH, Soda",
    9: "Einheit 09 Grosschemie Schwefel",
    10: "Einheit 10 Anorganische Bindemittel",
    11: "Einheit 11 Glas und Keramik",
}


@dataclass
class SourceText:
    path: Path
    chapter: int
    title: str
    text: str


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"([a-zäöüß])([A-ZÄÖÜ])", r"\1. \2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?i)chemische technologie[n]? anorganischer stoffe", "", text)
    text = re.sub(r"(?i)technische universitaet wien|technische universität wien|tu wien", "", text)
    text = re.sub(r"(?i)institut fuer chemische technologien|institut für chemische technologien", "", text)
    return text.strip()


def chapter_for(path: Path) -> int:
    m = re.search(r"Einheit[_\s-]+(\d{1,2})", path.name, re.I)
    if m:
        return max(1, min(int(m.group(1)), 11))
    return 11


def extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = clean_text(page.extract_text() or "")
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def load_sources() -> list[SourceText]:
    out: list[SourceText] = []
    for path in sorted(SOURCE_DIR.glob("*.pdf")):
        text = extract_pdf(path)
        if len(text) < 500:
            continue
        chapter = chapter_for(path)
        out.append(SourceText(path, chapter, CHAPTERS[chapter], text))
    return out


def noisy(s: str) -> bool:
    low = s.lower()
    if any(x in low for x in ["raumnummer", "email:", "web:", "copyright", "literatur", "quelle:", "http"]):
        return True
    if re.fullmatch(r"[\d\s.,:/()-]+", s):
        return True
    if len(re.findall(r"\d", s)) > max(12, len(s) * 0.22):
        return True
    if s.count("|") > 2 or s.count("/") > 8:
        return True
    if len(re.findall(r"\b[a-zA-ZÄÖÜäöüß]\b", s)) > 9:
        return True
    return False


def sentences(text: str) -> list[str]:
    raw: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip(" -;:")
        if not line or re.fullmatch(r"\d{1,3}", line):
            continue
        if re.search(r"^(seite|slide|vorlesung|einheit|prof\\.|dr\\.)\\b", line, re.I):
            continue
        raw.append(line)
    chunks: list[str] = []
    for line in raw:
        chunks.extend(re.split(r"(?<=[.!?])\s+|(?:\s+[•▪●]\s+)|(?:\s+-\s+)", line))
    cleaned: list[str] = []
    for s in chunks:
        s = re.sub(r"\s+", " ", s).strip(" -;:")
        if 50 <= len(s) <= 380 and len(s.split()) >= 6 and not noisy(s):
            if re.search(r"[A-Za-zÄÖÜäöüß]", s):
                cleaned.append(s)
    return cleaned


TERM_RE = re.compile(
    r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9][A-Za-zÄÖÜäöüß0-9 /()\\-]{2,58})\b"
)

GENERIC_TERMS = {
    "beispiel", "eigenschaften", "verfahren", "prozess", "produkte", "vorteile",
    "nachteile", "rohstoffe", "einleitung", "tools", "anwendung", "materialien",
}

DOMAIN_BONUS = [
    "stahl", "eisen", "hochofen", "metall", "oxid", "reduktion", "kupfer",
    "aluminium", "stickstoff", "ammoniak", "salpeter", "chlor", "natron",
    "soda", "schwefel", "gips", "kalk", "zement", "glas", "keramik",
    "sinter", "roest", "elektro", "erz", "schlacke", "klinker",
]


def valid_term(term: str) -> bool:
    t = term.strip(" ,.;:-")
    low = t.lower()
    if low in GENERIC_TERMS:
        return False
    if t.count("(") != t.count(")"):
        return False
    if len(t.split()) > 6:
        return False
    if re.search(r"[A-Za-zÄÖÜäöüß]{18,}", t):
        return False
    if noisy(t):
        return False
    return True


def pick_term(sentence: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    for m in TERM_RE.finditer(sentence):
        term = m.group(1).strip(" ,.;:-")
        if len(term) < 3 or not valid_term(term):
            continue
        score = len(term)
        low = term.lower()
        if any(x in low for x in DOMAIN_BONUS):
            score += 28
        if any(c.isupper() for c in term[1:]):
            score += 12
        if re.search(r"\b(Fe|Cu|Al|Na|Cl|Ca|Mg|Si|SO|NO|NH|CO)\b", term):
            score += 20
        candidates.append((score, term))
    if not candidates:
        return None
    return max(candidates)[1]


def answer_html(sentence: str, source: SourceText) -> str:
    return (
        f"{escape(sentence)}"
        f"<br><br><span class='source'>Quelle: {escape(source.title)}</span>"
    )


def make_cards(sources: list[SourceText]) -> list[dict]:
    cards: list[dict] = []
    seen: set[str] = set()

    def add(source: SourceText, question: str, answer: str, kind: str, weight: int = 1) -> None:
        key = re.sub(r"\W+", "", (question + answer).lower())
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        if digest in seen:
            return
        seen.add(digest)
        cards.append({
            "id": f"inorg:{digest}",
            "module": "inorganic",
            "deck": "anki",
            "kap": source.chapter,
            "sub": f"VO{source.chapter}",
            "subname": CHAPTERS[source.chapter],
            "source": source.title,
            "kind": kind,
            "q": question,
            "a": answer,
            "weight": weight,
        })

    for source in sources:
        for s in sentences(source.text):
            term = pick_term(s)
            if term and 8 <= len(term) <= 65:
                cloze = re.sub(re.escape(term), "_____", s, count=1)
                add(
                    source,
                    f"Ergaenze den zentralen Begriff: {escape(cloze)}",
                    answer_html(f"{term} - {s}", source),
                    "cloze",
                    2,
                )
            lead = term or "diesem Thema"
            if re.search(r"\b(ist|sind|wird|werden|entsteht|erfolgt|dient|besteht|enthaelt|enthält|kann|koennen|können|fuehrt|führt)\b", s, re.I):
                add(
                    source,
                    f"Was musst du zu {escape(lead)} wissen?",
                    answer_html(s, source),
                    "concept",
                    2,
                )
            if re.search(r"\b(Vorteil|Nachteil|Anwendung|Beispiel|Verfahren|Prozess|Reaktion|Produkt|Eigenschaft|Rohstoff|Temperatur|Druck)\b", s, re.I):
                add(
                    source,
                    f"Nenne den relevanten Pruefungspunkt zu {escape(lead)}.",
                    answer_html(s, source),
                    "exam_fact",
                    1,
                )

    if len(cards) < 600:
        for source in sources:
            for unit in sentences(source.text):
                add(
                    source,
                    f"Welche Kernaussage gehoert zu {escape(source.title)}?",
                    answer_html(unit, source),
                    "source_fact",
                    1,
                )
                if len(cards) >= 600:
                    break
            if len(cards) >= 600:
                break

    cards.sort(key=lambda c: (-c["weight"], c["kap"], c["kind"], c["q"]))
    buckets: dict[int, list[dict]] = {}
    for card in cards:
        buckets.setdefault(card["kap"], []).append(card)
    balanced: list[dict] = []
    while len(balanced) < TARGET_CARDS and any(buckets.values()):
        for kap in sorted(buckets):
            if buckets[kap] and len(balanced) < TARGET_CARDS:
                balanced.append(buckets[kap].pop(0))
    for i, card in enumerate(balanced, start=1):
        card["order"] = i
    return balanced


def organic_payload(payload: dict) -> tuple[list[dict], dict]:
    modules = payload.get("modules") or {
        "organic": {
            "title": "Organische Chemie",
            "full_title": payload.get("title", "Chemische Technologien Organischer Stoffe"),
            "chapters": payload.get("chapters", {}),
        }
    }
    cards = []
    for card in payload.get("cards", []):
        if card.get("module", "organic") == "organic":
            c = dict(card)
            c["module"] = "organic"
            cards.append(c)
    return cards, modules


def main() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing_index = []
    if RAW_OUT.exists():
        try:
            existing_index = json.loads(RAW_OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_index = []
    organic_cards, modules = organic_payload(payload)
    sources = load_sources()
    inorganic_cards = make_cards(sources)
    modules["inorganic"] = {
        "title": "Anorganische Chemie",
        "full_title": "Chemische Technologien Anorganischer Stoffe",
        "chapters": {str(k): v for k, v in CHAPTERS.items()},
    }
    coverage = []
    for kap, title in CHAPTERS.items():
        coverage.append({
            "module": "inorganic",
            "kap": kap,
            "name": title,
            "anki": sum(1 for c in inorganic_cards if c["kap"] == kap),
            "sources": sorted({s.title for s in sources if s.chapter == kap}),
        })
    merged = {
        "title": "Manuels TU Chemie SR-Trainer",
        "exam_date": payload.get("exam_date", "2026-09-21"),
        "modules": modules,
        "cards": organic_cards + inorganic_cards,
        "coverage": payload.get("coverage", []) + coverage,
        "source_count": payload.get("source_count", 0) + len(sources),
    }
    SEED_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_index = [row for row in existing_index if row.get("module", "organic") == "organic"]
    RAW_OUT.write_text(json.dumps(organic_index + [
        {
            "module": "inorganic",
            "path": str(s.path),
            "chapter": s.chapter,
            "title": s.title,
            "chars": len(s.text),
            "text": s.text[:4000],
        }
        for s in sources
    ], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(inorganic_cards)} inorganic cards from {len(sources)} sources")
    for row in coverage:
        print(f"{row['kap']:>2}: {row['anki']:>3} {row['name']}")


if __name__ == "__main__":
    main()
