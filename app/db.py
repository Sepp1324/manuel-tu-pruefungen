from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


DB_PATH = os.environ.get("SR_DB_PATH", "/data/organicsr.db")
JOURNAL_MODE = os.environ.get("SR_JOURNAL_MODE", "WAL")
SEED_PATH = Path(__file__).parent / "seed_data.json"


SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,
    module      TEXT NOT NULL DEFAULT 'organic',
    deck        TEXT NOT NULL DEFAULT 'anki',
    kap         INTEGER,
    sub         TEXT,
    subname     TEXT,
    source      TEXT,
    ord         INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'active',
    review_note TEXT NOT NULL DEFAULT '',
    updated_at  TEXT,
    payload     TEXT NOT NULL,
    state       INTEGER NOT NULL DEFAULT 0,
    stability   REAL    NOT NULL DEFAULT 0,
    difficulty  REAL    NOT NULL DEFAULT 0,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    last_review TEXT,
    due         TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_deck_due ON cards(deck, due);
CREATE INDEX IF NOT EXISTS idx_cards_kap ON cards(kap);

CREATE TABLE IF NOT EXISTS reviews (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id   TEXT NOT NULL,
    deck      TEXT NOT NULL,
    rating    INTEGER NOT NULL,
    reviewed_at TEXT NOT NULL,
    elapsed_days REAL,
    scheduled_minutes INTEGER,
    interval_due TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_at ON reviews(reviewed_at);

CREATE TABLE IF NOT EXISTS xp_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source     TEXT NOT NULL,
    amount     INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    ref_id     TEXT
);
CREATE INDEX IF NOT EXISTS idx_xp_events_created ON xp_events(created_at);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_login    TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    user_agent TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);
"""


def get_conn() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.executescript(AUTH_SCHEMA)
    migrate(conn)
    try:
        conn.execute(f"PRAGMA journal_mode={JOURNAL_MODE}")
    except sqlite3.DatabaseError:
        pass
    seed(conn)
    conn.commit()
    conn.close()


def migrate(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(cards)").fetchall()}
    migrations = {
        "module": "ALTER TABLE cards ADD COLUMN module TEXT NOT NULL DEFAULT 'organic'",
        "status": "ALTER TABLE cards ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
        "review_note": "ALTER TABLE cards ADD COLUMN review_note TEXT NOT NULL DEFAULT ''",
        "updated_at": "ALTER TABLE cards ADD COLUMN updated_at TEXT",
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_module ON cards(module)")
    conn.commit()


def init_auth_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(AUTH_SCHEMA)
    conn.commit()


def count_users(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def create_user(conn: sqlite3.Connection, username: str, password_hash: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO users(username, password_hash, created_at) VALUES(?,?,?)",
        (username, password_hash, created_at),
    )
    conn.commit()
    return cur.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str):
    return conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int):
    return conn.execute("SELECT id, username, created_at, last_login FROM users WHERE id=?", (user_id,)).fetchone()


def touch_login(conn: sqlite3.Connection, user_id: int, now_iso: str) -> None:
    conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso, user_id))
    conn.commit()


def create_session(conn: sqlite3.Connection, token_hash: str, user_id: int, created_iso: str,
                   expires_iso: str, user_agent: str | None = None) -> None:
    conn.execute(
        """INSERT INTO sessions(token_hash, user_id, created_at, expires_at, user_agent)
           VALUES(?,?,?,?,?)""",
        (token_hash, user_id, created_iso, expires_iso, user_agent),
    )
    conn.commit()


def get_session_user(conn: sqlite3.Connection, token_hash: str, now_iso: str):
    return conn.execute(
        """SELECT u.id, u.username, u.created_at, u.last_login
           FROM sessions s JOIN users u ON u.id=s.user_id
           WHERE s.token_hash=? AND s.expires_at>?""",
        (token_hash, now_iso),
    ).fetchone()


def refresh_session(conn: sqlite3.Connection, token_hash: str, expires_iso: str) -> None:
    conn.execute("UPDATE sessions SET expires_at=? WHERE token_hash=?", (expires_iso, token_hash))
    conn.commit()


def delete_session(conn: sqlite3.Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
    conn.commit()


def purge_expired_sessions(conn: sqlite3.Connection, now_iso: str) -> int:
    cur = conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now_iso,))
    conn.commit()
    return cur.rowcount


def seed(conn: sqlite3.Connection) -> int:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    added = 0
    for card in payload["cards"]:
        exists = conn.execute("SELECT 1 FROM cards WHERE id=?", (card["id"],)).fetchone()
        if exists:
            continue
        conn.execute(
            """INSERT INTO cards(id, module, deck, kap, sub, subname, source, ord, status, payload)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                card["id"],
                card.get("module", "organic"),
                card.get("deck", "anki"),
                card.get("kap"),
                card.get("sub"),
                card.get("subname"),
                card.get("source"),
                card.get("order", 0),
                card.get("status", "active"),
                json.dumps(card, ensure_ascii=False),
            ),
        )
        added += 1
    conn.execute(
        """INSERT INTO meta(key, value) VALUES('seed_title', ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (payload.get("title", "Chemie SR-Trainer"),),
    )
    conn.execute(
        """INSERT INTO meta(key, value) VALUES('exam_date', ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (payload.get("exam_date", "2026-09-21"),),
    )
    conn.commit()
    return added


def row_to_card(row: sqlite3.Row) -> dict:
    d = dict(row)
    payload = json.loads(d.pop("payload"))
    payload.update(d)
    return payload


def get_card(conn: sqlite3.Connection, card_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    return row_to_card(row) if row else None


def due_cards(conn: sqlite3.Connection, now_iso: str, limit: int = 30,
              kap: int | None = None, module: str = "organic") -> list[dict]:
    params: list[object] = [now_iso]
    kap_sql = ""
    if kap:
        kap_sql = " AND kap=?"
        params.append(kap)
    due = conn.execute(
        f"""SELECT * FROM cards
            WHERE module=? AND deck='anki' AND status='active' AND due IS NOT NULL AND due<=? {kap_sql}
            ORDER BY due ASC LIMIT ?""",
        (module, *params, limit),
    ).fetchall()
    remaining = max(limit - len(due), 0)
    new: list[sqlite3.Row] = []
    if remaining:
        new_params: list[object] = []
        kap_new_sql = ""
        if kap:
            kap_new_sql = " AND kap=?"
            new_params.append(kap)
        new = conn.execute(
            f"""SELECT * FROM cards
                WHERE module=? AND deck='anki' AND status='active' AND due IS NULL {kap_new_sql}
                ORDER BY kap ASC, ord ASC, id ASC LIMIT ?""",
            (module, *new_params, remaining),
        ).fetchall()
    return [row_to_card(r) for r in [*due, *new]]


def apply_review(conn: sqlite3.Connection, card_id: str, updated: dict, rating: int,
                 elapsed_days: float, deck: str = "anki") -> None:
    conn.execute(
        """UPDATE cards SET state=?, stability=?, difficulty=?, reps=?, lapses=?,
           last_review=?, due=? WHERE id=?""",
        (
            updated["state"], updated["stability"], updated["difficulty"], updated["reps"],
            updated["lapses"], updated["last_review"], updated["due"], card_id,
        ),
    )
    conn.execute(
        """INSERT INTO reviews(card_id, deck, rating, reviewed_at, elapsed_days,
           scheduled_minutes, interval_due) VALUES(?,?,?,?,?,?,?)""",
        (
            card_id, deck, rating, updated["last_review"], elapsed_days,
            updated.get("scheduled_minutes"), updated["due"],
        ),
    )
    conn.commit()


def deck_stats(conn: sqlite3.Connection, now_iso: str, module: str = "organic") -> dict:
    row = conn.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN due IS NULL THEN 1 ELSE 0 END) new,
                  SUM(CASE WHEN due IS NOT NULL AND due<=? THEN 1 ELSE 0 END) due,
                  SUM(CASE WHEN state=1 OR state=3 THEN 1 ELSE 0 END) learning,
                  SUM(CASE WHEN state=2 THEN 1 ELSE 0 END) review,
                  SUM(CASE WHEN last_review IS NOT NULL THEN 1 ELSE 0 END) seen
           FROM cards WHERE module=? AND deck='anki' AND status='active'""",
        (now_iso, module),
    ).fetchone()
    today = now_iso[:10]
    reviews_today = conn.execute(
        """SELECT COUNT(*) c FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=? AND substr(rv.reviewed_at,1,10)=?""",
        (module, today),
    ).fetchone()["c"]
    total_reviews = conn.execute(
        """SELECT COUNT(*) c FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=?""",
        (module,),
    ).fetchone()["c"]
    ok = conn.execute(
        """SELECT COUNT(*) c FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=? AND rv.rating>=3""",
        (module,),
    ).fetchone()["c"]
    return {
        "total": row["total"] or 0,
        "new": row["new"] or 0,
        "due": row["due"] or 0,
        "learning": row["learning"] or 0,
        "review": row["review"] or 0,
        "seen": row["seen"] or 0,
        "reviews_today": reviews_today or 0,
        "total_reviews": total_reviews or 0,
        "hit_rate": round(ok / total_reviews * 100) if total_reviews else None,
    }


def chapter_stats(conn: sqlite3.Connection, now_iso: str, module: str = "organic") -> list[dict]:
    rows = conn.execute(
        """SELECT kap, subname,
                  COUNT(*) total,
                  SUM(CASE WHEN due IS NULL THEN 1 ELSE 0 END) new,
                  SUM(CASE WHEN due IS NOT NULL AND due<=? THEN 1 ELSE 0 END) due,
                  SUM(CASE WHEN last_review IS NOT NULL THEN 1 ELSE 0 END) seen,
                  AVG(CASE WHEN last_review IS NOT NULL THEN stability ELSE NULL END) avg_stability
           FROM cards WHERE module=? AND deck='anki' AND status='active'
           GROUP BY kap, subname ORDER BY kap""",
        (now_iso, module),
    ).fetchall()
    out = []
    for r in rows:
        review_row = conn.execute(
            """SELECT COUNT(*) reviews,
                      SUM(CASE WHEN rating>=3 THEN 1 ELSE 0 END) correct,
                      SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) again
               FROM reviews rv
               JOIN cards c ON c.id=rv.card_id
               WHERE c.module=? AND c.kap=? AND c.status='active'""",
            (module, r["kap"]),
        ).fetchone()
        reviews = review_row["reviews"] or 0
        correct = review_row["correct"] or 0
        again = review_row["again"] or 0
        hit_rate = round(correct / reviews * 100) if reviews else None
        progress = round(((r["seen"] or 0) / (r["total"] or 1)) * 100)
        due = r["due"] or 0
        new = r["new"] or 0
        weak_score = round((100 - progress) * .45 + due * 1.4 + again * 2.5 + (100 - (hit_rate if hit_rate is not None else 60)) * .35)
        out.append({
            "kap": r["kap"],
            "name": r["subname"],
            "total": r["total"] or 0,
            "new": r["new"] or 0,
            "due": r["due"] or 0,
            "seen": r["seen"] or 0,
            "progress": progress,
            "avg_stability": round(r["avg_stability"] or 0, 1),
            "reviews": reviews,
            "again": again,
            "hit_rate": hit_rate,
            "weak_score": weak_score,
        })
    return out


def weakness_heatmap(conn: sqlite3.Connection, now_iso: str, module: str = "organic") -> list[dict]:
    rows = chapter_stats(conn, now_iso, module)
    return sorted(rows, key=lambda r: (-r["weak_score"], r["kap"]))


def random_cards(conn: sqlite3.Connection, limit: int = 20, mode: str = "mixed",
                 module: str = "organic") -> list[dict]:
    where = "module=? AND deck='anki' AND status='active'"
    if mode == "weak":
        where += " AND (lapses>0 OR reps=0 OR difficulty>=6.5)"
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {where}
            ORDER BY RANDOM() LIMIT ?""",
        (module, limit),
    ).fetchall()
    if mode == "weak" and not rows:
        rows = conn.execute(
            """SELECT * FROM cards
               WHERE module=? AND deck='anki' AND status='active'
               ORDER BY RANDOM() LIMIT ?""",
            (module, limit),
        ).fetchall()
    return [row_to_card(r) for r in rows]


