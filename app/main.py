from __future__ import annotations

import os
import csv
import io
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth
import cache
import db
from fsrs import Scheduler

try:
    import httpx
except ImportError:  # httpx is optional; only needed for the LLM coach
    httpx = None

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
COACH_MODEL = os.environ.get("COACH_MODEL", "claude-haiku-4-5-20251001")
NOTIFY_TOKEN = os.environ.get("NOTIFY_TOKEN", "")


app = FastAPI(title="TU Chemie SR-Trainer")
app.add_middleware(GZipMiddleware, minimum_size=1024)
sched = Scheduler()

EXAM_DATE = date.fromisoformat(os.environ.get("EXAM_DATE", "2026-09-21"))
MODULE_EXAM_DATE_DEFAULTS = {
    "organic": "2026-09-21",
    "inorganic": "2026-09-29",
}
SEED_PATH = Path(__file__).parent / "seed_data.json"
SPA_DIR = Path(os.environ.get("SPA_DIR", Path(__file__).parent / "spa"))
if not SPA_DIR.exists() and (Path(__file__).parent.parent / "dist").exists():
    SPA_DIR = Path(__file__).parent.parent / "dist"
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024 * 1024)))
AUTO_QUALITY_TTL_SECONDS = int(os.environ.get("AUTO_QUALITY_TTL_SECONDS", "300"))
KNOWLEDGE_MAP_TTL_SECONDS = int(os.environ.get("KNOWLEDGE_MAP_TTL_SECONDS", "90"))
PHOTO_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|webp|gif)$", re.I)
PHOTO_URL_RE = re.compile(r"/uploads/cards/([^\"'\s<>]+)", re.I)
_AUTO_QUALITY_CACHE: dict[str, tuple[datetime, int]] = {}
_KNOWLEDGE_MAP_CACHE: dict[str, tuple[datetime, dict]] = {}
_REQUEST_METRICS: list[dict] = []
MAX_REQUEST_METRICS = 300

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

PUBLIC_EXACT = {"/healthz", "/login", "/api/auth/login", "/api/notify/digest"}
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


@lru_cache(maxsize=1)
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
        default_exam_date = payload.get("exam_date", EXAM_DATE.isoformat())
        modules = {}
        for key, value in payload["modules"].items():
            item = {"key": key, **value}
            item.setdefault("exam_date", MODULE_EXAM_DATE_DEFAULTS.get(key, default_exam_date))
            modules[key] = item
        return modules
    return {
        "organic": {
            "key": "organic",
            "title": "Organische Chemie",
            "full_title": payload.get("title", "Chemische Technologien Organischer Stoffe"),
            "exam_date": payload.get("exam_date", EXAM_DATE.isoformat()),
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


def _auto_quality_sweep_cached(conn, module: str, now_iso: str) -> int:
    if AUTO_QUALITY_TTL_SECONDS <= 0:
        return db.auto_quality_sweep(conn, module, now_iso)
    now = datetime.now(timezone.utc)
    cached = _AUTO_QUALITY_CACHE.get(module)
    if cached and (now - cached[0]).total_seconds() < AUTO_QUALITY_TTL_SECONDS:
        return 0
    moved = db.auto_quality_sweep(conn, module, now_iso)
    _AUTO_QUALITY_CACHE[module] = (now, moved)
    if moved:
        _KNOWLEDGE_MAP_CACHE.pop(module, None)
    return moved


RESPONSE_CACHE_TTL = int(os.environ.get("RESPONSE_CACHE_TTL", "10") or "10")


def _redis_json_cache(key: str, builder, ttl: int | None = None):
    """Full-response cache backed by Redis (with in-memory fallback).

    Falls closed: on any cache problem the builder is called directly, so a
    missing/broken Redis never breaks the endpoint.
    """
    cached = cache.get_json(key)
    if cached is not None:
        if isinstance(cached, dict):
            cached.setdefault("_cache", {})["hit"] = True
        return cached
    payload = builder()
    cache.set_json(key, payload, ttl or RESPONSE_CACHE_TTL)
    if isinstance(payload, dict):
        payload.setdefault("_cache", {})["hit"] = False
    return payload


def _invalidate_module_caches(module: str) -> None:
    _AUTO_QUALITY_CACHE.pop(module, None)
    _KNOWLEDGE_MAP_CACHE.pop(module, None)
    cache.delete_pattern(f"chem:*:{module}")


def _invalidate_all_caches() -> None:
    _AUTO_QUALITY_CACHE.clear()
    _KNOWLEDGE_MAP_CACHE.clear()
    cache.delete_pattern("chem:*")


def _record_request_metric(request: Request, status_code: int, elapsed_ms: float) -> None:
    path = request.url.path
    if not path.startswith("/api/"):
        return
    _REQUEST_METRICS.append({
        "path": path,
        "method": request.method,
        "status": status_code,
        "ms": round(elapsed_ms, 1),
        "at": datetime.now(timezone.utc).isoformat(),
    })
    if len(_REQUEST_METRICS) > MAX_REQUEST_METRICS:
        del _REQUEST_METRICS[:len(_REQUEST_METRICS) - MAX_REQUEST_METRICS]


def _performance_summary() -> dict:
    recent = list(_REQUEST_METRICS)
    by_path: dict[str, dict] = {}
    for item in recent:
        bucket = by_path.setdefault(item["path"], {"path": item["path"], "count": 0, "total_ms": 0.0, "max_ms": 0.0, "errors": 0, "samples": []})
        bucket["count"] += 1
        bucket["total_ms"] += item["ms"]
        bucket["max_ms"] = max(bucket["max_ms"], item["ms"])
        bucket["errors"] += 1 if item["status"] >= 500 else 0
        bucket["samples"].append(item["ms"])
    endpoints = []
    for bucket in by_path.values():
        samples = sorted(bucket.pop("samples"))
        p95 = samples[min(len(samples) - 1, int(len(samples) * .95))] if samples else 0
        endpoints.append({
            **bucket,
            "avg_ms": round(bucket["total_ms"] / max(bucket["count"], 1), 1),
            "p95_ms": round(p95, 1),
        })
    endpoints.sort(key=lambda item: (item["p95_ms"], item["avg_ms"]), reverse=True)
    assets = []
    asset_dir = SPA_DIR / "assets"
    if asset_dir.exists():
        for path in sorted(asset_dir.glob("*")):
            if path.is_file():
                assets.append({"name": path.name, "bytes": path.stat().st_size})
    return {
        "window": len(recent),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": endpoints[:12],
        "slowest": sorted(recent, key=lambda item: item["ms"], reverse=True)[:10],
        "assets": assets,
        "asset_bytes": sum(item["bytes"] for item in assets),
    }


def _exam_date(module: str = "organic") -> date:
    env_value = os.environ.get(f"{module.upper()}_EXAM_DATE")
    catalog_value = _module_catalog().get(module, {}).get("exam_date")
    fallback = MODULE_EXAM_DATE_DEFAULTS.get(module, EXAM_DATE.isoformat())
    raw = env_value or catalog_value or os.environ.get("EXAM_DATE") or fallback
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return date.fromisoformat(fallback)


def _days_left(module: str = "organic") -> int:
    return max((_exam_date(module) - db.app_today()).days, 0)


def _max_fsrs_interval_days(now: datetime | None = None, module: str = "organic") -> int:
    now = now or datetime.now(timezone.utc)
    return max((_exam_date(module) - now.date()).days, 0)


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


@app.middleware("http")
async def cache_static_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if response.status_code == 200 and path.startswith("/assets/"):
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    elif response.status_code == 200 and path.startswith("/uploads/"):
        response.headers.setdefault("Cache-Control", "private, max-age=3600")
    return response


@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers.setdefault("Server-Timing", f"app;dur={elapsed_ms:.1f}")
    _record_request_metric(request, response.status_code, elapsed_ms)
    return response


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


class CardImportIn(BaseModel):
    module: str = "organic"
    default_kap: int = Field(default=1, ge=1, le=11)
    source: str = "Import"
    format: str = Field(default="csv", pattern="^(csv|tsv|json)$")
    text: str = ""
    cards: list[dict] = Field(default_factory=list)
    dedupe: bool = True


class OpenExamResultIn(BaseModel):
    card_id: str
    sub_scores: list[str] = Field(default_factory=list)
    confidence: str = ""
    error_types: list[str] = Field(default_factory=list)
    answer_note: str = ""
    auto_score: int | None = Field(default=None, ge=0, le=100)
    auto_missing_terms: list[str] = Field(default_factory=list)
    auto_checklist: list[str] = Field(default_factory=list)


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
    ("source", "Quelle schwach", "Skriptanker, Quelle oder Herleitung ist nicht belastbar"),
    ("missing_context", "Kein Kontext", "Quelle, VO oder fachlicher Rahmen fehlt"),
    ("photo", "Foto empfohlen", "Struktur, Formel, Schema oder Mechanismus braucht ein Bild"),
    ("sketch", "Skizze erforderlich", "Formel- oder Strukturkarte aktiv skizzieren"),
    ("formula", "Formeln kaputt", "Chemische Formeln mit verlorenen Indizes reparieren"),
    ("extracted", "Extraktion holprig", "OCR-/HTML-/Folienreste in der Karte"),
    ("person_company", "Person/Firma", "Personen-, Firmen- oder Quellenrauschen"),
    ("lecture_info", "Vorlesungsinfo", "Organisatorische Vorlesungsinfos statt Fachstoff"),
    ("duplicate", "Duplikate", "Sehr aehnliche Karten zusammenfuehren oder deaktivieren"),
    ("nonsense", "Nonsense", "Zu wenig verwertbare Antwortpunkte"),
]
WORKSHOP_CATEGORY_LABELS = {key: label for key, label, _ in WORKSHOP_CATEGORIES}

KNOWLEDGE_DEPENDENCIES = {
    "organic": [
        ("Fossile Rohstoffe", "Raffinerie", "Rohstoffbasis fuer Raffinerieprozesse"),
        ("Raffinerie", "Polymere", "Olefine und Aromaten als Polymerbausteine"),
        ("Nachwachsende Rohstoffe", "Kohlenhydrate", "Biogene Rohstoffe fuer Zucker/Staerke"),
        ("Kohlenhydrate", "Cellulose", "Polysaccharid-Strukturen vergleichen"),
        ("Cellulose", "Farbstoffe", "Faser, Papier und Farbstoffanwendungen"),
        ("Polymere", "Kunststoffrecycling", "Polymerstruktur bestimmt Recyclingweg"),
    ],
    "inorganic": [
        ("Rohstoffe", "Metallurgie", "Erzaufbereitung als Vorstufe"),
        ("Metallurgie", "Eisen/Stahl", "Reduktion und Schlackenbildung anwenden"),
        ("Metallurgie", "Kupfer/Aluminium", "Pyro-/Hydrometallurgie vergleichen"),
        ("Rohstoffe", "Glas/Keramik", "Mineralische Rohstoffe als Basis"),
        ("Schwefel", "Chloralkali/Soda", "Grosschemische Stoffkreislaeufe vergleichen"),
        ("Stickstoff", "Schwefel", "Grosschemische Prozessparameter vergleichen"),
        ("Bindemittel", "Glas/Keramik", "Anorganische Werkstoffe und Sinter-/Abbindeprozesse"),
    ],
}


def _daily_goal(stats: dict, chapters: list[dict], module: str) -> dict:
    days = max(_days_left(module), 1)
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
        "date": db.app_today().isoformat(),
        "days_left": _days_left(module),
        "target": target,
        "completed": completed,
        "remaining": max(target - completed, 0),
        "progress_pct": progress,
        "label": label,
        "status": status,
        "message": message,
        "focus_chapters": focus,
    }


