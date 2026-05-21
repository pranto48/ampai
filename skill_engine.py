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
  - Safety levels: read-only, write, privileged
  - Approval workflow: skills require user/admin approval before activation
  - Pattern detection: repeated patterns (3+ sessions in 30 days) trigger suggestions
  - Rejection tracking: rejected patterns are not re-suggested
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from database import engine, get_config

logger = logging.getLogger("ampai.skill_engine")

# Valid safety levels for skills
SAFETY_LEVELS = ("read-only", "write", "privileged")

# Approval statuses
APPROVAL_PENDING = "pending_approval"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

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
    """Create agent_skills, skill_runs, skill_versions, and skill_rejections tables."""
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
                    safety_level VARCHAR DEFAULT 'read-only',
                    approval_status VARCHAR DEFAULT 'pending_approval',
                    approved_by VARCHAR,
                    approved_at TIMESTAMPTZ,
                    source_pattern_hash VARCHAR,
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
                    error_reason TEXT,
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
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS skill_rejections (
                    id SERIAL PRIMARY KEY,
                    pattern_hash VARCHAR NOT NULL,
                    pattern_description TEXT,
                    rejected_by VARCHAR NOT NULL,
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
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_skill_rejections_hash ON skill_rejections (pattern_hash)"
            ))
            # Add new columns to existing tables if they don't exist
            conn.execute(text(
                "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS safety_level VARCHAR DEFAULT 'read-only'"
            ))
            conn.execute(text(
                "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS approval_status VARCHAR DEFAULT 'pending_approval'"
            ))
            conn.execute(text(
                "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS approved_by VARCHAR"
            ))
            conn.execute(text(
                "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ"
            ))
            conn.execute(text(
                "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS source_pattern_hash VARCHAR"
            ))
            conn.execute(text(
                "ALTER TABLE skill_runs ADD COLUMN IF NOT EXISTS error_reason TEXT"
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
    safety_level: str = "read-only",
    approval_status: str = APPROVAL_PENDING,
    source_pattern_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a new agent skill. Returns the created skill dict, or None on failure."""
    if not engine or not name.strip() or not system_prompt.strip():
        return None
    # Validate safety level
    if safety_level not in SAFETY_LEVELS:
        safety_level = "read-only"
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO agent_skills
                        (name, description, trigger_pattern, system_prompt, parameters, tags,
                         created_by, is_auto_created, status, safety_level, approval_status,
                         source_pattern_hash, created_at, updated_at)
                    VALUES
                        (:name, :desc, :trigger, :prompt, :params, :tags,
                         :created_by, :auto, 'active', :safety_level, :approval_status,
                         :pattern_hash, NOW(), NOW())
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
                    "safety_level": safety_level,
                    "approval_status": approval_status,
                    "pattern_hash": source_pattern_hash,
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
    allowed = {"name", "description", "trigger_pattern", "system_prompt", "parameters",
               "tags", "status", "safety_level", "approval_status", "approved_by", "approved_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    # Validate safety_level if provided
    if "safety_level" in updates and updates["safety_level"] not in SAFETY_LEVELS:
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
    error_reason: Optional[str] = None,
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
                         latency_ms, notes, improvement_applied, error_reason, started_at, finished_at)
                    VALUES
                        (:sid, :sess, :uname, :params, :outcome, :rating,
                         :latency, :notes, :improvement, :error_reason, NOW(), NOW())
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
                    "error_reason": error_reason,
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
    confirmed: bool = False,
) -> Dict[str, Any]:
    """
    Execute a skill against a user message.
    Enforces approval status and safety level checks.
    On failure: halts skill, preserves pre-execution state, returns error.
    Returns dict with 'response', 'outcome', 'run_id', 'skill_improvement'.
    """
    import time
    skill = get_skill(skill_id)
    if not skill:
        return {"error": f"Skill {skill_id} not found", "response": "", "outcome": "failure"}

    # Check approval status - skill must be approved before execution
    approval_status = skill.get("approval_status", APPROVAL_PENDING)
    if approval_status != APPROVAL_APPROVED:
        return {
            "error": "Skill has not been approved for execution",
            "response": "",
            "outcome": "blocked",
            "reason": f"approval_status={approval_status}",
        }

    # Check safety level and confirmation requirements
    safety_level = skill.get("safety_level", "read-only")
    if safety_level in ("write", "privileged") and not confirmed:
        return {
            "error": "Per-execution confirmation required for this skill",
            "response": "",
            "outcome": "confirmation_required",
            "safety_level": safety_level,
            "skill_name": skill["name"],
        }

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
    error_reason = None

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
        error_reason = str(exc)
        response_text = f"Skill execution failed: {exc}"
        outcome = "failure"

    latency_ms = int((time.time() - t0) * 1000)

    # On failure: halt skill (set status to halted), preserve pre-execution state
    if outcome == "failure" and error_reason:
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE agent_skills SET status = 'halted', updated_at = NOW() WHERE id = :sid"),
                    {"sid": skill_id},
                )
        except Exception:
            pass

    run_id = record_skill_run(
        skill_id=skill_id,
        session_id=session_id,
        username=username,
        parameters=parameters,
        outcome=outcome,
        latency_ms=latency_ms,
        improvement_applied=skill_improvement,
        error_reason=error_reason,
    )

    result = {
        "response": response_text,
        "outcome": outcome,
        "run_id": run_id,
        "skill_name": skill["name"],
        "skill_improvement": skill_improvement,
        "latency_ms": latency_ms,
    }
    if error_reason:
        result["error"] = error_reason
    return result


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


# ── PATTERN DETECTION (Requirement 14.1) ─────────────────────────────────────

import hashlib


def _compute_pattern_hash(pattern_description: str) -> str:
    """Compute a stable hash for a conversation pattern to track rejections."""
    normalized = pattern_description.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def detect_repeated_patterns(
    username: str,
    lookback_days: int = 30,
    min_occurrences: int = 3,
) -> List[Dict[str, Any]]:
    """
    Detect repeated conversation patterns (3+ sessions in 30-day window).
    Returns list of pattern suggestions that haven't been rejected.

    Analyzes session categories and task_suggestions to find recurring workflows.
    """
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            # Find categories with 3+ sessions in the lookback window
            rows = conn.execute(
                text("""
                    SELECT category, COUNT(*) AS session_count,
                           array_agg(session_id ORDER BY updated_at DESC) AS session_ids
                    FROM session_metadata
                    WHERE owner_username = :username
                      AND updated_at >= NOW() - make_interval(days => :days)
                      AND category IS NOT NULL
                      AND category != 'Uncategorized'
                    GROUP BY category
                    HAVING COUNT(*) >= :min_occ
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """),
                {"username": username, "days": lookback_days, "min_occ": min_occurrences},
            ).fetchall()

            suggestions = []
            for row in rows:
                category = row[0]
                session_count = row[1]
                session_ids = row[2] if row[2] else []

                pattern_hash = _compute_pattern_hash(category)

                # Check if this pattern was already rejected
                if _is_pattern_rejected(conn, pattern_hash):
                    continue

                # Check if a skill already exists for this pattern
                existing = conn.execute(
                    text("SELECT id FROM agent_skills WHERE source_pattern_hash = :hash AND status != 'deleted'"),
                    {"hash": pattern_hash},
                ).fetchone()
                if existing:
                    continue

                suggestions.append({
                    "pattern_hash": pattern_hash,
                    "pattern_description": category,
                    "session_count": session_count,
                    "session_ids": session_ids[:5],  # Limit to 5 most recent
                    "suggested_name": f"Skill: {category}",
                    "suggested_safety_level": "read-only",
                })

            return suggestions
    except Exception as exc:
        logger.warning("detect_repeated_patterns failed: %s", exc)
        return []


def _is_pattern_rejected(conn, pattern_hash: str) -> bool:
    """Check if a pattern has been previously rejected."""
    try:
        row = conn.execute(
            text("SELECT id FROM skill_rejections WHERE pattern_hash = :hash LIMIT 1"),
            {"hash": pattern_hash},
        ).fetchone()
        return row is not None
    except Exception:
        return False


def is_pattern_rejected(pattern_hash: str) -> bool:
    """Public check if a pattern has been previously rejected."""
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            return _is_pattern_rejected(conn, pattern_hash)
    except Exception:
        return False


# ── APPROVAL WORKFLOW (Requirement 14.2) ──────────────────────────────────────


def approve_skill(skill_id: int, approved_by: str) -> bool:
    """Approve a skill for execution. Required before any skill can run."""
    if not engine:
        return False
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE agent_skills
                    SET approval_status = :status,
                        approved_by = :approved_by,
                        approved_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :sid
                """),
                {"status": APPROVAL_APPROVED, "approved_by": approved_by, "sid": skill_id},
            )
            return (result.rowcount or 0) > 0
    except Exception as exc:
        logger.warning("approve_skill failed: %s", exc)
        return False


