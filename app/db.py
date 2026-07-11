from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path


DB_PATH = os.environ.get("SR_DB_PATH", "/data/organicsr.db")
JOURNAL_MODE = os.environ.get("SR_JOURNAL_MODE", "WAL")
SEED_PATH = Path(__file__).parent / "seed_data.json"

ENGLISH_ARTIFACT_RE = re.compile(
    r"(?i)("
    r"\btake-home messages\b|\bplastics recycling paths\b|"
    r"\bethylene polymerization\b|"
    r"\binput for new polymerization\b|\bfresh virgin polymers\b|\bvirgin polymers\b|"
    r"\bre[- ]use of the entire material\b|\bre[- ]use of the polymer chains\b|"
    r"\bpolymer chains\+fillers\+additives\+pigments\+contamination\b|"
    r"\bseparation, upgrading\b|\byoutube\b|\byou\.\s*tube\b|"
    r"\bfood packaging\b|\bmedical grades\b|\bexternal use\b|\binternal confidential\b|"
    r"\bglobal organization\b|\bcompany overview\b|\bheadquarters\b|\bmanufacturing sites\b|"
    r"\bpatent applications\b|\bownership of\b|\bleading innovation\b"
    r")"
)
ENGLISH_CARD_WORDS = {
    "the", "and", "with", "for", "from", "this", "that", "which", "between",
    "take", "home", "messages", "mechanical", "chemical", "plastics", "paths",
    "dissolution", "depolymerization", "polymerization", "polymerzation",
    "ethylene", "youtube", "input", "entire", "material", "chains", "fillers",
    "additives", "pigments", "contamination", "target", "fraction", "monomer",
    "molecule", "molecules", "often", "diverse", "mixture", "thereof", "need",
    "undergo", "further", "separation", "upgrading", "treatment", "conversion",
    "before", "potentially", "introduced", "processes", "make", "fresh", "virgin",
    "polymers", "compounded", "stabilizers", "company", "global", "headquarters",
    "manufacturing", "ownership", "innovation", "supporting", "reliable", "supply",
    "external", "internal", "confidential", "medical", "grades", "packaging",
}
GERMAN_CARD_WORDS = {
    "der", "die", "das", "und", "oder", "mit", "wird", "werden", "durch",
    "bei", "zur", "zum", "aus", "von", "fuer", "für", "als", "eine", "einer",
    "eines", "nicht", "nach", "vor", "verfahren", "prozess", "reaktion",
    "herstellung", "eigenschaften", "anwendung", "beispiel", "rohstoff",
    "kunststoff", "recycling", "polymerisation", "depolymerisation",
}
OLD_ENGLISH_ARTIFACT_NOTE = "Automatisch deaktiviert: englische Folien- oder Quellenartefakte"
ENGLISH_ARTIFACT_NOTE = "Auto-Review: englische Folien- oder Quellenartefakte pruefen"
ENGLISH_HOLD_NOTE = "Auto-Review: englische Karte aus dem Lernmodus genommen"

CHEM_FORMULA_REPAIRS = (
    (r"\bH\s+SO\b", "H<sub>2</sub>SO<sub>4</sub>"),
    (r"\bH\s+S\s+O\b", "H<sub>2</sub>S<sub>2</sub>O<sub>7</sub>"),
    (r"\bNa\s+S\s+O\b", "Na<sub>2</sub>S<sub>2</sub>O<sub>3</sub>"),
    (r"\bNa\s+SO\b", "Na<sub>2</sub>SO<sub>4</sub>"),
    (r"\bCu\.?\s+SO\b", "CuSO<sub>4</sub>"),
    (r"\bCa\.?\s+SO\b", "CaSO<sub>4</sub>"),
    (r"\bH\s+CO\b", "H<sub>2</sub>CO<sub>3</sub>"),
    (r"\bNa\s+CO\b", "Na<sub>2</sub>CO<sub>3</sub>"),
    (r"\bCa\.?\s+CO\b", "CaCO<sub>3</sub>"),
    (r"\bH\s+O\b", "H<sub>2</sub>O"),
    (r"\bH\s+S\b", "H<sub>2</sub>S"),
    (r"\bNH\b(?![A-Za-z0-9])", "NH<sub>3</sub>"),
    (r"\bSi\.?\s+O\b", "SiO<sub>2</sub>"),
    (r"\bAl\s+O\b", "Al<sub>2</sub>O<sub>3</sub>"),
    (r"\bFe\s+O\b", "Fe<sub>2</sub>O<sub>3</sub>"),
    (r"\bV\s+O\b", "V<sub>2</sub>O<sub>5</sub>"),
    (r"\bB\s+O\b", "B<sub>2</sub>O<sub>3</sub>"),
    (r"\bNa\s+O\b", "Na<sub>2</sub>O"),
    (r"\bK\s+O\b", "K<sub>2</sub>O"),
    (r"\bMg\.?\s+O\b", "MgO"),
    (r"\bCa\.?\s+O\b", "CaO"),
    (r"\bBa\.?\s+O\b", "BaO"),
    (r"\bPb\.?\s+O\b", "PbO"),
    (r"\bMn\.?\s+O\b", "MnO"),
)


def auto_deactivation_note(note: str | None) -> bool:
    text = str(note or "").strip()
    return text.startswith("Automatisch deaktiviert:")


def organic_context(card: dict) -> str:
    parts = ["Organische Chemie"]
    sub = str(card.get("sub") or "").strip()
    subname = str(card.get("subname") or "").strip()
    if sub or subname:
        parts.append(" ".join(x for x in (sub, subname) if x).strip())
    source = str(card.get("source") or "").strip()
    context = " / ".join(parts)
    if source:
        context = f"{context}. Quelle: {source}"
    return context


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
    quality_checked_at TEXT,
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
CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id);
CREATE INDEX IF NOT EXISTS idx_reviews_card_rating ON reviews(card_id, rating);

CREATE TABLE IF NOT EXISTS xp_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source     TEXT NOT NULL,
    amount     INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    ref_id     TEXT
);
CREATE INDEX IF NOT EXISTS idx_xp_events_created ON xp_events(created_at);

CREATE TABLE IF NOT EXISTS quality_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id    TEXT NOT NULL,
    module     TEXT NOT NULL,
    event_type TEXT NOT NULL,
    reason     TEXT NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quality_events_module ON quality_events(module, created_at);
CREATE INDEX IF NOT EXISTS idx_quality_events_card ON quality_events(card_id);

