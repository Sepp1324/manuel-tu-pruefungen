from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

import pdfplumber
from docx import Document


@dataclass
class SourceDoc:
    path: Path
    chapter: int
    title: str
    pages: list[str]


ADMIN_RE = re.compile(
    r"(?i)\b("
    r"studierende|matrikelnummer|studienkennzahl|angaben zur pruefung|angaben zur prüfung|"
    r"beschriften sie|antwortzettel|pruefungsbogen|prüfungsbogen|sitzplatz|"
    r"smartwatch|smartphone|taschenrechner|tiss|tuwel|sommersemester|"
    r"bachelor studium|msc chemie|katharina\.ehrmann|@tuwien|tu wien|"
    r"vorlesung 164\.211|vorlesung 164\.221|t\.?\s*konegger|und analytik|"
    r"was sie ab heute verstehen werden|inhaltsverzeichnis|überblick über|ueberblick ueber|"
    r"administrative|lernunterlagen|ullmann|baerns|jess et al"
    r")\b"
)

SOURCE_NOISE_RE = re.compile(
    r"(?i)\b("
    r"doi:|https?://|www\.|copyright|literatur|sources?:|quellen?:|quelle:|"
    r"systematic review|meta-regression|company overview|global headquarters|"
    r"regional headquarters|patent applications|microsoft copilot|"
    r"guardian|kurier\.at|derstandard|der standard|welt\.de|lv-evaluierung|tiss|"
    r"bertau|offermanns|salesch|zement-taschenbuch|industrielle anorganische chemie"
    r")\b"
)

LECTURE_ADMIN_RE = re.compile(
    r"(?i)\b("
    r"vor-?\s*(?:&amp;|&|und)\s*nachbereitung|vorlesungseinheiten|"
    r"positive absolvierung|mindestens 50\s*%|digitale geraete|digitale geräte|"
    r"abgabe am ende|zugewiesenen sitzplatz|anmeldeformalitaeten|anmeldeformalitäten"
    r")\b"
)

QUESTION_RE = re.compile(r"\?\s*(?:\[\d|$)")
FORMULA_RE = re.compile(r"\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)+\b|->|→|Δ|∆")

PROCESS_TERMS = (
    "prozess", "verfahren", "synthese", "herstellung", "reaktion", "polymerisation",
    "cracking", "reforming", "vergasung", "roest", "röst", "elektrolyse", "hochofen",
    "claus", "solvay", "haber", "bosch", "bayer", "aufschluss", "recycling",
)
STRUCTURE_TERMS = (
    "struktur", "formel", "aufbau", "wiederholeinheit", "bindung", "monomer",
    "polymer", "molekular", "kristall", "netzwerk", "funktionelle gruppe",
)
COMPARE_TERMS = (
    "unterschied", "vs", "versus", "vergleich", "arten", "formen", "einteilung",
    "klassifizieren", "kategorie", "typen",
)
APPLICATION_TERMS = (
    "anwendung", "produkt", "eigenschaft", "vorteil", "nachteil", "kritik",
    "problem", "umwelt", "recycling", "rohstoff", "quelle", "vorkommen",
)
DOMAIN_TERMS = (
    "erdöl", "erdoel", "erdgas", "kohle", "claus", "synthesegas", "methanol",
    "olefin", "seife", "emulsion", "fett", "öl", "oel", "stärke", "staerke",
    "cellulose", "papier", "farbstoff", "polymer", "radikal", "stufenwachstum",
    "kunststoff", "mikroplastik", "stahl", "eisen", "hochofen", "oxid",
    "reduktion", "kupfer", "aluminium", "stickstoff", "ammoniak", "chlor",
    "natron", "soda", "schwefel", "gips", "kalk", "zement", "glas", "keramik",
)


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = text.replace("\uf0b7", "•").replace("", "•").replace("▪", "•")
    text = text.replace("→", "->")
    text = re.sub(r"([a-zäöüß])([A-ZÄÖÜ])", r"\1. \2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?i)chemische technologie[n]? (?:organischer|anorganischer) stoffe", "", text)
    text = re.sub(r"(?i)technische universitaet wien|technische universität wien|tu wien", "", text)
    text = re.sub(r"(?i)institut fuer chemische technologien|institut für chemische technologien", "", text)
    return text.strip()


