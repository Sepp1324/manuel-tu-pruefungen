from __future__ import annotations

import os
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
import db
from fsrs import Scheduler


app = FastAPI(title="Organische Chemie SR-Trainer")
sched = Scheduler()

EXAM_DATE = date.fromisoformat(os.environ.get("EXAM_DATE", "2026-09-21"))
SEED_PATH = Path(__file__).parent / "seed_data.json"
SPA_DIR = Path(os.environ.get("SPA_DIR", Path(__file__).parent / "spa"))
if not SPA_DIR.exists() and (Path(__file__).parent.parent / "dist").exists():
    SPA_DIR = Path(__file__).parent.parent / "dist"
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))

ADMIN_USER = os.environ.get("ADMIN_USER", "manuel").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

ARCHIVE_EXAMS = {
    "organic": [
        {
            "id": "organic-example-2024",
            "title": "Beispielpruefung Organische Chemie",
            "source": "Beispielpruefungen",
            "questions": [
                {"topic": "Fossile Rohstoffe", "points": 4, "prompts": ["Fossile und nachwachsende Rohstoffe erklaeren", "Entstehung von Erdoel beschreiben", "Konventionelle Erdoelfoerderung erklaeren", "Kohlevergasung mit Druck/Temperatur und Verfahrensart erlaeutern"]},
                {"topic": "Synthesegas und Methanol", "points": 4, "prompts": ["Synthesegas definieren und Herstellung aus Kohle erklaeren", "Prozessfuehrungen und Syngas-Zusammensetzung vergleichen", "Methanol-Synthese mit Druck/Temperatur erklaeren", "Methanol-to-Olefins und Olefin-Nutzung einordnen"]},
                {"topic": "Seife und Emulsionen", "points": 4, "prompts": ["Allgemeine Strukturformel von Seifen angeben", "Rohstoffe und Seifenherstellung erklaeren", "Kernseife und Schmierseife unterscheiden", "Emulsion und Stabilisierung mit Struktur/Wirkweise erklaeren"]},
                {"topic": "Staerke", "points": 4, "prompts": ["Vorkommen und chemischen Aufbau nennen", "Modifizierte Staerke erklaeren", "Beispiel mit Reaktionsgleichung beschreiben", "Eigenschaft, Anwendung und Substitutionsgrad erklaeren"]},
                {"topic": "Ketten- und Stufenwachstum", "points": 4, "prompts": ["Kinetischen Verlauf vergleichen", "Polymerisationsgrad und Reaktionsfortschritt erklaeren", "Mechanistische Typen nennen", "Reaktive Gruppen in Monomeren zuordnen"]},
                {"topic": "Radikalische Polymerisation", "points": 4, "prompts": ["Mechanistischen Ablauf beschreiben", "Polyreaktionstyp zuordnen", "Initiation und Kettenwachstum erklaeren", "Beispielpolymer mit Struktur nennen"]},
            ],
        },
        {
            "id": "organic-2025-focus",
            "title": "Pruefungsbogen-Fokus 2025",
            "source": "Beispielpruefungen",
            "questions": [
                {"topic": "Erdgas", "points": 4, "prompts": ["Zusammensetzung von Erdgas", "Suesses und saures Gas unterscheiden", "Lagerstaetten erklaeren", "Fracking mit Funktionsweise beschreiben"]},
                {"topic": "Fluid Catalytic Cracking", "points": 4, "prompts": ["Ausgangsstoff nennen", "Produkte erklaeren", "Reaktionen und Bedingungen beschreiben", "Katalysatorregeneration erklaeren"]},
                {"topic": "Staerke und Glycosidische Bindung", "points": 4, "prompts": ["Wiederholeinheit zeichnen/benennen", "Funktion und Strukturmotive erklaeren", "Aldosen/Ketosen und D/L erklaeren", "Bindungsarten benennen und zeichnen"]},
                {"topic": "Holz und Zellstoff", "points": 4, "prompts": ["Hierarchischen Aufbau bis molekular erklaeren", "Hauptbestandteile und Nutzung nennen", "Energetische Verwendung erklaeren", "Chemischen Holzaufschluss beschreiben"]},
                {"topic": "Thermoplaste und Duroplaste", "points": 4, "prompts": ["Polymerarchitektur vergleichen", "Thermische und mechanische Eigenschaften erklaeren", "Elastomere einordnen", "Recyclingstrategien nennen"]},
                {"topic": "Radikalische Polymerisation und Effekte", "points": 4, "prompts": ["Vier Teilschritte nennen", "Initiation und Kettenwachstum im Detail", "Glas-/Trommsdorff-Effekt erklaeren", "Geeignete technische Verfahren begruenden"]},
            ],
        },
    ],
    "inorganic": [
        {
            "id": "inorganic-simulation",
            "title": "Anorganik-Simulationsbogen",
            "source": "Aus Skript-Schwerpunkten generiert",
            "questions": [
                {"topic": "Rohstoffaufbereitung", "points": 4, "prompts": ["Zerkleinern und Klassieren erklaeren", "Sieb-/Sichterverfahren vergleichen", "Trennprinzipien nennen", "Bedeutung fuer technische Prozesse begruenden"]},
                {"topic": "Metallurgie", "points": 4, "prompts": ["Pyro- und Hydrometallurgie vergleichen", "Roesten und Reduktion erklaeren", "Ellingham/Boudouard einordnen", "Raffination und Zementation beschreiben"]},
                {"topic": "Eisen und Stahl", "points": 4, "prompts": ["Hochofenprozess erklaeren", "Reduktionsmittel und Schlacke einordnen", "Stahlerzeugungsverfahren vergleichen", "Direktreduktion nennen"]},
                {"topic": "Kupfer und Aluminium", "points": 4, "prompts": ["Kupfergewinnung erklaeren", "Bayer- und Hall-Heroult-Verfahren beschreiben", "Elektrolysebedingungen nennen", "Recycling/Emissionen einordnen"]},
                {"topic": "Grosschemie N/Cl/S", "points": 4, "prompts": ["Haber-Bosch und Ostwald erklaeren", "Chloralkali/Solvay einordnen", "Schwefelsaeure/Kontaktverfahren erklaeren", "Prozessparameter begruenden"]},
                {"topic": "Bindemittel, Glas und Keramik", "points": 4, "prompts": ["Kalk/Gips/Zement-Abbinden erklaeren", "Klinkerphasen nennen", "Glasherstellung beschreiben", "Keramikprozess und Sinterung erklaeren"]},
            ],
        }
    ],
}

PUBLIC_EXACT = {"/healthz", "/login", "/api/auth/login"}
PUBLIC_PREFIXES = ("/assets/", "/static/")

EXAM_ERROR_TYPES = {
    "definition": "Definition fehlt",
    "process": "Prozessschritte vertauscht",
    "conditions": "Bedingungen fehlen",
    "formula": "Formel/Reaktion fehlt",
    "example": "Beispiel fehlt",
}
CONFIDENCE_LEVELS = {"sure", "unsure", "none", ""}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
    "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/webp": (".webp", lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
    "image/gif": (".gif", lambda data: data.startswith((b"GIF87a", b"GIF89a"))),
}


def _module_catalog() -> dict:
    fallback = {
        "organic": {
            "key": "organic",
            "title": "Organische Chemie",
            "full_title": "Chemische Technologien Organischer Stoffe",
            "chapters": {},
        }
    }
    try:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if "modules" in payload:
        return {
            key: {"key": key, **value}
            for key, value in payload["modules"].items()
        }
    return {
        "organic": {
            "key": "organic",
            "title": "Organische Chemie",
            "full_title": payload.get("title", "Chemische Technologien Organischer Stoffe"),
            "chapters": payload.get("chapters", {}),
        }
    }


def _valid_module(module: str) -> str:
    modules = _module_catalog()
    if module not in modules:
        raise HTTPException(400, "ungueltiges Modul")
    return module


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_left() -> int:
    return max((EXAM_DATE - date.today()).days, 0)