CREATE TABLE IF NOT EXISTS exam_attempts (
    id           TEXT PRIMARY KEY,
    module       TEXT NOT NULL,
    attempt_type TEXT NOT NULL,
    mode         TEXT NOT NULL,
    title        TEXT NOT NULL,
    ref_id       TEXT NOT NULL DEFAULT '',
    earned       REAL NOT NULL DEFAULT 0,
    total        REAL NOT NULL DEFAULT 0,
    pct          INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    payload      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exam_attempts_module ON exam_attempts(module, created_at);

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
        "quality_checked_at": "ALTER TABLE cards ADD COLUMN quality_checked_at TEXT",
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_module ON cards(module)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_module_deck_status_due ON cards(module, deck, status, due)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_module_deck_status_kap ON cards(module, deck, status, kap)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_card_rating ON reviews(card_id, rating)")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS quality_events (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id    TEXT NOT NULL,
        module     TEXT NOT NULL,
        event_type TEXT NOT NULL,
        reason     TEXT NOT NULL,
        note       TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_quality_events_module ON quality_events(module, created_at);
    CREATE INDEX IF NOT EXISTS idx_quality_events_card ON quality_events(card_id);
    CREATE TABLE IF NOT EXISTS exam_attempts (
        id           TEXT PRIMARY KEY,
        module       TEXT NOT NULL,
        attempt_type TEXT NOT NULL,
        mode         TEXT NOT NULL,
        title        TEXT NOT NULL,
        ref_id       TEXT NOT NULL DEFAULT '',
        earned       REAL NOT NULL DEFAULT 0,
        total        REAL NOT NULL DEFAULT 0,
        pct          INTEGER NOT NULL DEFAULT 0,
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL,
        payload      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_exam_attempts_module ON exam_attempts(module, created_at);
    CREATE TABLE IF NOT EXISTS fehlerbuch (
        card_id       TEXT PRIMARY KEY,
        module        TEXT NOT NULL,
        first_missed_at TEXT NOT NULL,
        last_missed_at  TEXT NOT NULL,
        miss_count    INTEGER NOT NULL DEFAULT 1,
        source        TEXT NOT NULL DEFAULT 'review',
        note          TEXT NOT NULL DEFAULT '',
        resolved_at   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_fehlerbuch_module ON fehlerbuch(module, resolved_at);
    CREATE TABLE IF NOT EXISTS quest_claims (
        quest_key    TEXT NOT NULL,
        period_start TEXT NOT NULL,
        claimed_at   TEXT NOT NULL,
        amount       INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(quest_key, period_start)
    );
    """)
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
    seed_ids = {card["id"] for card in payload["cards"]}
    added = 0
    for card in payload["cards"]:
        exists = conn.execute("SELECT updated_at, status, review_note FROM cards WHERE id=?", (card["id"],)).fetchone()
        if exists:
            if exists["updated_at"] is None:
                synced = dict(card)
                synced["status"] = exists["status"] or card.get("status", "active")
                conn.execute(
                    """UPDATE cards SET module=?, kap=?, sub=?, subname=?, source=?, ord=?, payload=?
                       WHERE id=?""",
                    (
                        card.get("module", "organic"),
                        card.get("kap"),
                        card.get("sub"),
                        card.get("subname"),
                        card.get("source"),
                        card.get("order", 0),
                        json.dumps(synced, ensure_ascii=False),
                        card["id"],
                    ),
                )
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
    if seed_ids:
        placeholders = ",".join("?" for _ in seed_ids)
        conn.execute(
            f"""UPDATE cards
                SET status='suspended',
                    review_note='Automatisch deaktiviert: Quellen-, Personen- oder Firmenrauschen',
                    updated_at=COALESCE(updated_at, datetime('now'))
                WHERE updated_at IS NULL
                  AND (id LIKE 'org:%' OR id LIKE 'inorg:%')
                  AND id NOT IN ({placeholders})""",
            tuple(seed_ids),
        )
    seed_updated_at = datetime.now(timezone.utc).isoformat()
    repair_english_artifacts(conn, updated_at=seed_updated_at)
    restore_seed_auto_suspensions(conn, seed_ids, updated_at=seed_updated_at)
    restore_english_artifact_suspensions(conn, updated_at=seed_updated_at)
    flag_english_noise(conn, updated_at=seed_updated_at)
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


TAG_RULES = {
    "organic": [
        ("Raffinerie", ["raffin", "erdöl", "erdoel", "crack", "destillation", "naphta", "naphtha", "benzin", "diesel"]),
        ("Fossile Rohstoffe", ["fossil", "erdgas", "kohle", "rohöl", "rohoel", "petroleum"]),
        ("Nachwachsende Rohstoffe", ["nachwachs", "nawaro", "biomasse", "biofuel", "btl", "fett", "öl", "oel"]),
        ("Kohlenhydrate", ["kohlenhydrat", "stärke", "staerke", "zucker", "glucose", "sacchar"]),
        ("Cellulose", ["cellulose", "papier", "lignin", "hemicellulose", "viskose"]),
        ("Polymere", ["polymer", "polyamid", "polyethylen", "polypropylen", "kunststoff", "recycling"]),
        ("Farbstoffe", ["farbstoff", "farbe", "pigment", "chromophor"]),
    ],
    "inorganic": [
        ("Metallurgie", ["metallurgie", "erz", "roest", "röst", "reduktion", "schlacke", "sinter", "pyro", "hydro"]),
        ("Eisen/Stahl", ["eisen", "stahl", "hochofen", "blast", "corex", "midrex", "roheisen"]),
        ("Kupfer/Aluminium", ["kupfer", "cu", "aluminium", "al ", "bauxit", "hall", "heroult", "heroult"]),
        ("Stickstoff", ["stickstoff", "ammoniak", "haber", "salpeter", "nitrat", "nh3", "no3"]),
        ("Chloralkali/Soda", ["chlor", "natron", "naoh", "soda", "nacl", "solvay", "chloralkali"]),
        ("Schwefel", ["schwefel", "sulfat", "sulfid", "so2", "so3", "h2so4", "kontaktverfahren"]),
        ("Bindemittel", ["zement", "kalk", "gips", "klinker", "portland", "calcium"]),
        ("Glas/Keramik", ["glas", "keramik", "silikat", "ton", "porzellan", "sintern"]),
        ("Rohstoffe", ["rohstoff", "lagerstätte", "lagerstaette", "mineral", "abbau"]),
    ],
}

CHAPTER_TAGS = {
    "organic": {
        1: "Fossile Rohstoffe",
        2: "Raffinerie",
        3: "Raffinerie",
        4: "Raffinerie",
        5: "Nachwachsende Rohstoffe",
        6: "Kohlenhydrate",
        7: "Cellulose",
        8: "Cellulose",
        9: "Polymere",
        10: "Polymere",
        11: "Pruefung",
    },
    "inorganic": {
        1: "Grundlagen",
        2: "Rohstoffe",
        3: "Metallurgie",
        4: "Metallurgie",
        5: "Eisen/Stahl",
        6: "Kupfer/Aluminium",
        7: "Stickstoff",
        8: "Chloralkali/Soda",
        9: "Schwefel",
        10: "Bindemittel",
        11: "Glas/Keramik",
    },
}


def infer_tags(card: dict) -> list[str]:
    existing = card.get("tags")
    if isinstance(existing, list) and existing:
        return sorted({str(t) for t in existing if str(t).strip()})
    module = card.get("module", "organic")
    text = " ".join(str(card.get(k, "")) for k in ("q", "a", "source", "subname")).lower()
    tags: set[str] = set()
    chapter_tag = CHAPTER_TAGS.get(module, {}).get(card.get("kap"))
    if chapter_tag:
        tags.add(chapter_tag)
    for tag, needles in TAG_RULES.get(module, []):
        if any(needle in text for needle in needles):
            tags.add(tag)
    return sorted(tags)


def normalize_chemical_formulas(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    for pattern, replacement in CHEM_FORMULA_REPAIRS:
        text = re.sub(pattern, replacement, text)
    return text


def plain_card_text(card: dict) -> str:
    raw = f"{card.get('q', '')} {card.get('a', '')} {card.get('source', '')} {card.get('subname', '')}"
    raw = re.sub(r"<span[^>]*class=['\"]source['\"][^>]*>.*?</span>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def english_noise(card: dict) -> bool:
    text = plain_card_text(card)
    if not text:
        return False
    if ENGLISH_ARTIFACT_RE.search(text):
        return True
    tokens = re.findall(r"\b[a-z]{3,}\b", text.lower())
    english = sum(1 for token in tokens if token in ENGLISH_CARD_WORDS)
    german = sum(1 for token in tokens if token in GERMAN_CARD_WORDS)
    has_german_chars = bool(re.search(r"[äöüßÄÖÜ]", text))
    if english >= 8 and english >= german * 2 + 4:
        return True
    if english >= 5 and german <= 1 and not has_german_chars:
        return True
    return False


def depolymerisation_repair(card: dict) -> dict | None:
    text = plain_card_text(card).lower()
    if not (
        "plastics recycling paths" in text
        and "take-home messages" in text
        and ("depolymerization" in text or "depolymerisation" in text)
    ):
        return None
    context = organic_context(card)
    source = str(card.get("source") or "VO10 Gastvortrag - Recycling von Kunststoffen").strip()
    repaired = dict(card)
    repaired["q"] = (
        f"Kontext: {context}\n\n"
        "Erlaeutern Sie Depolymerisation. Gehen Sie auf Ausgangsstoffe, "
        "Prozessfuehrung, wichtige Bedingungen, Produkte und Zweck ein."
    )
    repaired["a"] = (
        f"<b>Kontext:</b> {context}<br><br>"
        "<b>Pruefungsantwort zu Depolymerisation:</b>"
        "<ul>"
        "<li>Depolymerisation zerlegt Kunststoff-Polymere gezielt in Monomere oder wenige definierte Bausteine.</li>"
        "<li>Ausgangsstoffe sind sortierte, moeglichst saubere Kunststoffstroeme; Stoerstoffe, Additive und Pigmente muessen je nach Verfahren abgetrennt oder beruecksichtigt werden.</li>"
        "<li>Der Unterschied zum mechanischen Recycling ist die chemische Rueckfuehrung: Nicht der ganze Werkstoff wird wiederverwendet, sondern die Bausteinebene des Polymers.</li>"
        "<li>Beim Loesungsrecycling werden Polymerketten oder definierte Polymerfraktionen zurueckgewonnen; bei der Depolymerisation entstehen Monomere fuer eine erneute Polymerisation.</li>"
        "<li>Andere chemische Recyclingwege liefern oft kleinere Molekuelgemische, die vor einer neuen Polymerherstellung aufgetrennt, aufgereinigt und chemisch umgesetzt werden muessen.</li>"
        "<li>Ziel ist ein Rohstoffkreislauf mit Monomeren oder Basischemikalien, aus denen wieder Kunststoffe mit eingestellten Additiven und Stabilisatoren hergestellt werden koennen.</li>"
        "</ul>"
        "<b>Beim Antworten aktiv abdecken:</b> Definition/Prinzip, Prozess oder Struktur, "
        "wichtige Bedingungen, Produkte/Beispiele und typische Begruendung."
        f"<br><br><span class='source'>Quelle: {source}</span>"
    )
    repaired["status"] = "active"
    repaired["review_note"] = ""
    return repaired


def repair_english_artifact_card(card: dict) -> dict | None:
    return depolymerisation_repair(card)


def quality_score(card: dict) -> int:
    q = str(card.get("q", ""))
    a = str(card.get("a", ""))
    text = f"{q} {a}"
    score = 0
    if card.get("status") == "needs_review" or card.get("review_note"):
        score += 80
    if "_____" in q:
        score += 16
    if any(x in text for x in ["•", "", "→", "-->", " - (", "[Seite"]):
        score += 18
    if len(q) > 220 or len(a) > 650:
        score += 18
    if text.count("(") != text.count(")"):
        score += 12
    if card.get("lapses", 0) > 0:
        score += min(40, card.get("lapses", 0) * 8)
    if card.get("reps", 0) == 0:
        score += 5
    english = card.get("english_noise")
    if english is None:
        english = english_noise(card)
    if english:
        score += 120
    recommended_photo = card.get("photo_recommended")
    if recommended_photo is None:
        recommended_photo = photo_recommended(card)
    if recommended_photo:
        score += 22
    return score


def has_photo(card: dict) -> bool:
    text = f"{card.get('q', '')} {card.get('a', '')}".lower()
    return "<img" in text or "card-photo" in text or "/uploads/cards/" in text


def photo_recommended(card: dict) -> bool:
    if has_photo(card):
        return False
    text = f"{card.get('q', '')} {card.get('a', '')} {card.get('kind', '')}".lower()
    markers = (
        "strukturformel", "reaktionsformel", "diagramm", "schema",
        "schaubild", "skizz", "zeichnen", "chemischen aufbau",
        "wiederholeinheit", "prozessschema", "apparatur", "mechanismus",
        "monomer", "polymerarchitektur",
    )
    return any(marker in text for marker in markers)


def sketch_required(card: dict) -> bool:
    text = f"{card.get('q', '')} {card.get('a', '')} {card.get('kind', '')}".lower()
    markers = (
        "strukturformel", "reaktionsformel", "formel", "gleichung", "skizz",
        "zeichnen", "wiederholeinheit", "mechanismus", "chemischen aufbau",
        "monomer", "polymerarchitektur",
    )
    return any(marker in text for marker in markers)


def answer_points(card: dict) -> list[str]:
    answer = str(card.get("a", ""))
    points = re.findall(r"<li[^>]*>(.*?)</li>", answer, flags=re.I | re.S)
    if not points:
        points = re.split(r"(?:\n|<br\s*/?>|;)\s*", answer, flags=re.I)
    cleaned = []
    for point in points:
        text = re.sub(r"<[^>]+>", " ", point)
        text = unescape(re.sub(r"\s+", " ", text)).strip(" -*;")
        if len(text) >= 12:
            cleaned.append(text)
    return cleaned[:8]


def source_anchor(card: dict) -> dict:
    source = str(card.get("source") or "").strip()
    subname = str(card.get("subname") or "").strip()
    module = card.get("module") or "organic"
    module_label = "Organische Chemie" if module == "organic" else "Anorganische Chemie"
    kap = card.get("kap")
    chapter = f"VO{kap}" if kap else "ohne VO"
    raw_tags = card.get("tags")
    if isinstance(raw_tags, list):
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()][:6]
    else:
        tags = infer_tags(card)[:6]
    topic = subname or CHAPTER_TAGS.get(module, {}).get(kap) or (tags[0] if tags else "Thema")
    text = plain_card_text(card)
    q = str(card.get("q") or "")
    a = str(card.get("a") or "")
    points = answer_points(card)
    issues: list[str] = []
    score = 100
    if not source or source.lower() in {"import", "manuell", "unbekannt"}:
        score -= 28
        issues.append("Quelle fehlt oder ist generisch")
    if not q.startswith("Kontext:") and "Quelle:" not in f"{q} {a}":
        score -= 22
        issues.append("Kontext/Quelle steht nicht in der Karte")
    if len(points) < 2:
        score -= 18
        issues.append("Antwort hat zu wenige pruefbare Punkte")
    english = card.get("english_noise")
    if english is None:
        english = english_noise(card)
    if english:
        score -= 28
        issues.append("Englisches Quellen- oder Folienrauschen")
    if re.search(r"(?i)\b(vorlesungseinheiten|tiss|raumnummer|allgemeine informationen)\b", text):
        score -= 18
        issues.append("Organisatorische Vorlesungsinfo statt Fachanker")
    if tags:
        score += 5
    score = max(0, min(100, score))
    status = "green" if score >= 78 else "yellow" if score >= 52 else "red"
    label = "gute Quelle" if status == "green" else "Quelle pruefen" if status == "yellow" else "unsicher"
    derivation = []
    lower_answer = plain_card_text({"q": "", "a": a}).lower()
    if any(x in lower_answer for x in ["definition", "prinzip", "ist ", "nennt man"]):
        derivation.append("Definition/Prinzip ist in der Musterantwort erkennbar.")
    if any(x in lower_answer for x in ["verfahren", "prozess", "ablauf", "schritt", "reaktion"]):
        derivation.append("Prozess oder Ablauf wird aus den Antwortpunkten abgeleitet.")
    if any(x in lower_answer for x in ["temperatur", "druck", "katalysator", "bedingungen", "parameter"]):
        derivation.append("Wichtige Bedingungen sind als Pruefungspunkt vorhanden.")
    if any(x in lower_answer for x in ["produkt", "beispiel", "anwendung", "zweck", "verwendung"]):
        derivation.append("Produkte, Beispiele oder Zweck sichern die Einordnung.")
    if not derivation and points:
        derivation = [f"Antwortpunkt: {point[:110]}" for point in points[:3]]
    return {
        "score": score,
        "status": status,
        "label": label,
        "module": module_label,
        "chapter": chapter,
        "topic": topic,
        "source": source or "nicht gesetzt",
        "anchor": f"{module_label} / {chapter} / {topic}",
        "tags": tags,
        "issues": issues,
        "derivation": derivation[:5],
    }


def row_to_card(row: sqlite3.Row, include_source_anchor: bool = True,
                include_quality: bool = True) -> dict:
    d = dict(row)
    payload = json.loads(d.pop("payload"))
    payload.update(d)
    payload["q"] = normalize_chemical_formulas(payload.get("q", ""))
    payload["a"] = normalize_chemical_formulas(payload.get("a", ""))
    payload["tags"] = infer_tags(payload)
    payload["has_photo"] = has_photo(payload)
    payload["photo_recommended"] = photo_recommended(payload)
    payload["sketch_required"] = sketch_required(payload)
    payload["english_noise"] = english_noise(payload)
    if include_quality:
        payload["quality_score"] = quality_score(payload)
    if include_source_anchor:
        payload["source_anchor"] = source_anchor(payload)
    return payload


def lightweight_card_from_row(row: sqlite3.Row) -> dict:
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload.update({
        "id": row["id"],
        "module": row["module"],
        "kap": row["kap"],
        "sub": row["sub"],
        "subname": row["subname"],
        "source": row["source"],
        "status": row["status"],
        "due": row["due"],
        "lapses": row["lapses"],
    })
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


def add_quality_event(conn: sqlite3.Connection, card_id: str, module: str, event_type: str,
                      reason: str, note: str, created_at: str) -> None:
    if not reason:
        return
    conn.execute(
        """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
           VALUES(?,?,?,?,?,?)""",
        (card_id, module, event_type, reason, note or "", created_at),
    )
    conn.commit()


def mark_card_needs_review(conn: sqlite3.Connection, card_id: str, note: str, updated_at: str) -> None:
    card = get_card(conn, card_id)
    if not card:
        return
    payload = dict(card)
    payload["status"] = "needs_review"
    conn.execute(
        """UPDATE cards SET status='needs_review', review_note=?, updated_at=?, payload=?
           WHERE id=?""",
        (note, updated_at, json.dumps(payload, ensure_ascii=False), card_id),
    )
    conn.commit()


def repair_english_artifacts(conn: sqlite3.Connection, module: str | None = None,
                             updated_at: str | None = None) -> int:
    clauses = ["deck='anki'"]
    params: list[object] = []
    if module:
        clauses.append("module=?")
        params.append(module)
    rows = conn.execute(
        f"SELECT * FROM cards WHERE {' AND '.join(clauses)}",
        params,
    ).fetchall()
    changed = 0
    changed_at = updated_at or datetime.now(timezone.utc).isoformat()
    for row in rows:
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        repaired = repair_english_artifact_card(card)
        if not repaired:
            continue
        status = "active"
        if card.get("status") == "suspended" and not auto_deactivation_note(card.get("review_note")):
            status = "suspended"
        repaired["status"] = status
        repaired["review_note"] = "" if status == "active" else card.get("review_note", "")
        conn.execute(
            """UPDATE cards
               SET status=?, review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (
                repaired["status"], repaired.get("review_note", ""), changed_at,
                json.dumps(repaired, ensure_ascii=False), card["id"],
            ),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                card["id"], card.get("module", module or "organic"), "auto_quality",
                "english_artifact_repaired", "Englische Recycling-Karte automatisch uebersetzt", changed_at,
            ),
        )
        changed += 1
    return changed


def restore_seed_auto_suspensions(conn: sqlite3.Connection, seed_ids: set[str],
                                  updated_at: str | None = None) -> int:
    if not seed_ids:
        return 0
    placeholders = ",".join("?" for _ in seed_ids)
    rows = conn.execute(
        f"""SELECT * FROM cards
            WHERE deck='anki' AND status='suspended' AND id IN ({placeholders})""",
        tuple(seed_ids),
    ).fetchall()
    changed = 0
    changed_at = updated_at or datetime.now(timezone.utc).isoformat()
    for row in rows:
        if not auto_deactivation_note(row["review_note"]):
            continue
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        note = ENGLISH_ARTIFACT_NOTE if english_noise(card) else ""
        payload = dict(card)
        payload["status"] = "active"
        payload["review_note"] = note
        conn.execute(
            """UPDATE cards
               SET status='active', review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (note, changed_at, json.dumps(payload, ensure_ascii=False), card["id"]),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                card["id"], card.get("module", "organic"), "auto_quality",
                "seed_auto_suspension_restored", "Seed-Karte automatisch reaktiviert", changed_at,
            ),
        )
        changed += 1
    return changed


def restore_english_artifact_suspensions(conn: sqlite3.Connection, module: str | None = None,
                                         updated_at: str | None = None) -> int:
    clauses = ["deck='anki'", "status='suspended'", "review_note=?"]
    params: list[object] = [OLD_ENGLISH_ARTIFACT_NOTE]
    if module:
        clauses.append("module=?")
        params.append(module)
    rows = conn.execute(
        f"SELECT * FROM cards WHERE {' AND '.join(clauses)}",
        params,
    ).fetchall()
    changed = 0
    changed_at = updated_at or datetime.now(timezone.utc).isoformat()
    for row in rows:
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        note = ENGLISH_ARTIFACT_NOTE if english_noise(card) else ""
        payload = dict(card)
        payload["status"] = "active"
        payload["review_note"] = note
        conn.execute(
            """UPDATE cards
               SET status='active', review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (note, changed_at, json.dumps(payload, ensure_ascii=False), card["id"]),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                card["id"], card.get("module", module or "organic"), "auto_quality",
                "english_noise_restored", "Auto-Deaktivierung zurueckgenommen", changed_at,
            ),
        )
        changed += 1
    return changed


