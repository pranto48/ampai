"""
AmpAI Skill Engine
==================
Autonomous skill creation, execution, and self-improvement.
Inspired by hermes-agent's skill system (hermes-agent/skills/).

Key concepts:
  - Skills are reusable prompt templates for recurring tasks
  - Skills are auto-detected after complex multi-step tasks
  - Skills self-improve: each run is scored; failing skills get their prompts rewritten
  - Skills track version history
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from database import engine, get_config

logger = logging.getLogger("ampai.skill_engine")

# Complexity signals that suggest a skill opportunity
_SKILL_TRIGGER_SIGNALS = [
    r"\b(step \d|first[,.]|second[,.]|then|finally|summarize|analyze|convert|generate|extract|format|transform)\b",
    r"\b(write a|create a|build a|make a|set up|configure|deploy|install|draft)\b",
    r"\[SKILL_OPPORTUNITY:",
]
_SKILL_OPPORTUNITY_RE = re.compile(
    r"\[SKILL_OPPORTUNITY:\s*([^|\]]+)\|([^\]]+)\]", re.IGNORECASE
)
_SKILL_COMPLETE_RE = re.compile(
    r"\[SKILL_COMPLETE:\s*(success|failure|partial)\]", re.IGNORECASE
)
_SKILL_IMPROVEMENT_RE = re.compile(
    r"\[SKILL_IMPROVEMENT:\s*([^\]]+)\]", re.IGNORECASE | re.DOTALL
)

# Success rate threshold below which self-improvement triggers
IMPROVEMENT_THRESHOLD = 0.65
MIN_RUNS_BEFORE_IMPROVEMENT = 5


def _ensure_skill_tables() -> None:
    """Create agent_skills, skill_runs, and skill_versions tables."""
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_skills (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    description TEXT,
                    trigger_pattern VARCHAR,
                    system_prompt TEXT NOT NULL,
                    parameters JSONB DEFAULT '{}',
                    tags VARCHAR,
                    success_rate FLOAT DEFAULT 0.0,
                    run_count INTEGER DEFAULT 0,
                    version INTEGER DEFAULT 1,
                    created_by VARCHAR,
                    is_auto_created BOOLEAN DEFAULT FALSE,
                    status VARCHAR DEFAULT 'active',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    last_improved_at TIMESTAMPTZ,
                    CONSTRAINT agent_skills_name_unique UNIQUE (name)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS skill_runs (
                    id SERIAL PRIMARY KEY,
                    skill_id INTEGER REFERENCES agent_skills(id) ON DELETE CASCADE,
                    session_id VARCHAR,
                    username VARCHAR,
                    parameters JSONB DEFAULT '{}',
                    outcome VARCHAR DEFAULT 'unknown',
                    user_rating INTEGER,
                    improvement_applied TEXT,
                    notes TEXT,
                    latency_ms INTEGER,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    finished_at TIMESTAMPTZ
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS skill_versions (
                    id SERIAL PRIMARY KEY,
                    skill_id INTEGER REFERENCES agent_skills(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    system_prompt TEXT NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_skill_runs_skill_id ON skill_runs (skill_id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_skill_runs_outcome ON skill_runs (outcome)"
            ))
    except Exception as exc:
        logger.warning("Could not ensure skill tables: %s", exc)


_ensure_skill_tables()


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_skill(
    name: str,
    description: str,
    system_prompt: str,
    trigger_pattern: str = "",
    parameters: Optional[Dict] = None,
    tags: str = "",
    created_by: str = "system",
    is_auto_created: bool = False,
) -> Optional[Dict[str, Any]]:
    """Create a new agent skill. Returns the created skill dict, or None on failure."""
    if not engine or not name.strip() or not system_prompt.strip():
        return None
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO agent_skills
                        (name, description, trigger_pattern, system_prompt, parameters, tags,
                         created_by, is_auto_created, status, created_at, updated_at)
                    VALUES
                        (:name, :desc, :trigger, :prompt, :params, :tags,
                         :created_by, :auto, 'active', NOW(), NOW())
                    ON CONFLICT (name) DO UPDATE
                        SET description = EXCLUDED.description,
                            system_prompt = EXCLUDED.system_prompt,
                            updated_at = NOW()
                    RETURNING id, name, version
                """),
                {
                    "name": name.strip()[:200],
                    "desc": (description or "").strip()[:1000],
                    "trigger": (trigger_pattern or "").strip()[:500],
                    "prompt": system_prompt.strip(),
                    "params": json.dumps(parameters or {}),
                    "tags": (tags or "").strip()[:500],
                    "created_by": (created_by or "system")[:100],
                    "auto": is_auto_created,
                },
            )
            row = result.fetchone()
            if not row:
                return None
            skill_id, skill_name, version = row[0], row[1], row[2]
            # Save initial version
            conn.execute(
                text("""
                    INSERT INTO skill_versions (skill_id, version, system_prompt, reason)
                    VALUES (:sid, :ver, :prompt, 'initial')
                    ON CONFLICT DO NOTHING
                """),
                {"sid": skill_id, "ver": version or 1, "prompt": system_prompt.strip()},
            )
        return get_skill(skill_id)
    except Exception as exc:
        logger.warning("create_skill failed: %s", exc)
        return None