def _max_fsrs_interval_days(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return max((EXAM_DATE - now.date()).days, 0)


def _seed_admin(conn) -> None:
    if db.count_users(conn) > 0:
        return
    if not ADMIN_USER or not ADMIN_PASSWORD:
        print("[auth] Kein Benutzer vorhanden. Setze ADMIN_USER=manuel und ADMIN_PASSWORD.")
        return
    db.create_user(conn, ADMIN_USER, auth.hash_password(ADMIN_PASSWORD), _now_iso())
    print(f"[auth] Benutzer '{ADMIN_USER}' angelegt.")


def _is_public(path: str) -> bool:
    return path in PUBLIC_EXACT or any(path.startswith(p) for p in PUBLIC_PREFIXES)


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    conn = db.get_conn()
    db.init_auth_tables(conn)
    db.purge_expired_sessions(conn, _now_iso())
    _seed_admin(conn)
    conn.close()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if _is_public(path):
        return await call_next(request)

    token = request.cookies.get(auth.COOKIE_NAME)
    user = None
    if token:
        conn = db.get_conn()
        token_hash = auth.hash_token(token)
        user = db.get_session_user(conn, token_hash, _now_iso())
        if user:
            db.refresh_session(conn, token_hash, auth.session_expiry().isoformat())
        conn.close()

    if not user:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "nicht angemeldet"}, status_code=401)
        return RedirectResponse("/login", status_code=302)

    request.state.user = user
    return await call_next(request)


class LoginIn(BaseModel):
    username: str
    password: str


class ReviewIn(BaseModel):
    card_id: str
    rating: int = Field(ge=1, le=4)
    source: str = "review"
    feedback_reason: str = ""


class CardEditIn(BaseModel):
    q: str = Field(min_length=3)
    a: str = Field(min_length=3)
    status: str = Field(pattern="^(active|needs_review|suspended)$")
    review_note: str = ""


class CardTriageIn(BaseModel):
    action: str = Field(pattern="^(approve|needs_review|suspend)$")
    q: str | None = Field(default=None, min_length=3)
    a: str | None = Field(default=None, min_length=3)
    review_note: str = ""
    reason: str = ""


class ManualCardIn(BaseModel):
    module: str = "organic"
    kap: int = Field(ge=1, le=11)
    q: str = Field(min_length=3)
    a: str = Field(min_length=3)
    source: str = "Manuell"


class OpenExamResultIn(BaseModel):
    card_id: str
    sub_scores: list[str] = Field(default_factory=list)
    confidence: str = ""
    error_types: list[str] = Field(default_factory=list)
    answer_note: str = ""


class OpenExamSubmitIn(BaseModel):
    module: str = "organic"
    mode: str = "full"
    exam_id: str = ""
    duration_seconds: int = 0
    results: list[OpenExamResultIn] = Field(default_factory=list)


class ArchiveCorrectionResultIn(BaseModel):
    topic: str
    score: str = Field(pattern="^(full|partial|miss)$")
    card_ids: list[str] = Field(default_factory=list)
    note: str = ""
    confidence: str = ""
    error_types: list[str] = Field(default_factory=list)
    rubric_scores: list[str] = Field(default_factory=list)


class ArchiveCorrectionSubmitIn(BaseModel):
    module: str = "organic"
    exam_id: str
    duration_seconds: int = 0
    results: list[ArchiveCorrectionResultIn] = Field(default_factory=list)


WORKSHOP_CATEGORIES = [
    ("english", "Englisch", "Englische Folienreste oder Begriffe"),
    ("long", "Zu lang", "Frage oder Antwort ist schwer scanbar"),
    ("missing_context", "Kein Kontext", "Quelle, VO oder fachlicher Rahmen fehlt"),
    ("photo", "Foto empfohlen", "Struktur, Formel, Schema oder Mechanismus braucht ein Bild"),
    ("sketch", "Skizze erforderlich", "Formel- oder Strukturkarte aktiv skizzieren"),
    ("extracted", "Extraktion holprig", "OCR-/HTML-/Folienreste in der Karte"),
    ("person_company", "Person/Firma", "Personen-, Firmen- oder Quellenrauschen"),
    ("lecture_info", "Vorlesungsinfo", "Organisatorische Vorlesungsinfos statt Fachstoff"),
    ("duplicate", "Duplikate", "Sehr aehnliche Karten zusammenfuehren oder deaktivieren"),
    ("nonsense", "Nonsense", "Zu wenig verwertbare Antwortpunkte"),
]