def flag_english_noise(conn: sqlite3.Connection, module: str | None = None,
                       updated_at: str | None = None) -> int:
    clauses = ["deck='anki'", "status='active'", "review_note<>?"]
    params: list[object] = []
    params.append(ENGLISH_HOLD_NOTE)
    if module:
        clauses.append("module=?")
        params.append(module)
    rows = conn.execute(
        f"SELECT * FROM cards WHERE {' AND '.join(clauses)}",
        params,
    ).fetchall()
    changed = 0
    changed_at = updated_at or datetime.now(timezone.utc).isoformat()
    for row in rows:
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        if not english_noise(card):
            continue
        payload = dict(card)
        repaired = repair_english_artifact_card(card)
        if repaired:
            payload = repaired
            payload["status"] = "active"
            note = ""
            reason = "english_artifact_repaired"
        else:
            payload["status"] = "needs_review"
            payload["review_note"] = ENGLISH_HOLD_NOTE
            note = ENGLISH_HOLD_NOTE
            reason = "english_noise_held"
        conn.execute(
            """UPDATE cards
               SET status=?, review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (payload["status"], note, changed_at, json.dumps(payload, ensure_ascii=False), card["id"]),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                card["id"], card.get("module", module or "organic"), "auto_quality",
                reason, note or "Englische Karte automatisch bearbeitet", changed_at,
            ),
        )
        changed += 1
    return changed


def auto_quality_sweep(conn: sqlite3.Connection, module: str, updated_at: str) -> int:
    changed = repair_english_artifacts(conn, module, updated_at)
    changed += restore_english_artifact_suspensions(conn, module, updated_at)
    changed += flag_english_noise(conn, module, updated_at)
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status='active'
             AND (lapses>=3 OR id IN (
                 SELECT card_id FROM quality_events
                 WHERE module=? AND reason IN ('frage_unklar', 'karte_schlecht')
                 GROUP BY card_id HAVING COUNT(*)>=2
             ))
           LIMIT 40""",
        (module, module),
    ).fetchall()
    for row in rows:
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        payload = dict(card)
        payload["status"] = "needs_review"
        note = "Auto-Quality: wiederholt falsch oder als unklar markiert"
        conn.execute(
            """UPDATE cards SET status='needs_review', review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (note, updated_at, json.dumps(payload, ensure_ascii=False), card["id"]),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (card["id"], module, "auto_quality", "wiederholt_schwach", note, updated_at),
        )
        changed += 1
    photo_rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status='active'
             AND quality_checked_at IS NULL
             AND review_note NOT LIKE 'Foto empfohlen:%'
             AND payload NOT LIKE '%<img%'
             AND payload NOT LIKE '%/uploads/cards/%'
             AND (
                payload LIKE '%Strukturformel%' OR payload LIKE '%Reaktionsformel%'
                OR payload LIKE '%Diagramm%' OR payload LIKE '%Schema%'
                OR payload LIKE '%Skizz%' OR payload LIKE '%zeichnen%'
                OR payload LIKE '%Wiederholeinheit%' OR payload LIKE '%Mechanismus%'
                OR payload LIKE '%chemischen Aufbau%' OR payload LIKE '%Monomer%'
             )
           LIMIT 25""",
        (module,),
    ).fetchall()
    for row in photo_rows:
        card = row_to_card(row, include_source_anchor=False, include_quality=False)
        if not photo_recommended(card):
            continue
        payload = dict(card)
        payload["status"] = card.get("status", "active")
        note = "Foto empfohlen: Struktur, Formel, Schema oder Mechanismus visuell ergaenzen"
        conn.execute(
            """UPDATE cards SET review_note=?, updated_at=?, payload=?
               WHERE id=?""",
            (note, updated_at, json.dumps(payload, ensure_ascii=False), card["id"]),
        )
        conn.execute(
            """INSERT INTO quality_events(card_id, module, event_type, reason, note, created_at)
               VALUES(?,?,?,?,?,?)""",
            (card["id"], module, "auto_quality", "foto_empfohlen", note, updated_at),
        )
        changed += 1
    conn.commit()
    return changed


