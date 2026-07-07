"""Authentifizierung: DB-gestützte Benutzerkonten + Sessions.

Bewusst nur mit der Standardbibliothek umgesetzt (kein zusätzliches
Dependency), damit das schlanke Image so bleibt:

* Passwörter: PBKDF2-HMAC-SHA256 mit pro-Benutzer-Salt, im Format
  ``pbkdf2_sha256$<iterations>$<salt-hex>$<hash-hex>`` in der DB.
* Sessions: zufälliges Token (``secrets.token_urlsafe``); in der DB wird nur
  der SHA-256-Hash des Tokens gespeichert. Das Klartext-Token lebt nur im
  HttpOnly-Cookie des Browsers.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

# --- Konfiguration (via Env überschreibbar) ---
PBKDF2_ITERATIONS = int(os.environ.get("AUTH_PBKDF2_ITERATIONS", "210000"))
SESSION_TTL_DAYS = int(os.environ.get("AUTH_SESSION_TTL_DAYS", "30"))
COOKIE_NAME = os.environ.get("AUTH_COOKIE_NAME", "organicsr_session")
# Cookie nur über HTTPS senden. In Produktion (öffentlich, TLS) unbedingt "1".
COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "1") not in ("0", "false", "False", "")

MIN_PASSWORD_LEN = 8


# ---------- Passwort-Hashing ----------
def hash_password(password: str, *, salt: str | None = None,
                  iterations: int = PBKDF2_ITERATIONS) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, hexhash = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), int(iters))
    return hmac.compare_digest(dk.hex(), hexhash)


# ---------- Session-Token ----------
def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + timedelta(days=SESSION_TTL_DAYS)


def cookie_max_age() -> int:
    return SESSION_TTL_DAYS * 86400
