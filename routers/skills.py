"""Skills router: synthesize, list, run, optimize, rollback plus full skill engine CRUD."""

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

router = APIRouter(tags=["skills"])

logger = logging.getLogger("ampai")


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
    user: UserContext = Depends(get_current_user_from_cookie),
):
    ensure_skill_registry_tables()
    return {"skills": list_agent_skills(status=status, limit=limit)}


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


# ── Skill Engine CRUD (autonomous agent section) ──────────────────────────────


@router.post("/api/skills")
def api_create_skill(
    req: SkillCreateRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from skill_engine import create_skill

    skill = create_skill(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        trigger_pattern=req.trigger_pattern,
        parameters=req.parameters,
        tags=req.tags,
        created_by=user.username,
    )
    if not skill:
        raise HTTPException(
            status_code=400, detail="Failed to create skill (name may already exist)"
        )
    return skill


@router.get("/api/skills/{skill_id}")
def api_get_skill(
    skill_id: int, user: UserContext = Depends(get_current_user_from_cookie)
):
    from skill_engine import get_skill

    skill = get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.put("/api/skills/{skill_id}")
def api_update_skill(
    skill_id: int,
    req: SkillUpdateRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from skill_engine import update_skill

    updates = {k: v for k, v in req.dict().items() if v is not None}
    ok = update_skill(skill_id, **updates)
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"ok": True}


@router.delete("/api/skills/{skill_id}")
def api_delete_skill(
    skill_id: int, user: UserContext = Depends(get_current_user_from_cookie)
):
    from skill_engine import delete_skill

    ok = delete_skill(skill_id)
    return {"ok": ok}


@router.post("/api/skills/{skill_id}/run")
def api_run_skill(
    skill_id: int,
    req: SkillExecuteRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
):
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
    )
    return result


@router.post("/api/skills/{skill_id}/improve")
def api_improve_skill(
    skill_id: int,
    user: UserContext = Depends(get_current_user_from_cookie),
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
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from skill_engine import get_skill_runs

    return get_skill_runs(skill_id, limit=limit)


@router.get("/api/skills/{skill_id}/versions")
def api_skill_versions(
    skill_id: int, user: UserContext = Depends(get_current_user_from_cookie)
):
    from skill_engine import get_skill_versions

    return get_skill_versions(skill_id)


@router.get("/api/skills/{skill_id}/performance")
def api_skill_performance(
    skill_id: int,
    lookback_days: int = 14,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from skill_engine import get_skill_performance as _perf

    return _perf(skill_id, lookback_days=lookback_days)


@router.post("/api/skills/auto-create")
def api_auto_create_skill(
    req: SkillAutoCreateRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
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