def quality_summary(conn: sqlite3.Connection, module: str = "organic") -> dict:
    counts = conn.execute(
        """SELECT event_type, reason, COUNT(*) c, MAX(created_at) latest
           FROM quality_events
           WHERE module=?
           GROUP BY event_type, reason
           ORDER BY c DESC, latest DESC""",
        (module,),
    ).fetchall()
    recent = conn.execute(
        """SELECT qe.id, qe.card_id, qe.event_type, qe.reason, qe.note, qe.created_at,
                  c.kap, c.subname, c.status, c.payload
           FROM quality_events qe
           LEFT JOIN cards c ON c.id=qe.card_id
           WHERE qe.module=?
           ORDER BY qe.id DESC
           LIMIT 12""",
        (module,),
    ).fetchall()
    unchecked = conn.execute(
        """SELECT COUNT(*) c FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
             AND quality_checked_at IS NULL""",
        (module,),
    ).fetchone()["c"]
    status_rows = conn.execute(
        """SELECT status, COUNT(*) c FROM cards
           WHERE module=? AND deck='anki' GROUP BY status""",
        (module,),
    ).fetchall()
    by_status = {"active": 0, "needs_review": 0, "suspended": 0}
    for row in status_rows:
        by_status[row["status"] or "active"] = row["c"] or 0
    media_rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')""",
        (module,),
    ).fetchall()
    media_cards = [lightweight_card_from_row(row) for row in media_rows]
    return {
        "unchecked": unchecked or 0,
        "active": by_status["active"],
        "needs_review": by_status["needs_review"],
        "suspended": by_status["suspended"],
        "with_photo": sum(1 for card in media_cards if card.get("has_photo")),
        "photo_recommended": sum(1 for card in media_cards if card.get("photo_recommended")),
        "reasons": [
            {
                "event_type": r["event_type"],
                "reason": r["reason"],
                "count": r["c"] or 0,
                "latest": r["latest"],
            }
            for r in counts
        ],
        "recent": [
            {
                "card_id": r["card_id"],
                "id": r["id"],
                "event_type": r["event_type"],
                "reason": r["reason"],
                "note": r["note"],
                "created_at": r["created_at"],
                "kap": r["kap"],
                "subname": r["subname"],
                "status": r["status"],
                "question": (json.loads(r["payload"]).get("q", "") if r["payload"] else "")[:140],
            }
            for r in recent
        ],
    }