def get_skill(skill_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single skill by ID."""
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM agent_skills WHERE id = :sid"),
                {"sid": skill_id},
            ).fetchone()
            if not row:
                return None
            return dict(row._mapping)
    except Exception as exc:
        logger.warning("get_skill failed: %s", exc)
        return None


def list_skills(
    status: str = "active",
    created_by: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List agent skills, optionally filtered by status/creator."""
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            where = "WHERE status = :status"
            params: Dict[str, Any] = {"status": status, "lim": min(limit, 500)}
            if created_by:
                where += " AND created_by = :creator"
                params["creator"] = created_by
            rows = conn.execute(
                text(f"SELECT * FROM agent_skills {where} ORDER BY run_count DESC, updated_at DESC LIMIT :lim"),
                params,
            ).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("list_skills failed: %s", exc)
        return []


def update_skill(skill_id: int, **kwargs) -> bool:
    """Update skill fields. Returns True on success."""
    if not engine:
        return False
    allowed = {"name", "description", "trigger_pattern", "system_prompt", "parameters", "tags", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    try:
        with engine.begin() as conn:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["sid"] = skill_id
            updates["updated_at"] = datetime.now(timezone.utc)
            conn.execute(
                text(f"UPDATE agent_skills SET {set_clause}, updated_at = :updated_at WHERE id = :sid"),
                updates,
            )
        return True
    except Exception as exc:
        logger.warning("update_skill failed: %s", exc)
        return False


def delete_skill(skill_id: int) -> bool:
    """Soft-delete a skill by setting status='deleted'."""
    return update_skill(skill_id, status="deleted")


def record_skill_run(
    skill_id: int,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    parameters: Optional[Dict] = None,
    outcome: str = "unknown",
    user_rating: Optional[int] = None,
    latency_ms: Optional[int] = None,
    notes: Optional[str] = None,
    improvement_applied: Optional[str] = None,
) -> Optional[int]:
    """Log a skill execution. Returns run ID."""
    if not engine:
        return None
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO skill_runs
                        (skill_id, session_id, username, parameters, outcome, user_rating,
                         latency_ms, notes, improvement_applied, started_at, finished_at)
                    VALUES
                        (:sid, :sess, :uname, :params, :outcome, :rating,
                         :latency, :notes, :improvement, NOW(), NOW())
                    RETURNING id
                """),
                {
                    "sid": skill_id,
                    "sess": session_id,
                    "uname": username,
                    "params": json.dumps(parameters or {}),
                    "outcome": outcome,
                    "rating": user_rating,
                    "latency": latency_ms,
                    "notes": notes,
                    "improvement": improvement_applied,
                },
            )
            run_id = result.fetchone()
            # Update aggregate stats
            conn.execute(
                text("""
                    UPDATE agent_skills SET
                        run_count = run_count + 1,
                        success_rate = (
                            SELECT ROUND(
                                COUNT(*) FILTER (WHERE outcome = 'success')::NUMERIC /
                                NULLIF(COUNT(*), 0), 4
                            )
                            FROM skill_runs WHERE skill_id = :sid
                        ),
                        updated_at = NOW()
                    WHERE id = :sid
                """),
                {"sid": skill_id},
            )
            return int(run_id[0]) if run_id else None
    except Exception as exc:
        logger.warning("record_skill_run failed: %s", exc)
        return None


def get_skill_performance(skill_id: int, lookback_days: int = 14) -> Dict[str, Any]:
    """Return performance stats for a skill over the lookback window."""
    if not engine:
        return {}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT
                        COUNT(*) AS runs,
                        COUNT(*) FILTER (WHERE outcome = 'success') AS successes,
                        AVG(latency_ms) AS avg_latency,
                        MAX(started_at) AS last_run
                    FROM skill_runs
                    WHERE skill_id = :sid
                      AND started_at >= NOW() - INTERVAL ':days days'
                """.replace(":days", str(int(lookback_days)))),
                {"sid": skill_id},
            ).fetchone()
            if not row:
                return {"runs": 0, "success_rate": 0.0}
            runs = int(row[0] or 0)
            successes = int(row[1] or 0)
            return {
                "runs": runs,
                "successes": successes,
                "success_rate": round(successes / max(runs, 1), 4),
                "avg_latency_ms": round(float(row[2] or 0), 1),
                "last_run": str(row[3]) if row[3] else None,
            }
    except Exception as exc:
        logger.warning("get_skill_performance failed: %s", exc)
        return {}


