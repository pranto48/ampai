import math
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


def search_recall_hybrid(
    query: str,
    username: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 20,
    lexical_weight: float = 0.35,
    semantic_weight: float = 0.55,
    recency_weight: float = 0.10,
) -> List[Dict[str, Any]]:
    hits = search_recall(query=query, username=username, session_id=session_id, limit=max(10, limit * 4))
    if not hits:
        return []
    try:
        from memory_indexer import get_embedding_model
        embedder = get_embedding_model("ollama")
        query_embedding = embedder.embed_query(query)
    except Exception:
        return hits[: max(1, min(int(limit), 100))]

    lexical_values = [float(abs(h.get("rowid") or 0)) for h in hits]
    lexical_max = max(lexical_values) if lexical_values else 1.0
    lexical_max = lexical_max if lexical_max > 0 else 1.0
    now = datetime.now(timezone.utc)
    scored: List[Dict[str, Any]] = []

    for h in hits:
        content = (h.get("content") or "").strip()
        if not content:
            continue
        try:
            emb = embedder.embed_query(content[:2000])
            dot = sum((a * b) for a, b in zip(query_embedding, emb))
            qn = math.sqrt(sum((a * a) for a in query_embedding)) or 1.0
            en = math.sqrt(sum((b * b) for b in emb)) or 1.0
            semantic_score = max(0.0, min(1.0, (dot / (qn * en) + 1.0) / 2.0))
        except Exception:
            semantic_score = 0.0

        created_at = h.get("created_at") or ""
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            recency_score = 1.0 / (1.0 + (age_days / 7.0))
        except Exception:
            recency_score = 0.0

        lexical_score = 1.0 - (float(abs(h.get("rowid") or 0)) / lexical_max)
        hybrid = (lexical_weight * lexical_score) + (semantic_weight * semantic_score) + (recency_weight * recency_score)
        item = dict(h)
        item["scores"] = {
            "hybrid": round(hybrid, 6),
            "lexical": round(lexical_score, 6),
            "semantic": round(semantic_score, 6),
            "recency": round(recency_score, 6),
        }
        scored.append(item)

    scored.sort(key=lambda x: x.get("scores", {}).get("hybrid", 0.0), reverse=True)
    return scored[: max(1, min(int(limit), 100))]


def summarize_hits(hits: List[Dict[str, Any]], max_items: int = 5) -> str:
    """Rule-based summarizer (kept for compatibility). Use llm_summarize_hits for LLM version."""
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


def llm_summarize_hits(
    hits: List[Dict[str, Any]],
    query: str,
    model_type: str = "ollama",
    max_snippets: int = 10,
) -> str:
    """
    Use the local LLM (AmpAI / Ollama) to produce a coherent, query-relevant summary
    of FTS5 cross-session search hits. This is the hermes-agent-style context injection.
    Falls back to rule-based summarizer if the LLM call fails.
    """
    if not hits:
        return ""

    raw_snippets = "\n".join([
        f"[Session {h.get('session_id', '')[:8]} | {h.get('role', 'unknown')}]: {(h.get('content') or '')[:300]}"
        for h in hits[:max_snippets]
    ])

    prompt = (
        "You are reviewing past conversation snippets to find context relevant to a current query.\n\n"
        f'Current query: "{query}"\n\n'
        f"Past conversation snippets:\n{raw_snippets}\n\n"
        "Provide a concise 2-3 sentence summary of what is relevant to the current query. "
        "Focus only on actionable context. If nothing is relevant, respond with exactly: (no relevant past context)"
    )

    try:
        from agent import get_llm
        llm = get_llm(model_type)
        resp = llm.invoke(prompt)
        result = (resp.content if hasattr(resp, "content") else str(resp)).strip()
        if "(no relevant past context)" in result.lower() or not result:
            return ""
        return result
    except Exception:
        return summarize_hits(hits, max_items=3)


def search_and_summarize(
    query: str,
    username: Optional[str] = None,
    model_type: str = "ollama",
    limit: int = 15,
    use_llm: bool = True,
) -> str:
    """
    One-stop function: FTS5 search + LLM summarization.
    Called by agent.py to inject cross-session context into every chat turn.
    Returns empty string if nothing relevant found.
    """
    if not query or not query.strip():
        return ""
    hits = search_recall(query, username=username, limit=limit)
    if not hits:
        return ""
    if use_llm:
        return llm_summarize_hits(hits, query, model_type=model_type)
    return summarize_hits(hits, max_items=5)


def bulk_index_unindexed_sessions(batch_size: int = 50) -> Dict[str, int]:
    """
    Nightly scheduled job: index chat sessions not yet in the FTS5 store.
    Reads from PostgreSQL message_store and writes to SQLite FTS5.
    """
    stats: Dict[str, int] = {"sessions_indexed": 0, "turns_indexed": 0, "errors": 0}

    ensure_session_recall_tables()
    conn = _conn()
    try:
        indexed_sessions = set(
            row["session_id"]
            for row in conn.execute("SELECT DISTINCT session_id FROM session_recall_fts").fetchall()
            if row["session_id"]
        )
    finally:
        conn.close()

    try:
        from database import engine, list_chat_messages, get_all_sessions
        if not engine:
            return stats
        all_sessions = get_all_sessions()
        unindexed = [s["session_id"] for s in all_sessions if s["session_id"] not in indexed_sessions]
        for session_id in unindexed[:batch_size]:
            try:
                messages = list_chat_messages(session_id, dedupe=True)
                for msg in messages:
                    role = "human" if msg.get("type") == "human" else "ai"
                    content = (msg.get("content") or "").strip()
                    if content:
                        index_chat_turn(session_id=session_id, username="", role=role, content=content)
                        stats["turns_indexed"] += 1
                stats["sessions_indexed"] += 1
            except Exception:
                stats["errors"] += 1
    except Exception:
        stats["errors"] += 1

    return stats


def get_fts_stats() -> Dict[str, Any]:
    """Return stats about the FTS5 index for admin/health dashboards."""
    ensure_session_recall_tables()
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM session_recall_fts").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM session_recall_fts").fetchone()[0]
        return {
            "total_turns_indexed": int(total or 0),
            "distinct_sessions": int(sessions or 0),
            "db_path": DB_PATH,
        }
    finally:
        conn.close()
