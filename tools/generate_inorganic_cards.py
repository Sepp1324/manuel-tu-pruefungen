from __future__ import annotations

import json
import os
import re
from pathlib import Path

from exam_style_generation import SourceDoc, extract_document_pages, generate_exam_style_cards


REPO = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(os.environ.get("INORG_SOURCE_DIR", "/private/tmp/anorganik_sources_clean"))
SEED_PATH = REPO / "app" / "seed_data.json"
RAW_OUT = REPO / "app" / "source_text_index.json"

TARGET_CARDS = 420

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


def chapter_for(path: Path) -> int:
    m = re.search(r"Einheit[_\s-]+(\d{1,2})", path.name, re.I)
    if m:
        return max(1, min(int(m.group(1)), 11))
    return 11


def load_sources() -> list[SourceDoc]:
    sources: list[SourceDoc] = []
    for path in sorted(SOURCE_DIR.glob("*.pdf")):
        pages = extract_document_pages(path)
        if sum(len(page) for page in pages) < 500:
            continue
        chapter = chapter_for(path)
        sources.append(SourceDoc(path, chapter, CHAPTERS[chapter], pages))
    return sources


def organic_payload(payload: dict) -> tuple[list[dict], dict, list[dict]]:
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
    coverage = [row for row in payload.get("coverage", []) if row.get("module", "organic") == "organic"]
    return cards, modules, coverage


def main() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing_index = []
    if RAW_OUT.exists():
        try:
            existing_index = json.loads(RAW_OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_index = []

    organic_cards, modules, organic_coverage = organic_payload(payload)
    sources = load_sources()
    inorganic_cards = generate_exam_style_cards(sources, CHAPTERS, "inorganic", "inorg", TARGET_CARDS)
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
            "anki": sum(1 for card in inorganic_cards if card["kap"] == kap),
            "sources": sorted({source.title for source in sources if source.chapter == kap}),
        })
    merged = {
        "title": "Manuels TU Chemie SR-Trainer",
        "exam_date": payload.get("exam_date", "2026-09-21"),
        "modules": modules,
        "cards": organic_cards + inorganic_cards,
        "coverage": organic_coverage + coverage,
        "source_count": payload.get("source_count", 0) + len(sources),
    }
    SEED_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    organic_index = [row for row in existing_index if row.get("module", "organic") == "organic"]
    RAW_OUT.write_text(json.dumps(organic_index + [
        {
            "module": "inorganic",
            "path": str(source.path),
            "chapter": source.chapter,
            "title": source.title,
            "pages": len(source.pages),
            "chars": sum(len(page) for page in source.pages),
            "preview": source.pages[0][:1200] if source.pages else "",
        }
        for source in sources
    ], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(inorganic_cards)} inorganic exam-style cards from {len(sources)} sources")
    for row in coverage:
        print(f"{row['kap']:>2}: {row['anki']:>3} {row['name']}")


if __name__ == "__main__":
    main()
