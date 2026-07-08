from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

import db  # noqa: E402


SEED_PATH = REPO / "app" / "seed_data.json"


def strip_question_context(question: str) -> str:
    return re.sub(r"^Kontext: .*?\n\n", "", question, count=1, flags=re.S).strip()


def strip_answer_context(answer: str) -> str:
    return re.sub(r"^<b>Kontext:</b>.*?<br><br>", "", answer, count=1, flags=re.S).strip()


def context_for(card: dict, modules: dict) -> str:
    module = card.get("module", "organic")
    module_title = modules.get(module, {}).get("title") or modules.get(module, {}).get("full_title") or module
    tags = db.infer_tags(card)
    topic = " / ".join(tags[:3]) if tags else card.get("subname", "")
    parts = [
        module_title,
        card.get("subname", ""),
        topic,
    ]
    context = " / ".join(p for p in parts if p)
    source = card.get("source")
    if source:
        context = f"{context}. Quelle: {source}"
    return context


def contextualize(card: dict, modules: dict) -> dict:
    out = dict(card)
    out["tags"] = db.infer_tags(out)
    context = context_for(out, modules)
    base_q = strip_question_context(str(out.get("q", "")))
    base_a = strip_answer_context(str(out.get("a", "")))
    out["q"] = f"Kontext: {escape(context)}\n\n{base_q}"
    out["a"] = f"<b>Kontext:</b> {escape(context)}<br><br>{base_a}"
    return out


def main() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    modules = payload.get("modules", {})
    cards = [contextualize(card, modules) for card in payload.get("cards", [])]
    payload["cards"] = cards
    SEED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"contextualized {len(cards)} cards")


if __name__ == "__main__":
    main()