# ── SKILL EXECUTION ───────────────────────────────────────────────────────────

def run_skill(
    skill_id: int,
    user_message: str,
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    parameters: Optional[Dict] = None,
    model_type: str = "ollama",
    core_facts: str = "",
) -> Dict[str, Any]:
    """
    Execute a skill against a user message.
    Returns dict with 'response', 'outcome', 'run_id', 'skill_improvement'.
    """
    import time
    skill = get_skill(skill_id)
    if not skill:
        return {"error": f"Skill {skill_id} not found", "response": "", "outcome": "failure"}

    from ampai_identity import get_identity_info
    facts_section = core_facts.strip() or "No facts stored yet."
    param_str = "\n".join(f"  {k}: {v}" for k, v in (parameters or {}).items()) or "  (none)"

    system_prompt = (
        f"You are AmpAI executing the skill: \"{skill['name']}\"\n"
        f"Description: {skill.get('description', '')}\n\n"
        f"SKILL INSTRUCTIONS:\n{skill['system_prompt']}\n\n"
        f"PARAMETERS:\n{param_str}\n\n"
        f"CORE USER FACTS:\n{facts_section}\n\n"
        "After completing, append [SKILL_COMPLETE: success|failure|partial] to your response.\n"
        "If you improved the approach, note it with [SKILL_IMPROVEMENT: <what you did differently>]."
    )

    t0 = time.time()
    response_text = ""
    outcome = "failure"
    skill_improvement = None

    try:
        from agent import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage
        llm = get_llm(model_type)
        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        response_text = resp.content if hasattr(resp, "content") else str(resp)

        # Parse outcome tag
        complete_match = _SKILL_COMPLETE_RE.search(response_text)
        if complete_match:
            outcome = complete_match.group(1).lower()
            response_text = _SKILL_COMPLETE_RE.sub("", response_text).strip()

        # Parse improvement tag
        improvement_match = _SKILL_IMPROVEMENT_RE.search(response_text)
        if improvement_match:
            skill_improvement = improvement_match.group(1).strip()
            response_text = _SKILL_IMPROVEMENT_RE.sub("", response_text).strip()

        if not complete_match:
            # Heuristic: non-empty response = likely success
            outcome = "success" if response_text.strip() else "failure"

    except Exception as exc:
        logger.warning("Skill execution error (id=%s): %s", skill_id, exc)
        response_text = f"Skill execution failed: {exc}"
        outcome = "failure"

    latency_ms = int((time.time() - t0) * 1000)
    run_id = record_skill_run(
        skill_id=skill_id,
        session_id=session_id,
        username=username,
        parameters=parameters,
        outcome=outcome,
        latency_ms=latency_ms,
        improvement_applied=skill_improvement,
    )

    return {
        "response": response_text,
        "outcome": outcome,
        "run_id": run_id,
        "skill_name": skill["name"],
        "skill_improvement": skill_improvement,
        "latency_ms": latency_ms,
    }


# ── AUTO-DETECTION & SELF-IMPROVEMENT ────────────────────────────────────────

def detect_skill_opportunity(message: str, response: str) -> Optional[Tuple[str, str]]:
    """
    Detect if the LLM tagged a skill opportunity.
    Returns (skill_name, description) or None.
    """
    combined = f"{message}\n{response}"
    match = _SKILL_OPPORTUNITY_RE.search(combined)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def auto_create_skill_from_session(
    session_id: str,
    skill_name: str,
    description: str,
    username: str,
    model_type: str = "ollama",
) -> Optional[Dict[str, Any]]:
    """
    Synthesize a skill prompt from a session transcript using the local LLM.
    Returns the created skill dict.
    """
    from database import list_chat_messages
    messages = list_chat_messages(session_id, dedupe=True)
    if not messages:
        return None

    lines = []
    for msg in messages[-20:]:
        role = "User" if msg.get("type") == "human" else "AmpAI"
        lines.append(f"{role}: {(msg.get('content') or '')[:400]}")
    transcript = "\n".join(lines)

    synthesis_prompt = (
        f'Based on this conversation where AmpAI performed the task "{skill_name}", '
        "write a reusable skill system prompt that could reproduce this capability.\n\n"
        f"CONVERSATION:\n{transcript}\n\n"
        "Write a clear, parameterizable skill prompt. Use {{parameter_name}} for dynamic parts.\n"
        "Return ONLY the skill prompt, no explanation."
    )

    skill_prompt = ""
    try:
        from agent import get_llm
        llm = get_llm(model_type)
        resp = llm.invoke(synthesis_prompt)
        skill_prompt = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as exc:
        logger.warning("Skill synthesis LLM call failed: %s", exc)
        skill_prompt = f"Perform the task: {description}"

    return create_skill(
        name=skill_name,
        description=description,
        system_prompt=skill_prompt.strip() or f"Perform the task: {description}",
        created_by=username,
        is_auto_created=True,
    )


