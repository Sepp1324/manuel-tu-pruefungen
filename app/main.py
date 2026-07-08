from __future__ import annotations

import os
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
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


class OpenExamSubmitIn(BaseModel):
    module: str = "organic"
    mode: str = "full"
    results: list[OpenExamResultIn] = Field(default_factory=list)


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
        subquestions.append({"id": f"{idx}-{i}", "prompt": prompt, "points": point_value})
    if formula:
        question = f"Geben oder skizzieren Sie die pruefungsrelevanten Reaktions- oder Strukturformeln zu {title}."
    else:
        question = card.get("q", "")
        if question.startswith("Kontext:") and "\n\n" in question:
            question = question.split("\n\n", 1)[1]
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
        "points": 4,
        "answer": card.get("a", ""),
        "scaffold": _scaffold_for(card, points),
        "tags": card.get("tags", []),
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
    quality = db.quality_summary(conn, module)
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
    mode = mode if mode in {"full", "weak", "mini"} else "full"
    count = 4 if mode == "mini" else 6
    minutes = 45 if mode == "mini" else 120
    conn = db.get_conn()
    cards = db.exam_candidates(conn, module, 160, "weak" if mode in {"weak", "mini"} else "mixed")
    selected = _pick_balanced(cards, module, count)
    conn.close()
    return {
        "id": f"{module}-{mode}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "module": module,
        "mode": mode,
        "title": "Schwaechen-Mini-Pruefung" if mode == "mini" else "Offene Pruefungssimulation",
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
        "title": "Reaktions- und Strukturformel-Trainer",
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
            questions.append({**q, "matches": _matching_cards(conn, module, q["topic"])})
        exams.append({**exam, "questions": questions})
    conn.close()
    return {"module": module, "exams": exams}


@app.post("/api/exam/open/submit")
def submit_open_exam(inp: OpenExamSubmitIn):
    module = _valid_module(inp.module)
    conn = db.get_conn()
    now = datetime.now(timezone.utc)
    total_points = 0.0
    earned = 0.0
    reviewed = 0
    for result in inp.results:
        card = db.get_card(conn, result.card_id)
        if not card or card.get("module") != module:
            continue
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
        reviewed += 1
    pct_score = round((earned / total_points) * 100) if total_points else 0
    xp = db.add_xp_event(conn, max(10, round(earned * 4)), "open_exam", f"Offene Pruefung: {pct_score}%", inp.mode, _now_iso())
    conn.close()
    return {
        "ok": True,
        "reviewed": reviewed,
        "earned": round(earned, 1),
        "total": round(total_points, 1),
        "pct": pct_score,
        "xp": xp,
    }


@app.get("/api/cards")
def cards(status: str = "needs_review", limit: int = 80, kap: int | None = None,
          q: str = "", module: str = "organic", tag: str = ""):
    module = _valid_module(module)
    if status not in ("all", "active", "needs_review", "suspended"):
        raise HTTPException(400, "ungueltiger Status")
    conn = db.get_conn()
    out = db.list_cards(conn, status, max(1, min(limit, 200)), kap, q.strip(), module, tag.strip())
    conn.close()
    return out


@app.get("/api/triage")
def triage(module: str = "organic", limit: int = 10, tag: str = ""):
    module = _valid_module(module)
    conn = db.get_conn()
    out = db.triage_cards(conn, module, max(1, min(limit, 30)), tag.strip())
    conn.close()
    return out


@app.patch("/api/cards/{card_id:path}")
def edit_card(card_id: str, inp: CardEditIn):
    conn = db.get_conn()
    card = db.update_card(conn, card_id, inp.q, inp.a, inp.status, inp.review_note, _now_iso())
    conn.close()
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    return {"ok": True, "card": card}


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


@app.get("/login")
def login_page():
    return FileResponse(SPA_DIR / "index.html")


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