def record_exam_attempt(conn: sqlite3.Connection, module: str, attempt_type: str, mode: str,
                        title: str, ref_id: str, earned: float, total: float,
                        pct_score: int, duration_seconds: int, payload: dict,
                        created_at: str) -> str:
    attempt_id = f"attempt:{secrets.token_hex(8)}"
    conn.execute(
        """INSERT INTO exam_attempts(id, module, attempt_type, mode, title, ref_id, earned,
                  total, pct, duration_seconds, created_at, payload)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            attempt_id, module, attempt_type, mode, title, ref_id or "", earned,
            total, pct_score, max(duration_seconds, 0), created_at,
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    return attempt_id


def exam_attempt_history(conn: sqlite3.Connection, module: str = "organic",
                         limit: int = 24) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM exam_attempts
           WHERE module=?
           ORDER BY created_at DESC
           LIMIT ?""",
        (module, limit),
    ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        out.append(item)
    return out


def exam_repair_cards(conn: sqlite3.Connection, module: str = "organic",
                      limit: int = 30) -> list[dict]:
    attempts = exam_attempt_history(conn, module, 30)
    picked: dict[str, dict] = {}
    for attempt in attempts:
        for q in (attempt.get("payload") or {}).get("questions", []):
            weak = q.get("repair") or (q.get("score") in {"partial", "miss"}) or (q.get("pct") or 100) < 85
            if not weak:
                continue
            card_ids = q.get("card_ids") or ([q.get("card_id")] if q.get("card_id") else [])
            for card_id in card_ids:
                if card_id and card_id not in picked:
                    picked[card_id] = {
                        "attempt_id": attempt["id"],
                        "created_at": attempt["created_at"],
                        "reason": q.get("topic") or q.get("title") or "Pruefungsfehler",
                        "score": q.get("score") or q.get("pct"),
                        "confidence": q.get("confidence", ""),
                        "error_types": q.get("error_types", []),
                    }
                if len(picked) >= limit * 2:
                    break
            if len(picked) >= limit * 2:
                break
        if len(picked) >= limit * 2:
            break
    if not picked:
        return []
    placeholders = ",".join("?" for _ in picked)
    rows = conn.execute(
        f"""SELECT * FROM cards
            WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
              AND id IN ({placeholders})""",
        (module, *picked.keys()),
    ).fetchall()
    cards = []
    for row in rows:
        card = row_to_card(row)
        card["repair"] = picked.get(card["id"], {})
        cards.append(card)
    cards.sort(key=lambda c: list(picked).index(c["id"]) if c["id"] in picked else 999)
    return cards[:limit]


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
    review_row = conn.execute(
        """SELECT COUNT(*) total_reviews,
                  SUM(CASE WHEN rv.rating>=3 THEN 1 ELSE 0 END) ok,
                  SUM(CASE WHEN substr(rv.reviewed_at,1,10)=? THEN 1 ELSE 0 END) reviews_today
           FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=?""",
        (today, module),
    ).fetchone()
    total_reviews = review_row["total_reviews"] or 0
    ok = review_row["ok"] or 0
    return {
        "total": row["total"] or 0,
        "new": row["new"] or 0,
        "due": row["due"] or 0,
        "learning": row["learning"] or 0,
        "review": row["review"] or 0,
        "seen": row["seen"] or 0,
        "reviews_today": review_row["reviews_today"] or 0,
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
    review_rows = conn.execute(
        """SELECT c.kap,
                  COUNT(*) reviews,
                  SUM(CASE WHEN rv.rating>=3 THEN 1 ELSE 0 END) correct,
                  SUM(CASE WHEN rv.rating=1 THEN 1 ELSE 0 END) again
           FROM reviews rv
           JOIN cards c ON c.id=rv.card_id
           WHERE c.module=? AND c.status='active'
           GROUP BY c.kap""",
        (module,),
    ).fetchall()
    review_by_kap = {
        r["kap"]: {
            "reviews": r["reviews"] or 0,
            "correct": r["correct"] or 0,
            "again": r["again"] or 0,
        }
        for r in review_rows
    }
    out = []
    for r in rows:
        review_row = review_by_kap.get(r["kap"], {})
        reviews = review_row.get("reviews", 0) or 0
        correct = review_row.get("correct", 0) or 0
        again = review_row.get("again", 0) or 0
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


def weakness_heatmap(conn: sqlite3.Connection, now_iso: str, module: str = "organic",
                     chapters: list[dict] | None = None) -> list[dict]:
    rows = chapters if chapters is not None else chapter_stats(conn, now_iso, module)
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


def exam_candidates(conn: sqlite3.Connection, module: str = "organic", limit: int = 120,
                    mode: str = "mixed", formula: bool = False) -> list[dict]:
    clauses = ["module=?", "deck='anki'", "status='active'", "payload LIKE '%\"kind\": \"exam_%\"%'"]
    params: list[object] = [module]
    if formula:
        clauses.append(
            """(payload LIKE '%Reaktions%' OR payload LIKE '%Struktur%' OR payload LIKE '%Formel%'
                OR payload LIKE '%Gleichung%' OR payload LIKE '%Polymerisation%' OR payload LIKE '%Synthese%'
                OR payload LIKE '%Claus%' OR payload LIKE '%Haber%' OR payload LIKE '%Ostwald%'
                OR payload LIKE '%Solvay%' OR payload LIKE '%Elektrolyse%')"""
        )
    where = " AND ".join(clauses)
    if mode == "weak":
        order = "lapses DESC, difficulty DESC, reps ASC, due ASC, RANDOM()"
    else:
        order = "kap ASC, RANDOM()"
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {where}
            ORDER BY {order} LIMIT ?""",
        (*params, limit),
    ).fetchall()
    if formula and not rows:
        rows = conn.execute(
            """SELECT * FROM cards
               WHERE module=? AND deck='anki' AND status='active'
               ORDER BY RANDOM() LIMIT ?""",
            (module, limit),
        ).fetchall()
    return [row_to_card(r) for r in rows]


def tag_stats(conn: sqlite3.Connection, module: str = "organic") -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status='active'""",
        (module,),
    ).fetchall()
    counts: dict[str, dict] = {}
    for row in rows:
        card = lightweight_card_from_row(row)
        for tag in infer_tags(card):
            item = counts.setdefault(tag, {"tag": tag, "total": 0, "due": 0, "again": 0})
            item["total"] += 1
            if card.get("due") is not None:
                item["due"] += 1
            item["again"] += card.get("lapses", 0) or 0
    return sorted(counts.values(), key=lambda x: (-x["again"], -x["due"], -x["total"], x["tag"]))


def list_cards(conn: sqlite3.Connection, status: str = "needs_review", limit: int = 80,
               kap: int | None = None, q: str = "", module: str = "organic",
               tag: str = "", media: str = "all") -> dict:
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
    if media == "with_photo":
        clauses.append("(payload LIKE '%<img%' OR payload LIKE '%/uploads/cards/%')")
    elif media in {"without_photo", "photo_recommended"}:
        clauses.append("payload NOT LIKE '%<img%' AND payload NOT LIKE '%/uploads/cards/%'")
    where = " AND ".join(clauses)
    fetch_limit = limit if not tag and media != "photo_recommended" else max(limit * 8, 300)
    rows = conn.execute(
        f"""SELECT * FROM cards WHERE {where}
            ORDER BY CASE status WHEN 'needs_review' THEN 0 WHEN 'active' THEN 1 ELSE 2 END,
                     lapses DESC, reps ASC, kap ASC, ord ASC
            LIMIT ?""",
        (*params, fetch_limit),
    ).fetchall()
    cards = [row_to_card(r) for r in rows]
    if tag:
        cards = [c for c in cards if tag in c.get("tags", [])]
    if media == "photo_recommended":
        cards = [c for c in cards if c.get("photo_recommended")]
    cards = cards[:limit]
    summary_rows = conn.execute(
        "SELECT status, COUNT(*) c FROM cards WHERE module=? AND deck='anki' GROUP BY status",
        (module,),
    ).fetchall()
    summary = {"active": 0, "needs_review": 0, "suspended": 0}
    for r in summary_rows:
        summary[r["status"] or "active"] = r["c"] or 0
    return {"cards": cards, "summary": summary}


def triage_cards(conn: sqlite3.Connection, module: str = "organic", limit: int = 10,
                 tag: str = "") -> dict:
    rows = conn.execute(
        """SELECT * FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
           ORDER BY CASE WHEN quality_checked_at IS NULL THEN 0 ELSE 1 END,
                    CASE status WHEN 'needs_review' THEN 0 ELSE 1 END,
                    lapses DESC, reps ASC, kap ASC, ord ASC
           LIMIT 500""",
        (module,),
    ).fetchall()
    cards = [row_to_card(r) for r in rows]
    if tag:
        cards = [c for c in cards if tag in c.get("tags", [])]
    cards.sort(key=lambda c: (c.get("quality_checked_at") is not None, -c.get("quality_score", 0), c.get("kap") or 99, c.get("ord") or 0))
    unchecked = conn.execute(
        """SELECT COUNT(*) c FROM cards
           WHERE module=? AND deck='anki' AND status IN ('active', 'needs_review')
             AND quality_checked_at IS NULL""",
        (module,),
    ).fetchone()["c"]
    return {"cards": cards[:limit], "remaining": unchecked or 0, "tags": tag_stats(conn, module)}


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
        """UPDATE cards SET status=?, review_note=?, updated_at=?,
           quality_checked_at=CASE WHEN ?='active' THEN ? ELSE quality_checked_at END,
           payload=?
           WHERE id=?""",
        (status, review_note, updated_at, status, updated_at, json.dumps(payload, ensure_ascii=False), card_id),
    )
    conn.commit()
    return get_card(conn, card_id)