def reject_skill_suggestion(
    skill_id: Optional[int] = None,
    pattern_hash: Optional[str] = None,
    pattern_description: Optional[str] = None,
    rejected_by: str = "system",
    reason: Optional[str] = None,
) -> bool:
    """
    Reject a skill suggestion. Records the rejection so the same pattern
    is not re-suggested unless the user explicitly requests re-evaluation.
    (Requirement 14.6)
    """
    if not engine:
        return False
    try:
        with engine.begin() as conn:
            # If we have a skill_id, get its pattern hash
            if skill_id and not pattern_hash:
                row = conn.execute(
                    text("SELECT source_pattern_hash, name FROM agent_skills WHERE id = :sid"),
                    {"sid": skill_id},
                ).fetchone()
                if row:
                    pattern_hash = row[0] or _compute_pattern_hash(row[1])
                    if not pattern_description:
                        pattern_description = row[1]

            if not pattern_hash and pattern_description:
                pattern_hash = _compute_pattern_hash(pattern_description)

            if not pattern_hash:
                return False

            # Record the rejection
            conn.execute(
                text("""
                    INSERT INTO skill_rejections (pattern_hash, pattern_description, rejected_by, reason, created_at)
                    VALUES (:hash, :desc, :rejected_by, :reason, NOW())
                """),
                {
                    "hash": pattern_hash,
                    "desc": (pattern_description or "")[:1000],
                    "rejected_by": rejected_by,
                    "reason": (reason or "")[:500],
                },
            )

            # If there's a skill_id, update its status
            if skill_id:
                conn.execute(
                    text("""
                        UPDATE agent_skills
                        SET approval_status = 'rejected', status = 'inactive', updated_at = NOW()
                        WHERE id = :sid
                    """),
                    {"sid": skill_id},
                )

            return True
    except Exception as exc:
        logger.warning("reject_skill_suggestion failed: %s", exc)
        return False


