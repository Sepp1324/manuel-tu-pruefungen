from __future__ import annotations

import os
import json
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


class ManualCardIn(BaseModel):
    module: str = "organic"
    kap: int = Field(ge=1, le=11)
    q: str = Field(min_length=3)
    a: str = Field(min_length=3)
    source: str = "Manuell"


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
    xp = db.xp_summary(conn)
    streak = db.streak(conn)
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
        card = db.triage_card(conn, card_id, inp.action, _now_iso(), inp.q, inp.a, inp.review_note)
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