def run_improvement_pass(model_type: str = "ollama") -> Dict[str, int]:
    """
    Scheduled job: review underperforming skills and rewrite their prompts.
    Returns stats dict.
    """
    stats = {"skills_reviewed": 0, "skills_improved": 0}
    skills = list_skills(status="active")

    for skill in skills:
        skill_id = skill["id"]
        perf = get_skill_performance(skill_id, lookback_days=14)
        runs = perf.get("runs", 0)
        success_rate = perf.get("success_rate", 1.0)

        if runs < MIN_RUNS_BEFORE_IMPROVEMENT:
            continue
        if success_rate >= IMPROVEMENT_THRESHOLD:
            continue

        stats["skills_reviewed"] += 1

        # Fetch recent failure examples
        failure_examples: List[str] = []
        if engine:
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("""
                            SELECT notes FROM skill_runs
                            WHERE skill_id = :sid AND outcome IN ('failure','partial')
                            ORDER BY started_at DESC LIMIT 3
                        """),
                        {"sid": skill_id},
                    ).fetchall()
                    failure_examples = [r[0] for r in rows if r and r[0]]
            except Exception:
                pass

        from ampai_identity import get_skill_improvement_prompt
        improvement_prompt = get_skill_improvement_prompt(
            skill_name=skill["name"],
            current_prompt=skill["system_prompt"],
            failure_examples=failure_examples,
        )

        improved_prompt = ""
        try:
            from agent import get_llm
            llm = get_llm(model_type)
            resp = llm.invoke(improvement_prompt)
            improved_prompt = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            logger.warning("Skill improvement LLM failed for skill %s: %s", skill_id, exc)
            continue

        if not improved_prompt.strip():
            continue

        # Save new version and update skill
        try:
            with engine.begin() as conn:
                new_version = (skill.get("version") or 1) + 1
                conn.execute(
                    text("""
                        INSERT INTO skill_versions (skill_id, version, system_prompt, reason)
                        VALUES (:sid, :ver, :prompt, :reason)
                    """),
                    {
                        "sid": skill_id,
                        "ver": new_version,
                        "prompt": improved_prompt.strip(),
                        "reason": f"auto-improved (success_rate={success_rate:.0%}, runs={runs})",
                    },
                )
                conn.execute(
                    text("""
                        UPDATE agent_skills SET
                            system_prompt = :prompt,
                            version = :ver,
                            last_improved_at = NOW(),
                            updated_at = NOW()
                        WHERE id = :sid
                    """),
                    {"prompt": improved_prompt.strip(), "ver": new_version, "sid": skill_id},
                )
            stats["skills_improved"] += 1
            logger.info(
                "Auto-improved skill '%s' (id=%s) from v%s to v%s (was %.0f%% success over %d runs)",
                skill["name"], skill_id, skill.get("version", 1), new_version,
                success_rate * 100, runs,
            )
        except Exception as exc:
            logger.warning("Failed to save skill improvement for %s: %s", skill_id, exc)

    return stats


def get_skill_runs(skill_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent runs for a skill."""
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, skill_id, session_id, username, parameters, outcome,
                           user_rating, latency_ms, notes, improvement_applied, started_at
                    FROM skill_runs WHERE skill_id = :sid
                    ORDER BY started_at DESC LIMIT :lim
                """),
                {"sid": skill_id, "lim": min(limit, 200)},
            ).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("get_skill_runs failed: %s", exc)
        return []


def get_skill_versions(skill_id: int) -> List[Dict[str, Any]]:
    """Return all versions of a skill's system prompt."""
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, skill_id, version, system_prompt, reason, created_at
                    FROM skill_versions WHERE skill_id = :sid
                    ORDER BY version DESC
                """),
                {"sid": skill_id},
            ).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("get_skill_versions failed: %s", exc)
        return []
