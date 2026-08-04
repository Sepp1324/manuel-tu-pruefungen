"""Optional Redis cache helpers.

Redis is intentionally non-critical: every helper fails closed and lets the app
compute responses directly when Redis is not configured or temporarily down.
"""
from __future__ import annotations

import json
import fnmatch
import os
import time
from typing import Any
from urllib.parse import urlparse

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
DEFAULT_TTL = int(os.environ.get("REDIS_CACHE_TTL", "8") or "8")

_client = None
_client_error: str | None = None
_memory_cache: dict[str, tuple[float, str]] = {}


def configured() -> bool:
    return REDIS_URL.startswith(("redis://", "rediss://"))


def _masked_url() -> dict | None:
    if not REDIS_URL:
        return None
    parsed = urlparse(REDIS_URL)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path.lstrip("/") or "0",
        "configured": True,
    }


def client():
    global _client, _client_error
    if not configured():
        return None
    if _client is not None:
        return _client
    try:
        import redis

        _client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )
        _client_error = None
        return _client
    except Exception as exc:
        _client_error = str(exc)
        return None


def health_info() -> dict:
    info = {"configured": configured(), "redis": _masked_url(), "status": "disabled"}
    if not configured():
        return info
    c = client()
    if c is None:
        info["status"] = "error"
        info["error"] = _client_error or "Redis client unavailable"
        return info
    try:
        c.ping()
        info["status"] = "ok"
    except Exception as exc:
        info["status"] = "error"
        info["error"] = str(exc)
    return info


def get_json(key: str) -> Any | None:
    c = client()
    if c is None:
        return _memory_get_json(key)
    try:
        raw = c.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return _memory_get_json(key)


def set_json(key: str, value: Any, ttl: int | None = None) -> bool:
    c = client()
    if c is None:
        return _memory_set_json(key, value, ttl)
    try:
        c.setex(key, ttl or DEFAULT_TTL, json.dumps(value, ensure_ascii=False, default=str))
        return True
    except Exception:
        return _memory_set_json(key, value, ttl)


def delete_pattern(pattern: str) -> int:
    deleted = _memory_delete_pattern(pattern)
    c = client()
    if c is None:
        return deleted
    try:
        for key in c.scan_iter(pattern, count=100):
            deleted += c.delete(key)
    except Exception:
        return deleted
    return deleted


def _memory_get_json(key: str) -> Any | None:
    item = _memory_cache.get(key)
    if not item:
        return None
    expires_at, raw = item
    if expires_at <= time.monotonic():
        _memory_cache.pop(key, None)
        return None
    try:
        return json.loads(raw)
    except Exception:
        _memory_cache.pop(key, None)
        return None


def _memory_set_json(key: str, value: Any, ttl: int | None = None) -> bool:
    lifetime = max(1, int(ttl or DEFAULT_TTL))
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return False
    _memory_cache[key] = (time.monotonic() + lifetime, raw)
    return True


def _memory_delete_pattern(pattern: str) -> int:
    # Erst einen atomaren Schnappschuss der Keys ziehen (list(dict) laeuft unter dem GIL
    # ununterbrochen), DANN mit fnmatch filtern. Sonst kann ein paralleler Request das
    # Dict waehrend der Iteration aendern -> "dictionary keys changed during iteration"
    # (500er, obwohl die Aenderung des Clients laengst gespeichert ist).
    keys = [key for key in list(_memory_cache.keys()) if fnmatch.fnmatch(key, pattern)]
    for key in keys:
        _memory_cache.pop(key, None)
    return len(keys)