def _daily_goal(stats: dict, chapters: list[dict]) -> dict:
    days = max(_days_left(), 1)
    open_cards = (stats["new"] or 0) + (stats["due"] or 0)
    base = -(-open_cards // days) if open_cards else 0
    due_pressure = min(stats["due"], 80)
    target = max(20, min(90, base + due_pressure)) if open_cards else 0
    completed = stats["reviews_today"]
    progress = round(min(completed / target, 1) * 100) if target else 100
    focus = sorted(
        chapters,
        key=lambda c: (c["progress"], -c["due"], -c["new"], c["kap"]),
    )[:3]
    if progress >= 100:
        label = "Tagesziel erledigt"
        message = "Heute sitzt. Falls noch Energie da ist: nur lockere Wiederholung."
        status = "done"
    elif stats["due"] > 40:
        label = "Faellige Karten zuerst"
        message = "Starte mit den faelligen Karten, bevor du neue Themen anfasst."
        status = "behind"
    else:
        label = "Im Aufbau"
        message = "Eine konzentrierte Session bringt den Plan heute sauber weiter."
        status = "active"
    return {
        "date": date.today().isoformat(),
        "days_left": _days_left(),
        "target": target,
        "completed": completed,
        "remaining": max(target - completed, 0),
        "progress_pct": progress,
        "label": label,
        "status": status,
        "message": message,
        "focus_chapters": focus,
    }


def _forecast(stats: dict, chapters: list[dict]) -> dict:
    days = max(_days_left(), 1)
    total = max(stats["total"], 1)
    progress = stats["seen"] / total
    hit = (stats["hit_rate"] if stats["hit_rate"] is not None else 55) / 100
    stability_bonus = min(sum(c["avg_stability"] for c in chapters) / max(len(chapters), 1), 30) / 30
    score = round(min(98, max(5, (progress * 70 + hit * 20 + stability_bonus * 10) * 100 / 100)))
    needed_per_day = -(-((stats["new"] or 0) + (stats["due"] or 0)) // days)
    if score >= 80:
        band = "stark"
    elif score >= 55:
        band = "realistisch"
    else:
        band = "aufholen"
    return {
        "score": score,
        "band": band,
        "label": f"{max(score - 6, 0)}-{min(score + 8, 99)}%",
        "needed_per_day": needed_per_day,
        "summary": f"{stats['seen']} von {stats['total']} Karten gesehen, {needed_per_day} offene Karten pro Tag bis zur Pruefung.",
    }


def _study_plan(stats: dict, chapters: list[dict]) -> dict:
    days = _days_left()
    open_cards = (stats.get("new") or 0) + (stats.get("due") or 0)
    if days <= 0:
        phase = "exam_day"
        title = "Pruefungstag"
        new_limit = 0
        message = "Nur warm laufen: leichte Wiederholung, keine neuen Karten."
    elif days <= 7:
        phase = "final_review"
        title = "Finale Wiederholung"
        new_limit = 0
        message = "Keine neuen Karten mehr. Fokus auf faellige Karten und Schwachstellen."
    elif days <= 21:
        phase = "consolidate"
        title = "Konsolidieren"
        new_limit = max(5, min(18, -(-max(stats.get("new") or 0, 0) // max(days - 7, 1))))
        message = "Neue Karten dosieren, aber jeden Tag Schwachstellen wiederholen."
    else:
        phase = "build"
        title = "Aufbauphase"
        new_limit = max(8, min(25, -(-max(stats.get("new") or 0, 0) // max(days - 14, 1))))
        message = "Stoff breit aufbauen. Danach wird automatisch staerker wiederholt."
    focus = sorted(chapters, key=lambda c: (-c.get("weak_score", 0), c["kap"]))[:4]
    return {
        "phase": phase,
        "title": title,
        "message": message,
        "new_cards_today": new_limit,
        "reviews_today": min(90, max(20, stats.get("due") or 0)),
        "open_cards": open_cards,
        "focus": focus,
    }


def _strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</li>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", value).strip()


def _question_title(card: dict) -> str:
    raw = str(card.get("q", ""))
    if "\n\n" in raw and raw.startswith("Kontext:"):
        raw = raw.split("\n\n", 1)[1]
    text = _strip_html(raw)
    text = re.sub(r"^(Erlaeutern Sie|Erklaeren Sie|Beschreiben Sie|Vergleichen Sie|Nennen und erklaeren Sie)\s+", "", text)
    text = re.split(r"\.\s+(?:Gehen|Nennen|Erklaeren)", text, maxsplit=1)[0]
    return text[:120].strip(" .") or card.get("subname") or "Pruefungsfrage"


def _answer_points(answer: str) -> list[str]:
    points = []
    for item in re.findall(r"<li>(.*?)</li>", answer or "", flags=re.S | re.I):
        point = _strip_html(item)
        if 12 <= len(point) <= 220:
            points.append(point)
    if points:
        return points[:7]
    plain = _strip_html(answer)
    chunks = re.split(r"(?<=[.!?])\s+|;\s+|\s+•\s+", plain)
    return [c.strip() for c in chunks if 18 <= len(c.strip()) <= 220][:6]


def _scaffold_for(card: dict, points: list[str]) -> list[str]:
    text = " ".join([card.get("q", ""), card.get("a", ""), card.get("kind", "")]).lower()
    scaffold = ["Definition/Prinzip sauber angeben"]
    if any(x in text for x in ["prozess", "verfahren", "synthese", "herstellung", "polymerisation", "elektrolyse"]):
        scaffold.extend(["Ausgangsstoffe und Produkte nennen", "Prozessschritte in richtiger Reihenfolge erklaeren"])
    if any(x in text for x in ["druck", "temperatur", "bedingung", "katalysator"]):
        scaffold.append("Druck, Temperatur, Katalysator oder andere Bedingungen begruenden")
    if any(x in text for x in ["struktur", "formel", "gleichung", "reaktion", "monomer", "wiederholeinheit"]):
        scaffold.append("Reaktionsgleichung oder Strukturformel skizzieren")
    if any(x in text for x in ["anwendung", "problem", "vorteil", "nachteil", "recycling", "umwelt"]):
        scaffold.append("Anwendungen, Probleme oder typische Begruendung nennen")
    for point in points[:2]:
        scaffold.append(f"Konkreter Antwortpunkt: {point[:90]}")
    seen: set[str] = set()
    out = []
    for item in scaffold:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:6]


def _clean_confidence(value: str) -> str:
    return value if value in CONFIDENCE_LEVELS else ""


def _clean_error_types(values: list[str]) -> list[str]:
    out = []
    for value in values:
        if value in EXAM_ERROR_TYPES and value not in out:
            out.append(value)
    return out[:5]


def _safe_alt_text(filename: str | None) -> str:
    stem = Path(filename or "Foto").stem
    stem = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß _.-]+", " ", stem)
    return re.sub(r"\s+", " ", stem).strip()[:80] or "Foto"


def _image_type(content_type: str, data: bytes) -> tuple[str, str]:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    item = ALLOWED_IMAGE_TYPES.get(normalized)
    if not item:
        raise HTTPException(400, "Nur JPG, PNG, WebP oder GIF erlaubt")
    ext, check = item
    if not check(data):
        raise HTTPException(400, "Datei passt nicht zum Bildformat")
    return normalized, ext


def _card_context(card: dict) -> str:
    module_title = "Organische Chemie" if card.get("module") == "organic" else "Anorganische Chemie"
    bits = [module_title]
    if card.get("sub") or card.get("subname"):
        bits.append(" ".join(str(x) for x in [card.get("sub"), card.get("subname")] if x))
    if card.get("tags"):
        bits.append(" / ".join(card.get("tags", [])[:3]))
    context = " / ".join(bits)
    if card.get("source"):
        context = f"{context}. Quelle: {card.get('source')}"
    return context


def _workshop_card(card: dict, issues: list[str] | None = None) -> dict:
    return {
        "id": card["id"],
        "kap": card.get("kap"),
        "subname": card.get("subname"),
        "source": card.get("source"),
        "status": card.get("status"),
        "title": _question_title(card),
        "question": str(card.get("q", ""))[:180],
        "quality_score": card.get("quality_score", 0),
        "tags": card.get("tags", []),
        "has_photo": card.get("has_photo"),
        "photo_recommended": card.get("photo_recommended"),
        "sketch_required": card.get("sketch_required"),
        "issues": issues or [],
    }


def _card_signature(card: dict) -> str:
    text = _question_title(card).lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    words = [w for w in re.findall(r"[a-z0-9]{4,}", text) if w not in {"gehen", "nennen", "erklaeren", "beschreiben"}]
    return " ".join(words[:9])


def _card_issues(card: dict) -> list[str]:
    q = str(card.get("q", ""))
    a = str(card.get("a", ""))
    text = db.plain_card_text(card)
    lower = text.lower()
    issues: list[str] = []
    if card.get("english_noise") or db.english_noise(card):
        issues.append("english")
    if len(q) > 260 or len(a) > 950:
        issues.append("long")
    if not q.startswith("Kontext:") or "Quelle:" not in f"{q} {a}":
        issues.append("missing_context")
    if card.get("photo_recommended") or db.photo_recommended(card):
        issues.append("photo")
    if card.get("sketch_required") or db.sketch_required(card):
        issues.append("sketch")
    if any(x in f"{q} {a}" for x in ["_____", "[Seite", "(cid:", "", "", "", "", "&amp;"]):
        issues.append("extracted")
    if re.search(r"\b(?:AG|GmbH|Inc|Ltd|LLC|International)\b", text) or re.search(
        r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\s+[A-Z]\.?\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'.-]+\b",
        text,
    ):
        issues.append("person_company")
    if re.search(r"(?i)\b(vorlesungseinheiten|vor-?\s*(?:&|und)\s*nachbereitung|tiss|pruefungsbeginn|prüfungsbeginn|raumnummer|allgemeine informationen)\b", text):
        issues.append("lecture_info")
    points = _answer_points(a)
    if len(points) < 2 or len(text) < 60 or lower.count("quelle") >= 3:
        issues.append("nonsense")
    return list(dict.fromkeys(issues))


def _workshop_data(conn, module: str, limit: int = 8) -> dict:
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY status DESC, lapses DESC, reps ASC, kap ASC, ord ASC
           LIMIT 1200""",
        (module,),
    ).fetchall()
    cards = [db.row_to_card(r) for r in rows]
    category_defs = {key: {"key": key, "label": label, "description": desc, "count": 0, "cards": []} for key, label, desc in WORKSHOP_CATEGORIES}
    card_issues: dict[str, list[str]] = {}
    for card in cards:
        issues = _card_issues(card)
        card_issues[card["id"]] = issues
        for issue in issues:
            if issue not in category_defs:
                continue
            category_defs[issue]["count"] += 1
            if len(category_defs[issue]["cards"]) < limit:
                category_defs[issue]["cards"].append(_workshop_card(card, issues))
    groups: dict[str, list[dict]] = {}
    for card in cards:
        sig = _card_signature(card)
        if len(sig) >= 12:
            groups.setdefault(sig, []).append(card)
    duplicates = [group for group in groups.values() if len(group) > 1]
    for group in duplicates:
        for card in group[:3]:
            issues = card_issues.setdefault(card["id"], [])
            if "duplicate" not in issues:
                issues.append("duplicate")
        category_defs["duplicate"]["count"] += len(group)
        if len(category_defs["duplicate"]["cards"]) < limit:
            category_defs["duplicate"]["cards"].append(_workshop_card(group[0], card_issues.get(group[0]["id"], [])))
    category_list = [category_defs[key] for key, *_ in WORKSHOP_CATEGORIES]
    queue = sorted(
        [_workshop_card(card, card_issues.get(card["id"], [])) for card in cards if card_issues.get(card["id"])],
        key=lambda item: (-len(item["issues"]), -item["quality_score"], item.get("kap") or 99),
    )[:40]
    return {
        "module": module,
        "categories": category_list,
        "queue": queue,
        "duplicates": [
            {
                "signature": _card_signature(group[0]),
                "cards": [_workshop_card(card, card_issues.get(card["id"], [])) for card in group[:6]],
            }
            for group in duplicates[:12]
        ],
    }


def _improved_card_payload(card: dict) -> dict:
    title = _question_title(card)
    title = (
        title.replace("Depolymerization", "Depolymerisation")
        .replace("depolymerization", "Depolymerisation")
        .replace("Polymerization", "Polymerisation")
        .replace("polymerization", "Polymerisation")
        .replace("Plastics Recycling", "Kunststoffrecycling")
        .replace("Chemical Recycling", "chemisches Recycling")
    )
    if db.english_noise({"q": title, "a": ""}):
        title = str(card.get("subname") or card.get("source") or "das Thema")
    context = _card_context(card)
    points = []
    for point in _answer_points(card.get("a", "")):
        point = re.sub(r"(?i)\b(?:quelle|source):?.*$", "", point).strip(" -;:")
        if db.english_noise({"q": title, "a": point}):
            continue
        if len(point) >= 18 and point not in points:
            points.append(point)
    if len(points) < 3:
        points = _scaffold_for(card, points)
    points = points[:6]
    if len(points) < 4:
        points.extend([
            "Definition oder Grundprinzip klar nennen.",
            "Wichtige Prozessschritte, Bedingungen oder Strukturmerkmale erklaeren.",
            "Ein passendes Beispiel oder eine typische Anwendung nennen.",
        ])
    question = (
        f"Kontext: {context}\n\n"
        f"Erlaeutern Sie {title}. Gehen Sie auf Definition/Prinzip, Prozess oder Aufbau, "
        "wichtige Bedingungen, Produkte/Beispiele und typische Begruendung ein."
    )
    lis = "".join(f"<li>{escape(point)}</li>" for point in points[:6])
    answer = (
        f"<b>Kontext:</b> {escape(context)}<br><br>"
        f"<b>Pruefungsantwort zu {escape(title)}:</b><ul>{lis}</ul>"
        "<b>Beim Antworten aktiv abdecken:</b> Definition/Prinzip, Prozess oder Struktur, "
        "wichtige Bedingungen, Produkte/Beispiele und typische Begruendung."
        f"<br><br><span class='source'>Quelle: {escape(str(card.get('source') or 'Manuell'))}</span>"
    )
    payload = dict(card)
    payload["q"] = question
    payload["a"] = answer
    payload["status"] = "active"
    payload["review_note"] = ""
    payload["kind"] = payload.get("kind") or "exam_concept"
    return payload


def _today_work_plan(conn, module: str, stats: dict, chapters: list[dict], quality: dict) -> dict:
    due = stats.get("due") or 0
    new = stats.get("new") or 0
    focus = sorted(chapters, key=lambda c: (-c.get("weak_score", 0), c.get("kap") or 99))[:3]
    formula = _formula_checklist(conn, module)
    workshop = _workshop_data(conn, module, 3)
    tasks = [
        {"key": "due", "label": "Faellige Karten", "amount": min(max(due, 20), 80) if due else 20, "route": "home", "detail": "Erst faellige Karten abarbeiten."},
        {"key": "weak", "label": "Schwaechen-VO", "amount": len(focus), "route": "dashboard", "detail": "Die staerksten Luecken gezielt wiederholen."},
        {"key": "workshop", "label": "Karten-Werkstatt", "amount": len(workshop.get("queue", [])), "route": "workshop", "detail": "Holprige Karten glaetten oder deaktivieren."},
        {"key": "formula", "label": "Skizzen/Formeln", "amount": len(formula.get("draw", [])), "route": "exam", "detail": "Struktur- und Formelbilder aktiv abrufen."},
        {"key": "mini_exam", "label": "Mini-Pruefung", "amount": 1, "route": "exam", "detail": "Eine kurze offene Simulation mit Punkteschema."},
    ]
    if new:
        tasks.insert(1, {"key": "new", "label": "Neue Karten", "amount": min(new, 20), "route": "home", "detail": "Nur dosiert neue Karten aufnehmen."})
    return {
        "date": date.today().isoformat(),
        "exam_date": EXAM_DATE.isoformat(),
        "days_left": _days_left(),
        "tasks": tasks,
        "focus": focus,
        "quality": {
            "needs_review": quality.get("needs_review", 0),
            "photo_recommended": quality.get("photo_recommended", 0),
            "workshop_open": len(workshop.get("queue", [])),
        },
        "message": "Heute: faellige Karten, eine echte Schwachstelle, dann Werkstatt oder Mini-Pruefung.",
    }


def _rubric_category(text: str) -> str:
    value = text.lower()
    if any(x in value for x in ["defin", "nennen", "zusammensetzung", "struktur", "aufbau"]):
        return "Definition"
    if any(x in value for x in ["druck", "temperatur", "katalysator", "beding", "parameter"]):
        return "Bedingungen"
    if any(x in value for x in ["formel", "gleichung", "zeich", "wiederholeinheit", "strukturformel"]):
        return "Formel/Reaktion"
    if any(x in value for x in ["beispiel", "anwendung", "nutzung", "problem", "emission", "recycling"]):
        return "Beispiel/Einordnung"
    return "Ablauf/Erklaerung"


def _rubric_for_prompts(prompts: list[str], total_points: float = 4) -> list[dict]:
    if not prompts:
        prompts = ["Definition/Prinzip", "Ablauf erklaeren", "Bedingungen oder Formel", "Beispiel oder Einordnung"]
    base = round(total_points / max(len(prompts), 1), 2)
    out = []
    for i, prompt in enumerate(prompts):
        points = round(total_points - base * (len(prompts) - 1), 2) if i == len(prompts) - 1 else base
        out.append({
            "id": f"r{i + 1}",
            "category": _rubric_category(prompt),
            "prompt": prompt,
            "points": points,
        })
    return out


def _exam_block(module: str, kap: int | None) -> str:
    kap = kap or 0
    if module == "organic":
        if kap <= 4:
            return "Fossile Rohstoffe und Raffinerie"
        if kap <= 8:
            return "Nachwachsende Rohstoffe"
        return "Polymerchemie"
    if kap <= 2:
        return "Grundlagen und Rohstoffe"
    if kap <= 6:
        return "Metallurgie"
    if kap <= 9:
        return "Anorganische Grosschemie"
    return "Werkstoffe und Bindemittel"


def _pick_balanced(cards: list[dict], module: str, count: int) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for card in cards:
        buckets.setdefault(_exam_block(module, card.get("kap")), []).append(card)
    picked: list[dict] = []
    while len(picked) < count and any(buckets.values()):
        for block in sorted(buckets):
            if buckets[block] and len(picked) < count:
                picked.append(buckets[block].pop(0))
    return picked[:count]


def _exam_question(card: dict, idx: int, module: str, formula: bool = False) -> dict:
    points = _answer_points(card.get("a", ""))
    title = _question_title(card)
    sub_count = max(3, min(5, len(points) or 4))
    base_points = round(4 / sub_count, 2)
    subquestions = []
    for i in range(sub_count):
        point_value = round(4 - base_points * (sub_count - 1), 2) if i == sub_count - 1 else base_points
        if i < len(points):
            prompt = points[i]
            prompt = f"Erklaeren: {prompt[:125]}"
        else:
            fallback = ["Definition/Prinzip", "Prozess oder Aufbau", "Bedingungen/Formeln", "Beispiel/Anwendung", "Begruendung"][i]
            prompt = fallback
        subquestions.append({
            "id": f"{idx}-{i}",
            "prompt": prompt,
            "points": point_value,
            "category": _rubric_category(prompt),
        })
    if formula:
        question = f"Geben oder skizzieren Sie die pruefungsrelevanten Reaktions- oder Strukturformeln zu {title}."
    else:
        question = card.get("q", "")
        if question.startswith("Kontext:") and "\n\n" in question:
            question = question.split("\n\n", 1)[1]
    rubric_prompts = [f"{sub['category']}: {sub['prompt']}" for sub in subquestions]
    return {
        "idx": idx,
        "card_id": card["id"],
        "module": module,
        "kap": card.get("kap"),
        "block": _exam_block(module, card.get("kap")),
        "source": card.get("source"),
        "title": title,
        "question": question,
        "subquestions": subquestions,
        "rubric": _rubric_for_prompts(rubric_prompts, 4),
        "points": 4,
        "answer": card.get("a", ""),
        "scaffold": _scaffold_for(card, points),
        "tags": card.get("tags", []),
        "sketch_required": bool(card.get("sketch_required") or db.sketch_required(card)),
    }


def _exam_score_projection(stats: dict, chapters: list[dict], module: str) -> dict:
    blocks: dict[str, list[dict]] = {}
    for ch in chapters:
        blocks.setdefault(_exam_block(module, ch.get("kap")), []).append(ch)
    out = []
    for block, items in blocks.items():
        total = sum(i.get("total", 0) for i in items) or 1
        seen = sum(i.get("seen", 0) for i in items)
        progress = seen / total
        weighted_hit = []
        for item in items:
            if item.get("hit_rate") is not None:
                weighted_hit.append(item["hit_rate"] / 100)
        hit = sum(weighted_hit) / len(weighted_hit) if weighted_hit else .55
        again = sum(i.get("again", 0) for i in items)
        penalty = min(.18, again / max(total, 1))
        score = round(max(8, min(96, (progress * .55 + hit * .35 + .10 - penalty) * 100)))
        out.append({
            "block": block,
            "score": score,
            "label": f"{max(score - 8, 0)}-{min(score + 8, 99)}%",
            "chapters": [i.get("kap") for i in items],
            "detail": f"{seen}/{total} Karten gesehen, Trefferquote {round(hit * 100)}%",
        })
    overall = round(sum(b["score"] for b in out) / len(out)) if out else 0
    return {
        "overall": overall,
        "label": f"{max(overall - 8, 0)}-{min(overall + 8, 99)}%",
        "blocks": sorted(out, key=lambda b: b["block"]),
        "next_step": "Starte eine Schwächen-Mini-Pruefung und bewerte jeden Unterpunkt ehrlich.",
    }


def _matching_cards(conn, module: str, topic: str, limit: int = 4) -> list[dict]:
    terms = [t for t in re.findall(r"[A-Za-zÄÖÜäöüß0-9/-]{4,}", topic)[:5]]
    if not terms:
        return []
    clauses = ["module=?", "deck='anki'", "status='active'"]
    params: list[object] = [module]
    clauses.append("(" + " OR ".join("payload LIKE ?" for _ in terms) + ")")
    params.extend([f"%{term}%" for term in terms])
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {' AND '.join(clauses)}
            ORDER BY reps ASC, lapses DESC, kap ASC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [
        {
            "id": card["id"],
            "kap": card.get("kap"),
            "title": _question_title(card),
            "tags": card.get("tags", []),
        }
        for card in [db.row_to_card(r) for r in rows]
    ]


def _matching_full_cards(conn, module: str, topic: str, limit: int = 10) -> list[dict]:
    terms = [t for t in re.findall(r"[A-Za-zÄÖÜäöüß0-9/-]{4,}", topic)[:6]]
    if not terms:
        return []
    clauses = ["module=?", "deck='anki'", "status='active'"]
    params: list[object] = [module]
    clauses.append("(" + " OR ".join("payload LIKE ?" for _ in terms) + ")")
    params.extend([f"%{term}%" for term in terms])
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {' AND '.join(clauses)}
            ORDER BY lapses DESC, reps ASC, kap ASC LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [db.row_to_card(r) for r in rows]


def _card_mastery_score(card: dict, now_iso: str) -> int:
    reps = card.get("reps") or 0
    lapses = card.get("lapses") or 0
    difficulty = card.get("difficulty") or 0
    stability = card.get("stability") or 0
    score = 12 if not card.get("last_review") else 45
    score += min(28, reps * 6)
    score += min(18, stability * 1.2)
    score -= min(24, lapses * 8)
    score -= min(16, max(difficulty - 6, 0) * 4)
    if card.get("due") and card.get("due") <= now_iso:
        score -= 8
    return round(max(0, min(100, score)))


def _topic_mastery(conn, module: str, topic: str, prompts: list[str] | None = None) -> dict:
    now_iso = _now_iso()
    cards = _matching_full_cards(conn, module, topic, 12)
    if not cards and prompts:
        for prompt in prompts[:2]:
            cards.extend(_matching_full_cards(conn, module, prompt, 4))
    unique: dict[str, dict] = {}
    for card in cards:
        unique[card["id"]] = card
    cards = list(unique.values())[:12]
    scores = [_card_mastery_score(card, now_iso) for card in cards]
    score = round(sum(scores) / len(scores)) if scores else 0
    if score >= 72:
        status = "gruen"
    elif score >= 45:
        status = "gelb"
    else:
        status = "rot"
    return {
        "topic": topic,
        "score": score,
        "status": status,
        "cards": [
            {
                "id": card["id"],
                "kap": card.get("kap"),
                "title": _question_title(card),
                "score": _card_mastery_score(card, now_iso),
                "reps": card.get("reps") or 0,
                "lapses": card.get("lapses") or 0,
            }
            for card in cards[:5]
        ],
        "detail": f"{len(cards)} passende Karten, Status {status}",
    }


def _all_mastery(conn, module: str) -> list[dict]:
    topics: dict[str, list[str]] = {}
    for exam in ARCHIVE_EXAMS.get(module, []):
        for q in exam.get("questions", []):
            topics.setdefault(q["topic"], []).extend(q.get("prompts", []))
    out = [_topic_mastery(conn, module, topic, prompts) for topic, prompts in topics.items()]
    return sorted(out, key=lambda item: (item["score"], item["topic"]))


def _formula_checklist(conn, module: str) -> dict:
    now_iso = _now_iso()
    cards = db.exam_candidates(conn, module, 80, "mixed", formula=True)
    draw = []
    explain = []
    for card in cards:
        text = " ".join([card.get("q", ""), card.get("a", ""), card.get("kind", "")]).lower()
        item = {
            "id": card["id"],
            "kap": card.get("kap"),
            "title": _question_title(card),
            "score": _card_mastery_score(card, now_iso),
            "tags": card.get("tags", []),
        }
        if any(x in text for x in ["struktur", "formel", "gleichung", "wiederholeinheit", "monomer"]):
            draw.append(item)
        else:
            explain.append(item)
    return {
        "draw": sorted(draw, key=lambda x: (x["score"], x["kap"] or 0, x["title"]))[:18],
        "explain": sorted(explain, key=lambda x: (x["score"], x["kap"] or 0, x["title"]))[:18],
    }


def _final_plan(conn, module: str) -> dict:
    start = EXAM_DATE - timedelta(days=6)
    weaknesses = db.weakness_heatmap(conn, _now_iso(), module)[:4]
    focus = [f"VO{w['kap']} {w['name']}" for w in weaknesses]
    templates = [
        ("Bestandsaufnahme", ["Score-Prognose ansehen", "Schwaechen-Mini-Pruefung starten", "rote Mastery-Themen markieren"]),
        ("Prozesse", ["2h-Pruefung: 3 Prozessfragen", "Antwortgerueste laut wiederholen", "Fehlerkarten ins Qualitaetszentrum"]),
        ("Formeln", ["Reaktions-/Strukturtrainer", "Muss ich zeichnen koennen-Liste", "alle Luecken handschriftlich skizzieren"]),
        ("Alte Pruefung", ["Archivbogen korrigieren", "Unterpunkte ehrlich bewerten", "miss/partial direkt nachlernen"]),
        ("Schwaechen", ["Kann ich erklaeren-Modus", "nur rote/gelbe Mastery-Themen", "keine neuen Karten"]),
        ("Generalprobe", ["volle 2h-Simulation", "Punkteprognose vergleichen", "letzte Formelcheckliste"]),
        ("Pruefungstag", ["nur leichte Gerueste", "keine neuen Themen", "kurzer Formel-Warm-up"]),
    ]
    days = []
    for i, (title, tasks) in enumerate(templates):
        d = start + timedelta(days=i)
        days.append({
            "date": d.isoformat(),
            "title": title,
            "tasks": tasks,
            "focus": focus[:2] if i in {1, 4} else focus[2:] if i == 3 else focus[:1],
        })
    return {
        "exam_date": EXAM_DATE.isoformat(),
        "starts_on": start.isoformat(),
        "days": days,
        "rule": "In den letzten 7 Tagen keine neuen Karten: nur alte Pruefungen, Schwachstellen und Formeln.",
    }


def _score_from_label(score: str) -> int:
    return {"full": 100, "partial": 50, "miss": 0}.get(score, 0)


def _attempt_dashboard(conn, module: str) -> dict:
    attempts = db.exam_attempt_history(conn, module, 24)
    block_scores: dict[str, list[int]] = {}
    error_counts: dict[str, int] = {}
    confidence_traps = []
    for attempt in attempts:
        for q in (attempt.get("payload") or {}).get("questions", []):
            score = q.get("pct")
            if score is None:
                score = _score_from_label(q.get("score", ""))
            block = q.get("block") or "Archivfragen"
            block_scores.setdefault(block, []).append(int(score or 0))
            weak = q.get("repair") or (score or 0) < 60
            if q.get("confidence") == "sure" and weak:
                confidence_traps.append({
                    "attempt_id": attempt["id"],
                    "created_at": attempt["created_at"],
                    "title": q.get("title") or q.get("topic") or "Pruefungsfrage",
                    "score": score,
                    "mode": attempt["mode"],
                })
            for err in q.get("error_types", []):
                if err in EXAM_ERROR_TYPES:
                    error_counts[err] = error_counts.get(err, 0) + 1
    trend = [
        {
            "id": a["id"],
            "date": a["created_at"][:10],
            "title": a["title"],
            "mode": a["mode"],
            "pct": a["pct"],
            "earned": a["earned"],
            "total": a["total"],
        }
        for a in reversed(attempts[:10])
    ]
    return {
        "attempts": attempts,
        "trend": trend,
        "blocks": [
            {
                "block": block,
                "score": round(sum(values) / len(values)),
                "count": len(values),
            }
            for block, values in sorted(block_scores.items())
        ],
        "errors": [
            {"key": key, "label": EXAM_ERROR_TYPES[key], "count": count}
            for key, count in sorted(error_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "confidence_traps": confidence_traps[:8],
    }


def _weekly_plan(conn, module: str) -> dict:
    today = date.today()
    start = today if today <= EXAM_DATE else EXAM_DATE
    weaknesses = db.weakness_heatmap(conn, _now_iso(), module)
    focus = [f"VO{w['kap']} {w['name']}" for w in weaknesses[:8]]
    weeks = []
    current = start
    idx = 0
    while current <= EXAM_DATE and len(weeks) < 14:
        end = min(current + timedelta(days=6), EXAM_DATE)
        days_to_exam = max((EXAM_DATE - end).days, 0)
        if days_to_exam <= 7:
            phase = "Endspurt"
            tasks = ["2 Archiv- oder offene Pruefungen", "keine neuen Karten", "Formelcheckliste abschliessen"]
        elif days_to_exam <= 21:
            phase = "Pruefungsmodus"
            tasks = ["1 volle Simulation", "2 Schwaechen-Mini-Pruefungen", "Nachlern-Queue jeden zweiten Tag"]
        else:
            phase = "Aufbau"
            tasks = ["faellige Karten taeglich", "1 offene Mini-Pruefung", "rote Mastery-Themen glaetten"]
        weeks.append({
            "start": current.isoformat(),
            "end": end.isoformat(),
            "phase": phase,
            "tasks": tasks,
            "focus": focus[idx % max(len(focus), 1):][:3] if focus else [],
        })
        current = end + timedelta(days=1)
        idx += 2
    return {
        "module": module,
        "exam_date": EXAM_DATE.isoformat(),
        "weeks": weeks,
        "rule": "Wochenziele sind Sollwerte; nach jeder offenen Pruefung zieht die Nachlern-Queue die echten Luecken nach.",
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/auth/login")
def login(inp: LoginIn, request: Request, response: Response):
    conn = db.get_conn()
    user = db.get_user_by_username(conn, inp.username.strip())
    if not user or not auth.verify_password(inp.password, user["password_hash"]):
        conn.close()
        raise HTTPException(401, "Login fehlgeschlagen")
    token = auth.new_session_token()
    now = _now_iso()
    db.create_session(
        conn,
        auth.hash_token(token),
        user["id"],
        now,
        auth.session_expiry().isoformat(),
        request.headers.get("user-agent"),
    )
    db.touch_login(conn, user["id"], now)
    conn.close()
    response.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=auth.cookie_max_age(),
        httponly=True,
        secure=auth.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {"ok": True, "username": user["username"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        conn = db.get_conn()
        db.delete_session(conn, auth.hash_token(token))
        conn.close()
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    return {"username": user["username"] if user else None}


@app.get("/api/stats")
def stats(module: str = "organic"):
    module = _valid_module(module)
    modules = _module_catalog()
    conn = db.get_conn()
    now = _now_iso()
    st = db.deck_stats(conn, now, module)
    chapters = db.chapter_stats(conn, now, module)
    weaknesses = db.weakness_heatmap(conn, now, module)
    tags = db.tag_stats(conn, module)
    auto_quality = db.auto_quality_sweep(conn, module, now)
    quality = db.quality_summary(conn, module)
    today = _today_work_plan(conn, module, st, chapters, quality)
    xp = db.xp_summary(conn)
    streak = db.streak(conn)
    exam_score = _exam_score_projection(st, chapters, module)
    conn.close()
    return {
        "title": modules[module].get("full_title", modules[module].get("title", module)),
        "module": module,
        "modules": modules,
        "exam_date": EXAM_DATE.isoformat(),
        "days_until_exam": _days_left(),
        "anki": st,
        "chapters": chapters,
        "daily_goal": _daily_goal(st, chapters),
        "forecast": _forecast(st, chapters),
        "study_plan": _study_plan(st, chapters),
        "weaknesses": weaknesses,
        "tags": tags,
        "quality": quality,
        "today_plan": today,
        "auto_quality": {"moved": auto_quality},
        "exam_score": exam_score,
        "xp": xp,
        "streak": streak,
    }


@app.get("/api/dashboard")
def dashboard(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    now = _now_iso()
    st = db.deck_stats(conn, now, module)
    chapters = db.chapter_stats(conn, now, module)
    auto_quality = db.auto_quality_sweep(conn, module, now)
    out = {
        "module": module,
        "stats": st,
        "chapters": chapters,
        "timeline": db.reviews_timeline(conn, 21, module),
        "forecast": _forecast(st, chapters),
        "study_plan": _study_plan(st, chapters),
        "weaknesses": db.weakness_heatmap(conn, now, module),
        "tags": db.tag_stats(conn, module),
        "quality": db.quality_summary(conn, module),
        "auto_quality": {"moved": auto_quality},
        "exam_score": _exam_score_projection(st, chapters, module),
        "xp": db.xp_summary(conn),
        "streak": db.streak(conn),
    }
    conn.close()
    return out


@app.get("/api/study/anki")
def study(limit: int = 30, kap: int | None = None, module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    cards = db.due_cards(conn, _now_iso(), limit, kap, module)
    conn.close()
    return {"deck": "anki", "module": module, "cards": cards}


@app.get("/api/study/repair")
def repair_study(limit: int = 30, module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    cards = db.exam_repair_cards(conn, module, max(5, min(limit, 60)))
    conn.close()
    return {"deck": "repair", "module": module, "cards": cards}


@app.get("/api/exam/recall")
def recall_exam(n: int = 20, mode: str = "mixed", module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    cards = db.random_cards(conn, max(5, min(n, 60)), mode if mode in ("mixed", "weak") else "mixed", module)
    conn.close()
    return {"deck": "exam", "mode": mode, "module": module, "cards": cards}


@app.get("/api/exam/open")
def open_exam(module: str = "organic", mode: str = "full"):
    module = _valid_module(module)
    mode = mode if mode in {"full", "weak", "mini", "explain"} else "full"
    count = 8 if mode == "explain" else 4 if mode == "mini" else 6
    minutes = 16 if mode == "explain" else 45 if mode == "mini" else 120
    conn = db.get_conn()
    cards = db.exam_candidates(conn, module, 160, "weak" if mode in {"weak", "mini", "explain"} else "mixed")
    selected = _pick_balanced(cards, module, count)
    conn.close()
    return {
        "id": f"{module}-{mode}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "module": module,
        "mode": mode,
        "title": "Kann ich erklaeren?" if mode == "explain" else "Schwaechen-Mini-Pruefung" if mode == "mini" else "Offene Pruefungssimulation",
        "minutes": minutes,
        "total_points": len(selected) * 4,
        "questions": [_exam_question(card, i + 1, module) for i, card in enumerate(selected)],
    }


@app.get("/api/exam/formulas")
def formula_exam(module: str = "organic", n: int = 10):
    module = _valid_module(module)
    conn = db.get_conn()
    cards = db.exam_candidates(conn, module, max(20, min(n * 5, 120)), "weak", formula=True)
    selected = _pick_balanced(cards, module, max(4, min(n, 16)))
    conn.close()
    return {
        "id": f"{module}-formula-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "module": module,
        "mode": "formula",
        "title": "Skizzen- und Formeltrainer",
        "minutes": 35,
        "total_points": len(selected) * 4,
        "questions": [_exam_question(card, i + 1, module, formula=True) for i, card in enumerate(selected)],
    }


@app.get("/api/exam/prognosis")
def exam_prognosis(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    now = _now_iso()
    st = db.deck_stats(conn, now, module)
    chapters = db.chapter_stats(conn, now, module)
    out = _exam_score_projection(st, chapters, module)
    conn.close()
    return out


@app.get("/api/exam/archive")
def exam_archive(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    exams = []
    for exam in ARCHIVE_EXAMS.get(module, []):
        questions = []
        for q in exam["questions"]:
            questions.append({
                **q,
                "rubric": _rubric_for_prompts(q.get("prompts", []), q.get("points", 4)),
                "matches": _matching_cards(conn, module, q["topic"]),
            })
        exams.append({**exam, "questions": questions})
    conn.close()
    return {"module": module, "exams": exams}


@app.get("/api/exam/mastery")
def exam_mastery(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _all_mastery(conn, module)
    conn.close()
    return {"module": module, "topics": out}


@app.get("/api/exam/formula-checklist")
def formula_checklist(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _formula_checklist(conn, module)
    conn.close()
    return {"module": module, **out}


@app.get("/api/exam/final-plan")
def final_plan(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _final_plan(conn, module)
    conn.close()
    return {"module": module, **out}


@app.get("/api/exam/weekly-plan")
def weekly_plan(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _weekly_plan(conn, module)
    conn.close()
    return out


@app.get("/api/today")
def today_plan(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    now = _now_iso()
    st = db.deck_stats(conn, now, module)
    chapters = db.chapter_stats(conn, now, module)
    quality = db.quality_summary(conn, module)
    out = _today_work_plan(conn, module, st, chapters, quality)
    conn.close()
    return {"module": module, **out}


@app.get("/api/exam/history")
def exam_history(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _attempt_dashboard(conn, module)
    repair = db.exam_repair_cards(conn, module, 12)
    conn.close()
    return {"module": module, **out, "repair_queue": repair}


@app.post("/api/exam/archive/submit")
def submit_archive_correction(inp: ArchiveCorrectionSubmitIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    now = _now_iso()
    exam_meta = next((exam for exam in ARCHIVE_EXAMS.get(module, []) if exam["id"] == inp.exam_id), None)
    question_meta = {
        q["topic"]: q
        for q in (exam_meta or {}).get("questions", [])
    }
    weights = {"full": 1.0, "partial": 0.5, "miss": 0.0}
    earned = 0.0
    total = 0.0
    touched = 0
    attempt_questions = []
    for result in inp.results:
        ratio = weights.get(result.score, 0.0)
        confidence = _clean_confidence(result.confidence)
        error_types = _clean_error_types(result.error_types)
        rubric_scores = [score for score in result.rubric_scores if score in weights][:8]
        earned += ratio * 4
        total += 4
        meta = question_meta.get(result.topic, {})
        attempt_questions.append({
            "topic": result.topic,
            "block": "Archivfragen",
            "score": result.score,
            "pct": _score_from_label(result.score),
            "confidence": confidence,
            "error_types": error_types,
            "rubric_scores": rubric_scores,
            "card_ids": result.card_ids,
            "repair": result.score in {"partial", "miss"},
            "rubric": _rubric_for_prompts(meta.get("prompts", []), meta.get("points", 4)),
        })
        if result.score in {"partial", "miss"}:
            for card_id in result.card_ids[:6]:
                card = db.get_card(conn, card_id)
                if not card or card.get("module") != module:
                    continue
                reason = "archiv_partial" if result.score == "partial" else "archiv_miss"
                note = result.note or f"Archiv-Korrektur {result.topic}: {result.score}"
                db.add_quality_event(conn, card_id, module, "archive_correction", reason, note, now)
                for err in error_types:
                    db.add_quality_event(conn, card_id, module, "exam_error", f"exam_{err}", EXAM_ERROR_TYPES[err], now)
                if confidence == "sure":
                    db.add_quality_event(conn, card_id, module, "exam_error", "exam_confidence_trap", "Sicher gefuehlt, aber Punkte verloren", now)
                if result.score == "miss":
                    db.mark_card_needs_review(conn, card_id, note, now)
                touched += 1
    pct_score = round(earned / total * 100) if total else 0
    attempt_id = db.record_exam_attempt(
        conn,
        module,
        "archive",
        "archive",
        (exam_meta or {}).get("title", "Archivbogen"),
        inp.exam_id,
        round(earned, 1),
        round(total, 1),
        pct_score,
        inp.duration_seconds,
        {"questions": attempt_questions},
        now,
    )
    xp = db.add_xp_event(conn, max(8, round(earned * 3)), "archive_exam", f"Archiv-Korrektur: {pct_score}%", inp.exam_id, now)
    conn.close()
    return {"ok": True, "attempt_id": attempt_id, "earned": round(earned, 1), "total": round(total, 1), "pct": pct_score, "touched": touched, "xp": xp}


@app.post("/api/quality/autoprune")
def quality_autoprune(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    moved = db.auto_quality_sweep(conn, module, _now_iso())
    summary = db.quality_summary(conn, module)
    conn.close()
    return {"ok": True, "moved": moved, "quality": summary}


@app.get("/api/workshop")
def workshop(module: str = "organic", limit: int = 8):
    module = _valid_module(module)
    conn = db.get_conn()
    db.auto_quality_sweep(conn, module, _now_iso())
    out = _workshop_data(conn, module, max(3, min(limit, 20)))
    conn.close()
    return out


@app.post("/api/exam/open/submit")
def submit_open_exam(inp: OpenExamSubmitIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    total_points = 0.0
    earned = 0.0
    reviewed = 0
    attempt_questions = []
    for result in inp.results:
        card = db.get_card(conn, result.card_id)
        if not card or card.get("module") != module:
            continue
        confidence = _clean_confidence(result.confidence)
        error_types = _clean_error_types(result.error_types)
        weights = {"full": 1.0, "partial": 0.5, "miss": 0.0}
        values = [weights.get(score, 0.0) for score in result.sub_scores]
        if not values:
            values = [0.0]
        ratio = sum(values) / len(values)
        earned += ratio * 4
        total_points += 4
        rating = 4 if ratio >= .85 else 3 if ratio >= .6 else 2 if ratio >= .35 else 1
        elapsed = 0.0
        if card.get("last_review"):
            elapsed = max((now - datetime.fromisoformat(card["last_review"])).total_seconds() / 86400, 0.0)
        updated = sched.review(card, rating, now, max_interval_days=_max_fsrs_interval_days(now))
        db.apply_review(conn, result.card_id, updated, rating, elapsed, deck="open_exam")
        if rating == 1:
            db.add_quality_event(conn, result.card_id, module, "open_exam", "pruefung_miss", "In offener Pruefung nicht beantwortet", updated["last_review"])
        if ratio < .85:
            for err in error_types:
                db.add_quality_event(conn, result.card_id, module, "exam_error", f"exam_{err}", EXAM_ERROR_TYPES[err], updated["last_review"])
            if confidence == "sure":
                db.add_quality_event(conn, result.card_id, module, "exam_error", "exam_confidence_trap", "Sicher gefuehlt, aber Punkte verloren", updated["last_review"])
        attempt_questions.append({
            "card_id": result.card_id,
            "card_ids": [result.card_id],
            "title": _question_title(card),
            "topic": _question_title(card),
            "kap": card.get("kap"),
            "block": _exam_block(module, card.get("kap")),
            "score": "full" if ratio >= .85 else "partial" if ratio >= .35 else "miss",
            "pct": round(ratio * 100),
            "rating": rating,
            "confidence": confidence,
            "error_types": error_types,
            "sub_scores": result.sub_scores,
            "answer_note": result.answer_note[:4000],
            "repair": ratio < .85,
        })
        reviewed += 1
    moved = db.auto_quality_sweep(conn, module, _now_iso())
    pct_score = round((earned / total_points) * 100) if total_points else 0
    title = "Kann ich erklaeren?" if inp.mode == "explain" else "Skizzen- und Formeltrainer" if inp.mode == "formula" else "Schwaechen-Mini-Pruefung" if inp.mode == "mini" else "Offene Pruefungssimulation"
    attempt_id = db.record_exam_attempt(
        conn,
        module,
        "open",
        inp.mode,
        title,
        inp.exam_id,
        round(earned, 1),
        round(total_points, 1),
        pct_score,
        inp.duration_seconds,
        {"questions": attempt_questions, "auto_quality_moved": moved},
        now_iso,
    )
    xp = db.add_xp_event(conn, max(10, round(earned * 4)), "open_exam", f"Offene Pruefung: {pct_score}%", inp.mode, _now_iso())
    conn.close()
    return {
        "ok": True,
        "attempt_id": attempt_id,
        "reviewed": reviewed,
        "earned": round(earned, 1),
        "total": round(total_points, 1),
        "pct": pct_score,
        "auto_quality_moved": moved,
        "xp": xp,
    }


@app.get("/api/cards")
def cards(status: str = "needs_review", limit: int = 80, kap: int | None = None,
          q: str = "", module: str = "organic", tag: str = "", media: str = "all"):
    module = _valid_module(module)
    if status not in ("all", "active", "needs_review", "suspended"):
        raise HTTPException(400, "ungueltiger Status")
    if media not in ("all", "with_photo", "without_photo", "photo_recommended"):
        raise HTTPException(400, "ungueltiger Medienfilter")
    conn = db.get_conn()
    out = db.list_cards(conn, status, max(1, min(limit, 200)), kap, q.strip(), module, tag.strip(), media)
    conn.close()
    return out


@app.get("/api/triage")
def triage(module: str = "organic", limit: int = 10, tag: str = ""):
    module = _valid_module(module)
    conn = db.get_conn()
    out = db.triage_cards(conn, module, max(1, min(limit, 30)), tag.strip())
    conn.close()
    return out


@app.get("/api/cards/{card_id:path}")
def get_card(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return {"card": card}


@app.patch("/api/cards/{card_id:path}")
def edit_card(card_id: str, inp: CardEditIn):
    conn = db.get_conn()
    card = db.update_card(conn, card_id, inp.q, inp.a, inp.status, inp.review_note, _now_iso())
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return {"ok": True, "card": card}


@app.post("/api/cards/{card_id:path}/improve")
def improve_card(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    if not card:
        conn.close()
        raise HTTPException(404, "Karte nicht gefunden")
    improved = _improved_card_payload(card)
    updated = db.update_card(conn, card_id, improved["q"], improved["a"], "active", "", _now_iso())
    db.add_quality_event(conn, card_id, card.get("module", "organic"), "workshop", "auto_improved", "Karte automatisch pruefungsnah geglaettet", _now_iso())
    conn.close()
    return {"ok": True, "card": updated}


@app.post("/api/cards/{card_id:path}/triage")
def triage_card(card_id: str, inp: CardTriageIn):
    conn = db.get_conn()
    try:
        card = db.triage_card(conn, card_id, inp.action, _now_iso(), inp.q, inp.a, inp.review_note, inp.reason)
    except ValueError:
        conn.close()
        raise HTTPException(400, "ungueltige Aktion")
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return {"ok": True, "card": card}


@app.post("/api/cards/manual")
def add_manual_card(inp: ManualCardIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    card = db.add_manual_card(conn, inp.kap, inp.q, inp.a, inp.source, _now_iso(), module)
    xp = db.add_xp_event(conn, 15, "manual_card", "Manuelle Karte ergaenzt", card["id"], _now_iso())
    conn.close()
    return {"ok": True, "card": card, "xp": xp}


@app.get("/api/preview/{card_id:path}")
def preview(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return sched.preview(card, max_interval_days=_max_fsrs_interval_days())


@app.post("/api/review")
def review(inp: ReviewIn):
    conn = db.get_conn()
    card = db.get_card(conn, inp.card_id)
    if not card:
        conn.close()
        raise HTTPException(404, "Karte nicht gefunden")
    now = datetime.now(timezone.utc)
    elapsed = 0.0
    if card.get("last_review"):
        elapsed = max((now - datetime.fromisoformat(card["last_review"])).total_seconds() / 86400, 0.0)
    updated = sched.review(card, inp.rating, now, max_interval_days=_max_fsrs_interval_days(now))
    db.apply_review(conn, inp.card_id, updated, inp.rating, elapsed, deck=inp.source if inp.source == "exam" else "anki")
    if inp.feedback_reason:
        note = f"Lernfeedback: {inp.feedback_reason}"
        db.add_quality_event(conn, inp.card_id, card.get("module", "organic"), "review_feedback", inp.feedback_reason, note, updated["last_review"])
        if inp.feedback_reason in {"frage_unklar", "karte_schlecht"}:
            db.mark_card_needs_review(conn, inp.card_id, note, updated["last_review"])
    if inp.rating == 1:
        db.auto_quality_sweep(conn, card.get("module", "organic"), updated["last_review"])
    xp_amount = 6 + inp.rating * 3 + (5 if inp.rating >= 3 else 0)
    xp = db.add_xp_event(conn, xp_amount, "review", f"Karte bewertet: {inp.rating}", inp.card_id, updated["last_review"])
    conn.close()
    return {"ok": True, "xp": xp, **updated}


@app.post("/api/reset")
def reset():
    conn = db.get_conn()
    db.reset_progress(conn)
    conn.close()
    return {"ok": True}


@app.post("/api/uploads/photo")
async def upload_photo(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Foto ist zu gross")
    content_type, ext = _image_type(file.content_type or "", data)
    target_dir = UPLOAD_DIR / "cards"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    target = target_dir / filename
    target.write_bytes(data)
    url = f"/uploads/cards/{filename}"
    alt = _safe_alt_text(file.filename)
    return {
        "ok": True,
        "url": url,
        "content_type": content_type,
        "html": f'<img class="card-photo" src="{url}" alt="{escape(alt)}" loading="lazy">',
    }


@app.get("/login")
def login_page():
    return FileResponse(SPA_DIR / "index.html")


app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")


if SPA_DIR.exists():
    assets = SPA_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{path:path}")
def spa(path: str):
    target = SPA_DIR / path
    if target.exists() and target.is_file():
        return FileResponse(target)
    return FileResponse(SPA_DIR / "index.html")