def _forecast(stats: dict, chapters: list[dict], module: str) -> dict:
    days = max(_days_left(module), 1)
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


def _study_plan(stats: dict, chapters: list[dict], module: str) -> dict:
    days = _days_left(module)
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
    daily_cards = min(120, max(20, (stats.get("due") or 0) + new_limit))
    return {
        "phase": phase,
        "title": title,
        "message": message,
        "new_cards_today": new_limit,
        "reviews_today": min(90, max(20, stats.get("due") or 0)),
        "daily_cards": daily_cards,
        "mini_exams_per_week": 3 if days > 21 else 5 if days > 7 else 7,
        "open_cards": open_cards,
        "focus": focus,
    }


def _strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</li>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", value).strip()


IMPORT_Q_KEYS = ("q", "frage", "question", "front", "vorderseite", "prompt")
IMPORT_A_KEYS = ("a", "antwort", "answer", "back", "rueckseite", "rückseite", "loesung", "lösung")
IMPORT_KAP_KEYS = ("kap", "vo", "chapter", "einheit", "lecture")
IMPORT_SOURCE_KEYS = ("source", "quelle", "skript", "origin")


def _import_signature(q: str, a: str) -> str:
    text = _strip_html(f"{q} {a}").lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()[:360]


def _import_value(row: dict, keys: tuple[str, ...]) -> str:
    normalized = {str(k).strip().lower().lstrip("\ufeff"): v for k, v in row.items()}
    for key in keys:
        if key in normalized and normalized[key] is not None:
            return str(normalized[key]).strip()
    return ""


def _import_kap(value: str, default: int) -> int:
    match = re.search(r"\d+", str(value or ""))
    if not match:
        return default
    return max(1, min(11, int(match.group(0))))


def _normalize_import_row(row: dict, default_kap: int, default_source: str, idx: int) -> tuple[dict | None, str | None]:
    q = _import_value(row, IMPORT_Q_KEYS)
    a = _import_value(row, IMPORT_A_KEYS)
    if len(q) < 3 or len(a) < 3:
        return None, f"Zeile {idx}: Frage oder Antwort fehlt"
    return {
        "kap": _import_kap(_import_value(row, IMPORT_KAP_KEYS), default_kap),
        "q": q,
        "a": a,
        "source": _import_value(row, IMPORT_SOURCE_KEYS) or default_source or "Import",
    }, None


def _parse_import_input(inp: CardImportIn) -> tuple[list[dict], list[str]]:
    raw_rows: list[dict] = []
    errors: list[str] = []
    if inp.cards:
        raw_rows = [row for row in inp.cards if isinstance(row, dict)]
    elif inp.text.strip():
        text = inp.text.strip()
        if inp.format == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return [], [f"JSON ungueltig: {exc.msg}"]
            if isinstance(payload, dict):
                payload = payload.get("cards") or payload.get("items") or []
            if not isinstance(payload, list):
                return [], ["JSON muss eine Liste oder {\"cards\": [...]} sein"]
            raw_rows = [row for row in payload if isinstance(row, dict)]
        else:
            sample = text[:2048]
            if inp.format == "tsv":
                delimiter = "\t"
            else:
                try:
                    delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
                except csv.Error:
                    delimiter = ","
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            raw_rows = [dict(row) for row in reader]
    else:
        return [], ["Keine Importdaten gefunden"]

    cards: list[dict] = []
    for idx, row in enumerate(raw_rows[:1000], start=1):
        card, error = _normalize_import_row(row, inp.default_kap, inp.source, idx)
        if error:
            errors.append(error)
            continue
        cards.append(card)
    if len(raw_rows) > 1000:
        errors.append("Maximal 1000 Karten pro Import; Rest wurde ignoriert")
    return cards, errors[:100]


def _dedupe_import_cards(conn, module: str, cards: list[dict]) -> tuple[list[dict], int]:
    rows = conn.execute(
        "SELECT payload FROM cards WHERE module=? AND deck='anki'",
        (module,),
    ).fetchall()
    seen = set()
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            continue
        sig = _import_signature(str(payload.get("q", "")), str(payload.get("a", "")))
        if sig:
            seen.add(sig)
    out = []
    skipped = 0
    for card in cards:
        sig = _import_signature(card["q"], card["a"])
        if sig in seen:
            skipped += 1
            continue
        seen.add(sig)
        out.append(card)
    return out, skipped


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


def _cards_photo_dir() -> Path:
    path = UPLOAD_DIR / "cards"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise HTTPException(503, "Fotopool-Verzeichnis ist nicht verfuegbar")
    return path


def _safe_photo_filename(filename: str) -> str:
    name = Path(filename).name
    if name != filename or not PHOTO_FILENAME_RE.fullmatch(name):
        raise HTTPException(400, "ungueltiger Dateiname")
    return name


def _photo_usage(conn) -> dict[str, list[dict]]:
    rows = conn.execute(
        """SELECT id, module, kap, subname, source, payload FROM cards
           WHERE deck='anki' AND payload LIKE '%/uploads/cards/%'"""
    ).fetchall()
    usage: dict[str, list[dict]] = {}
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            continue
        text = f"{payload.get('q', '')} {payload.get('a', '')}"
        for match in PHOTO_URL_RE.findall(text):
            filename = Path(match).name
            if not PHOTO_FILENAME_RE.fullmatch(filename):
                continue
            usage.setdefault(filename, []).append({
                "card_id": row["id"],
                "module": row["module"],
                "kap": row["kap"],
                "subname": row["subname"],
                "source": row["source"],
                "question": str(payload.get("q", ""))[:120],
            })
    return usage


def _photo_pool_item(path: Path, usage: dict[str, list[dict]]) -> dict:
    stat = path.stat()
    used_by = usage.get(path.name, [])
    return {
        "filename": path.name,
        "url": f"/uploads/cards/{path.name}",
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "used_count": len(used_by),
        "used_by": used_by[:12],
        "unused": len(used_by) == 0,
    }


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
        "formula_repair_available": card.get("formula_repair_available"),
        "source_anchor": card.get("source_anchor"),
        "issues": issues or [],
    }


def _formula_repair_available(q: str, a: str) -> bool:
    return db.normalize_chemical_formulas(q) != q or db.normalize_chemical_formulas(a) != a


def _row_to_workshop_card(row) -> dict:
    card = db.row_to_card(row)
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    raw_q = str(payload.get("q", ""))
    raw_a = str(payload.get("a", ""))
    card["formula_repair_available"] = _formula_repair_available(raw_q, raw_a)
    return card


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
    english = card.get("english_noise")
    if english is None:
        english = db.english_noise(card)
    if english:
        issues.append("english")
    if len(q) > 260 or len(a) > 950:
        issues.append("long")
    if not q.startswith("Kontext:") or "Quelle:" not in f"{q} {a}":
        issues.append("missing_context")
    if (card.get("source_anchor") or {}).get("score", 100) < 60:
        issues.append("source")
    recommended_photo = card.get("photo_recommended")
    if recommended_photo is None:
        recommended_photo = db.photo_recommended(card)
    if recommended_photo:
        issues.append("photo")
    required_sketch = card.get("sketch_required")
    if required_sketch is None:
        required_sketch = db.sketch_required(card)
    if required_sketch:
        issues.append("sketch")
    if card.get("formula_repair_available"):
        issues.append("formula")
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
    cards = [_row_to_workshop_card(r) for r in rows]
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


