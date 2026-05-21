"""Tasks router: CRUD plus task-from-suggestion endpoints.

Endpoints:
- GET /api/tasks: list tasks paginated (default 20), filterable by status, priority,
  due date range, searchable by title/description
- POST /api/tasks: create task with title (max 150 chars), description (max 1000 chars),
  priority, due_at, session_id
- PATCH /api/tasks/{id}: update task, allow status transitions (todo, in_progress, done)
  in any direction
- DELETE /api/tasks/{id}: delete task

Requirements: 11.2, 11.4, 11.5, 11.6
"""

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
    get_task_by_id,
    list_tasks,
    log_audit_event,
    update_task,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(tags=["tasks"])

# Valid values for status and priority fields
VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


# ── Task CRUD ─────────────────────────────────────────────────────────────────


@router.get("/api/tasks")
def api_list_tasks(
    status: Optional[str] = Query(default=None, description="Filter by status: todo, in_progress, done"),
    priority: Optional[str] = Query(default=None, description="Filter by priority: low, medium, high, urgent"),
    due_from: Optional[str] = Query(default=None, description="Filter tasks due on or after this ISO date"),
    due_to: Optional[str] = Query(default=None, description="Filter tasks due on or before this ISO date"),
    search: Optional[str] = Query(default=None, description="Search by title or description text"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserContext = Depends(require_authenticated_user),
):
    """List tasks paginated (default 20), filterable by status, priority, due date range,
    searchable by title/description."""
    # Validate filter values
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

    tasks_list, total = list_tasks(
        status=status,
        username=user.username,
        priority=priority,
        due_from=due_from,
        due_to=due_to,
        search=search,
        limit=limit,
        offset=offset,
    )

    # Serialize datetime objects to ISO strings for JSON response
    for task in tasks_list:
        for key in ("created_at", "updated_at", "due_at"):
            val = task.get(key)
            if val and isinstance(val, datetime):
                task[key] = val.isoformat()

    return {
        "tasks": tasks_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.post("/api/tasks", status_code=201)
def api_create_task(
    request: TaskCreateRequest, user: UserContext = Depends(require_authenticated_user)
):
    """Create a task with title (max 150 chars), description (max 1000 chars),
    priority, due_at, and session_id."""
    # Validate title length
    if not request.title or not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    title = request.title.strip()
    if len(title) > 150:
        raise HTTPException(status_code=400, detail="Title must be 150 characters or fewer")

    # Validate description length
    description = (request.description or "").strip()
    if len(description) > 1000:
        raise HTTPException(status_code=400, detail="Description must be 1000 characters or fewer")

    # Validate priority
    priority = request.priority or "medium"
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

    task_id = create_task(
        title=title,
        description=description,
        priority=priority,
        due_at=request.due_at,
        session_id=request.session_id,
        username=user.username,
    )
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    log_audit_event(
        username=user.username,
        action="task.create",
        details=f"id={task_id};title={title}",
    )
    return {"status": "success", "id": task_id}


@router.patch("/api/tasks/{task_id}")
def api_update_task(
    task_id: int,
    request: TaskUpdateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """Update task. Allows status transitions (todo, in_progress, done) in any direction."""
    # Verify task exists and belongs to user
    existing = get_task_by_id(task_id, username=user.username)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = {}

    # Validate title if provided
    if request.title is not None:
        title = request.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        if len(title) > 150:
            raise HTTPException(status_code=400, detail="Title must be 150 characters or fewer")
        updates["title"] = title

    # Validate description if provided
    if request.description is not None:
        description = request.description.strip()
        if len(description) > 1000:
            raise HTTPException(status_code=400, detail="Description must be 1000 characters or fewer")
        updates["description"] = description

    # Validate status transition (any direction allowed between todo, in_progress, done)
    if request.status is not None:
        if request.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
        updates["status"] = request.status

    # Validate priority if provided
    if request.priority is not None:
        if request.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")
        updates["priority"] = request.priority

    # due_at and session_id pass through
    if request.due_at is not None:
        updates["due_at"] = request.due_at

    if request.session_id is not None:
        updates["session_id"] = request.session_id

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    ok = update_task(task_id, updates, username=user.username)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or update failed")

    log_audit_event(
        username=user.username,
        action="task.update",
        details=f"id={task_id};fields={','.join(updates.keys())}",
    )
    return {"status": "success"}


@router.delete("/api/tasks/{task_id}")
def api_delete_task(
    task_id: int, user: UserContext = Depends(require_authenticated_user)
):
    """Delete a task owned by the authenticated user."""
    # Verify task exists and belongs to user
    existing = get_task_by_id(task_id, username=user.username)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    ok = delete_task(task_id, username=user.username)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")

    log_audit_event(
        username=user.username,
        action="task.delete",
        details=f"id={task_id}",
    )
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
        title=(target.get("title") or "Suggested Task")[:150],
        description=(target.get("description") or "")[:1000],
        priority=(target.get("priority") or "medium"),
        due_at=target.get("due_at"),
        session_id=target.get("session_id"),
        username=current_user.username,
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
                title=(item.get("title") or "Untitled task")[:150],
                description=(item.get("description") or "")[:1000],
                priority=item.get("priority") or "medium",
                due_at=item.get("due_at"),
                session_id=session_id,
                username=user.username,
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


# ── Dismiss/reject task suggestion ────────────────────────────────────────────


@router.post("/api/tasks/dismiss-suggestion/{suggestion_id}")
def dismiss_task_suggestion(
    suggestion_id: str,
    request: SuggestionTaskCreateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    """Dismiss/reject a task suggestion. Marks it as dismissed without creating a task.

    On rejection: mark suggestion as dismissed (Requirement 11.5).
    """
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
            # Mark as dismissed
            suggestions[idx]["resolved"] = True
            suggestions[idx]["status"] = "dismissed"
            suggestions[idx]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            _save_session_suggestions(session_id, suggestions)
            log_audit_event(
                username=user.username,
                action="task.suggestion.dismissed",
                session_id=session_id,
                details=f"suggestion_id={suggestion_id}",
            )
            return {"status": "success", "dismissed": True, "session_id": session_id}
    raise HTTPException(status_code=404, detail="Suggestion not found")
