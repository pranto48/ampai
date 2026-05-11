"""Sessions router: list, history, delete, export, import, category, reports, brief, status."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent import get_redis_history
from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.helpers import (
    _append_session_suggestions,
    _can_access_session,
    _classify_tier,
    _enforce_session_access_or_403,
    _load_config_list,
    _load_session_suggestions,
    _parse_iso_dt,
    _save_session_suggestions,
)
from core.models import CategoryRequest, ImportRequest, SuggestionTaskCreateRequest
from database import (
    CHAT_HISTORY_TABLE,
    build_session_report_card,
    create_task,
    delete_session_metadata,
    engine,
    ensure_session_owner,
    find_report_matches,
    get_accessible_session_ids,
    get_all_sessions,
    get_config,
    get_session_owner,
    get_sql_chat_history,
    list_chat_messages,
    list_shared_sessions_for_user,
    log_audit_event,
    session_exists,
    set_session_category,
    touch_session,
)
from database import engine as db_engine
from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_community.chat_message_histories import SQLChatMessageHistory
from session_recall import get_session_recall_messages
from sqlalchemy import text

router = APIRouter(tags=["sessions"])

logger = logging.getLogger("ampai")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")


@router.get("/api/sessions")
def get_sessions(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    archived: Optional[bool] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserContext = Depends(require_authenticated_user),
):
    sessions = get_all_sessions(query=query, category=category, archived=archived)
    needs_migration = False
    if current_user.role != "admin":
        fallback_open = str(
            get_config("auth_open_session_fallback", "true")
        ).strip().lower() in {"1", "true", "yes", "on"}
        accessible_ids = set(
            get_accessible_session_ids(username=current_user.username, is_admin=False)
        )
        if fallback_open:
            accessible_ids = {
                s.get("session_id") for s in sessions if s.get("session_id")
            }
        if not accessible_ids:
            adopted = 0
            for sess in sessions:
                sid = (sess or {}).get("session_id")
                if not sid:
                    continue
                if get_session_owner(sid):
                    continue
                if ensure_session_owner(sid, current_user.username):
                    adopted += 1
            if adopted > 0:
                accessible_ids = set(
                    get_accessible_session_ids(
                        username=current_user.username, is_admin=False
                    )
                )
            if not accessible_ids:
                if not fallback_open:
                    needs_migration = True
                    sessions = []
        if accessible_ids:
            shared_ids = set(list_shared_sessions_for_user(current_user.username))
            sessions = [s for s in sessions if s.get("session_id") in accessible_ids]
            for session in sessions:
                if session["session_id"] in shared_ids:
                    session["shared_via_group"] = True
    category_counts: Dict[str, int] = {}
    for session in sessions:
        cat = session.get("category") or "Uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    total = len(sessions)
    paged_sessions = sessions[offset : offset + limit]
    for sess in paged_sessions:
        sess["tier"] = _classify_tier(sess.get("updated_at"))
    return {
        "sessions": paged_sessions,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "categories": category_counts,
        "needs_migration": needs_migration,
    }


@router.get("/api/history/{session_id}")
def get_history(
    session_id: str, user: UserContext = Depends(require_authenticated_user)
):
    if not _can_access_session(session_id, user):
        if (
            user.role != "admin"
            and session_exists(session_id)
            and not get_session_owner(session_id)
        ):
            ensure_session_owner(session_id, user.username)
        if not _can_access_session(session_id, user):
            fallback_open = str(
                get_config("auth_open_session_fallback", "true")
            ).strip().lower() in {"1", "true", "yes", "on"}
            if not (fallback_open and session_exists(session_id)):
                raise HTTPException(status_code=403, detail="Forbidden session")
    try:
        messages = list_chat_messages(session_id, dedupe=True)
        raw_row_count = 0
        if not messages:
            try:
                with db_engine.connect() as _conn:
                    raw_row_count = (
                        _conn.execute(
                            text(
                                f"SELECT COUNT(*) FROM {CHAT_HISTORY_TABLE} WHERE session_id = :s"
                            ),
                            {"s": session_id},
                        ).scalar()
                        or 0
                    )
            except Exception:
                pass

        if not messages:
            try:
                redis_msgs = get_redis_history(session_id).messages
                mapped = []
                for m in redis_msgs or []:
                    mtype = (
                        getattr(m, "type", "")
                        or getattr(m, "__class__", type("x", (), {})).__name__.lower()
                    )
                    role = "human" if "human" in str(mtype).lower() else "ai"
                    content = getattr(m, "content", "") or ""
                    if content:
                        mapped.append({"type": role, "content": content})
                if mapped:
                    messages = mapped
            except Exception:
                pass
        if not messages:
            try:
                messages = get_session_recall_messages(session_id=session_id, limit=500)
            except Exception:
                pass
        log_audit_event(
            username=user.username,
            action="memory.read.history",
            session_id=session_id,
            details=f"count={len(messages)};raw_rows={raw_row_count}",
        )
        return {"messages": messages, "raw_row_count": raw_row_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error loading history for session %s", session_id)
        return {"messages": [], "error": str(e)}


@router.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: str, user: UserContext = Depends(require_authenticated_user)
):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    try:
        _enforce_session_access_or_403(session_id, user)
        delete_session_metadata(session_id)
        SQLChatMessageHistory(
            session_id=session_id, connection_string=DATABASE_URL
        ).clear()
        get_redis_history(session_id).clear()
        log_audit_event(
            username=user.username,
            action="memory.delete.session",
            session_id=session_id,
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/export/{session_id}")
def export_session(
    session_id: str, user: UserContext = Depends(require_authenticated_user)
):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    try:
        _enforce_session_access_or_403(session_id, user)
        messages = list_chat_messages(session_id, dedupe=True)
        sessions = get_all_sessions()
        category = "Uncategorized"
        for s in sessions:
            if s["session_id"] == session_id:
                category = s["category"]
                break
        return {"session_id": session_id, "category": category, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/import")
def import_session(
    request: ImportRequest, user: UserContext = Depends(require_authenticated_user)
):
    try:
        ensure_session_owner(request.session_id, user.username)
        history = get_sql_chat_history(request.session_id)
        existing_messages = {
            (msg["type"], msg["content"])
            for msg in list_chat_messages(request.session_id, dedupe=False)
        }
        inserted = 0
        skipped = 0
        for msg in request.messages:
            key = (msg.type, msg.content)
            if key in existing_messages:
                skipped += 1
                continue
            if msg.type == "human":
                history.add_user_message(msg.content)
                inserted += 1
            elif msg.type == "ai":
                history.add_ai_message(msg.content)
        set_session_category(request.session_id, request.category)
        touch_session(request.session_id)
        return {"status": "success", "session_id": request.session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/sessions/{session_id}/category")
def update_category(
    session_id: str,
    request: CategoryRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    success = set_session_category(session_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category")
    log_audit_event(
        username=user.username,
        action="memory.update.category",
        session_id=session_id,
        category=request.category,
    )
    return {"status": "success"}


@router.get("/api/sessions/{session_id}/task-suggestions")
def list_session_task_suggestions(
    session_id: str, current_user: UserContext = Depends(require_authenticated_user)
):
    rows = _load_config_list("task_suggestions")
    scoped = [
        r
        for r in rows
        if r.get("session_id") == session_id
        and (current_user.role == "admin" or r.get("username") == current_user.username)
    ]
    return {"suggestions": scoped[:200]}


@router.get("/api/sessions/{session_id}/task-suggestions", include_in_schema=False)
def get_session_task_suggestions(
    session_id: str, user: UserContext = Depends(require_authenticated_user)
):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    suggestions = _load_session_suggestions(session_id)
    unresolved = [s for s in suggestions if not bool(s.get("resolved"))]
    return {"session_id": session_id, "suggestions": unresolved}


@router.get("/api/reports/find")
def find_reports(
    q: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    shared_only: bool = Query(default=False),
    limit: int = Query(default=60, ge=1, le=200),
    current_user: UserContext = Depends(require_authenticated_user),
):
    if session_id and not _can_access_session(session_id, current_user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    matches = find_report_matches(
        username=current_user.username,
        is_admin=current_user.role == "admin",
        keyword=q,
        date_from=date_from,
        date_to=date_to,
        session_id=session_id,
        category=category,
        shared_only=shared_only,
        limit=limit,
    )
    return {"count": len(matches), "matches": matches}


@router.get("/api/reports/session-summary/{session_id}")
def get_session_summary_report(
    session_id: str, current_user: UserContext = Depends(require_authenticated_user)
):
    if not _can_access_session(session_id, current_user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    report = build_session_report_card(
        session_id=session_id,
        username=current_user.username,
        is_admin=current_user.role == "admin",
    )
    if not report:
        raise HTTPException(status_code=404, detail="No session data available")
    return report


@router.get("/api/daily-brief")
def get_daily_brief(current_user: UserContext = Depends(require_authenticated_user)):
    from database import get_core_memories, list_tasks

    all_tasks = list_tasks()
    open_tasks = [t for t in all_tasks if (t.get("status") or "todo") != "done"][:10]
    memories = get_core_memories()[:8]
    pending_replies_raw = (
        get_config(f"pending_reply_notifications_{current_user.username}", "[]") or "[]"
    )
    try:
        pending_replies = json.loads(pending_replies_raw)
        if not isinstance(pending_replies, list):
            pending_replies = []
    except Exception:
        pending_replies = []
    candidates = _load_config_list("memory_inbox_candidates")
    pending_candidates = [
        c
        for c in candidates
        if c.get("username") == current_user.username and c.get("status") == "pending"
    ][:8]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "open_tasks": open_tasks,
        "recent_memories": memories,
        "pending_replies": pending_replies[:10],
        "pending_memory_candidates": pending_candidates,
    }


@router.get("/api/status")
def get_status(user: UserContext = Depends(require_authenticated_user)):
    backend_path = os.path.dirname(os.path.dirname(__file__))
    frontend_path = os.path.join(backend_path, "..", "frontend")

    def _get_latest_mtime(directories: List[str]) -> float:
        latest = 0.0
        for directory in directories:
            if not os.path.exists(directory):
                continue
            for root, _, files in os.walk(directory):
                for file in files:
                    if (
                        file.endswith(".pyc")
                        or "__pycache__" in root
                        or file.endswith(".db")
                        or file.endswith(".db-journal")
                    ):
                        continue
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        if mtime > latest:
                            latest = mtime
                    except OSError:
                        pass
        return latest

    latest_mtime = _get_latest_mtime([backend_path, frontend_path])
    return {"latest_mtime": latest_mtime}