def list_cards(conn: sqlite3.Connection, status: str = "needs_review", limit: int = 80,
               kap: int | None = None, q: str = "", module: str = "organic") -> dict:
    clauses = ["module=?", "deck='anki'"]
    params: list[object] = [module]
    if status != "all":
        if status == "needs_review":
            clauses.append("(status='needs_review' OR review_note<>'' OR payload LIKE '%[Seite%' OR payload LIKE '%_____%')")
        else:
            clauses.append("status=?")
            params.append(status)
    if kap:
        clauses.append("kap=?")
        params.append(kap)
    if q:
        clauses.append("payload LIKE ?")
        params.append(f"%{q}%")
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {where}
            ORDER BY CASE status WHEN 'needs_review' THEN 0 WHEN 'active' THEN 1 ELSE 2 END,
                     lapses DESC, reps ASC, kap ASC, ord ASC
            LIMIT ?""",
        (*params, limit),
    ).fetchall()
    summary_rows = conn.execute(
        "SELECT status, COUNT(*) c FROM cards WHERE module=? AND deck='anki' GROUP BY status",
        (module,),
    ).fetchall()
    summary = {"active": 0, "needs_review": 0, "suspended": 0}
    for r in summary_rows:
        summary[r["status"] or "active"] = r["c"] or 0
    return {"cards": [row_to_card(r) for r in rows], "summary": summary}


def update_card(conn: sqlite3.Connection, card_id: str, q: str, a: str,
                status: str, review_note: str, updated_at: str) -> dict | None:
    card = get_card(conn, card_id)
    if not card:
        return None
    payload = dict(card)
    payload["q"] = q
    payload["a"] = a
    payload["status"] = status
    conn.execute(
        """UPDATE cards SET status=?, review_note=?, updated_at=?, payload=?
           WHERE id=?""",
        (status, review_note, updated_at, json.dumps(payload, ensure_ascii=False), card_id),
    )
    conn.commit()
    return get_card(conn, card_id)


def add_manual_card(conn: sqlite3.Connection, kap: int, question: str, answer: str,
                    source: str, created_at: str, module: str = "organic") -> dict:
    chapter = conn.execute(
        "SELECT subname FROM cards WHERE module=? AND kap=? AND subname IS NOT NULL LIMIT 1",
        (module, kap),
    ).fetchone()
    subname = chapter["subname"] if chapter else f"VO{kap}"
    card_id = f"manual:{module}:{secrets.token_hex(8)}"
    max_ord = conn.execute(
        "SELECT COALESCE(MAX(ord),0) m FROM cards WHERE module=? AND kap=?",
        (module, kap),
    ).fetchone()["m"] or 0
    payload = {
        "id": card_id,
        "module": module,
        "deck": "anki",
        "kap": kap,
        "sub": f"VO{kap}",
        "subname": subname,
        "source": source or "Manuell",
        "kind": "manual",
        "q": question,
        "a": answer,
        "order": max_ord + 1,
        "status": "active",
    }
    conn.execute(
        """INSERT INTO cards(id, module, deck, kap, sub, subname, source, ord, status,
                             updated_at, payload)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            card_id, module, "anki", kap, payload["sub"], subname, payload["source"],
            max_ord + 1, "active", created_at, json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    return get_card(conn, card_id)