def triage_card(conn: sqlite3.Connection, card_id: str, action: str, updated_at: str,
                q: str | None = None, a: str | None = None, review_note: str = "",
                reason: str = "") -> dict | None:
    card = get_card(conn, card_id)
    if not card:
        return None
    if action not in {"approve", "needs_review", "suspend"}:
        raise ValueError("invalid action")
    status = {"approve": "active", "needs_review": "needs_review", "suspend": "suspended"}[action]
    payload = dict(card)
    if q is not None:
        payload["q"] = q
    if a is not None:
        payload["a"] = a
    payload["status"] = status
    conn.execute(
        """UPDATE cards SET status=?, review_note=?, updated_at=?, quality_checked_at=?, payload=?
           WHERE id=?""",
        (status, review_note, updated_at, updated_at, json.dumps(payload, ensure_ascii=False), card_id),
    )
    conn.commit()
    if reason:
        add_quality_event(conn, card_id, card.get("module", "organic"), "triage", reason, review_note, updated_at)
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


def add_imported_cards(conn: sqlite3.Connection, cards: list[dict],
                       created_at: str, module: str = "organic") -> list[str]:
    if not cards:
        return []
    kap_values = sorted({int(card.get("kap") or 1) for card in cards})
    chapters = {
        row["kap"]: row["subname"]
        for row in conn.execute(
            f"""SELECT kap, subname FROM cards
                WHERE module=? AND kap IN ({','.join('?' for _ in kap_values)}) AND subname IS NOT NULL
                GROUP BY kap""",
            (module, *kap_values),
        ).fetchall()
    }
    max_rows = conn.execute(
        f"""SELECT kap, COALESCE(MAX(ord),0) m FROM cards
            WHERE module=? AND kap IN ({','.join('?' for _ in kap_values)})
            GROUP BY kap""",
        (module, *kap_values),
    ).fetchall()
    ord_by_kap = {row["kap"]: row["m"] or 0 for row in max_rows}
    rows = []
    ids = []
    for card in cards:
        kap = int(card.get("kap") or 1)
        ord_by_kap[kap] = ord_by_kap.get(kap, 0) + 1
        card_id = f"import:{module}:{secrets.token_hex(8)}"
        source = str(card.get("source") or "Import").strip() or "Import"
        subname = chapters.get(kap) or f"VO{kap}"
        payload = {
            "id": card_id,
            "module": module,
            "deck": "anki",
            "kap": kap,
            "sub": f"VO{kap}",
            "subname": subname,
            "source": source,
            "kind": "import",
            "q": str(card.get("q") or ""),
            "a": str(card.get("a") or ""),
            "order": ord_by_kap[kap],
            "status": "active",
        }
        ids.append(card_id)
        rows.append((
            card_id, module, "anki", kap, payload["sub"], subname, source,
            ord_by_kap[kap], "active", created_at, json.dumps(payload, ensure_ascii=False),
        ))
    conn.executemany(
        """INSERT INTO cards(id, module, deck, kap, sub, subname, source, ord, status,
                             updated_at, payload)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    return ids


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


# ---------------------------------------------------------------------------
# Fehlerbuch (error book): tracks cards that were missed in review or exam.
# ---------------------------------------------------------------------------

def log_mistake(conn: sqlite3.Connection, card_id: str, module: str, source: str,
                note: str, created_at: str) -> None:
    row = conn.execute("SELECT miss_count FROM fehlerbuch WHERE card_id=?", (card_id,)).fetchone()
    if row:
        conn.execute(
            """UPDATE fehlerbuch SET last_missed_at=?, miss_count=miss_count+1,
               source=?, note=?, resolved_at=NULL WHERE card_id=?""",
            (created_at, source, note or "", card_id),
        )
    else:
        conn.execute(
            """INSERT INTO fehlerbuch(card_id, module, first_missed_at, last_missed_at,
               miss_count, source, note, resolved_at) VALUES(?,?,?,?,1,?,?,NULL)""",
            (card_id, module, created_at, created_at, source, note or ""),
        )
    conn.commit()


def resolve_mistake(conn: sqlite3.Connection, card_id: str, resolved_at: str) -> bool:
    cur = conn.execute(
        "UPDATE fehlerbuch SET resolved_at=? WHERE card_id=?", (resolved_at, card_id)
    )
    conn.commit()
    return cur.rowcount > 0


def fehlerbuch_entries(conn: sqlite3.Connection, module: str = "organic",
                       include_resolved: bool = False) -> list[dict]:
    clause = "WHERE f.module=?"
    if not include_resolved:
        clause += " AND f.resolved_at IS NULL"
    rows = conn.execute(
        f"""SELECT f.*, c.payload, c.kap, c.sub, c.subname, c.status, c.due
            FROM fehlerbuch f JOIN cards c ON c.id=f.card_id
            {clause}
            ORDER BY (f.resolved_at IS NOT NULL), f.miss_count DESC, f.last_missed_at DESC""",
        (module,),
    ).fetchall()
    out = []
    for r in rows:
        card = row_to_card(r)
        out.append({
            "card_id": r["card_id"],
            "kap": r["kap"],
            "sub": r["sub"],
            "subname": r["subname"],
            "miss_count": r["miss_count"],
            "source": r["source"],
            "note": r["note"],
            "first_missed_at": r["first_missed_at"],
            "last_missed_at": r["last_missed_at"],
            "resolved_at": r["resolved_at"],
            "q": card.get("q", ""),
            "a": card.get("a", ""),
        })
    return out


def fehlerbuch_summary(conn: sqlite3.Connection, module: str = "organic") -> dict:
    row = conn.execute(
        """SELECT
             COUNT(*) total,
             SUM(CASE WHEN resolved_at IS NULL THEN 1 ELSE 0 END) open,
             SUM(CASE WHEN resolved_at IS NOT NULL THEN 1 ELSE 0 END) resolved
           FROM fehlerbuch WHERE module=?""",
        (module,),
    ).fetchone()
    by_kap = conn.execute(
        """SELECT c.kap kap, COUNT(*) n FROM fehlerbuch f JOIN cards c ON c.id=f.card_id
           WHERE f.module=? AND f.resolved_at IS NULL AND c.kap IS NOT NULL
           GROUP BY c.kap ORDER BY n DESC LIMIT 5""",
        (module,),
    ).fetchall()
    return {
        "total": row["total"] or 0,
        "open": row["open"] or 0,
        "resolved": row["resolved"] or 0,
        "top_chapters": [{"kap": r["kap"], "count": r["n"]} for r in by_kap],
    }


# ---------------------------------------------------------------------------
# Item analytics: per-card performance from the reviews log.
# ---------------------------------------------------------------------------

def item_analytics(conn: sqlite3.Connection, module: str = "organic", limit: int = 40) -> dict:
    rows = conn.execute(
        """SELECT c.id, c.kap, c.subname, c.payload, c.reps, c.lapses,
                  c.stability, c.difficulty, c.status,
                  COUNT(r.id) n_rev,
                  SUM(CASE WHEN r.rating>=3 THEN 1 ELSE 0 END) hits,
                  SUM(CASE WHEN r.rating=1 THEN 1 ELSE 0 END) agains,
                  AVG(r.rating) avg_rating
           FROM cards c LEFT JOIN reviews r ON r.card_id=c.id
           WHERE c.module=? AND c.deck='anki'
           GROUP BY c.id""",
        (module,),
    ).fetchall()
    items = []
    for r in rows:
        n = r["n_rev"] or 0
        hit_rate = round((r["hits"] or 0) / n * 100) if n else None
        card = row_to_card(r)
        # difficulty score: FSRS difficulty + penalty for low hit-rate + lapses
        pain = (r["difficulty"] or 0) * 8 + (r["lapses"] or 0) * 12
        if hit_rate is not None:
            pain += (100 - hit_rate) * 0.6
        items.append({
            "card_id": r["id"],
            "kap": r["kap"],
            "subname": r["subname"],
            "title": _plain_title(card.get("q", "")),
            "reps": r["reps"] or 0,
            "reviews": n,
            "hit_rate": hit_rate,
            "agains": r["agains"] or 0,
            "lapses": r["lapses"] or 0,
            "avg_rating": round(r["avg_rating"], 2) if r["avg_rating"] is not None else None,
            "stability": round(r["stability"] or 0, 1),
            "difficulty": round(r["difficulty"] or 0, 2),
            "pain": round(pain, 1),
            "status": r["status"],
        })
    reviewed = [i for i in items if i["reviews"] > 0]
    worst = sorted(reviewed, key=lambda i: -i["pain"])[:limit]
    total_rev = sum(i["reviews"] for i in items)
    overall_hits = sum((i["hit_rate"] or 0) * i["reviews"] for i in reviewed)
    overall_hit_rate = round(overall_hits / sum(i["reviews"] for i in reviewed)) if reviewed else 0
    return {
        "worst": worst,
        "cards_total": len(items),
        "cards_reviewed": len(reviewed),
        "reviews_total": total_rev,
        "overall_hit_rate": overall_hit_rate,
    }


def _plain_title(q: str) -> str:
    text = q.split("\n\n", 1)[1] if "\n\n" in q else q
    text = re.sub(r"<[^>]+>", "", text)
    return text[:110].strip()


# ---------------------------------------------------------------------------
# FSRS insights: scheduling forecast and state/retention distribution.
# ---------------------------------------------------------------------------

def fsrs_insights(conn: sqlite3.Connection, module: str = "organic", days: int = 14) -> dict:
    today = date.today()
    rows = conn.execute(
        """SELECT status, state, stability, due FROM cards
           WHERE module=? AND deck='anki'""",
        (module,),
    ).fetchall()
    active = [r for r in rows if r["status"] == "active"]
    forecast = []
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        n = sum(1 for r in active if (r["due"] or "")[:10] == d)
        forecast.append({"date": d, "count": n})
    overdue = sum(1 for r in active if r["due"] and r["due"][:10] < today.isoformat())
    new = sum(1 for r in active if not r["due"])
    buckets = {"jung (<7d)": 0, "reifend (7-30d)": 0, "stabil (>30d)": 0}
    for r in active:
        s = r["stability"] or 0
        if s <= 0:
            continue
        if s < 7:
            buckets["jung (<7d)"] += 1
        elif s < 30:
            buckets["reifend (7-30d)"] += 1
        else:
            buckets["stabil (>30d)"] += 1
    retention_row = conn.execute(
        """SELECT AVG(CASE WHEN rating>=3 THEN 1.0 ELSE 0.0 END) ret, COUNT(*) n
           FROM reviews r JOIN cards c ON c.id=r.card_id
           WHERE c.module=? AND r.elapsed_days >= 1""",
        (module,),
    ).fetchone()
    return {
        "forecast": forecast,
        "overdue": overdue,
        "new": new,
        "active": len(active),
        "stability_buckets": [{"label": k, "count": v} for k, v in buckets.items()],
        "retention_pct": round((retention_row["ret"] or 0) * 100) if retention_row["n"] else None,
        "retention_reviews": retention_row["n"] or 0,
    }


# ---------------------------------------------------------------------------
# Gamification: quest claims.
# ---------------------------------------------------------------------------

def claim_quest(conn: sqlite3.Connection, quest_key: str, period_start: str,
                amount: int, created_at: str) -> bool:
    exists = conn.execute(
        "SELECT 1 FROM quest_claims WHERE quest_key=? AND period_start=?",
        (quest_key, period_start),
    ).fetchone()
    if exists:
        return False
    conn.execute(
        "INSERT INTO quest_claims(quest_key, period_start, claimed_at, amount) VALUES(?,?,?,?)",
        (quest_key, period_start, created_at, amount),
    )
    conn.commit()
    return True


def claimed_quests(conn: sqlite3.Connection, period_starts: list[str]) -> set[str]:
    if not period_starts:
        return set()
    marks = ",".join("?" for _ in period_starts)
    rows = conn.execute(
        f"SELECT quest_key, period_start FROM quest_claims WHERE period_start IN ({marks})",
        period_starts,
    ).fetchall()
    return {f"{r['quest_key']}|{r['period_start']}" for r in rows}


def reviews_count_since(conn: sqlite3.Connection, since_iso: str, module: str | None = None) -> int:
    if module:
        row = conn.execute(
            """SELECT COUNT(*) n FROM reviews r JOIN cards c ON c.id=r.card_id
               WHERE r.reviewed_at>=? AND c.module=?""",
            (since_iso, module),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) n FROM reviews WHERE reviewed_at>=?", (since_iso,)
        ).fetchone()
    return row["n"] or 0
