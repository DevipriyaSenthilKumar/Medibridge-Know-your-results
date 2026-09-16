"""Minimal local persistence for users, sessions and report history.

SQLite (standard library) keeps the whole privacy story local: no cloud, no
externally-hosted medical data. Passwords are hashed with PBKDF2-HMAC-SHA256
and session tokens are random 32-byte values stored only on the client.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(os.environ.get("MEDIBRIDGE_DB", str(Path(__file__).resolve().parent / "history.db")))
_LOCK = threading.RLock()
_PBKDF2_ITERATIONS = 120_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    analysis TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id, kind, created_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_schema() -> None:
    """Create tables if the DB file is missing/recreated."""
    with _LOCK, _connect() as conn:
        conn.executescript(_SCHEMA)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return secrets.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_user(email: str, password: str) -> Optional[dict]:
    """Create a user. Returns dict with id/email or None if email is taken."""
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters long.")
    email = email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as conn:
        _ensure_schema()
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, _hash_password(password), now),
            )
        except sqlite3.IntegrityError:
            return None
        return {"id": cur.lastrowid, "email": email}


def verify_user(email: str, password: str) -> Optional[dict]:
    email = email.strip().lower()
    with _LOCK, _connect() as conn:
        _ensure_schema()
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"]}


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as conn:
        _ensure_schema()
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now),
        )
    return token


def get_user_by_token(token: str) -> Optional[dict]:
    with _LOCK, _connect() as conn:
        _ensure_schema()
        row = conn.execute(
            """
            SELECT u.id, u.email FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "email": row["email"]}


def delete_session(token: str) -> None:
    with _LOCK, _connect() as conn:
        _ensure_schema()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def add_report(user_id: int, kind: str, language: str, analysis: dict) -> int:
    summary = (
        analysis.get("report_summary", "").strip()
        or str(analysis.get("medicines", ""))[:80]
        or "Report"
    )
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as conn:
        _ensure_schema()
        cur = conn.execute(
            "INSERT INTO reports (user_id, kind, language, analysis, summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, kind, language, json.dumps(analysis, ensure_ascii=False), summary, now),
        )
        return cur.lastrowid


def list_reports(user_id: int) -> list[dict]:
    with _LOCK, _connect() as conn:
        _ensure_schema()
        rows = conn.execute(
            "SELECT id, kind, language, summary, created_at FROM reports "
            "WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report(user_id: int, report_id: int) -> Optional[dict]:
    with _LOCK, _connect() as conn:
        _ensure_schema()
        row = conn.execute(
            "SELECT id, kind, language, analysis, summary, created_at FROM reports "
            "WHERE id = ? AND user_id = ?",
            (report_id, user_id),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["analysis"] = json.loads(data["analysis"])
    return data


def get_previous_report(user_id: int, report_id: int, kind: str) -> Optional[dict]:
    with _LOCK, _connect() as conn:
        _ensure_schema()
        row = conn.execute(
            "SELECT id, kind, language, analysis, created_at FROM reports "
            "WHERE user_id = ? AND kind = ? AND id < ? "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (user_id, kind, report_id),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["analysis"] = json.loads(data["analysis"])
    return data