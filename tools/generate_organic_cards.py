from __future__ import annotations

import json
import re
from pathlib import Path

from exam_style_generation import SourceDoc, extract_document_pages, generate_exam_style_cards


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "sources" / "organic_chem"
OUT_PATH = ROOT / "organicsr" / "app" / "seed_data.json"
RAW_OUT = ROOT / "organicsr" / "app" / "source_text_index.json"

TARGET_CARDS = 560

CHAPTERS = {
    1: "VO1 Einfuehrung und fossile Rohstoffe",
    2: "VO2 Raffinerieprozesse",
    3: "VO3 Raffinerie-Gastvortrag",
    4: "VO4 Raffinerie, Midstream und Vokabeln",
    5: "VO5 Nachwachsende Rohstoffe, Fette und Oele",
    6: "VO6 Kohlenhydrate und Staerke",
    7: "VO7 Cellulose",
    8: "VO8 Papier, Farbstoffe und Cellulose-Vertiefung",
    9: "VO9 Polymerchemie und Polymerisation",
    10: "VO10 Kunststoffrecycling",
    11: "Pruefungsvorbereitung und Beispielaufgaben",
}


def chapter_for(path: Path) -> int:
    name = path.name.lower()
    parent = " ".join(p.lower() for p in path.parts)
    m = re.search(r"\bvo\s*([0-9]{1,2})(?:\b|_)", name)
    if m:
        return max(1, min(int(m.group(1)), 11))
    if "pr_fung" in parent or "prüfung" in parent or "beispiel" in parent:
        return 11
    vocab_map = {
        "vokabelsammlung vo1": 1,
        "vokabelsammlung vo2": 2,
        "vokabelsammlung vo3": 3,
        "vo4 vokabel": 4,
        "vokabelsammlung vo5": 5,
        "vokabelsammlung vo6": 6,
        "vokabelsammlung vo 7": 7,
        "vokabelsammlung vo8": 8,
        "vokabelsammlung vo 9": 9,
    }
    for marker, chapter in vocab_map.items():
        if marker in name:
            return chapter
    return 11


def load_sources() -> list[SourceDoc]:
    sources: list[SourceDoc] = []
    for path in sorted(SOURCE_DIR.rglob("*")):
        if path.suffix.lower() not in {".pdf", ".docx"}:
            continue
        if path.name.startswith("~$") or path.stat().st_size < 1000:
            continue
        try:
            pages = extract_document_pages(path)
        except Exception as exc:
            print(f"skip {path}: {exc}")
            continue
        if sum(len(page) for page in pages) < 500:
            continue
        chapter = chapter_for(path)
        sources.append(SourceDoc(path, chapter, path.stem, pages))
    return sources


def main() -> None:
    sources = load_sources()
    cards = generate_exam_style_cards(sources, CHAPTERS, "organic", "org", TARGET_CARDS)
    coverage = []
    for kap, title in CHAPTERS.items():
        coverage.append({
            "module": "organic",
            "kap": kap,
            "name": title,
            "anki": sum(1 for card in cards if card["kap"] == kap),
            "sources": sorted({source.title for source in sources if source.chapter == kap}),
        })
    payload = {
        "title": "Manuels TU Chemie SR-Trainer",
        "exam_date": "2026-09-21",
        "modules": {
            "organic": {
                "title": "Organische Chemie",
                "full_title": "Chemische Technologien Organischer Stoffe",
                "chapters": {str(k): v for k, v in CHAPTERS.items()},
            }
        },
        "cards": cards,
        "coverage": coverage,
        "source_count": len(sources),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    RAW_OUT.write_text(json.dumps([
        {
            "module": "organic",
            "path": str(source.path.relative_to(ROOT)),
            "chapter": source.chapter,
            "title": source.title,
            "pages": len(source.pages),
            "chars": sum(len(page) for page in source.pages),
            "preview": source.pages[0][:1200] if source.pages else "",
        }
        for source in sources
    ], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(cards)} organic exam-style cards from {len(sources)} sources")
    for row in coverage:
        print(f"{row['kap']:>2}: {row['anki']:>3} {row['name']}")


if __name__ == "__main__":
    main()