def _quality_audit(conn, module: str, limit: int = 12) -> dict:
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY status DESC, quality_checked_at ASC, lapses DESC, reps ASC, kap ASC, ord ASC
           LIMIT 900""",
        (module,),
    ).fetchall()
    items = []
    issue_counts: dict[str, int] = {}
    for row in rows:
        card = _row_to_workshop_card(row)
        issues = _card_issues(card)
        if not issues:
            continue
        for issue in issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        preview = _improved_card_payload(card)
        items.append({
            "card": _workshop_card(card, issues),
            "issues": issues,
            "preview": {
                "q": preview["q"],
                "a": preview["a"],
                "status": preview.get("status", "active"),
                "review_note": preview.get("review_note", ""),
            },
        })
        if len(items) >= limit:
            break
    return {
        "module": module,
        "items": items,
        "issue_counts": [{"issue": key, "label": WORKSHOP_CATEGORY_LABELS.get(key, key), "count": count} for key, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))],
    }


def _source_audit(conn, module: str, limit: int = 12) -> dict:
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY kap ASC, ord ASC
           LIMIT 1800""",
        (module,),
    ).fetchall()
    cards = [db.row_to_card(row, include_quality=False) for row in rows]
    anchors = [(card, card.get("source_anchor") or {}) for card in cards]
    weak = [(card, anchor) for card, anchor in anchors if anchor.get("score", 0) < 60]
    medium = [(card, anchor) for card, anchor in anchors if 60 <= anchor.get("score", 0) < 78]
    strong = [(card, anchor) for card, anchor in anchors if anchor.get("score", 0) >= 78]
    issue_counts: dict[str, int] = {}
    for _, anchor in anchors:
        for issue in anchor.get("issues") or []:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    weak.sort(key=lambda item: (item[1].get("score", 0), item[0].get("kap") or 99, item[0].get("ord") or 0))
    return {
        "module": module,
        "total": len(cards),
        "strong": len(strong),
        "medium": len(medium),
        "weak": len(weak),
        "avg_score": round(sum(anchor.get("score", 0) for _, anchor in anchors) / max(len(anchors), 1)),
        "issue_counts": [{"issue": key, "count": count} for key, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))],
        "items": [
            {
                "card": _workshop_card(card, _card_issues(card)),
                "anchor": anchor,
            }
            for card, anchor in weak[:limit]
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


def _formula_repaired_payload(card: dict) -> dict:
    payload = dict(card)
    payload["q"] = db.normalize_chemical_formulas(str(card.get("q", "")))
    payload["a"] = db.normalize_chemical_formulas(str(card.get("a", "")))
    return payload


def _summarized_card_payload(card: dict) -> dict:
    title = _question_title(card)
    context = _card_context(card)
    points = []
    for point in _answer_points(card.get("a", "")):
        cleaned = re.sub(r"(?i)\b(?:quelle|source):?.*$", "", point).strip(" -;:")
        if len(cleaned) >= 18 and cleaned not in points:
            points.append(cleaned)
    if len(points) < 3:
        points = _scaffold_for(card, points)
    points = points[:4]
    lis = "".join(f"<li>{escape(point)}</li>" for point in points)
    payload = dict(card)
    payload["q"] = (
        f"Kontext: {context}\n\n"
        f"Erlaeutern Sie {title}. Antworten Sie kompakt, aber pruefungsnah."
    )
    payload["a"] = (
        f"<b>Kurzantwort zu {escape(title)}:</b><ul>{lis}</ul>"
        "<b>Merke:</b> Definition/Prinzip, Ablauf oder Struktur, Bedingungen und Beispiel/Zweck abdecken."
        f"<br><br><span class='source'>Quelle: {escape(str(card.get('source') or 'Manuell'))}</span>"
    )
    payload["status"] = "active"
    payload["review_note"] = "Automatisch gekuerzt: bitte kurz gegen das Skript pruefen"
    return payload


def _mission_band(score: int) -> tuple[str, str, str]:
    if score >= 82:
        return ("ready", "pruefungsbereit", "Absichern und Tempo halten")
    if score >= 68:
        return ("steady", "stabilisieren", "Schwache Knoten gezielt schliessen")
    if score >= 50:
        return ("build", "aufbauen", "Taeglich Reviews plus eine offene Pruefungsfrage")
    return ("rescue", "aufholen", "Heute nur die groessten Blocker angreifen")


def _today_work_plan(conn, module: str, stats: dict, chapters: list[dict], quality: dict,
                     exam_score: dict | None = None) -> dict:
    due = stats.get("due") or 0
    new = stats.get("new") or 0
    exam_score = exam_score or _exam_score_projection(stats, chapters, module, quality)
    exam_date = _exam_date(module)
    days = max(_days_left(module), 1)
    focus = sorted(chapters, key=lambda c: (-c.get("weak_score", 0), c.get("kap") or 99))[:3]
    formula = _formula_checklist(conn, module)
    knowledge = _knowledge_map_cached(conn, module)
    knowledge_route = knowledge.get("route", [])
    workshop_open = min((quality.get("needs_review") or 0) + (quality.get("photo_recommended") or 0), 40)
    daily_new = 0 if days <= 7 else min(25, max(0, -(-new // max(days - 7, 1)))) if new else 0
    daily_reviews = min(100, max(20, due + daily_new))
    repair_cards = min(12, max(0, quality.get("needs_review") or 0))
    photo_cards = min(10, max(0, quality.get("photo_recommended") or 0))
    mini_exam = 1 if days <= 21 or due < 30 else 0
    score = int(exam_score.get("overall") or 0)
    band, band_label, band_action = _mission_band(score)
    tasks = [
        {"key": "due", "label": "Faellige Karten", "amount": daily_reviews, "route": "home", "detail": "Erst faellige Karten abarbeiten."},
        {"key": "weak", "label": "Schwaechen-VO", "amount": len(focus), "route": "dashboard", "detail": "Die staerksten Luecken gezielt wiederholen."},
        {"key": "workshop", "label": "Karten-Werkstatt", "amount": repair_cards or workshop_open, "route": "workshop", "detail": "Holprige Karten glaetten oder deaktivieren."},
        {"key": "formula", "label": "Skizzen/Formeln", "amount": len(formula.get("draw", [])), "route": "exam", "detail": "Struktur- und Formelbilder aktiv abrufen."},
        {"key": "photo", "label": "Foto-Queue", "amount": photo_cards, "route": "photos", "detail": "Struktur, Formel oder Schema visuell ergaenzen."},
        {"key": "mini_exam", "label": "Mini-Pruefung", "amount": mini_exam, "route": "exam", "detail": "Eine kurze offene Simulation mit Punkteschema."},
    ]
    if daily_new:
        tasks.insert(1, {"key": "new", "label": "Neue Karten", "amount": daily_new, "route": "home", "detail": "Nur dosiert neue Karten aufnehmen."})

    missions = []

    def add_mission(key: str, title: str, detail: str, amount: int, unit: str,
                    minutes: int, route: str, cta: str, priority: str = "mittel",
                    kap: int | None = None, deck: str | None = None,
                    done_when: str = "") -> None:
        if amount <= 0:
            return
        missions.append({
            "key": key,
            "title": title,
            "detail": detail,
            "amount": amount,
            "unit": unit,
            "minutes": minutes,
            "route": route,
            "cta": cta,
            "priority": priority,
            "kap": kap,
            "deck": deck,
            "done_when": done_when,
        })

    add_mission(
        "review_block",
        "Review-Block",
        "Faellige Karten zuerst, damit die Vergessenskurve heute nicht weiter auflaeuft.",
        daily_reviews,
        "Karten",
        25 if daily_reviews <= 40 else 40,
        "home",
        "Session starten",
        "hoch" if due else "mittel",
        deck="anki",
        done_when=f"{min(daily_reviews, max(due, 20))} Karten bewertet",
    )
    if focus:
        weak = focus[0]
        add_mission(
            "weak_chapter",
            f"Blocker-VO: VO{weak['kap']}",
            f"{weak['name']} ist aktuell der wichtigste Hebel fuer die Pruefungsreife.",
            max(8, min(18, weak.get("due", 0) + 6)),
            "Karten",
            18,
            "home",
            "VO lernen",
            "hoch",
            kap=weak.get("kap"),
            deck="anki",
            done_when="mindestens eine Karte mit Gut/Leicht abgeschlossen",
        )
    if knowledge_route:
        step = knowledge_route[0]
        add_mission(
            "knowledge_node",
            f"Landkarten-Knoten: {step['topic']}",
            step.get("action") or "Querverbindungen pruefen",
            1,
            "Knoten",
            12,
            "knowledge",
            "Landkarte oeffnen",
            "hoch" if step.get("status") == "critical" else "mittel",
            kap=step.get("kap"),
            done_when=step.get("detail", "Knoten einmal aktiv erklaert"),
        )
    add_mission(
        "exam_question",
        "Offene Pruefungsfrage",
        "Eine kurze Antwort im Beispielpruefungs-Stil schreiben und danach ehrlich bewerten.",
        1 if mini_exam else 2,
        "Frage",
        16,
        "exam",
        "Pruefungsmodus",
        "hoch" if score < 70 else "mittel",
        done_when="Antwort mit Definition, Prozess, Bedingungen und Beispiel gecheckt",
    )
    if repair_cards:
        add_mission(
            "repair_cards",
            "Qualitaets-Sprint",
            "Holprige Karten stoeren die Reifeprognose staerker als neue Karten helfen.",
            repair_cards,
            "Karten",
            14,
            "workshop",
            "Werkstatt",
            "mittel",
            done_when="schlechte Karten verbessert oder deaktiviert",
        )
    elif photo_cards:
        add_mission(
            "photo_queue",
            "Foto-/Skizzen-Sprint",
            "Strukturen, Formeln oder Schemata sichtbar machen statt im Text zu verstecken.",
            photo_cards,
            "Karten",
            14,
            "photos",
            "Fotopool",
            "mittel",
            done_when="mindestens ein Bild oder eine Skizze ergaenzt",
        )
    elif formula.get("draw"):
        add_mission(
            "formula_sprint",
            "Formel-Sprint",
            "Eine Formel, Struktur oder Reaktionsgleichung aktiv aus dem Kopf zeichnen.",
            min(6, len(formula.get("draw", []))),
            "Skizzen",
            10,
            "exam",
            "Formeltrainer",
            "mittel",
            done_when="Skizze aus dem Kopf geschafft",
        )

    missions = missions[:5]
    total_minutes = sum(m["minutes"] for m in missions)
    blockers = exam_score.get("blockers", [])[:5]
    if blockers:
        message = f"Heute: {blockers[0]['label']} zuerst, dann eine offene Pruefungsfrage."
    else:
        message = "Heute: Reife halten, eine kurze Pruefungsfrage und gezielte Wiederholung."
    return {
        "date": db.app_today().isoformat(),
        "exam_date": exam_date.isoformat(),
        "days_left": _days_left(module),
        "title": f"Tagesmission: {band_label}",
        "band": band,
        "readiness": {
            "score": score,
            "label": exam_score.get("label"),
            "band": band,
            "band_label": band_label,
            "action": band_action,
            "gap_to_ready": max(0, 80 - score),
        },
        "mission": {
            "minutes": total_minutes,
            "count": len(missions),
            "summary": f"{total_minutes} Minuten, {len(missions)} klare Schritte",
            "primary": missions[0]["title"] if missions else "Freie Wiederholung",
        },
        "missions": missions,
        "blockers": blockers,
        "knowledge_route": knowledge_route[:3],
        "workload": {
            "daily_cards": daily_reviews,
            "daily_new": daily_new,
            "due": due,
            "repair_cards": repair_cards,
            "photo_cards": photo_cards,
            "mini_exam": mini_exam,
            "backlog_per_day": -(-(new + due) // days) if new + due else 0,
        },
        "tasks": tasks,
        "focus": focus,
        "quality": {
            "needs_review": quality.get("needs_review", 0),
            "photo_recommended": quality.get("photo_recommended", 0),
            "workshop_open": workshop_open,
        },
        "message": message,
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
        "source_anchor": card.get("source_anchor"),
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


def _oral_prompts_for(card: dict, question: dict) -> list[dict]:
    title = question.get("title") or _question_title(card)
    subquestions = question.get("subquestions") or []
    prompts = [{
        "id": f"{question.get('idx', 0)}-oral-start",
        "label": "Einstieg",
        "prompt": f"Erklaeren Sie {title} frei und strukturiert, als waeren Sie gerade in der muendlichen Pruefung.",
        "focus": "Definition, Einordnung und roter Faden",
    }]
    for i, sub in enumerate(subquestions[:3], start=1):
        prompts.append({
            "id": f"{question.get('idx', 0)}-oral-follow-{i}",
            "label": f"Nachfrage {i}",
            "prompt": sub.get("prompt", "Ergaenzen Sie den fehlenden Teil."),
            "focus": sub.get("category", "Vertiefung"),
        })
    prompts.append({
        "id": f"{question.get('idx', 0)}-oral-transfer",
        "label": "Transfer",
        "prompt": "Nennen Sie einen typischen Fehler, eine wichtige Bedingung oder eine industrielle Anwendung dazu.",
        "focus": "Begruendung, Grenzen und Praxisbezug",
    })
    if question.get("sketch_required"):
        prompts.append({
            "id": f"{question.get('idx', 0)}-oral-sketch",
            "label": "Skizze",
            "prompt": "Skizzieren oder beschreiben Sie die relevante Formel, Struktur oder den Mechanismus.",
            "focus": "Visuelle/chemische Darstellung",
        })
    return prompts[:6]


def _component(label: str, score: float, weight: int, detail: str) -> dict:
    return {
        "label": label,
        "score": round(max(0, min(100, score))),
        "weight": weight,
        "detail": detail,
    }


def _exam_score_projection(stats: dict, chapters: list[dict], module: str,
                           quality: dict | None = None) -> dict:
    quality = quality or {}
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
            "status": "ready" if score >= 80 else "steady" if score >= 65 else "risk",
        })
    total_cards = max(stats.get("total") or 0, 1)
    seen = stats.get("seen") or 0
    due = stats.get("due") or 0
    new = stats.get("new") or 0
    hit_rate = stats.get("hit_rate")
    avg_stability = sum(ch.get("avg_stability") or 0 for ch in chapters) / max(len(chapters), 1)
    weakest = sorted(chapters, key=lambda ch: (-ch.get("weak_score", 0), ch.get("kap") or 99))[:3]
    weak_pressure = sum(ch.get("weak_score") or 0 for ch in weakest) / max(len(weakest), 1) if weakest else 0
    coverage_score = seen / total_cards * 100
    retention_score = hit_rate if hit_rate is not None else 45
    due_score = 100 - min(80, due / total_cards * 140)
    new_score = 100 - min(80, new / total_cards * 100)
    stability_score = min(100, avg_stability / 28 * 100)
    weakness_score = 100 - min(80, weak_pressure)
    quality_penalty = min(35, (quality.get("needs_review") or 0) * 2 + (quality.get("photo_recommended") or 0) * .8)
    block_balance = min((b["score"] for b in out), default=0)
    components = [
        _component("Abdeckung", coverage_score, 28, f"{seen}/{stats.get('total') or 0} Karten gesehen"),
        _component("Trefferquote", retention_score, 22, f"{hit_rate if hit_rate is not None else 45}% aus bisherigen Reviews"),
        _component("Wiederholungsdruck", due_score, 18, f"{due} faellige Karten"),
        _component("Neue Karten", new_score, 12, f"{new} Karten noch ungesehen"),
        _component("Stabilitaet", stability_score, 10, f"Durchschnitt {round(avg_stability, 1)} Tage"),
        _component("Schwaechen", weakness_score, 10, f"Top-Blocker-Score {round(weak_pressure)}"),
    ]
    weighted = sum(c["score"] * c["weight"] for c in components) / max(sum(c["weight"] for c in components), 1)
    block_penalty = max(0, 70 - block_balance) * .18 if out else 0
    overall = round(max(5, min(98, weighted - quality_penalty - block_penalty)))
    band, band_label, band_action = _mission_band(overall)
    blockers = []
    if due:
        blockers.append({
            "key": "due",
            "label": "Faellige Karten",
            "impact": min(100, round(due / total_cards * 140)),
            "detail": f"{due} Karten laufen gegen die Stabilitaet.",
            "route": "home",
        })
    if new:
        blockers.append({
            "key": "new",
            "label": "Ungesehener Stoff",
            "impact": min(100, round(new / total_cards * 100)),
            "detail": f"{new} Karten sind noch nicht aktiv abrufbar.",
            "route": "home",
        })
    for ch in weakest:
        if ch.get("weak_score", 0) <= 0:
            continue
        blockers.append({
            "key": f"kap-{ch.get('kap')}",
            "label": f"VO{ch.get('kap')} {ch.get('name')}",
            "impact": min(100, round(ch.get("weak_score", 0))),
            "detail": f"{ch.get('progress')}% gesehen, {ch.get('due')} faellig, Quote {ch.get('hit_rate') if ch.get('hit_rate') is not None else '-'}%",
            "route": "home",
            "kap": ch.get("kap"),
        })
    for b in out:
        if b["score"] < 65:
            blockers.append({
                "key": f"block-{b['block']}",
                "label": b["block"],
                "impact": 65 - b["score"],
                "detail": b["detail"],
                "route": "exam",
            })
    if quality.get("needs_review"):
        blockers.append({
            "key": "quality",
            "label": "Kartenqualitaet",
            "impact": min(100, (quality.get("needs_review") or 0) * 5),
            "detail": f"{quality.get('needs_review')} Karten brauchen Review.",
            "route": "workshop",
        })
    blockers.sort(key=lambda item: (-item.get("impact", 0), item["label"]))
    if blockers:
        next_step = f"{blockers[0]['label']} zuerst angehen, danach eine offene Pruefungsfrage."
    else:
        next_step = "Eine kurze Simulation starten und die Reifeprognose gegen echte Antworten pruefen."
    return {
        "overall": overall,
        "label": f"{max(overall - 8, 0)}-{min(overall + 8, 99)}%",
        "band": band,
        "band_label": band_label,
        "status": band_label,
        "action": band_action,
        "gap_to_ready": max(0, 80 - overall),
        "exam_date": _exam_date(module).isoformat(),
        "days_left": _days_left(module),
        "components": components,
        "blockers": blockers[:8],
        "blocks": sorted(out, key=lambda b: b["block"]),
        "next_step": next_step,
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
    exam_date = _exam_date(module)
    start = exam_date - timedelta(days=6)
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
        "exam_date": exam_date.isoformat(),
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


def _knowledge_status(score: int, due: int, needs_review: int, total: int) -> str:
    if total <= 0:
        return "unknown"
    if score < 45 or needs_review >= max(2, total * .3):
        return "critical"
    if score < 70 or due >= max(3, total * .25):
        return "shaky"
    if score >= 85 and due == 0 and needs_review == 0:
        return "secure"
    return "building"


def _card_due(card: dict, now_iso: str) -> bool:
    due = str(card.get("due") or "")
    return bool(due and due <= now_iso)


def _knowledge_map(conn, module: str) -> dict:
    now = _now_iso()
    chapters = db.chapter_stats(conn, now, module)
    chapter_names = {int(ch["kap"]): ch["name"] for ch in chapters if ch.get("kap") is not None}
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY lapses DESC, reps ASC, kap ASC, ord ASC
           LIMIT 1800""",
        (module,),
    ).fetchall()
    cards = [
        db.row_to_card(row, include_source_anchor=False, include_quality=False)
        for row in rows
    ]
    topics: dict[str, dict] = {}
    edge_counts: dict[tuple[str, str], dict] = {}

    def topic_bucket(name: str) -> dict:
        return topics.setdefault(name, {
            "id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "topic",
            "topic": name,
            "total": 0,
            "seen": 0,
            "due": 0,
            "needs_review": 0,
            "lapses": 0,
            "reps": 0,
            "chapters": set(),
            "cards": [],
        })

    for card in cards:
        tags = list(dict.fromkeys(str(tag).strip() for tag in (card.get("tags") or []) if str(tag).strip()))
        chapter_tag = db.CHAPTER_TAGS.get(module, {}).get(card.get("kap"))
        if chapter_tag and chapter_tag not in tags:
            tags.insert(0, chapter_tag)
        tags = tags[:5] or [chapter_names.get(card.get("kap"), f"VO{card.get('kap') or '?'}")]
        due = _card_due(card, now)
        compact_card = {
            "id": card["id"],
            "kap": card.get("kap"),
            "title": _question_title(card),
            "source": card.get("source") or card.get("subname") or "",
            "status": card.get("status", "active"),
            "due": due,
            "lapses": card.get("lapses", 0),
            "reps": card.get("reps", 0),
        }
        for tag in tags:
            bucket = topic_bucket(tag)
            bucket["total"] += 1
            bucket["seen"] += 1 if (card.get("reps") or 0) > 0 else 0
            bucket["due"] += 1 if due else 0
            bucket["needs_review"] += 1 if card.get("status") == "needs_review" else 0
            bucket["lapses"] += card.get("lapses", 0) or 0
            bucket["reps"] += card.get("reps", 0) or 0
            if card.get("kap") is not None:
                bucket["chapters"].add(int(card.get("kap")))
            if len(bucket["cards"]) < 8:
                bucket["cards"].append(compact_card)
        for i, source in enumerate(tags):
            for target in tags[i + 1:]:
                if source == target:
                    continue
                key = tuple(sorted((source, target)))
                edge = edge_counts.setdefault(key, {"source": key[0], "target": key[1], "weight": 0, "cards": []})
                edge["weight"] += 1
                if len(edge["cards"]) < 4:
                    edge["cards"].append(compact_card)

    nodes = []
    for topic, bucket in topics.items():
        total = max(bucket["total"], 1)
        exposure = bucket["seen"] / total * 100
        pressure = min(80, (bucket["due"] * 10 + bucket["needs_review"] * 16 + bucket["lapses"] * 4) / total)
        score = round(max(0, min(100, exposure * .72 + 28 - pressure)))
        status = _knowledge_status(score, bucket["due"], bucket["needs_review"], bucket["total"])
        chapters_list = sorted(bucket["chapters"])
        nodes.append({
            "id": bucket["id"],
            "topic": topic,
            "status": status,
            "score": score,
            "total": bucket["total"],
            "seen": bucket["seen"],
            "due": bucket["due"],
            "needs_review": bucket["needs_review"],
            "lapses": bucket["lapses"],
            "chapters": chapters_list,
            "chapter_label": ", ".join(f"VO{kap}" for kap in chapters_list[:4]) or "ohne VO",
            "cards": sorted(bucket["cards"], key=lambda c: (-int(c["due"]), -int(c["lapses"] or 0), int(c["reps"] or 0)))[:5],
        })
    nodes.sort(key=lambda item: (
        {"critical": 0, "shaky": 1, "building": 2, "secure": 3, "unknown": 4}.get(item["status"], 5),
        item["score"],
        -item["due"],
        item["topic"],
    ))

    node_topics = {node["topic"] for node in nodes}
    edges = [
        {
            **edge,
            "kind": "cooccurrence",
            "label": f"{edge['weight']} gemeinsame Karte(n)",
        }
        for edge in edge_counts.values()
        if edge["weight"] >= 2
    ]
    for source, target, label in KNOWLEDGE_DEPENDENCIES.get(module, []):
        if source in node_topics and target in node_topics:
            edges.append({
                "source": source,
                "target": target,
                "weight": 3,
                "kind": "dependency",
                "label": label,
                "cards": [],
            })
    edges.sort(key=lambda item: (item["kind"] != "dependency", -item["weight"], item["source"], item["target"]))

    route = []
    for idx, node in enumerate(nodes[:8], start=1):
        if node["status"] == "secure":
            continue
        action = "Grundlagen klaeren" if node["score"] < 45 else "Pruefungsnah festigen" if node["due"] or node["needs_review"] else "Querverbindungen pruefen"
        route.append({
            "step": idx,
            "topic": node["topic"],
            "status": node["status"],
            "score": node["score"],
            "action": action,
            "detail": f"{node['due']} faellig, {node['needs_review']} im Review, {node['total']} Karten",
            "kap": node["chapters"][0] if node["chapters"] else None,
        })
    if not route and nodes:
        route.append({
            "step": 1,
            "topic": nodes[0]["topic"],
            "status": nodes[0]["status"],
            "score": nodes[0]["score"],
            "action": "Generalprobe",
            "detail": "Alle grossen Knoten wirken stabil; mit offener Pruefung absichern.",
            "kap": nodes[0]["chapters"][0] if nodes[0]["chapters"] else None,
        })

    return {
        "module": module,
        "exam_date": _exam_date(module).isoformat(),
        "generated_at": now,
        "nodes": nodes[:24],
        "edges": edges[:36],
        "route": route[:6],
        "summary": {
            "critical": sum(1 for node in nodes if node["status"] == "critical"),
            "shaky": sum(1 for node in nodes if node["status"] == "shaky"),
            "secure": sum(1 for node in nodes if node["status"] == "secure"),
            "topics": len(nodes),
            "edges": len(edges),
        },
    }


def _knowledge_map_cached(conn, module: str) -> dict:
    if KNOWLEDGE_MAP_TTL_SECONDS <= 0:
        return _knowledge_map(conn, module)
    now = datetime.now(timezone.utc)
    cached = _KNOWLEDGE_MAP_CACHE.get(module)
    if cached and (now - cached[0]).total_seconds() < KNOWLEDGE_MAP_TTL_SECONDS:
        return cached[1]
    out = _knowledge_map(conn, module)
    _KNOWLEDGE_MAP_CACHE[module] = (now, out)
    return out


def _weekly_plan(conn, module: str) -> dict:
    today = db.app_today()
    exam_date = _exam_date(module)
    start = today if today <= exam_date else exam_date
    weaknesses = db.weakness_heatmap(conn, _now_iso(), module)
    focus = [f"VO{w['kap']} {w['name']}" for w in weaknesses[:8]]
    weeks = []
    current = start
    idx = 0
    while current <= exam_date and len(weeks) < 14:
        end = min(current + timedelta(days=6), exam_date)
        days_to_exam = max((exam_date - end).days, 0)
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
        "exam_date": exam_date.isoformat(),
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


@app.get("/api/performance")
def performance():
    payload = _performance_summary()
    db_path = Path(db.DB_PATH)
    payload["db"] = {
        "path": str(db_path),
        "bytes": db_path.stat().st_size if db_path.exists() else 0,
    }
    return payload


@app.get("/api/stats")
def stats(module: str = "organic"):
    module = _valid_module(module)

    def build():
        modules = _module_catalog()
        conn = db.get_conn()
        now = _now_iso()
        st = db.deck_stats(conn, now, module)
        chapters = db.chapter_stats(conn, now, module)
        weaknesses = db.weakness_heatmap(conn, now, module, chapters)
        tags = db.tag_stats(conn, module)
        auto_quality = _auto_quality_sweep_cached(conn, module, now)
        quality = db.quality_summary(conn, module)
        exam_score = _exam_score_projection(st, chapters, module, quality)
        today = _today_work_plan(conn, module, st, chapters, quality, exam_score)
        xp = db.xp_summary(conn)
        streak = db.streak(conn)
        exam_date = _exam_date(module)
        conn.close()
        return {
            "title": modules[module].get("full_title", modules[module].get("title", module)),
            "module": module,
            "modules": modules,
            "exam_date": exam_date.isoformat(),
            "days_until_exam": _days_left(module),
            "anki": st,
            "chapters": chapters,
            "daily_goal": _daily_goal(st, chapters, module),
            "forecast": _forecast(st, chapters, module),
            "study_plan": _study_plan(st, chapters, module),
            "weaknesses": weaknesses,
            "tags": tags,
            "quality": quality,
            "today_plan": today,
            "auto_quality": {"moved": auto_quality},
            "exam_score": exam_score,
            "xp": xp,
            "streak": streak,
        }

    return _redis_json_cache(f"chem:stats:{module}", build)


@app.get("/api/dashboard")
def dashboard(module: str = "organic"):
    module = _valid_module(module)

    def build():
        conn = db.get_conn()
        now = _now_iso()
        st = db.deck_stats(conn, now, module)
        chapters = db.chapter_stats(conn, now, module)
        auto_quality = _auto_quality_sweep_cached(conn, module, now)
        quality = db.quality_summary(conn, module)
        out = {
            "module": module,
            "stats": st,
            "chapters": chapters,
            "timeline": db.reviews_timeline(conn, 21, module),
            "forecast": _forecast(st, chapters, module),
            "study_plan": _study_plan(st, chapters, module),
            "weaknesses": db.weakness_heatmap(conn, now, module, chapters),
            "tags": db.tag_stats(conn, module),
            "quality": quality,
            "auto_quality": {"moved": auto_quality},
            "exam_score": _exam_score_projection(st, chapters, module, quality),
            "xp": db.xp_summary(conn),
            "streak": db.streak(conn),
        }
        conn.close()
        return out

    return _redis_json_cache(f"chem:dashboard:{module}", build)


@app.get("/api/notify/digest")
def notify_digest(request: Request, token: str = ""):
    # Token-geschuetzt (oeffentlicher Pfad, damit ein CronJob ohne Login zugreifen kann).
    header_token = request.headers.get("X-Token", "")
    provided = token or header_token
    if not NOTIFY_TOKEN or provided != NOTIFY_TOKEN:
        raise HTTPException(403, "ungueltiger oder fehlender Token")
    conn = db.get_conn()
    now = _now_iso()
    mods = _module_catalog()
    lines = []
    out_modules = []
    for module in ("organic", "inorganic"):
        st = db.deck_stats(conn, now, module)
        fb = db.fehlerbuch_summary(conn, module)
        days = _days_left(module)
        due = st.get("due") or 0
        new = (st.get("total") or 0) - (st.get("seen") or 0)
        title = mods[module]["title"]
        lines.append(f"{title}: noch {days} Tage · {due} faellig · {new} neu · {fb.get('open', 0)} Fehler offen")
        out_modules.append({"module": module, "days_left": days, "due": due,
                            "new": new, "open_mistakes": fb.get("open", 0)})
    streak = db.streak(conn)
    conn.close()
    text = "\n".join(lines) + f"\nStreak: {streak.get('current', 0)} Tage – dranbleiben!"
    return {"ok": True, "text": text, "modules": out_modules, "streak": streak.get("current", 0)}


@app.get("/api/runtime/storage")
def runtime_storage():
    return {
        "database": db.backend_name(),
        "cache": cache.health_info(),
        "response_cache_ttl": RESPONSE_CACHE_TTL,
    }


@app.get("/api/knowledge-map")
def knowledge_map(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _knowledge_map_cached(conn, module)
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


@app.get("/api/study/photos")
def photo_study(limit: int = 20, module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
             AND payload NOT LIKE '%<img%' AND payload NOT LIKE '%/uploads/cards/%'
           ORDER BY lapses DESC, reps ASC, kap ASC, ord ASC
           LIMIT 500""",
        (module,),
    ).fetchall()
    cards = []
    for row in rows:
        card = db.row_to_card(row)
        if card.get("photo_recommended") or card.get("sketch_required"):
            cards.append(card)
        if len(cards) >= max(5, min(limit, 40)):
            break
    conn.close()
    return {"deck": "photos", "module": module, "cards": cards}


@app.get("/api/exam/recall")
def recall_exam(n: int = 20, mode: str = "mixed", module: str = "organic"):
    module = _valid_module(module)
    count = max(5, min(n, 60))
    mode = mode if mode in ("mixed", "weak") else "mixed"
    conn = db.get_conn()
    cards = db.random_cards(conn, count, mode, module)
    conn.close()
    minutes = max(5, min(60, round(len(cards) * (1.1 if mode == "weak" else .85))))
    return {
        "deck": "exam",
        "mode": mode,
        "module": module,
        "title": "Schwachstellen-Drill" if mode == "weak" else "Pruefungs-Karten-Drill",
        "minutes": minutes,
        "cards": cards,
    }


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


@app.get("/api/exam/oral")
def oral_exam(module: str = "organic", n: int = 5):
    module = _valid_module(module)
    count = max(3, min(n, 8))
    conn = db.get_conn()
    cards = db.exam_candidates(conn, module, 180, "weak")
    selected = _pick_balanced(cards, module, count)
    conn.close()
    questions = []
    for i, card in enumerate(selected):
        question = _exam_question(card, i + 1, module)
        question["question"] = f"Muendliche Pruefung: {question['title']}"
        question["oral_prompts"] = _oral_prompts_for(card, question)
        question["points"] = 4
        questions.append(question)
    minutes = max(12, min(45, len(questions) * 5))
    return {
        "id": f"{module}-oral-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "module": module,
        "mode": "oral",
        "title": "Muendlicher Pruefermodus",
        "minutes": minutes,
        "total_points": len(questions) * 4,
        "questions": questions,
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
    quality = db.quality_summary(conn, module)
    out = _exam_score_projection(st, chapters, module, quality)
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
    exam_score = _exam_score_projection(st, chapters, module, quality)
    out = _today_work_plan(conn, module, st, chapters, quality, exam_score)
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
                db.log_mistake(conn, card_id, module, "exam",
                               f"Pruefung {result.topic}: {result.score}", now)
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
    _invalidate_module_caches(module)
    return {"ok": True, "attempt_id": attempt_id, "earned": round(earned, 1), "total": round(total, 1), "pct": pct_score, "touched": touched, "xp": xp}


@app.post("/api/quality/autoprune")
def quality_autoprune(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    moved = db.auto_quality_sweep(conn, module, _now_iso())
    summary = db.quality_summary(conn, module)
    conn.close()
    if moved:
        _invalidate_module_caches(module)
    return {"ok": True, "moved": moved, "quality": summary}


@app.get("/api/quality/audit")
def quality_audit(module: str = "organic", limit: int = 12):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _quality_audit(conn, module, max(3, min(limit, 30)))
    conn.close()
    return out


@app.get("/api/source-audit")
def source_audit(module: str = "organic", limit: int = 12):
    module = _valid_module(module)
    conn = db.get_conn()
    out = _source_audit(conn, module, max(3, min(limit, 30)))
    conn.close()
    return out


@app.get("/api/workshop")
def workshop(module: str = "organic", limit: int = 8):
    module = _valid_module(module)
    conn = db.get_conn()
    moved = db.auto_quality_sweep(conn, module, _now_iso())
    out = _workshop_data(conn, module, max(3, min(limit, 20)))
    conn.close()
    if moved:
        _invalidate_module_caches(module)
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
        updated = sched.review(card, rating, now, max_interval_days=_max_fsrs_interval_days(now, module))
        db.apply_review(conn, result.card_id, updated, rating, elapsed, deck="open_exam")
        if rating == 1:
            db.add_quality_event(conn, result.card_id, module, "open_exam", "pruefung_miss", "In offener Pruefung nicht beantwortet", updated["last_review"])
        auto_missing = [str(term).strip() for term in result.auto_missing_terms if str(term).strip()][:12]
        if result.auto_score is not None and result.auto_score < 65:
            reason = "pruefung_miss" if result.auto_score < 40 else "archiv_partial"
            note = f"Antwortpruefung 2.0: {result.auto_score}%"
            if auto_missing:
                note += f"; fehlt: {', '.join(auto_missing[:6])}"
            db.add_quality_event(conn, result.card_id, module, "answer_review", reason, note, updated["last_review"])
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
            "auto_score": result.auto_score,
            "auto_missing_terms": auto_missing,
            "auto_checklist": [str(item).strip() for item in result.auto_checklist if str(item).strip()][:8],
            "answer_note": result.answer_note[:4000],
            "repair": ratio < .85,
        })
        reviewed += 1
    moved = db.auto_quality_sweep(conn, module, _now_iso())
    pct_score = round((earned / total_points) * 100) if total_points else 0
    title = "Muendlicher Pruefermodus" if inp.mode == "oral" else "Kann ich erklaeren?" if inp.mode == "explain" else "Skizzen- und Formeltrainer" if inp.mode == "formula" else "Schwaechen-Mini-Pruefung" if inp.mode == "mini" else "Offene Pruefungssimulation"
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
    xp_label = "Pruefermodus" if inp.mode == "oral" else "Offene Pruefung"
    xp = db.add_xp_event(conn, max(10, round(earned * 4)), "open_exam", f"{xp_label}: {pct_score}%", inp.mode, _now_iso())
    conn.close()
    _invalidate_module_caches(module)
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
          q: str = "", module: str = "organic", tag: str = "", media: str = "all",
          sort: str = "default"):
    module = _valid_module(module)
    if status not in ("all", "active", "needs_review", "suspended"):
        raise HTTPException(400, "ungueltiger Status")
    if media not in ("all", "with_photo", "without_photo", "photo_recommended"):
        raise HTTPException(400, "ungueltiger Medienfilter")
    if sort not in ("default", "updated", "updated_asc"):
        raise HTTPException(400, "ungueltige Sortierung")
    conn = db.get_conn()
    out = db.list_cards(conn, status, max(1, min(limit, 200)), kap, q.strip(), module, tag.strip(), media, sort)
    conn.close()
    return out


@app.get("/api/triage")
def triage(module: str = "organic", limit: int = 10, tag: str = ""):
    module = _valid_module(module)
    conn = db.get_conn()
    out = db.triage_cards(conn, module, max(1, min(limit, 30)), tag.strip())
    conn.close()
    return out


@app.get("/api/cards/{card_id:path}/quality-preview")
def quality_preview(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    preview = _improved_card_payload(card)
    return {
        "ok": True,
        "issues": _card_issues(card),
        "preview": {
            "q": preview["q"],
            "a": preview["a"],
            "status": preview.get("status", "active"),
            "review_note": preview.get("review_note", ""),
        },
    }


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
    _invalidate_module_caches(card.get("module", "organic"))
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
    _invalidate_module_caches(card.get("module", "organic"))
    return {"ok": True, "card": updated}


@app.post("/api/cards/{card_id:path}/summarize")
def summarize_card(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    if not card:
        conn.close()
        raise HTTPException(404, "Karte nicht gefunden")
    summarized = _summarized_card_payload(card)
    updated = db.update_card(
        conn,
        card_id,
        summarized["q"],
        summarized["a"],
        summarized.get("status", "active"),
        summarized.get("review_note", ""),
        _now_iso(),
    )
    db.add_quality_event(conn, card_id, card.get("module", "organic"), "workshop", "summarized", "Karte automatisch gekuerzt", _now_iso())
    conn.close()
    _invalidate_module_caches(card.get("module", "organic"))
    return {"ok": True, "card": updated}


@app.post("/api/cards/{card_id:path}/repair-formulas")
def repair_card_formulas(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    if not card:
        conn.close()
        raise HTTPException(404, "Karte nicht gefunden")
    repaired = _formula_repaired_payload(card)
    updated = db.update_card(
        conn,
        card_id,
        repaired["q"],
        repaired["a"],
        repaired.get("status", card.get("status", "active")),
        repaired.get("review_note", card.get("review_note", "")),
        _now_iso(),
    )
    db.add_quality_event(conn, card_id, card.get("module", "organic"), "workshop", "formula_repaired", "Chemische Formelindizes repariert", _now_iso())
    conn.close()
    _invalidate_module_caches(card.get("module", "organic"))
    return {"ok": True, "card": updated}


@app.post("/api/workshop/repair-formulas")
def repair_formula_batch(module: str = "organic", limit: int = 120):
    module = _valid_module(module)
    limit = max(1, min(limit, 500))
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY updated_at DESC, kap ASC, ord ASC
           LIMIT 1500""",
        (module,),
    ).fetchall()
    fixed = 0
    now = _now_iso()
    for row in rows:
        if fixed >= limit:
            break
        try:
            payload = json.loads(row["payload"] or "{}")
        except json.JSONDecodeError:
            continue
        raw_q = str(payload.get("q", ""))
        raw_a = str(payload.get("a", ""))
        if not _formula_repair_available(raw_q, raw_a):
            continue
        card = db.row_to_card(row)
        db.update_card(conn, card["id"], card.get("q", ""), card.get("a", ""), card.get("status", "active"), card.get("review_note", ""), now)
        db.add_quality_event(conn, card["id"], module, "workshop", "formula_repaired", "Chemische Formelindizes im Batch repariert", now)
        fixed += 1
    conn.close()
    if fixed:
        _invalidate_module_caches(module)
    return {"ok": True, "fixed": fixed}


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
    _invalidate_module_caches(card.get("module", "organic"))
    return {"ok": True, "card": card}


@app.post("/api/cards/import/preview")
def preview_card_import(inp: CardImportIn):
    module = _valid_module(inp.module)
    cards, errors = _parse_import_input(inp)
    skipped_duplicates = 0
    if inp.dedupe and cards:
        conn = db.get_conn()
        cards, skipped_duplicates = _dedupe_import_cards(conn, module, cards)
        conn.close()
    return {
        "ok": True,
        "module": module,
        "valid": len(cards),
        "errors": errors,
        "skipped_duplicates": skipped_duplicates,
        "cards": cards[:30],
    }


@app.post("/api/cards/import")
def import_cards(inp: CardImportIn):
    module = _valid_module(inp.module)
    cards, errors = _parse_import_input(inp)
    conn = db.get_conn()
    skipped_duplicates = 0
    if inp.dedupe and cards:
        cards, skipped_duplicates = _dedupe_import_cards(conn, module, cards)
    if not cards:
        conn.close()
        raise HTTPException(400, "Keine gueltigen neuen Karten im Import")
    ids = db.add_imported_cards(conn, cards, _now_iso(), module)
    xp = db.add_xp_event(conn, min(500, max(20, len(ids) * 8)), "card_import", f"{len(ids)} Karten importiert", module, _now_iso())
    conn.close()
    _invalidate_module_caches(module)
    return {
        "ok": True,
        "imported": len(ids),
        "skipped_duplicates": skipped_duplicates,
        "errors": errors,
        "ids": ids[:20],
        "xp": xp,
    }


@app.post("/api/cards/manual")
def add_manual_card(inp: ManualCardIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    card = db.add_manual_card(conn, inp.kap, inp.q, inp.a, inp.source, _now_iso(), module)
    xp = db.add_xp_event(conn, 15, "manual_card", "Manuelle Karte ergaenzt", card["id"], _now_iso())
    conn.close()
    _invalidate_module_caches(module)
    return {"ok": True, "card": card, "xp": xp}


@app.get("/api/preview/{card_id:path}")
def preview(card_id: str):
    conn = db.get_conn()
    card = db.get_card(conn, card_id)
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return sched.preview(card, max_interval_days=_max_fsrs_interval_days(module=card.get("module", "organic")))


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
    updated = sched.review(card, inp.rating, now, max_interval_days=_max_fsrs_interval_days(now, card.get("module", "organic")))
    db.apply_review(conn, inp.card_id, updated, inp.rating, elapsed, deck=inp.source if inp.source == "exam" else "anki")
    if inp.feedback_reason:
        note = f"Lernfeedback: {inp.feedback_reason}"
        db.add_quality_event(conn, inp.card_id, card.get("module", "organic"), "review_feedback", inp.feedback_reason, note, updated["last_review"])
        if inp.rating == 1 or inp.feedback_reason in {"frage_unklar", "karte_schlecht"}:
            db.mark_card_needs_review(conn, inp.card_id, note, updated["last_review"])
    if inp.rating == 1:
        db.auto_quality_sweep(conn, card.get("module", "organic"), updated["last_review"])
        db.log_mistake(conn, inp.card_id, card.get("module", "organic"), "review",
                       "Im Trainer nicht gewusst", updated["last_review"])
    elif inp.rating >= 3:
        db.resolve_mistake(conn, inp.card_id, updated["last_review"])
    xp_amount = 6 + inp.rating * 3 + (5 if inp.rating >= 3 else 0)
    xp = db.add_xp_event(conn, xp_amount, "review", f"Karte bewertet: {inp.rating}", inp.card_id, updated["last_review"])
    conn.close()
    _invalidate_module_caches(card.get("module", "organic"))
    return {"ok": True, "xp": xp, **updated}


# ---------------------------------------------------------------------------
# Fehlerbuch (error book)
# ---------------------------------------------------------------------------

@app.get("/api/fehlerbuch")
def fehlerbuch(module: str = "organic", include_resolved: bool = False):
    module = _valid_module(module)
    conn = db.get_conn()
    entries = db.fehlerbuch_entries(conn, module, include_resolved)
    for e in entries:
        e["title"] = _question_title({"q": e.get("q", ""), "subname": e.get("subname")})
        e["points"] = _answer_points(e.get("a", ""))
    summary = db.fehlerbuch_summary(conn, module)
    conn.close()
    return {"module": module, "summary": summary, "entries": entries}


@app.post("/api/fehlerbuch/{card_id:path}/resolve")
def fehlerbuch_resolve(card_id: str):
    conn = db.get_conn()
    ok = db.resolve_mistake(conn, card_id, _now_iso())
    conn.close()
    return {"ok": ok, "card_id": card_id}


# ---------------------------------------------------------------------------
# Item analytics
# ---------------------------------------------------------------------------

@app.get("/api/item-analytics")
def item_analytics(module: str = "organic", limit: int = 40):
    module = _valid_module(module)
    conn = db.get_conn()
    out = db.item_analytics(conn, module, min(max(limit, 5), 120))
    conn.close()
    return {"module": module, **out}


# ---------------------------------------------------------------------------
# FSRS insights
# ---------------------------------------------------------------------------

@app.get("/api/fsrs-insights")
def fsrs_insights(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    out = db.fsrs_insights(conn, module)
    conn.close()
    return {"module": module, **out}


# ---------------------------------------------------------------------------
# Last-minute sheet (condensed cram sheet from weak chapters)
# ---------------------------------------------------------------------------

@app.get("/api/last-minute-sheet")
def last_minute_sheet(module: str = "organic"):
    module = _valid_module(module)
    modules = _module_catalog()
    conn = db.get_conn()
    now = _now_iso()
    chapters = db.chapter_stats(conn, now, module)
    chapters_sorted = sorted(chapters, key=lambda c: (-c.get("weak_score", 0), c.get("kap") or 99))
    sheet = []
    for ch in chapters_sorted:
        kap = ch.get("kap")
        rows = conn.execute(
            """SELECT payload FROM cards
               WHERE module=? AND deck='anki' AND status='active' AND kap=?
               ORDER BY (last_review IS NULL) DESC, difficulty DESC, ord ASC LIMIT 6""",
            (module, kap),
        ).fetchall()
        facts = []
        for r in rows:
            card = db.row_to_card(r)
            title = _question_title(card)
            points = _answer_points(card.get("a", ""))
            if points:
                facts.append({"title": title, "point": points[0]})
        if facts:
            sheet.append({
                "kap": kap,
                "name": modules[module]["chapters"].get(str(kap), ch.get("name") or f"Kapitel {kap}"),
                "weak_score": ch.get("weak_score", 0),
                "facts": facts,
            })
    conn.close()
    return {"module": module, "chapters": sheet}


# ---------------------------------------------------------------------------
# Readiness plan
# ---------------------------------------------------------------------------

@app.get("/api/readiness-plan")
def readiness_plan(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    now = _now_iso()
    st = db.deck_stats(conn, now, module)
    chapters = db.chapter_stats(conn, now, module)
    quality = db.quality_summary(conn, module)
    exam_score = _exam_score_projection(st, chapters, module, quality)
    fb = db.fehlerbuch_summary(conn, module)
    conn.close()
    days = max(_days_left(module), 1)
    unseen = (st.get("total") or 0) - (st.get("seen") or 0)
    due = st.get("due") or 0
    # rough daily workload to be ready in time
    daily_new = -(-unseen // days) if unseen else 0
    daily_reviews = due + daily_new
    band = "risk"
    overall = int(exam_score.get("overall") or 0)
    if overall >= 80:
        band = "ready"
    elif overall >= 60:
        band = "steady"
    blocks = exam_score.get("blocks") or []
    focus = sorted(blocks, key=lambda b: b.get("score", 0))[:3]
    milestones = []
    for b in sorted(blocks, key=lambda b: b.get("score", 0)):
        milestones.append({
            "block": b.get("block"),
            "score": b.get("score"),
            "status": b.get("status"),
            "action": "Grundlagen sichern" if b.get("score", 0) < 55 else
                      "Prüfungsfragen üben" if b.get("score", 0) < 80 else "Halten & wiederholen",
        })
    # Bestehens-Prognose nach der echten Pruefungsregel:
    # mindestens 50 % in JEDEM Teil/Block UND insgesamt mindestens 50 %.
    PASS = 50
    parts = [{
        "name": b.get("block"),
        "score": int(b.get("score") or 0),
        "pass": int(b.get("score") or 0) >= PASS,
    } for b in sorted(blocks, key=lambda b: b.get("block") or "")]
    overall_pass = overall >= PASS
    all_parts_pass = bool(parts) and all(p["pass"] for p in parts)
    would_pass = all_parts_pass and overall_pass
    weakest_part = min(parts, key=lambda p: p["score"]) if parts else None
    if would_pass:
        verdict = "Aktuell auf Bestehenskurs – jeder Teil und die Gesamtquote liegen über 50 %."
    elif not overall_pass:
        verdict = "Gesamtquote noch unter 50 % – breit weiterlernen."
    else:
        failing = [p["name"] for p in parts if not p["pass"]]
        verdict = f"Gesamt reicht, aber unter 50 % in: {', '.join(failing)} – hier ist die Bestehensgrenze der Knackpunkt."
    pass_prediction = {
        "threshold": PASS,
        "parts": parts,
        "overall": overall,
        "overall_pass": overall_pass,
        "would_pass": would_pass,
        "weakest_part": weakest_part,
        "verdict": verdict,
        "rule": "≥50 % in jedem Teil und ≥50 % gesamt",
    }
    return {
        "module": module,
        "days_left": _days_left(module),
        "overall": overall,
        "band": band,
        "unseen": unseen,
        "due": due,
        "daily_new": daily_new,
        "daily_reviews": daily_reviews,
        "open_mistakes": fb.get("open", 0),
        "focus_blocks": focus,
        "milestones": milestones,
        "components": exam_score.get("components", []),
        "pass_prediction": pass_prediction,
    }


# ---------------------------------------------------------------------------
# Gamification: quests + level + badges
# ---------------------------------------------------------------------------

def _week_start_iso() -> str:
    today = db.app_today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _quest_defs(conn, module: str) -> list[dict]:
    today = db.app_today()
    week = _week_start_iso()
    # Tagesgrenzen in Wiener Zeit (Timestamps sind UTC): Wiener Mitternacht als UTC-Bound.
    # Pro Modul zaehlen: sonst wuerde ein modul-spezifischer Claim (siehe claim_quest)
    # dieselben modul-uebergreifenden Reviews in beiden Modulen als XP auszahlbar machen.
    day_reviews = db.reviews_count_since(conn, db.day_start_utc(today), module)
    week_reviews = db.reviews_count_since(conn, db.day_start_utc(date.fromisoformat(week)), module)
    week_exams = conn.execute(
        "SELECT COUNT(*) n FROM exam_attempts WHERE module=? AND local_date(created_at)>=?",
        (module, week),
    ).fetchone()["n"] or 0
    today = today.isoformat()
    fb = db.fehlerbuch_summary(conn, module)
    return [
        {"key": "daily_reviews", "period": "daily", "period_start": today,
         "title": "Tagesdrill: 20 Karten wiederholen", "goal": 20,
         "progress": min(day_reviews, 20), "raw": day_reviews, "xp": 40},
        {"key": "weekly_reviews", "period": "weekly", "period_start": week,
         "title": "Wochenpensum: 150 Karten", "goal": 150,
         "progress": min(week_reviews, 150), "raw": week_reviews, "xp": 120},
        {"key": "weekly_exam", "period": "weekly", "period_start": week,
         "title": "Eine Prüfung/Simulation diese Woche", "goal": 1,
         "progress": min(week_exams, 1), "raw": week_exams, "xp": 90},
        {"key": "clear_mistakes", "period": "weekly", "period_start": week,
         "title": "Fehlerbuch abbauen (max. 5 offen)", "goal": 1,
         "progress": 1 if fb.get("open", 0) <= 5 else 0, "raw": fb.get("open", 0), "xp": 80},
    ]


def _badges(xp_level: dict, streak: dict, fb: dict, st: dict) -> list[dict]:
    seen = st.get("seen") or 0
    total = st.get("total") or 1
    return [
        {"key": "level5", "label": "Level 5", "earned": xp_level.get("level", 1) >= 5},
        {"key": "streak7", "label": "7-Tage-Streak", "earned": streak.get("best", 0) >= 7},
        {"key": "streak30", "label": "30-Tage-Streak", "earned": streak.get("best", 0) >= 30},
        {"key": "half_deck", "label": "Halbes Deck gesehen", "earned": seen >= total / 2},
        {"key": "full_deck", "label": "Ganzes Deck gesehen", "earned": seen >= total},
        {"key": "clean_book", "label": "Fehlerbuch leer", "earned": fb.get("open", 0) == 0 and fb.get("total", 0) > 0},
    ]


@app.get("/api/gamification")
def gamification(module: str = "organic"):
    module = _valid_module(module)
    conn = db.get_conn()
    now = _now_iso()
    xp = db.xp_summary(conn)
    streak = db.streak(conn)
    st = db.deck_stats(conn, now, module)
    fb = db.fehlerbuch_summary(conn, module)
    quests = _quest_defs(conn, module)
    claimed = db.claimed_quests(conn, [q["period_start"] for q in quests], module)
    for q in quests:
        q["done"] = q["progress"] >= q["goal"]
        q["claimed"] = f"{q['key']}|{q['period_start']}" in claimed
    conn.close()
    return {
        "module": module,
        "xp": xp,
        "streak": streak,
        "quests": quests,
        "badges": _badges(xp, streak, fb, st),
    }


class QuestClaimIn(BaseModel):
    key: str
    module: str = "organic"


@app.post("/api/gamification/quests/claim")
def claim_quest(inp: QuestClaimIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    quests = {q["key"]: q for q in _quest_defs(conn, module)}
    quest = quests.get(inp.key)
    if not quest:
        conn.close()
        raise HTTPException(404, "Quest nicht gefunden")
    if quest["progress"] < quest["goal"]:
        conn.close()
        raise HTTPException(400, "Quest noch nicht abgeschlossen")
    ok = db.claim_quest(conn, quest["key"], quest["period_start"], module, quest["xp"], _now_iso())
    xp = db.xp_summary(conn)
    if ok:
        xp = db.add_xp_event(conn, quest["xp"], "quest", f"Quest: {quest['title']}", quest["key"], _now_iso())
    conn.close()
    return {"ok": ok, "xp": xp, "awarded": quest["xp"] if ok else 0}


# ---------------------------------------------------------------------------
# LLM coach (optional; needs ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

def _coach_available() -> bool:
    return bool(ANTHROPIC_API_KEY and httpx is not None)


def _call_anthropic(system: str, prompt: str, max_tokens: int = 700) -> str:
    if not _coach_available():
        raise HTTPException(503, "LLM-Coach ist nicht konfiguriert (ANTHROPIC_API_KEY fehlt).")
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": COACH_MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"LLM-Coach-Aufruf fehlgeschlagen: {exc}")


class CoachExplainIn(BaseModel):
    card_id: str
    question: str = ""


@app.get("/api/coach/status")
def coach_status():
    return {"available": _coach_available(), "model": COACH_MODEL if _coach_available() else None}


@app.post("/api/coach/explain")
def coach_explain(inp: CoachExplainIn):
    conn = db.get_conn()
    card = db.get_card(conn, inp.card_id)
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    q = _strip_html(card.get("q", "")).replace("Kontext:", "").strip()
    a = " ".join(_answer_points(card.get("a", "")))
    system = ("Du bist ein Chemie-Tutor fuer eine oesterreichische TU-Pruefung "
              "(Chemische Technologien organischer/anorganischer Stoffe). Antworte praegnant "
              "auf Deutsch, praxisnah und pruefungsorientiert. Nutze bei Bedarf Reaktionsgleichungen.")
    prompt = (f"Erklaere die folgende Pruefungsfrage verstaendlich (kurze Herleitung, Merksatz, "
              f"typische Fehler):\n\nFRAGE: {q}\n\nERWARTETE ANTWORTPUNKTE: {a}")
    text = _call_anthropic(system, prompt)
    return {"ok": True, "card_id": inp.card_id, "explanation": text}


_GRADE_STOP = {"eine", "einer", "eines", "einem", "einen", "oder", "und", "der", "die", "das",
               "den", "dem", "des", "mit", "fuer", "für", "auf", "aus", "bei", "zum", "zur",
               "wird", "werden", "sind", "kann", "durch", "sowie", "beim", "sich", "ihre",
               "ihren", "als", "bzw", "z.b", "etwa"}


def _offline_grade(answer: str, points: list[str]) -> dict:
    ans = answer.lower()
    hit, missed = [], []
    for p in points:
        # dict.fromkeys behaelt die Fundreihenfolge und dedupliziert. Ein set waere
        # PYTHONHASHSEED-abhaengig geordnet -> nach Neustart andere 8 Keywords, andere Note.
        words = [w for w in re.findall(r"[a-zA-Zäöüß0-9]{4,}", p.lower()) if w not in _GRADE_STOP]
        key = list(dict.fromkeys(words))[:8]
        overlap = sum(1 for w in key if w in ans)
        if key and overlap >= max(1, len(key) // 3):
            hit.append(p)
        else:
            missed.append(p)
    n = len(points) or 1
    ratio = len(hit) / n
    label = "full" if ratio >= 0.8 else "partial" if ratio >= 0.4 else "miss"
    return {"score_label": label, "score_pct": round(ratio * 100),
            "hit_points": hit, "missed_points": missed}


def _coerce_pct(value) -> int:
    """Modell liefert score_pct mal als 85, "85", "85%", "85 %" oder 0.85 - alles robust auf 0-100."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        m = re.search(r"-?\d+(?:[.,]\d+)?", str(value or ""))
        if not m:
            return 0
        num = float(m.group(0).replace(",", "."))
    if 0 < num < 1:  # Anteil (z.B. 0.85) statt Prozent; 1 bleibt 1%
        num *= 100
    return max(0, min(100, round(num)))


def _coerce_str_list(value) -> list[str]:
    """hit/missed koennen String, None oder Liste mit Nicht-Strings sein."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


class CoachGradeIn(BaseModel):
    card_id: str
    answer: str


@app.post("/api/coach/grade")
def coach_grade(inp: CoachGradeIn):
    conn = db.get_conn()
    card = db.get_card(conn, inp.card_id)
    if not card:
        conn.close()
        raise HTTPException(404, "Karte nicht gefunden")
    module = card.get("module", "organic")
    question = _question_title(card)
    points = _answer_points(card.get("a", ""))
    answer = (inp.answer or "").strip()
    if not answer:
        conn.close()
        raise HTTPException(400, "Keine Antwort angegeben")

    if not _coach_available():
        result = _offline_grade(answer, points)
        result["feedback"] = ("Naeherung ueber Stichwort-Abgleich (kein KI-Key konfiguriert). "
                              "Vergleiche deine Antwort mit den erwarteten Punkten unten.")
        offline = True
    else:
        system = ("Du bist Pruefer einer oesterreichischen TU-Chemie-Pruefung (offene Fragen). "
                  "Bewerte die Studierenden-Antwort streng aber fair gegen die erwarteten "
                  "Antwortpunkte. Beruecksichtige fachliche Korrektheit, nicht Formulierung. "
                  "Antworte AUSSCHLIESSLICH mit JSON.")
        prompt = (f"FRAGE: {question}\n\nERWARTETE ANTWORTPUNKTE:\n- "
                  + "\n- ".join(points)
                  + f"\n\nSTUDIERENDEN-ANTWORT:\n{answer}\n\n"
                  "Gib JSON mit exakt diesen Feldern zurueck:\n"
                  '{"score_label":"full|partial|miss","score_pct":<0-100>,'
                  '"hit":["<abgedeckter Punkt>"],"missed":["<fehlender Punkt>"],'
                  '"feedback":"<2-4 Saetze konkretes Feedback auf Deutsch>"}')
        text = _call_anthropic(system, prompt, max_tokens=700)
        parsed = _extract_json(text)
        if not parsed:
            # Modell hat kein sauberes JSON geliefert -> Offline-Naeherung + Rohtext
            result = _offline_grade(answer, points)
            result["feedback"] = text.strip()[:600] or "Keine Bewertung erhalten."
        else:
            label = parsed.get("score_label")
            if label not in {"full", "partial", "miss"}:
                label = "partial"
            result = {
                "score_label": label,
                "score_pct": _coerce_pct(parsed.get("score_pct")),
                "hit_points": _coerce_str_list(parsed.get("hit")),
                "missed_points": _coerce_str_list(parsed.get("missed")),
                "feedback": str(parsed.get("feedback") or ""),
            }
        offline = False

    if result["score_label"] == "miss":
        db.log_mistake(conn, inp.card_id, module, "grade", "Antwort-Check: verfehlt", _now_iso())
    elif result["score_label"] == "full":
        db.resolve_mistake(conn, inp.card_id, _now_iso())
    xp = db.add_xp_event(conn, {"full": 12, "partial": 6, "miss": 3}.get(result["score_label"], 4),
                         "grade", "Antwort-Check", inp.card_id, _now_iso())
    conn.close()
    _invalidate_module_caches(module)
    return {"ok": True, "offline": offline, "card_id": inp.card_id, "question": question,
            "model_points": points, "xp": xp, **result}


class CoachDiagnosisIn(BaseModel):
    module: str = "organic"


@app.post("/api/coach/error-diagnosis")
def coach_error_diagnosis(inp: CoachDiagnosisIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    entries = db.fehlerbuch_entries(conn, module, include_resolved=False)[:25]
    summary = db.fehlerbuch_summary(conn, module)
    modules = _module_catalog()
    conn.close()
    if not entries:
        return {"ok": True, "offline": not _coach_available(),
                "diagnosis": "Kein offener Fehler im Fehlerbuch. Weiter so!"}
    topics = [_question_title({"q": e.get("q", ""), "subname": e.get("subname")}) for e in entries]
    top_ch = ", ".join(
        f"{modules[module]['chapters'].get(str(c['kap']), 'Kapitel ' + str(c['kap']))} ({c['count']})"
        for c in summary.get("top_chapters", [])
    )
    if not _coach_available():
        # offline rule-based fallback
        lines = [
            f"{summary.get('open', 0)} offene Fehler, Schwerpunkt: {top_ch or 'verteilt'}.",
            "Empfehlung: die betroffenen Kapitel gezielt wiederholen und die Fehlerbuch-Karten "
            "abarbeiten, bis sie zweimal sicher sitzen.",
        ]
        return {"ok": True, "offline": True, "diagnosis": "\n".join(lines),
                "top_chapters": summary.get("top_chapters", [])}
    system = ("Du bist ein Lerncoach fuer eine Chemie-Pruefung. Analysiere die Fehlerthemen und "
              "gib eine kurze, konkrete Diagnose (Muster, wahrscheinliche Wissensluecken) plus 3 "
              "priorisierte Lernempfehlungen. Deutsch, stichpunktartig.")
    prompt = (f"Schwerpunkt-Kapitel der Fehler: {top_ch}.\n"
              f"Verfehlte Themen:\n- " + "\n- ".join(topics))
    text = _call_anthropic(system, prompt)
    return {"ok": True, "offline": False, "diagnosis": text,
            "top_chapters": summary.get("top_chapters", [])}


@app.post("/api/reset")
def reset():
    conn = db.get_conn()
    db.reset_progress(conn)
    conn.close()
    _invalidate_all_caches()
    return {"ok": True}


@app.get("/api/uploads/photos")
def photo_pool():
    photo_dir = _cards_photo_dir()
    conn = db.get_conn()
    usage = _photo_usage(conn)
    conn.close()
    files = []
    skipped = 0
    try:
        paths = list(photo_dir.iterdir())
    except OSError:
        raise HTTPException(503, "Fotopool-Verzeichnis ist nicht lesbar")
    for path in paths:
        try:
            if not path.is_file() or not PHOTO_FILENAME_RE.fullmatch(path.name):
                continue
            files.append(_photo_pool_item(path, usage))
        except OSError:
            skipped += 1
    files.sort(key=lambda item: item["modified_at"], reverse=True)
    return {
        "ok": True,
        "photos": files,
        "total": len(files),
        "unused": sum(1 for item in files if item["unused"]),
        "used": sum(1 for item in files if not item["unused"]),
        "bytes": sum(item["size"] for item in files),
        "skipped": skipped,
    }


@app.delete("/api/uploads/photos/{filename}")
def delete_photo(filename: str):
    safe_name = _safe_photo_filename(filename)
    target = _cards_photo_dir() / safe_name
    if not target.exists():
        raise HTTPException(404, "Foto nicht gefunden")
    conn = db.get_conn()
    usage = _photo_usage(conn)
    conn.close()
    if usage.get(safe_name):
        raise HTTPException(409, "Foto wird noch in Karten verwendet")
    try:
        target.unlink()
    except FileNotFoundError:
        raise HTTPException(404, "Foto nicht gefunden")
    except OSError:
        raise HTTPException(503, "Foto konnte nicht geloescht werden")
    return {"ok": True, "deleted": safe_name}


@app.post("/api/uploads/photos/cleanup")
def cleanup_unused_photos():
    photo_dir = _cards_photo_dir()
    conn = db.get_conn()
    usage = _photo_usage(conn)
    conn.close()
    deleted = []
    skipped = 0
    try:
        paths = list(photo_dir.iterdir())
    except OSError:
        raise HTTPException(503, "Fotopool-Verzeichnis ist nicht lesbar")
    for path in paths:
        try:
            if not path.is_file() or not PHOTO_FILENAME_RE.fullmatch(path.name):
                continue
            if usage.get(path.name):
                continue
            path.unlink()
            deleted.append(path.name)
        except FileNotFoundError:
            continue
        except OSError:
            skipped += 1
    return {"ok": True, "deleted": deleted, "count": len(deleted), "skipped": skipped}


@app.post("/api/uploads/photo")
async def upload_photo(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Leere Datei")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Foto ist zu gross")
    content_type, ext = _image_type(file.content_type or "", data)
    target_dir = _cards_photo_dir()
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
