"""
AmpAI Memory Curator
====================
LLM-driven curation of conversations into persistent memory facts.
Runs on a schedule (every 6h) and also on-demand.

Inspired by hermes-agent's periodic nudge system:
  - After sessions end, the LLM reviews the transcript
  - Extracts facts worth remembering
  - Creates 'curator_nudges' that the user can Accept or Dismiss
  - Accepted nudges are promoted to core_memories
"""
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database import engine, get_config, add_core_memory, list_chat_messages
from ampai_identity import get_memory_curation_prompt

logger = logging.getLogger("ampai.memory_curator")

# How many recent unreviewed sessions to curate per run
CURATION_BATCH_SIZE = 5
# Minimum messages in a session before we bother curating it
MIN_MESSAGES_TO_CURATE = 4


def _ensure_curator_nudges_table() -> None:
    """Create curator_nudges table if it doesn't exist."""
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS curator_nudges (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    session_id VARCHAR,
                    nudge_type VARCHAR NOT NULL DEFAULT 'memory_suggestion',
                    payload JSONB NOT NULL DEFAULT '{}',
                    status VARCHAR NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    reviewed_at TIMESTAMPTZ
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_curator_nudges_username_status "
                "ON curator_nudges (username, status)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_curator_nudges_created "
                "ON curator_nudges (created_at DESC)"
            ))
    except Exception as exc:
        logger.warning("Could not create curator_nudges table: %s", exc)


_ensure_curator_nudges_table()


def _call_local_llm(prompt: str, model_type: str = "ollama") -> str:
    """
    Call the local LLM for memory curation.
    Reuses get_llm() from agent.py to ensure provider fallback logic applies.
    """
    try:
        from agent import get_llm
        llm = get_llm(model_type)
        resp = llm.invoke(prompt)
        return resp.content if hasattr(resp, "content") else str(resp)
    except Exception as exc:
        logger.warning("LLM call failed in memory curator: %s", exc)
        return ""


def _mark_session_curated(session_id: str, username: str) -> None:
    """Mark a session as curated so we don't re-process it."""
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO session_curation_log (session_id, username, curated_at)
                    VALUES (:sid, :uname, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET curated_at = NOW()
                """),
                {"sid": session_id, "uname": username},
            )
    except Exception:
        # Table may not exist yet — silently skip
        pass


def _get_uncurated_sessions(username: str, limit: int = CURATION_BATCH_SIZE) -> List[str]:
    """Return session IDs that have enough messages but haven't been curated yet."""
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            # Sessions with messages that have NOT been marked curated
            rows = conn.execute(
                text("""
                    SELECT DISTINCT ms.session_id
                    FROM message_store ms
                    WHERE ms.session_id IS NOT NULL
                      AND ms.session_id NOT IN (
                          SELECT session_id FROM session_curation_log
                          WHERE username = :uname
                      )
                    ORDER BY ms.session_id DESC
                    LIMIT :lim
                """),
                {"uname": username, "lim": limit},
            ).fetchall()
            return [row[0] for row in rows if row and row[0]]
    except Exception as exc:
        logger.debug("get_uncurated_sessions failed: %s", exc)
        return []


def _ensure_curation_log_table() -> None:
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS session_curation_log (
                    session_id VARCHAR PRIMARY KEY,
                    username VARCHAR NOT NULL,
                    curated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
    except Exception:
        pass


_ensure_curation_log_table()


def create_nudge(
    username: str,
    fact: str,
    session_id: Optional[str] = None,
    nudge_type: str = "memory_suggestion",
) -> Optional[int]:
    """
    Insert a curator nudge into the database.
    Returns the new nudge ID, or None on failure.
    """
    if not engine or not fact or not fact.strip():
        return None
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO curator_nudges (username, session_id, nudge_type, payload, status, created_at)
                    VALUES (:uname, :sid, :ntype, :payload, 'pending', NOW())
                    RETURNING id
                """),
                {
                    "uname": username,
                    "sid": session_id,
                    "ntype": nudge_type,
                    "payload": json.dumps({"fact": fact.strip(), "source_session": session_id}),
                },
            )
            row = result.fetchone()
            return int(row[0]) if row else None
    except Exception as exc:
        logger.warning("create_nudge failed: %s", exc)
        return None


def list_pending_nudges(username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Return pending curator nudges for a user."""
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, username, session_id, nudge_type, payload, status, created_at
                    FROM curator_nudges
                    WHERE username = :uname AND status = 'pending'
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"uname": username, "lim": max(1, min(limit, 100))},
            ).fetchall()
            result = []
            for r in rows:
                payload = {}
                try:
                    payload = json.loads(r[4]) if r[4] else {}
                except Exception:
                    pass
                result.append({
                    "id": r[0],
                    "username": r[1],
                    "session_id": r[2],
                    "nudge_type": r[3],
                    "payload": payload,
                    "fact": payload.get("fact", ""),
                    "status": r[5],
                    "created_at": str(r[6]) if r[6] else None,
                })
            return result
    except Exception as exc:
        logger.warning("list_pending_nudges failed: %s", exc)
        return []


