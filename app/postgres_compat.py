"""Small sqlite3-style compatibility layer for PostgreSQL.

The app historically uses sqlite3 directly: qmark placeholders, ``executescript``,
``lastrowid`` and rows that support both ``row["name"]`` and ``row[0]``.
This module keeps that call surface stable while allowing ``DATABASE_URL`` to
switch the active database to PostgreSQL. Without ``DATABASE_URL`` the app keeps
using SQLite unchanged.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


# Tables whose INSERT needs a RETURNING id so ``cursor.lastrowid`` keeps working.
SERIAL_ID_TABLES = {
    "reviews",
    "xp_events",
    "quality_events",
    "users",
}


class CompatRow(dict):
    """Dict row that also supports sqlite3.Row-style positional access."""

    def __init__(self, values: dict[str, Any], columns: list[str]):
        super().__init__(values)
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, int):
            return dict.__getitem__(self, self._columns[key])
        return dict.__getitem__(self, key)


class PostgresCursor:
    def __init__(self, cursor, prefetched: list[CompatRow] | None = None,
                 columns: list[str] | None = None, lastrowid: int | None = None):
        self._cursor = cursor
        self._prefetched = prefetched
        self._columns = columns
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount if self._cursor is not None else 0

    def _columns_from_description(self) -> list[str]:
        if self._columns is not None:
            return self._columns
        self._columns = [col.name for col in (self._cursor.description or [])]
        return self._columns

    def _row(self, values):
        if values is None:
            return None
        columns = self._columns_from_description()
        return CompatRow(dict(zip(columns, values)), columns)

    def fetchone(self):
        if self._prefetched is not None:
            return self._prefetched.pop(0) if self._prefetched else None
        if self._cursor is None:
            return None
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        if self._prefetched is not None:
            rows = self._prefetched
            self._prefetched = []
            return rows
        if self._cursor is None:
            return []
        return [self._row(row) for row in self._cursor.fetchall()]

    def close(self):
        if self._cursor is not None:
            self._cursor.close()


class _NoopCursor:
    """Used for PRAGMA statements that Postgres does not understand."""
    description = None
    rowcount = 0


class PostgresConnection:
    def __init__(self, database_url: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL ist gesetzt, aber psycopg ist nicht installiert. "
                "Installiere die Requirements oder nutze SQLite ohne DATABASE_URL."
            ) from exc

        self._conn = psycopg.connect(database_url)

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> PostgresCursor:
        pragma = _pragma_table_info(sql)
        if pragma:
            return self._pragma_table_info(pragma)
        if _is_other_pragma(sql):
            # PRAGMA journal_mode / synchronous / ... -> no-op on Postgres.
            return PostgresCursor(_NoopCursor())

        translated = translate_sql(sql, params=params)
        translated, wants_lastrowid = _add_returning_id(translated)
        cur = self._conn.cursor()
        if params is None:
            cur.execute(translated)
        else:
            cur.execute(translated, tuple(params))

        lastrowid = None
        prefetched = None
        columns = None
        if wants_lastrowid and cur.description:
            row = cur.fetchone()
            if row:
                lastrowid = row[0]
            prefetched = []
            columns = [col.name for col in cur.description]
        return PostgresCursor(cur, prefetched=prefetched, columns=columns, lastrowid=lastrowid)

    def executemany(self, sql: str, seq_of_params):
        translated = translate_sql(sql, params=())
        cur = self._conn.cursor()
        cur.executemany(translated, [tuple(params) for params in seq_of_params])
        return PostgresCursor(cur)

    def executescript(self, script: str):
        last = None
        for statement in split_sql_script(script):
            if statement.strip():
                last = self.execute(statement)
        return last

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def _pragma_table_info(self, table: str) -> PostgresCursor:
        cur = self._conn.cursor()
        cur.execute(
            """SELECT column_name AS name
               FROM information_schema.columns
               WHERE table_schema = current_schema()
                 AND table_name = %s
               ORDER BY ordinal_position""",
            (table,),
        )
        return PostgresCursor(cur)


def split_sql_script(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    i = 0
    while i < len(script):
        ch = script[i]
        nxt = script[i + 1] if i + 1 < len(script) else ""
        current.append(ch)

        if line_comment:
            if ch == "\n":
                line_comment = False
        elif block_comment:
            if ch == "*" and nxt == "/":
                current.append(nxt)
                i += 1
                block_comment = False
        elif quote:
            if ch == quote and quote == "'" and nxt == "'":
                current.append(nxt)
                i += 1
            elif ch == quote and (i == 0 or script[i - 1] != "\\"):
                quote = None
        elif ch == "-" and nxt == "-":
            current.append(nxt)
            i += 1
            line_comment = True
        elif ch == "/" and nxt == "*":
            current.append(nxt)
            i += 1
            block_comment = True
        elif ch in {"'", '"'}:
            quote = ch
        elif ch == ";":
            statement = "".join(current).rstrip(";")
            if statement.strip():
                statements.append(statement)
            current = []
        i += 1
    statement = "".join(current)
    if statement.strip():
        statements.append(statement)
    return statements


def translate_sql(sql: str, params: Iterable[Any] | None = None) -> str:
    out = sql.strip()
    out = _translate_insert_or_replace(out)
    had_insert_or_ignore = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", out, flags=re.IGNORECASE))
    out = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", out, flags=re.IGNORECASE)
    if had_insert_or_ignore and "ON CONFLICT" not in out.upper():
        out = f"{out} ON CONFLICT DO NOTHING"
    out = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", out, flags=re.IGNORECASE)
    out = re.sub(r"(\b[\w.]+\b)\s*=\s*\?\s+COLLATE\s+NOCASE", r"LOWER(\1) = LOWER(?)", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+COLLATE\s+NOCASE\b", "", out, flags=re.IGNORECASE)
    # datetime('now') -> Postgres timestamp text (ISO-ish)
    out = re.sub(r"datetime\(\s*'now'\s*\)", "now()::text", out, flags=re.IGNORECASE)
    out = re.sub(
        r"json_extract\(([^,]+),\s*'\$\.(\w+)'\)",
        r"(\1::jsonb ->> '\2')",
        out,
        flags=re.IGNORECASE,
    )
    out = replace_qmarks(out)
    if params is not None:
        out = escape_literal_percents(out)
    return out


def replace_qmarks(sql: str) -> str:
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote and (i == 0 or sql[i - 1] != "\\"):
                quote = None
        elif ch in {"'", '"'}:
            quote = ch
            out.append(ch)
        elif ch == "?":
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def escape_literal_percents(sql: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if ch == "%" and nxt not in {"s", "b", "t", "(", "%"}:
            out.append("%%")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _translate_insert_or_replace(sql: str) -> str:
    match = re.match(
        r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s+VALUES\s*(\(.+\))\s*$",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return sql
    table, cols_raw, values = match.groups()
    cols = [c.strip() for c in cols_raw.split(",")]
    conflict = cols[0]
    updates = ", ".join(f"{col}=EXCLUDED.{col}" for col in cols[1:])
    return (
        f"INSERT INTO {table}({cols_raw}) VALUES {values} "
        f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
    )


def _add_returning_id(sql: str) -> tuple[str, bool]:
    if "RETURNING" in sql.upper() or "ON CONFLICT" in sql.upper():
        return sql, False
    match = re.match(r"^\s*INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return sql, False
    table, cols_raw = match.groups()
    if table not in SERIAL_ID_TABLES:
        return sql, False
    cols = {c.strip().strip('"').lower() for c in cols_raw.split(",")}
    if "id" in cols:
        return sql, False
    return f"{sql} RETURNING id", True


def _pragma_table_info(sql: str) -> str | None:
    match = re.match(r"^\s*PRAGMA\s+table_info\((\w+)\)\s*;?\s*$", sql, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _is_other_pragma(sql: str) -> bool:
    return bool(re.match(r"^\s*PRAGMA\b", sql, flags=re.IGNORECASE))