def clear_pattern_rejection(pattern_hash: str) -> bool:
    """
    Clear a pattern rejection so it can be re-suggested.
    Used when user explicitly requests re-evaluation.
    """
    if not engine:
        return False
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM skill_rejections WHERE pattern_hash = :hash"),
                {"hash": pattern_hash},
            )
            return True
    except Exception as exc:
        logger.warning("clear_pattern_rejection failed: %s", exc)
        return False


# ── METRICS (Requirement 14.5) ────────────────────────────────────────────────


def get_skill_metrics(skill_id: int) -> Dict[str, Any]:
    """
    Return skill performance metrics:
    - invocation_count: total number of executions
    - success_rate: ratio of successful executions
    - avg_execution_duration_ms: average latency in milliseconds
    """
    if not engine:
        return {"invocation_count": 0, "success_rate": 0.0, "avg_execution_duration_ms": 0.0}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT
                        COUNT(*) AS invocation_count,
                        COUNT(*) FILTER (WHERE outcome = 'success') AS successes,
                        AVG(latency_ms) AS avg_latency,
                        MAX(started_at) AS last_execution,
                        MIN(started_at) AS first_execution
                    FROM skill_runs
                    WHERE skill_id = :sid
                """),
                {"sid": skill_id},
            ).fetchone()
            if not row or not row[0]:
                return {
                    "invocation_count": 0,
                    "success_rate": 0.0,
                    "avg_execution_duration_ms": 0.0,
                }
            invocation_count = int(row[0] or 0)
            successes = int(row[1] or 0)
            return {
                "invocation_count": invocation_count,
                "success_rate": round(successes / max(invocation_count, 1), 4),
                "avg_execution_duration_ms": round(float(row[2] or 0), 1),
                "last_execution": str(row[3]) if row[3] else None,
                "first_execution": str(row[4]) if row[4] else None,
            }
    except Exception as exc:
        logger.warning("get_skill_metrics failed: %s", exc)
        return {"invocation_count": 0, "success_rate": 0.0, "avg_execution_duration_ms": 0.0}


# ── SAFETY LEVEL ASSIGNMENT (Requirement 14.3) ───────────────────────────────


def determine_safety_level(system_prompt: str, tool_requirements: Optional[List[str]] = None) -> str:
    """
    Determine the appropriate safety level for a skill based on its capabilities.
    - read-only: may retrieve data but not modify state
    - write: may modify user data (per-execution confirmation required)
    - privileged: may invoke browser/terminal (admin approval + per-execution confirmation)
    """
    prompt_lower = (system_prompt or "").lower()
    tools = [t.lower() for t in (tool_requirements or [])]

    # Privileged: references browser or terminal tools
    privileged_signals = [
        "browser", "terminal", "shell", "command", "execute",
        "playwright", "navigate", "click", "type_text",
    ]
    if any(sig in prompt_lower for sig in privileged_signals):
        return "privileged"
    if any(t in ("browser", "terminal", "shell") for t in tools):
        return "privileged"

    # Write: references modification actions
    write_signals = [
        "create", "update", "delete", "modify", "write", "save",
        "insert", "remove", "edit", "change", "set",
    ]
    if any(sig in prompt_lower for sig in write_signals):
        return "write"
    if any(t in ("tasks", "memory", "write") for t in tools):
        return "write"

    return "read-only"