def dismiss_nudge(nudge_id: int, username: str) -> bool:
    """Dismiss a curator nudge (won't be saved to memory)."""
    if not engine:
        return False
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE curator_nudges
                    SET status = 'dismissed', reviewed_at = NOW()
                    WHERE id = :nid AND username = :uname
                """),
                {"nid": nudge_id, "uname": username},
            )
        return True
    except Exception as exc:
        logger.warning("dismiss_nudge failed: %s", exc)
        return False


def accept_nudge(nudge_id: int, username: str) -> Optional[str]:
    """
    Accept a curator nudge — promotes the fact to core_memories.
    Returns the saved fact text, or None on failure.
    """
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT payload FROM curator_nudges WHERE id = :nid AND username = :uname"),
                {"nid": nudge_id, "uname": username},
            ).fetchone()
        if not row:
            return None
        payload = {}
        try:
            payload = json.loads(row[0]) if row[0] else {}
        except Exception:
            pass
        fact = (payload.get("fact") or "").strip()
        if not fact:
            return None
        add_core_memory(fact)
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE curator_nudges
                    SET status = 'accepted', reviewed_at = NOW()
                    WHERE id = :nid AND username = :uname
                """),
                {"nid": nudge_id, "uname": username},
            )
        return fact
    except Exception as exc:
        logger.warning("accept_nudge failed: %s", exc)
        return None


def curate_session(
    session_id: str,
    username: str,
    model_type: str = "ollama",
    dry_run: bool = False,
) -> List[str]:
    """
    Run LLM curation on a single session.
    Returns list of facts extracted (nudges created or just returned in dry_run).
    """
    messages = list_chat_messages(session_id, dedupe=True)
    if len(messages) < MIN_MESSAGES_TO_CURATE:
        return []

    # Build transcript
    lines = []
    for msg in messages[-30:]:  # last 30 messages max
        role = "User" if msg.get("type") == "human" else "AmpAI"
        lines.append(f"{role}: {(msg.get('content') or '')[:400]}")
    transcript = "\n".join(lines)

    prompt = get_memory_curation_prompt(transcript, username)
    raw_response = _call_local_llm(prompt, model_type)

    # Parse JSON array response
    facts: List[str] = []
    try:
        cleaned = raw_response.strip()
        # Find the JSON array even if LLM added text around it
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start >= 0 and end > start:
            facts = json.loads(cleaned[start:end])
            facts = [f for f in facts if isinstance(f, str) and f.strip()]
    except Exception as exc:
        logger.debug("Failed to parse curation JSON from LLM: %s | raw=%s", exc, raw_response[:200])

    if dry_run:
        return facts

    # Create nudges
    created = []
    for fact in facts[:5]:
        nudge_id = create_nudge(username=username, fact=fact, session_id=session_id)
        if nudge_id:
            created.append(fact)

    if not dry_run:
        _mark_session_curated(session_id, username)

    return created


def run_scheduled_curation(model_type: str = "ollama") -> Dict[str, int]:
    """
    Called by APScheduler every 6 hours.
    Curates uncurated sessions for all active users.
    Returns stats dict.
    """
    if not engine:
        return {"sessions_reviewed": 0, "nudges_created": 0, "users_processed": 0}

    stats = {"sessions_reviewed": 0, "nudges_created": 0, "users_processed": 0}

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT DISTINCT username FROM users WHERE role IS NOT NULL")).fetchall()
            usernames = [r[0] for r in rows if r and r[0]]
    except Exception as exc:
        logger.warning("Could not load users for curation: %s", exc)
        return stats

    for username in usernames:
        sessions = _get_uncurated_sessions(username, limit=CURATION_BATCH_SIZE)
        if not sessions:
            continue
        stats["users_processed"] += 1
        for sid in sessions:
            try:
                facts = curate_session(sid, username, model_type=model_type)
                stats["sessions_reviewed"] += 1
                stats["nudges_created"] += len(facts)
                logger.info(
                    "Curated session %s for %s: %d facts", sid[:12], username, len(facts)
                )
            except Exception as exc:
                logger.warning("Curation failed for session %s: %s", sid, exc)

    return stats