def extract_pdf_pages(path: Path) -> list[str]:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = clean_text(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
            if text:
                pages.append(text)
    return pages


def extract_docx_pages(path: Path) -> list[str]:
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = clean_text("\n".join(parts))
    chunks: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*(?:\d+\.\s+)?(?:Fossile|Nachwachsende|Makromolekulare|Polymer|Einheit)\b", line):
            if buf:
                chunks.append("\n".join(buf))
                buf = []
        buf.append(line)
    if buf:
        chunks.append("\n".join(buf))
    return [c for c in chunks if len(c) > 120]


def extract_document_pages(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_pages(path)
    if suffix == ".docx":
        return extract_docx_pages(path)
    return []


def plain_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip(" -;:")
    line = re.sub(r"(?i)\bT\.\s*Konegger\s*[–-].*$", "", line)
    line = re.sub(r"(?i)\bChem\.\s*Techn\.\s*Anorg\.\s*Stoffe.*$", "", line)
    line = re.sub(r"(?i)\b(?:sources?|quellen?):.*$", "", line)
    line = re.sub(r"(?i)\b(?:offermanns|salesch|ragaert|yin,|demets|akhras|fischer|winnacker|tegeder).*$", "", line)
    line = re.sub(r"^\s*[a-z]\.\s+", "", line)
    line = re.sub(r"\s*\[\d+(?:[.,]\d+)?\]\s*$", "", line)
    line = re.sub(r"\s*\(\d+(?:[.,]\d+)?\)\s*$", "", line)
    return line.strip()


def noisy(line: str) -> bool:
    low = line.lower()
    if len(line) < 8:
        return True
    if re.fullmatch(r"[\d\s.,:/()%-]+", line):
        return True
    if ADMIN_RE.search(line) or SOURCE_NOISE_RE.search(line) or LECTURE_ADMIN_RE.search(line):
        return True
    if any(x in low for x in (
        "guest lecture", "for external use", "generated by", "slide ", "recap",
        "terminology & concepts", "terminology and concepts", "market estimated",
        "usd ", "billion", "biggest players", "global organization",
        "what we do", "diversified portfolio", "borouge", "borstar", "sclairtech",
        "r&d employees", "patents", "high-voltage transmission", "medical grades",
        "flexible food packaging", "essential to everyday life",
        "population growth", "purchasing power", "textile growth", "metric tons", "cagr",
    )):
        return True
    if line.count("|") > 1:
        return True
    if len(re.findall(r"\d", line)) > max(18, len(line) * 0.28):
        return True
    if len(re.findall(r"\b[A-Za-zÄÖÜäöüß]\b", line)) > 10:
        return True
    return False


def meaningful_lines(text: str) -> list[str]:
    raw: list[str] = []
    for line in clean_text(text).splitlines():
        line = plain_line(line)
        if not line or noisy(line):
            continue
        raw.append(line)
    merged: list[str] = []
    for line in raw:
        if (
            merged
            and len(merged[-1]) < 120
            and len(line) < 120
            and not merged[-1].endswith((".", "?", "!", ":"))
            and not line.startswith(("•", "-", "a.", "b.", "c."))
        ):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return [line[:260].strip() for line in merged if not noisy(line)]


def source_is_exam_example(source: SourceDoc) -> bool:
    local = " ".join(part.lower() for part in [source.path.name, *[p.name for p in source.path.parents[:3]]])
    return "pr_fungsvorbereitung" in local or "beispielpr" in local or re.search(r"\bpr_fung[_-]\d", local) is not None


def title_from_lines(lines: list[str], fallback: str) -> tuple[str, list[str]]:
    if not lines:
        return fallback, []
    first = lines[0]
    if QUESTION_RE.search(first) or len(first) > 120:
        return fallback, lines
    if len(lines) > 1 and len(first) < 35 and not first.endswith(":") and not lines[1].startswith("•"):
        joined = f"{first}: {lines[1]}"
        if len(joined) < 120 and not QUESTION_RE.search(lines[1]):
            return joined, lines[2:]
    return first.rstrip(":"), lines[1:]


def normalize_topic(title: str, facts: list[str], fallback: str) -> str:
    topic = re.sub(r"^\d+\.\s*", "", title)
    topic = topic.split("•", 1)[0]
    topic = re.sub(r"(?i)^(fossile rohstoffe|nachwachsende rohstoffe|polymerchemie|makromolekulare chemie|grosschemie|großchemie)\s*:?\s*", "", topic)
    topic = re.sub(r"\s+", " ", topic)
    topic = topic.strip(" :-")
    if (
        len(topic) < 8
        or topic.lower() in {"einleitung", "grundlagen", "tools", "population"}
        or topic == fallback
        or re.fullmatch(r"(?:VO\d+|Einheit \d+).*", topic)
    ):
        text = " ".join(facts[:4])
        matches = re.findall(r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9/-]{4,45}\b", text)
        scored = sorted(matches, key=lambda x: (any(t in x.lower() for t in DOMAIN_TERMS), len(x)), reverse=True)
        topic = scored[0] if scored else fallback
    fact_text = " ".join(facts[:5])
    process_names = re.findall(
        r"\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß]+(?:-[A-ZÄÖÜ]?[A-Za-zÄÖÜäöüß]+)*(?:-Prozess|-Verfahren|verfahren|prozess))\b",
        fact_text,
    )
    if process_names and (len(topic.split()) <= 2 or not any(term in topic.lower() for term in PROCESS_TERMS)):
        topic = process_names[0]
    return topic[:90].strip(" :-")


def classify_card(topic: str, facts: list[str]) -> str:
    text = " ".join([topic, *facts]).lower()
    if any(t in text for t in PROCESS_TERMS):
        return "exam_process"
    if any(t in text for t in COMPARE_TERMS):
        return "exam_compare"
    if any(t in text for t in STRUCTURE_TERMS):
        return "exam_structure"
    if any(t in text for t in APPLICATION_TERMS):
        return "exam_application"
    return "exam_concept"


def question_for(topic: str, kind: str, facts: list[str]) -> str:
    text = " ".join(facts).lower()
    needs_formula = FORMULA_RE.search(" ".join(facts)) or any(x in text for x in ("struktur", "formel", "gleichung"))
    if kind == "exam_process":
        aspects = "Ausgangsstoffe, Prozessfuehrung, wichtige Bedingungen, Produkte und Zweck"
        if "temperatur" in text or "druck" in text:
            aspects = "Ausgangsstoffe, Druck/Temperatur, Reaktionsschritte, Produkte und Zweck"
        if needs_formula:
            aspects += " sowie relevante Reaktions- oder Strukturformeln"
        return f"Erlaeutern Sie {topic}. Gehen Sie auf {aspects} ein."
    if kind == "exam_compare":
        return f"Vergleichen Sie {topic}. Nennen Sie die wichtigen Arten/Merkmale, Unterschiede und Beispiele."
    if kind == "exam_structure":
        extra = " und verwenden Sie Strukturformeln, falls sie pruefungsrelevant sind" if needs_formula else ""
        return f"Beschreiben Sie den chemischen Aufbau von {topic}. Erklaeren Sie Strukturmerkmale, Bindungen/Funktionsgruppen{extra}."
    if kind == "exam_application":
        return f"Nennen und erklaeren Sie die wichtigsten Eigenschaften, Anwendungen oder Probleme von {topic}."
    return f"Erklaeren Sie {topic} pruefungsnah. Gehen Sie auf Definition, zentrale Merkmale und mindestens ein Beispiel ein."


def fact_quality(line: str) -> int:
    low = line.lower()
    score = min(len(line), 120)
    if QUESTION_RE.search(line):
        score -= 35
    if any(t in low for t in DOMAIN_TERMS):
        score += 55
    if any(t in low for t in PROCESS_TERMS + STRUCTURE_TERMS + APPLICATION_TERMS):
        score += 30
    if FORMULA_RE.search(line):
        score += 25
    if low.startswith(("was ", "welche ", "wie ", "wodurch ", "warum ")):
        score -= 20
    return score


def answer_html(facts: list[str], source: SourceDoc, topic: str) -> str:
    clean_facts = [fact for fact in facts if not QUESTION_RE.search(fact) and not noisy(fact)]
    if len(clean_facts) < 2:
        clean_facts = [fact for fact in facts if not noisy(fact)]
    best = sorted(clean_facts, key=fact_quality, reverse=True)[:7]
    best.sort(key=lambda x: facts.index(x))
    items = "".join(f"<li>{escape(f)}</li>" for f in best)
    return (
        f"<b>Pruefungsantwort zu {escape(topic)}:</b>"
        f"<ul>{items}</ul>"
        "<b>Beim Antworten aktiv abdecken:</b> Definition/Prinzip, Prozess oder Struktur, "
        "wichtige Bedingungen, Produkte/Beispiele und typische Begruendung."
        f"<br><br><span class='source'>Quelle: {escape(source.title)}</span>"
    )


def card_weight(kind: str, facts: list[str]) -> int:
    weight = {
        "exam_process": 5,
        "exam_structure": 4,
        "exam_compare": 4,
        "exam_application": 3,
        "exam_concept": 2,
    }.get(kind, 1)
    if any(FORMULA_RE.search(f) for f in facts):
        weight += 1
    if len(facts) >= 4:
        weight += 1
    return weight


def build_candidates(source: SourceDoc, module: str, id_prefix: str, chapter_name: str) -> list[dict]:
    if source_is_exam_example(source):
        return []
    candidates: list[dict] = []
    for page_no, page in enumerate(source.pages, start=1):
        lines = meaningful_lines(page)
        if len(lines) < 3:
            continue
        title, rest = title_from_lines(lines, chapter_name)
        facts = [line for line in rest if not noisy(line)]
        facts = [line for line in facts if len(line.split()) >= 3 or FORMULA_RE.search(line)]
        answer_facts = [line for line in facts if not QUESTION_RE.search(line)]
        if len(answer_facts) < 2:
            continue
        topic = normalize_topic(title, facts, chapter_name)
        if noisy(topic) or any(x in topic.lower() for x in (
            "market", "recap", "terminology", "essential materials", "population",
            "überblick", "ueberblick", "administrative", "vorlesung 164",
        )):
            continue
        kind = classify_card(topic, facts)
        question = question_for(topic, kind, facts)
        answer = answer_html(facts, source, topic)
        key = re.sub(r"\W+", "", f"{module}:{source.title}:{page_no}:{question}:{answer}".lower())
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        candidates.append({
            "id": f"{id_prefix}:{digest}",
            "module": module,
            "deck": "anki",
            "kap": source.chapter,
            "sub": f"VO{source.chapter}" if source.chapter < 11 else "PV",
            "subname": chapter_name,
            "source": source.title,
            "kind": kind,
            "q": escape(question),
            "a": answer,
            "weight": card_weight(kind, facts),
        })
        if len(facts) >= 8:
            detail_facts = facts[4:11]
            detail_topic = f"{topic}: Details"
            detail_question = question_for(detail_topic, "exam_application", detail_facts)
            detail_answer = answer_html(detail_facts, source, detail_topic)
            detail_key = re.sub(r"\W+", "", f"{module}:{source.title}:{page_no}:detail:{detail_question}".lower())
            detail_digest = hashlib.sha1(detail_key.encode("utf-8")).hexdigest()[:12]
            candidates.append({
                "id": f"{id_prefix}:{detail_digest}",
                "module": module,
                "deck": "anki",
                "kap": source.chapter,
                "sub": f"VO{source.chapter}" if source.chapter < 11 else "PV",
                "subname": chapter_name,
                "source": source.title,
                "kind": "exam_application",
                "q": escape(detail_question),
                "a": detail_answer,
                "weight": max(1, card_weight("exam_application", detail_facts) - 1),
            })
    return candidates


def balanced_cards(candidates: list[dict], target: int) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for card in sorted(candidates, key=lambda c: (-c["weight"], c["kap"], c["source"], c["q"])):
        fingerprint = re.sub(r"\W+", "", (card["q"] + card["a"]).lower())[:260]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(card)
    buckets: dict[int, list[dict]] = {}
    for card in unique:
        buckets.setdefault(card["kap"], []).append(card)
    out: list[dict] = []
    while len(out) < target and any(buckets.values()):
        for kap in sorted(buckets):
            if buckets[kap] and len(out) < target:
                out.append(buckets[kap].pop(0))
    for order, card in enumerate(out, start=1):
        card["order"] = order
    return out


def generate_exam_style_cards(
    sources: list[SourceDoc],
    chapters: dict[int, str],
    module: str,
    id_prefix: str,
    target: int,
) -> list[dict]:
    candidates: list[dict] = []
    for source in sources:
        candidates.extend(build_candidates(source, module, id_prefix, chapters[source.chapter]))
    return balanced_cards(candidates, target)
