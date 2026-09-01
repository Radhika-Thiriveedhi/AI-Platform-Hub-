"""SQLite persistence for AI Platform Hub.

The original application kept almost everything in process memory.  This module
adds a small, dependency-free persistence layer so chat history, image
history, analysis runs, contacts, and usage events survive restarts.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_BASE_DIR = Path(__file__).resolve().parents[1]
_DATA_DIR = _BASE_DIR / "data" / "runtime"
_DEFAULT_DB = _DATA_DIR / "platform.db"
_DB_PATH = Path(os.getenv("AI_HUB_DB_PATH", str(_DEFAULT_DB)))
_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _schema_sql() -> str:
    return """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant','system')), content TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_messages(conversation_id, id);
        CREATE TABLE IF NOT EXISTS generations (id TEXT PRIMARY KEY, prompt TEXT NOT NULL, enhanced_prompt TEXT NOT NULL, style TEXT NOT NULL, style_name TEXT NOT NULL, seed INTEGER, width INTEGER NOT NULL, height INTEGER NOT NULL, provider TEXT NOT NULL, status TEXT NOT NULL, image_url TEXT, estimated_cost REAL DEFAULT 0, error TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);
        CREATE TABLE IF NOT EXISTS analysis_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_type TEXT NOT NULL, text_length INTEGER NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS usage_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, model TEXT, units REAL DEFAULT 1, estimated_cost REAL DEFAULT 0, metadata_json TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_events(created_at DESC);
        CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, subject TEXT, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL);
    """


def init_db() -> None:
    """Create the runtime database and all tables if they do not exist."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        conn = sqlite3.connect(str(_DB_PATH), timeout=15)
        try:
            conn.executescript(_schema_sql())
            conn.commit()
        finally:
            conn.close()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection with safe commit/rollback."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        first_create = not _DB_PATH.exists()
        conn = sqlite3.connect(str(_DB_PATH), timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            if first_create:
                conn.executescript(_schema_sql())
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def add_chat_message(conversation_id: str, role: str, content: str, model: str = "") -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages(conversation_id, role, content, model, created_at) VALUES(?,?,?,?,?)",
            (conversation_id, role, content, model, utc_now()),
        )


def get_chat_messages(conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, conversation_id, role, content, model, created_at FROM chat_messages "
            "WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conversation_id, max(1, min(limit, 200))),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_chat_messages(conversation_id: str) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE conversation_id=?", (conversation_id,))


def add_generation(result: Dict[str, Any]) -> None:
    with connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO generations
            (id,prompt,enhanced_prompt,style,style_name,seed,width,height,provider,status,image_url,estimated_cost,error,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result["generation_id"], result["prompt"], result["enhanced_prompt"],
                result["style"], result["style_name"], result.get("seed"),
                result.get("width", 1024), result.get("height", 1024),
                result.get("provider", "unknown"), result.get("status", "success"),
                result.get("image_url"), result.get("estimated_cost", 0),
                result.get("error"), result.get("created_at", utc_now()),
            ),
        )


def get_recent_generations(limit: int = 10) -> List[Dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM generations ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [dict(row) for row in rows]


def add_analysis_run(analysis_type: str, text_length: int, result: Dict[str, Any]) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO analysis_runs(analysis_type,text_length,result_json,created_at) VALUES(?,?,?,?)",
            (analysis_type, text_length, json.dumps(result, ensure_ascii=False), utc_now()),
        )


def add_usage_event(event_type: str, model: str = "", units: float = 1, estimated_cost: float = 0, metadata: Optional[Dict[str, Any]] = None) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO usage_events(event_type,model,units,estimated_cost,metadata_json,created_at) VALUES(?,?,?,?,?,?)",
            (event_type, model, units, estimated_cost, json.dumps(metadata or {}), utc_now()),
        )


def add_contact(name: str, email: str, subject: str, message: str) -> int:
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO contacts(name,email,subject,message,created_at) VALUES(?,?,?,?,?)",
            (name, email, subject, message, utc_now()),
        )
        return int(cur.lastrowid)


def get_usage_summary() -> Dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS events, COALESCE(SUM(units),0) AS units, COALESCE(SUM(estimated_cost),0) AS cost FROM usage_events"
        ).fetchone()
        generations = conn.execute("SELECT COUNT(*) AS count FROM generations WHERE status='success'").fetchone()["count"]
        analyses = conn.execute("SELECT COUNT(*) AS count FROM analysis_runs").fetchone()["count"]
        chats = conn.execute("SELECT COUNT(*) AS count FROM chat_messages WHERE role='user'").fetchone()["count"]
    return {
        "events": int(row["events"]),
        "units": float(row["units"]),
        "cost": round(float(row["cost"]), 6),
        "images_generated": int(generations),
        "analysis_runs": int(analyses),
        "chat_messages": int(chats),
    }
