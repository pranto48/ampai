import os
import sqlite3
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

DB_PATH = os.getenv("SESSION_RECALL_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "agent_data", "session_recall.db"))


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_session_recall_tables() -> None:
    conn = _conn()
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS session_recall_fts
            USING fts5(session_id, username, role, content, created_at, tags)
        """)
        conn.commit()
    finally:
        conn.close()


def index_chat_turn(session_id: str, username: str, role: str, content: str, tags: Optional[str] = "") -> None:
    ensure_session_recall_tables()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO session_recall_fts (session_id, username, role, content, created_at, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                username or "",
                role or "unknown",
                content or "",
                datetime.now(timezone.utc).isoformat(),
                tags or "",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def search_recall(query: str, username: Optional[str] = None, session_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    ensure_session_recall_tables()
    conn = _conn()
    try:
        sql = "SELECT rowid, session_id, username, role, content, created_at, tags FROM session_recall_fts WHERE session_recall_fts MATCH ?"
        params: List[Any] = [query.strip() or "*"]
        if username:
            sql += " AND username = ?"
            params.append(username)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY bm25(session_recall_fts) LIMIT ?"
        params.append(max(1, min(int(limit), 100)))
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def summarize_hits(hits: List[Dict[str, Any]], max_items: int = 5) -> str:
    if not hits:
        return "No matching cross-session memories found."
    lines: List[str] = []
    grouped: Dict[str, List[str]] = {}
    for hit in hits[: max_items * 3]:
        grouped.setdefault(hit.get("session_id") or "unknown", []).append((hit.get("content") or "").strip())
    for sid, snippets in list(grouped.items())[:max_items]:
        short = " ".join([s for s in snippets[:2] if s])[:220]
        lines.append(f"- Session {sid[:12]}: {short}")
    return "Cross-session recall summary:\n" + "\n".join(lines)