def reviews_timeline(conn: sqlite3.Connection, days: int = 21, module: str = "organic") -> list[dict]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        """SELECT substr(rv.reviewed_at,1,10) d, COUNT(*) reviews,
                  SUM(CASE WHEN rv.rating>=3 THEN 1 ELSE 0 END) correct
           FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=? AND rv.reviewed_at>=?
           GROUP BY d""",
        (module, start),
    ).fetchall()
    by_day = {r["d"]: dict(r) for r in rows}
    out = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        row = by_day.get(d, {"reviews": 0, "correct": 0})
        reviews = row["reviews"] or 0
        correct = row["correct"] or 0
        out.append({"date": d, "reviews": reviews, "correct": correct, "rate": round(correct / reviews * 100) if reviews else 0})
    return out


def reset_progress(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE cards SET state=0, stability=0, difficulty=0, reps=0, lapses=0,
           last_review=NULL, due=NULL"""
    )
    conn.execute("DELETE FROM reviews")
    conn.execute("DELETE FROM xp_events")
    conn.commit()


def add_xp_event(conn: sqlite3.Connection, amount: int, source: str, reason: str,
                 ref_id: str | None, created_at: str) -> dict:
    conn.execute(
        "INSERT INTO xp_events(created_at, source, amount, reason, ref_id) VALUES(?,?,?,?,?)",
        (created_at, source, amount, reason, ref_id),
    )
    conn.commit()
    return xp_summary(conn)


def xp_needed_for_level(level: int) -> int:
    return 350 + (level - 1) * 90


def xp_rank_name(level: int) -> str:
    if level >= 20:
        return "Synthese-Profi"
    if level >= 14:
        return "Reaktionsstratege"
    if level >= 9:
        return "Raffinerie-Routinier"
    if level >= 5:
        return "Polymer-Praktiker"
    return "Labor-Starter"


def xp_level(total_xp: int) -> dict:
    level = 1
    rest = max(total_xp, 0)
    needed = xp_needed_for_level(level)
    while rest >= needed:
        rest -= needed
        level += 1
        needed = xp_needed_for_level(level)
    return {
        "level": level,
        "rank": xp_rank_name(level),
        "total_xp": total_xp,
        "xp_in_level": rest,
        "xp_to_next": max(needed - rest, 0),
        "next_level_xp": needed,
        "progress_pct": round(rest / needed * 100) if needed else 100,
    }


def xp_summary(conn: sqlite3.Connection, limit: int = 8) -> dict:
    total = conn.execute("SELECT COALESCE(SUM(amount),0) xp FROM xp_events").fetchone()["xp"] or 0
    today = datetime.now(timezone.utc).date().isoformat()
    today_xp = conn.execute(
        "SELECT COALESCE(SUM(amount),0) xp FROM xp_events WHERE substr(created_at,1,10)=?",
        (today,),
    ).fetchone()["xp"] or 0
    events = conn.execute(
        "SELECT * FROM xp_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return {
        **xp_level(total),
        "today_xp": today_xp,
        "recent": [dict(e) for e in events],
    }


def streak(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT DISTINCT substr(reviewed_at,1,10) d FROM reviews ORDER BY d DESC"
    ).fetchall()
    days = {r["d"] for r in rows}
    cur = 0
    day = date.today()
    while day.isoformat() in days:
        cur += 1
        day -= timedelta(days=1)
    best = 0
    run = 0
    prev = None
    for d in sorted(days):
        current = date.fromisoformat(d)
        if prev and current == prev + timedelta(days=1):
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev = current
    return {"current": cur, "best": best, "active_today": date.today().isoformat() in days}
