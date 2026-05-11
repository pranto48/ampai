"""Tasks router: CRUD plus task-from-suggestion endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.deps import UserContext, require_authenticated_user
from core.helpers import (
    _can_access_session,
    _load_config_list,
    _load_session_suggestions,
    _save_config_list,
    _save_session_suggestions,
)
from core.models import (
    SuggestionTaskCreateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from database import (
    create_task,
    delete_task,
    get_all_sessions,
    list_tasks,
    log_audit_event,
    update_task,
)
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(tags=["tasks"])


# ── Task CRUD ─────────────────────────────────────────────────────────────────


@router.get("/api/tasks")
def api_list_tasks(
    status: Optional[str] = None,
    user: UserContext = Depends(require_authenticated_user),
):
    return {"tasks": list_tasks(status=status)}


@router.post("/api/tasks")
def api_create_task(
    request: TaskCreateRequest, user: UserContext = Depends(require_authenticated_user)
):
    task_id = create_task(
        title=request.title,
        description=request.description,
        priority=request.priority,
        due_at=request.due_at,
        session_id=request.session_id,
    )
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    log_audit_event(
        username=user.username,
        action="task.create",
        details=f"id={task_id};title={request.title}",
    )
    return {"status": "success", "id": task_id}


@router.patch("/api/tasks/{task_id}")
def api_update_task(
    task_id: int,
    request: TaskUpdateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    updates = {k: v for k, v in request.dict().items() if v is not None}
    ok = update_task(task_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or update failed")
    return {"status": "success"}


@router.delete("/api/tasks/{task_id}")
def api_delete_task(
    task_id: int, user: UserContext = Depends(require_authenticated_user)
):
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}


# ── Task from legacy suggestion list ─────────────────────────────────────────


@router.post("/api/tasks/from-suggestion/{suggestion_id}", include_in_schema=False)
def create_task_from_suggestion_legacy(
    suggestion_id: str,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """Legacy path — reads from config-list task_suggestions store."""
    rows = _load_config_list("task_suggestions")
    target = None
    for row in rows:
        if row.get("id") == suggestion_id:
            target = row
            break
    if not target:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if current_user.role != "admin" and target.get("username") != current_user.username:
        raise HTTPException(status_code=403, detail="Forbidden")
    task_id = create_task(
        title=(target.get("title") or "Suggested Task")[:200],
        description=target.get("description") or "",
        priority=(target.get("priority") or "medium"),
        due_at=target.get("due_at"),
        session_id=target.get("session_id"),
    )
    target["status"] = "converted"
    target["converted_task_id"] = task_id
    target["converted_at"] = datetime.now(timezone.utc).isoformat()
    _save_config_list("task_suggestions", rows)
    return {"status": "success", "task_id": task_id}


@router.post("/api/tasks/from-suggestion/{suggestion_id}")
def create_task_from_suggestion(
    suggestion_id: str,
    request: SuggestionTaskCreateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """DB-backed path — reads from session_metadata task_suggestions column."""
    search_sessions = (
        [request.session_id]
        if request.session_id
        else [s.get("session_id") for s in get_all_sessions() if s.get("session_id")]
    )
    search_sessions = [sid for sid in search_sessions if sid]
    for session_id in search_sessions:
        if not _can_access_session(session_id, user):
            continue
        suggestions = _load_session_suggestions(session_id)
        for idx, item in enumerate(suggestions):
            if str(item.get("id")) != str(suggestion_id):
                continue
            if bool(item.get("resolved")):
                raise HTTPException(
                    status_code=409, detail="Suggestion already resolved"
                )
            task_id = create_task(
                title=item.get("title") or "Untitled task",
                description=item.get("description") or "",
                priority=item.get("priority") or "medium",
                due_at=item.get("due_at"),
                session_id=session_id,
            )
            if not task_id:
                raise HTTPException(status_code=500, detail="Failed to create task")
            suggestions[idx]["resolved"] = True
            suggestions[idx]["task_id"] = task_id
            suggestions[idx]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            _save_session_suggestions(session_id, suggestions)
            log_audit_event(
                username=user.username,
                action="task.create.from_suggestion",
                session_id=session_id,
                details=f"suggestion_id={suggestion_id};task_id={task_id}",
            )
            return {"status": "success", "task_id": task_id, "session_id": session_id}
    raise HTTPException(status_code=404, detail="Suggestion not found")
