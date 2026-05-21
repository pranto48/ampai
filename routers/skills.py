"""Skills router: synthesize, list, run, optimize, rollback plus full skill engine CRUD.

Implements Requirements 14.1-14.6:
- Pattern detection (3+ sessions in 30-day window) and skill suggestions
- User/admin approval before activation
- Safety levels: read-only, write, privileged
- CRUD endpoints: GET/POST/PATCH/DELETE /api/skills
- Execution: POST /api/skills/{id}/execute
- Metrics: GET /api/skills/{id}/metrics
- Failure handling: halt skill, preserve pre-execution state, return error
- Rejection tracking: don't re-suggest rejected patterns
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.deps import (
    UserContext,
    get_current_user_from_cookie,
    require_admin_user,
    require_authenticated_user,
)
from core.helpers import _ensure_session_owner_for_user, _load_session_suggestions
from core.models import (
    SkillAutoCreateRequest,
    SkillCreateRequest,
    SkillExecuteRequest,
    SkillOptimizeRequest,
    SkillRunRequest,
    SkillSynthesisRequest,
    SkillUpdateRequest,
)
from database import (
    create_agent_skill,
    create_skill_version,
    ensure_skill_registry_tables,
    get_config,
    get_skill_performance,
    list_agent_skills,
    list_chat_messages,
    log_audit_event,
    record_skill_run,
    set_config,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["skills"])

logger = logging.getLogger("ampai")


# ── Request/Response models for new endpoints ─────────────────────────────────


class SkillApproveRequest(BaseModel):
    """Request to approve a skill for execution."""
    pass


class SkillRejectRequest(BaseModel):
    """Request to reject a skill suggestion."""
    reason: Optional[str] = None


class SkillExecuteNewRequest(BaseModel):
    """Request to execute a skill (POST /api/skills/{id}/execute)."""
    user_message: str
    session_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    model_type: str = "ollama"
    confirmed: bool = False


class PatternDetectionRequest(BaseModel):
    """Request to detect repeated patterns."""
    lookback_days: int = 30
    min_occurrences: int = 3


class ClearRejectionRequest(BaseModel):
    """Request to clear a pattern rejection for re-evaluation."""
    pattern_hash: str


# ── Skill synthesis (from session) ────────────────────────────────────────────


def _synthesize_skill_from_session(
    session_id: str, username: str, min_messages: int = 4
) -> Dict[str, Any]:
    messages = list_chat_messages(session_id=session_id, dedupe=True)
    if len(messages) < max(2, min_messages):
        raise HTTPException(
            status_code=400, detail="Not enough messages to synthesize skill"
        )
    suggestion_rows = _load_session_suggestions(session_id)
    selected = [s for s in suggestion_rows if (s.get("title") or "").strip()]
    title = (selected[0].get("title") if selected else "Session Workflow").strip()
    desc = (
        selected[0].get("description")
        if selected
        else "Derived from successful session flow."
    ).strip()
    trigger_patterns = [title.lower(), "follow-up", "workflow"]
    tool_requirements = ["chat", "tasks"]
    instruction_lines = [
        f"Goal: {title}",
        f"Context: {desc}",
        "Procedure:",
        "1) Clarify user's objective and constraints.",
        "2) Propose a concise, ordered action plan.",
        "3) Create/track tasks when milestones are identified.",
        "4) Confirm completion criteria and next follow-up.",
    ]
    instructions = "\n".join(instruction_lines)
    confidence = 0.85 if selected else 0.65
    quality_score = min(0.95, 0.55 + (len(messages) / 40.0))
    skill_id = create_agent_skill(
        name=f"Skill: {title[:80]}",
        instructions=instructions,
        trigger_patterns=trigger_patterns,
        tool_requirements=tool_requirements,
        confidence=confidence,
        quality_score=quality_score,
        status="active" if confidence >= 0.8 else "draft",
        source_session_id=session_id,
        created_by=username,
    )
    if not skill_id:
        raise HTTPException(
            status_code=500, detail="Failed to create synthesized skill"
        )
    return {
        "skill_id": skill_id,
        "confidence": confidence,
        "quality_score": quality_score,
    }


@router.post("/api/skills/synthesize")
def synthesize_skill(
    request: SkillSynthesisRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    _ensure_session_owner_for_user(request.session_id, user)
    outcome = _synthesize_skill_from_session(
        session_id=request.session_id,
        username=user.username,
        min_messages=request.min_messages,
    )
    log_audit_event(
        username=user.username,
        action="skill.synthesize",
        session_id=request.session_id,
        details=f"skill_id={outcome['skill_id']};confidence={outcome['confidence']:.3f}",
    )
    return {"status": "success", **outcome}


# ── Skill registry (database-backed) ─────────────────────────────────────────


@router.get("/api/skills")
def get_skills(
    status: Optional[str] = None,
    limit: int = 100,
    user: UserContext = Depends(require_authenticated_user),
):
    """List all skills. Requirement 14.5."""
    ensure_skill_registry_tables()
    from skill_engine import list_skills as se_list_skills

    skills = se_list_skills(status=status or "active", limit=limit)
    # Also include from the legacy registry
    legacy_skills = list_agent_skills(status=status, limit=limit)
    return {"skills": skills or legacy_skills}


@router.post("/api/skills")
def api_create_skill(
    req: SkillCreateRequest,
    user: UserContext = Depends(require_admin_user),
):
    """Create a new skill. Requires admin. Requirement 14.5."""
    from skill_engine import create_skill, determine_safety_level

    # Determine safety level based on system prompt content
    safety_level = determine_safety_level(req.system_prompt)

    skill = create_skill(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        trigger_pattern=req.trigger_pattern,
        parameters=req.parameters,
        tags=req.tags,
        created_by=user.username,
        safety_level=safety_level,
    )
    if not skill:
        raise HTTPException(
            status_code=400, detail="Failed to create skill (name may already exist)"
        )
    log_audit_event(
        username=user.username,
        action="skill.create",
        details=f"skill_id={skill.get('id')};name={req.name};safety_level={safety_level}",
    )
    return skill


@router.patch("/api/skills/{skill_id}")
def api_patch_skill(
    skill_id: int,
    req: SkillUpdateRequest,
    user: UserContext = Depends(require_admin_user),
):
    """Update a skill (partial update). Requires admin. Requirement 14.5."""
    from skill_engine import get_skill, update_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    updates = {k: v for k, v in req.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    ok = update_skill(skill_id, **updates)
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")

    log_audit_event(
        username=user.username,
        action="skill.update",
        details=f"skill_id={skill_id};fields={list(updates.keys())}",
    )
    return {"ok": True, "skill_id": skill_id}


@router.get("/api/skills/{skill_id}")
def api_get_skill(
    skill_id: int, user: UserContext = Depends(require_authenticated_user)
):
    """Get a single skill by ID."""
    from skill_engine import get_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.put("/api/skills/{skill_id}")
def api_update_skill(
    skill_id: int,
    req: SkillUpdateRequest,
    user: UserContext = Depends(require_admin_user),
):
    """Full update of a skill. Requires admin."""
    from skill_engine import update_skill

    updates = {k: v for k, v in req.dict().items() if v is not None}
    ok = update_skill(skill_id, **updates)
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"ok": True}


@router.delete("/api/skills/{skill_id}")
def api_delete_skill(
    skill_id: int, user: UserContext = Depends(require_admin_user)
):
    """Delete (soft-delete) a skill. Requires admin. Requirement 14.5."""
    from skill_engine import delete_skill, get_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    ok = delete_skill(skill_id)
    log_audit_event(
        username=user.username,
        action="skill.delete",
        details=f"skill_id={skill_id};name={skill.get('name', '')}",
    )
    return {"ok": ok}


# ── Skill Execution (Requirement 14.4, 14.5) ─────────────────────────────────


@router.post("/api/skills/{skill_id}/execute")
def api_execute_skill(
    skill_id: int,
    req: SkillExecuteNewRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """
    Execute a skill. Requirement 14.5.

    Enforces:
    - Skill must be approved before execution (Req 14.2)
    - Safety level checks (Req 14.3):
      - read-only: executes directly
      - write: requires confirmed=True (per-execution confirmation)
      - privileged: requires admin approval + confirmed=True
    - On failure: halts skill, preserves pre-execution state, returns error (Req 14.4)
    """
    from skill_engine import get_skill, run_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Privileged skills require admin role
    safety_level = skill.get("safety_level", "read-only")
    if safety_level == "privileged" and user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Privileged skills require admin approval to execute",
        )

    from database import get_core_memories

    core_mems = get_core_memories()
    core_facts = "\n".join(f"- {m['fact']}" for m in core_mems) if core_mems else ""

    result = run_skill(
        skill_id=skill_id,
        user_message=req.user_message,
        session_id=req.session_id,
        username=user.username,
        parameters=req.parameters,
        model_type=req.model_type,
        core_facts=core_facts,
        confirmed=req.confirmed,
    )

    # Log execution to audit
    log_audit_event(
        username=user.username,
        action="skill.execute",
        session_id=req.session_id,
        details=f"skill_id={skill_id};outcome={result.get('outcome')};latency_ms={result.get('latency_ms')}",
    )

    # If execution failed with an error, return appropriate HTTP status
    if result.get("outcome") == "failure" and result.get("error"):
        raise HTTPException(
            status_code=500,
            detail={
                "error": result["error"],
                "outcome": "failure",
                "skill_halted": True,
                "run_id": result.get("run_id"),
            },
        )

    return result


# ── Skill Metrics (Requirement 14.5) ─────────────────────────────────────────


@router.get("/api/skills/{skill_id}/metrics")
def api_skill_metrics(
    skill_id: int,
    user: UserContext = Depends(require_authenticated_user),
):
    """
    Get skill performance metrics. Requirement 14.5.
    Returns: invocation_count, success_rate, avg_execution_duration_ms.
    """
    from skill_engine import get_skill, get_skill_metrics

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    metrics = get_skill_metrics(skill_id)
    return {
        "skill_id": skill_id,
        "skill_name": skill.get("name", ""),
        **metrics,
    }


# ── Skill Approval (Requirement 14.2) ────────────────────────────────────────


@router.post("/api/skills/{skill_id}/approve")
def api_approve_skill(
    skill_id: int,
    user: UserContext = Depends(require_admin_user),
):
    """Approve a skill for execution. Requires admin. Requirement 14.2."""
    from skill_engine import approve_skill, get_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    ok = approve_skill(skill_id, approved_by=user.username)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to approve skill")

    log_audit_event(
        username=user.username,
        action="skill.approve",
        details=f"skill_id={skill_id};name={skill.get('name', '')}",
    )
    return {"ok": True, "skill_id": skill_id, "approval_status": "approved"}


@router.post("/api/skills/{skill_id}/reject")
def api_reject_skill(
    skill_id: int,
    req: SkillRejectRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """
    Reject a skill suggestion. Records rejection so the same pattern
    is not re-suggested. Requirement 14.6.
    """
    from skill_engine import get_skill, reject_skill_suggestion

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    ok = reject_skill_suggestion(
        skill_id=skill_id,
        rejected_by=user.username,
        reason=req.reason,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to record rejection")

    log_audit_event(
        username=user.username,
        action="skill.reject",
        details=f"skill_id={skill_id};reason={req.reason or 'none'}",
    )
    return {"ok": True, "skill_id": skill_id, "approval_status": "rejected"}


# ── Pattern Detection (Requirement 14.1) ─────────────────────────────────────


@router.get("/api/skills/suggestions")
def api_skill_suggestions(
    lookback_days: int = 30,
    min_occurrences: int = 3,
    user: UserContext = Depends(require_authenticated_user),
):
    """
    Detect repeated patterns and suggest skill creation. Requirement 14.1.
    Returns patterns that have occurred 3+ times in the lookback window
    and haven't been previously rejected.
    """
    from skill_engine import detect_repeated_patterns

    suggestions = detect_repeated_patterns(
        username=user.username,
        lookback_days=lookback_days,
        min_occurrences=min_occurrences,
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.post("/api/skills/suggestions/clear-rejection")
def api_clear_rejection(
    req: ClearRejectionRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """
    Clear a pattern rejection so it can be re-suggested.
    Used when user explicitly requests re-evaluation. Requirement 14.6.
    """
    from skill_engine import clear_pattern_rejection

    ok = clear_pattern_rejection(req.pattern_hash)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to clear rejection")

    log_audit_event(
        username=user.username,
        action="skill.clear_rejection",
        details=f"pattern_hash={req.pattern_hash}",
    )
    return {"ok": True, "pattern_hash": req.pattern_hash}


# ── Legacy endpoints (backward compatibility) ─────────────────────────────────


@router.post("/api/skills/runs")
def log_skill_run(
    request: SkillRunRequest, user: UserContext = Depends(require_authenticated_user)
):
    run_id = record_skill_run(
        skill_id=request.skill_id,
        skill_version_id=request.skill_version_id,
        username=user.username,
        session_id=request.session_id,
        status=request.status,
        latency_ms=request.latency_ms,
        user_feedback=request.user_feedback,
        notes=request.notes,
    )
    if not run_id:
        raise HTTPException(status_code=500, detail="Failed to record skill run")
    return {"status": "success", "run_id": run_id}


@router.post("/api/skills/{skill_id}/optimize")
def optimize_skill(
    skill_id: int,
    request: SkillOptimizeRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    skills = [
        s for s in list_agent_skills(limit=500) if int(s.get("id")) == int(skill_id)
    ]
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill = skills[0]
    perf = get_skill_performance(skill_id=skill_id, lookback_days=request.lookback_days)
    if perf["runs"] < max(1, request.min_runs):
        return {"status": "skipped", "reason": "insufficient_runs", "performance": perf}
    if perf["success_rate"] >= float(request.success_threshold):
        return {"status": "skipped", "reason": "already_healthy", "performance": perf}
    improved_instructions = (
        f"{skill.get('instructions', '').strip()}\n\n"
        "Self-improvement patch:\n"
        "- Ask one clarifying question before execution.\n"
        "- Add explicit verification checkpoint before final answer.\n"
        "- If uncertainty remains, provide two alternatives with tradeoffs."
    ).strip()
    new_quality = min(1.0, max(0.0, float(skill.get("quality_score") or 0.5) + 0.05))
    version_id = create_skill_version(
        skill_id=skill_id,
        instructions=improved_instructions,
        trigger_patterns=skill.get("trigger_patterns") or [],
        quality_score=new_quality,
        change_note=f"Auto-refinement from optimization loop by {user.username}",
    )
    rollout_config = {
        "skill_id": skill_id,
        "candidate_version_id": version_id,
        "canary_fraction": max(0.05, min(float(request.canary_fraction), 1.0)),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "canary",
    }
    set_config(f"skill_rollout_{skill_id}", json.dumps(rollout_config))
    return {
        "status": "optimized",
        "new_version_id": version_id,
        "performance": perf,
        "rollout": rollout_config,
    }


@router.post("/api/skills/{skill_id}/rollback")
def rollback_skill(skill_id: int, user: UserContext = Depends(require_admin_user)):
    set_config(f"skill_rollout_{skill_id}", "")
    log_audit_event(
        username=user.username,
        action="skill.rollback",
        details=f"skill_id={skill_id}",
    )
    return {"status": "rolled_back", "skill_id": skill_id}


# ── Legacy run endpoint (backward compat) ────────────────────────────────────


@router.post("/api/skills/{skill_id}/run")
def api_run_skill(
    skill_id: int,
    req: SkillExecuteRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """Legacy run endpoint. Delegates to the new execute logic."""
    from database import get_core_memories
    from skill_engine import run_skill

    core_mems = get_core_memories()
    core_facts = "\n".join(f"- {m['fact']}" for m in core_mems) if core_mems else ""
    result = run_skill(
        skill_id=skill_id,
        user_message=req.user_message,
        session_id=req.session_id,
        username=user.username,
        parameters=req.parameters,
        model_type=req.model_type,
        core_facts=core_facts,
        confirmed=True,  # Legacy endpoint assumes confirmation
    )
    return result


@router.post("/api/skills/{skill_id}/improve")
def api_improve_skill(
    skill_id: int,
    user: UserContext = Depends(require_authenticated_user),
):
    from skill_engine import get_skill, run_improvement_pass

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    stats = run_improvement_pass()
    return {"ok": True, "stats": stats}


@router.get("/api/skills/{skill_id}/runs")
def api_skill_runs(
    skill_id: int,
    limit: int = 50,
    user: UserContext = Depends(require_authenticated_user),
):
    from skill_engine import get_skill_runs

    return get_skill_runs(skill_id, limit=limit)


@router.get("/api/skills/{skill_id}/versions")
def api_skill_versions(
    skill_id: int, user: UserContext = Depends(require_authenticated_user)
):
    from skill_engine import get_skill_versions

    return get_skill_versions(skill_id)


@router.get("/api/skills/{skill_id}/performance")
def api_skill_performance(
    skill_id: int,
    lookback_days: int = 14,
    user: UserContext = Depends(require_authenticated_user),
):
    from skill_engine import get_skill_performance as _perf

    return _perf(skill_id, lookback_days=lookback_days)


@router.post("/api/skills/auto-create")
def api_auto_create_skill(
    req: SkillAutoCreateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    from skill_engine import auto_create_skill_from_session

    skill = auto_create_skill_from_session(
        session_id=req.session_id,
        skill_name=req.skill_name,
        description=req.description,
        username=user.username,
        model_type=req.model_type,
    )
    if not skill:
        raise HTTPException(status_code=400, detail="Skill synthesis failed")
    return skill
