"""Memory router: inbox, explorer, analytics, core memories, nudges, quick-capture, groups."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.helpers import (
    _append_config_item,
    _can_access_session,
    _create_memory_candidate,
    _load_config_list,
    _notification_throttle_active,
    _parse_iso_dt,
    _save_config_list,
    _send_resend_email,
)
from core.models import (
    ChatReplyNotificationRequest,
    CuratorNudgeAckRequest,
    MemoryExplorerQuery,
    MemoryGroupCreateRequest,
    MemoryGroupShareRequest,
    MemoryInboxUpdateRequest,
)
from database import (
    acknowledge_curator_nudge,
    add_core_memory,
    add_user_to_memory_group,
    create_memory_group,
    delete_core_memory,
    enqueue_pending_reply_notification,
    ensure_session_owner,
    get_accessible_session_ids,
    get_all_configs,
    get_all_sessions,
    get_config,
    get_core_memories,
    get_effective_notification_preferences,
    get_memory_analytics,
    get_memory_group_members,
    get_memory_group_sessions,
    get_session_insight,
    get_session_owner,
    list_curator_nudges,
    list_memory_groups_for_user,
    list_shared_sessions_for_user,
    log_audit_event,
    memory_group_exists,
    memory_group_membership_exists,
    memory_group_session_share_exists,
    remove_user_from_memory_group,
    session_exists,
    share_session_to_group,
    unshare_session_from_group,
    update_core_memory,
    update_memory_candidate_status,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(tags=["memory"])

logger = logging.getLogger("ampai")


# ── Memory Inbox ──────────────────────────────────────────────────────────────


@router.get("/api/memory/inbox")
def list_memory_inbox(
    status: str = Query(default="pending"),
    session_id: str = Query(default=""),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: UserContext = Depends(require_authenticated_user),
):
    rows = _load_config_list("memory_inbox_candidates")
    scoped = [
        r
        for r in rows
        if current_user.role == "admin" or r.get("username") == current_user.username
    ]
    status_value = (status or "").strip().lower()
    if status_value and status_value != "all":
        scoped = [r for r in scoped if (r.get("status") or "").lower() == status_value]

    clean_session = (session_id or "").strip()
    if clean_session:
        scoped = [r for r in scoped if (r.get("session_id") or "") == clean_session]

    query_text = (q or "").strip().lower()
    if query_text:
        scoped = [
            r
            for r in scoped
            if query_text in (r.get("candidate_text") or "").lower()
            or query_text in (r.get("edited_text") or "").lower()
            or query_text in (r.get("session_id") or "").lower()
        ]

    from_dt = _parse_iso_dt(date_from)
    to_dt = _parse_iso_dt(date_to)
    if from_dt:
        scoped = [
            r
            for r in scoped
            if r.get("created_at") and str(r["created_at"]) >= from_dt.isoformat()
        ]
    if to_dt:
        scoped = [
            r
            for r in scoped
            if r.get("created_at") and str(r["created_at"]) <= to_dt.isoformat()
        ]

    scoped = sorted(scoped, key=lambda r: r.get("created_at") or "", reverse=True)
    page = scoped[offset : offset + limit]
    return {
        "items": page,
        "candidates": page,
        "status": status_value or "pending",
        "offset": offset,
        "limit": limit,
        "total": len(scoped),
        "has_more": (offset + limit) < len(scoped),
    }


@router.post("/api/memory/inbox/capture")
def capture_memory_candidate(
    payload: Dict[str, str],
    current_user: UserContext = Depends(require_authenticated_user),
):
    text = (payload.get("text") or "").strip()
    session_id = (payload.get("session_id") or "").strip() or "manual"
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    item = _create_memory_candidate(
        current_user.username, session_id, text, confidence=0.8
    )
    return {"status": "success", "item": item}


@router.patch("/api/memory/inbox/{candidate_id}")
def update_memory_inbox(
    candidate_id: str,
    request: MemoryInboxUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    next_status = (request.status or "").strip().lower()
    if next_status not in {"approved", "rejected", "pending"}:
        raise HTTPException(
            status_code=400, detail="status must be approved, rejected, or pending"
        )
    rows = _load_config_list("memory_inbox_candidates")
    updated = None
    for row in rows:
        if row.get("id") != candidate_id:
            continue
        if (
            current_user.role != "admin"
            and row.get("username") != current_user.username
        ):
            raise HTTPException(status_code=403, detail="Forbidden")
        row["status"] = next_status
        row["edited_text"] = (request.edited_text or "").strip()
        row["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        if next_status == "approved":
            approved_text = row["edited_text"] or row.get("candidate_text") or ""
            if approved_text:
                try:
                    add_core_memory(approved_text, row.get("username") or current_user.username)
                except Exception:
                    logger.exception("Failed to persist approved memory candidate")
        updated = row
        break
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    _save_config_list("memory_inbox_candidates", rows)
    log_audit_event(
        username=current_user.username,
        action=f"memory.review.{next_status}",
        session_id=updated.get("session_id"),
        details=updated.get("id"),
    )
    return {"status": "success", "item": updated}


@router.delete("/api/memory/inbox/{candidate_id}")
def delete_memory_inbox(
    candidate_id: str,
    current_user: UserContext = Depends(require_authenticated_user),
):
    rows = _load_config_list("memory_inbox_candidates")
    kept: List[Dict[str, Any]] = []
    removed: Optional[Dict[str, Any]] = None
    for row in rows:
        if str(row.get("id")) != str(candidate_id):
            kept.append(row)
            continue
        if (
            current_user.role != "admin"
            and row.get("username") != current_user.username
        ):
            raise HTTPException(status_code=403, detail="Forbidden")
        removed = row
    if not removed:
        raise HTTPException(status_code=404, detail="Candidate not found")
    _save_config_list("memory_inbox_candidates", kept)
    log_audit_event(
        username=current_user.username,
        action="memory.review.delete",
        session_id=removed.get("session_id"),
        details=str(removed.get("id")),
    )
    return {"status": "success"}


# ── Memory Explorer ───────────────────────────────────────────────────────────


@router.post("/api/memory/explorer")
def memory_explorer(
    request: MemoryExplorerQuery,
    current_user: UserContext = Depends(require_authenticated_user),
):
    query = (request.query or "").strip()
    category = (request.category or "").strip() or None
    owner_scope = (request.owner_scope or "mine").strip().lower()
    limit = max(1, min(int(request.limit), 200))
    offset = max(0, int(request.offset))
    date_from = _parse_iso_dt(request.date_from)
    date_to = _parse_iso_dt(request.date_to)

    if owner_scope not in {"mine", "shared", "all"}:
        raise HTTPException(
            status_code=400, detail="owner_scope must be mine, shared, or all"
        )
    if owner_scope == "all" and current_user.role != "admin":
        owner_scope = "mine"

    sessions = get_all_sessions(query=query, category=category, archived=False)
    shared_ids = set(list_shared_sessions_for_user(current_user.username))
    accessible_ids = set(
        get_accessible_session_ids(
            username=current_user.username, is_admin=current_user.role == "admin"
        )
    )
    if current_user.role != "admin" and not accessible_ids:
        adopted = 0
        for sess in sessions:
            sid = (sess or {}).get("session_id")
            if not sid or get_session_owner(sid):
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
            fallback_open = str(
                get_config("auth_open_session_fallback", "true")
            ).strip().lower() in {"1", "true", "yes", "on"}
            if fallback_open:
                accessible_ids = {
                    s.get("session_id") for s in sessions if s.get("session_id")
                }

    filtered = []
    for session in sessions:
        session_id = session.get("session_id")
        if not session_id or session_id not in accessible_ids:
            continue
        owner = get_session_owner(session_id) or "unknown"
        is_owned = owner == current_user.username or owner == "unknown"
        is_shared = session_id in shared_ids

        if owner_scope == "mine" and not is_owned:
            continue
        if owner_scope == "shared" and not is_shared:
            continue

        from core.helpers import _classify_tier

        updated_at_raw = session.get("updated_at") or ""
        updated_dt = _parse_iso_dt(updated_at_raw)
        if date_from and updated_dt and updated_dt < date_from:
            continue
        if date_to and updated_dt and updated_dt > date_to:
            continue

        filtered.append(
            {
                "session_id": session_id,
                "category": session.get("category") or "Uncategorized",
                "updated_at": updated_at_raw,
                "pinned": bool(session.get("pinned")),
                "owner": owner,
                "shared_via_group": is_shared,
                "visibility": "shared"
                if is_shared
                else ("mine" if is_owned else "other"),
                "tier": _classify_tier(updated_at_raw),
                "insight": get_session_insight(session_id),
            }
        )

    total = len(filtered)
    page = filtered[offset : offset + limit]
    category_counts: Dict[str, int] = {}
    for item in filtered:
        cat = item.get("category") or "Uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    memory_rows = _load_config_list("memory_inbox_candidates")
    pending_candidates = [
        row
        for row in memory_rows
        if (
            current_user.role == "admin" or row.get("username") == current_user.username
        )
        and (row.get("status") or "").lower() == "pending"
        and (not query or query.lower() in (row.get("candidate_text") or "").lower())
    ][:20]
    core_memories_all = get_core_memories()
    saved_facts = []
    for mem in core_memories_all:
        fact = str(mem.get("fact") or "").strip()
        if not fact:
            continue
        if query and query.lower() not in fact.lower():
            continue
        saved_facts.append({"id": mem.get("id"), "fact": fact})
        if len(saved_facts) >= 20:
            break

    log_audit_event(
        username=current_user.username,
        action="memory.read.explorer",
        details=f"scope={owner_scope};query={query};category={category or 'all'};count={total}",
    )
    return {
        "sessions": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
        "categories": category_counts,
    }


# ── Memory Analytics (lightweight) ───────────────────────────────────────────


@router.get("/api/memory/analytics", include_in_schema=False)
def get_memory_analytics_simple(
    days: int = 30, current_user: UserContext = Depends(require_authenticated_user)
):
    """Simple analytics (lightweight version for home dashboard)."""
    days = max(1, min(days, 365))
    sessions = get_all_sessions()
    visible_sessions = []
    for session in sessions:
        if current_user.role == "admin":
            visible_sessions.append(session)
        elif (session.get("owner") or "") == current_user.username:
            visible_sessions.append(session)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    recent_sessions = []
    for s in visible_sessions:
        raw = s.get("updated_at")
        try:
            ts = (
                datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if isinstance(raw, str)
                else None
            )
        except Exception:
            ts = None
        if ts and ts >= since:
            recent_sessions.append(s)
    categories: Dict[str, int] = {}
    for s in recent_sessions:
        cat = (s.get("category") or "Uncategorized").strip() or "Uncategorized"
        categories[cat] = categories.get(cat, 0) + 1
    candidates = _load_config_list("memory_inbox_candidates")
    suggestions = _load_config_list("task_suggestions")
    if current_user.role != "admin":
        candidates = [
            c for c in candidates if c.get("username") == current_user.username
        ]
        suggestions = [
            s for s in suggestions if s.get("username") == current_user.username
        ]
    approved_count = sum(1 for c in candidates if c.get("status") == "approved")
    pending_count = sum(1 for c in candidates if c.get("status") == "pending")
    converted_count = sum(1 for s in suggestions if s.get("status") == "converted")
    total_suggestions = len(suggestions)
    return {
        "days": days,
        "sessions_considered": len(recent_sessions),
        "category_counts": categories,
        "memory_candidates_pending": pending_count,
        "memory_candidates_approved": approved_count,
        "task_suggestions_total": total_suggestions,
        "task_suggestions_converted": converted_count,
        "task_suggestion_conversion_rate": round(
            (converted_count / total_suggestions), 3
        )
        if total_suggestions
        else 0.0,
    }


@router.get("/api/memory/analytics")
def memory_analytics(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    owner_scope: str = Query(default="mine"),
    stale_days: int = Query(default=30, ge=1, le=3650),
    top_n: int = Query(default=8, ge=1, le=20),
    export: Optional[str] = Query(default=None),
    current_user: UserContext = Depends(require_authenticated_user),
):
    normalized_scope = (owner_scope or "mine").strip().lower()
    if normalized_scope not in {"mine", "shared", "all"}:
        raise HTTPException(
            status_code=400, detail="owner_scope must be mine, shared, or all"
        )
    if current_user.role != "admin" and normalized_scope == "all":
        normalized_scope = "mine"

    payload = get_memory_analytics(
        username=current_user.username,
        is_admin=current_user.role == "admin",
        date_from=date_from,
        date_to=date_to,
        owner_scope=normalized_scope,
        stale_days=stale_days,
        top_n=top_n,
    )

    if (export or "").strip().lower() == "csv":
        csv_body = _memory_analytics_to_csv(payload)
        return Response(
            content=csv_body,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=memory-analytics.csv"
            },
        )
    return payload


def _memory_analytics_to_csv(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("section,key,value")
    kpis = payload.get("kpis") or {}
    for key in ["memory_writes_total", "retrieval_hits_total", "stale_memories_count"]:
        lines.append(f"kpi,{key},{kpis.get(key, 0)}")
    lines.append("")
    lines.append("memory_writes_per_day,day,count")
    for row in payload.get("memory_writes_per_day") or []:
        lines.append(
            f"memory_writes_per_day,{row.get('day', '')},{row.get('count', 0)}"
        )
    lines.append("")
    lines.append("retrieval_hits_per_day,day,count")
    for row in payload.get("retrieval_hits_per_day") or []:
        lines.append(
            f"retrieval_hits_per_day,{row.get('day', '')},{row.get('count', 0)}"
        )
    lines.append("")
    lines.append("top_categories,category,count")
    for row in payload.get("top_categories") or []:
        category = str(row.get("category", "")).replace('"', '""')
        lines.append(f'top_categories,"{category}",{row.get("count", 0)}')
    lines.append("")
    lines.append(
        "stale_memories,session_id,category,owner,updated_at,last_retrieval_at"
    )
    for row in payload.get("stale_memories") or []:
        category = str(row.get("category", "")).replace('"', '""')
        owner = str(row.get("owner", "")).replace('"', '""')
        lines.append(
            f'stale_memories,{row.get("session_id", "")},"{category}","{owner}",'
            f"{row.get('updated_at', '')},{row.get('last_retrieval_at', '') or ''}"
        )
    return "\n".join(lines) + "\n"


# ── Core Memories ─────────────────────────────────────────────────────────────


@router.get("/api/core-memories")
def api_get_core_memories_self(user: UserContext = Depends(require_authenticated_user)):
    return {"core_memories": get_core_memories(user.username)}


@router.post("/api/core-memories")
def api_add_core_memory(
    request: dict, user: UserContext = Depends(require_authenticated_user)
):
    fact = (request.get("fact") or "").strip()
    if not fact:
        raise HTTPException(status_code=400, detail="fact is required")
    success = add_core_memory(fact, user.username)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save core memory")
    log_audit_event(
        username=user.username,
        action="memory.write.core",
        details=f"fact_len={len(fact)}",
    )
    return {"status": "success"}


@router.patch("/api/core-memories/{mem_id}")
def api_edit_core_memory(
    mem_id: int, request: dict, user: UserContext = Depends(require_authenticated_user)
):
    from database import get_core_memory_owner
    owner = get_core_memory_owner(mem_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Memory not found")
    if user.role != "admin" and owner != user.username:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this memory")
    fact = (request.get("fact") or "").strip()
    if not fact:
        raise HTTPException(status_code=400, detail="fact is required")
    success = update_core_memory(mem_id, fact)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or unchanged")
    log_audit_event(
        username=user.username, action="memory.edit.core", details=f"id={mem_id}"
    )
    return {"status": "success"}


@router.delete("/api/core-memories/{mem_id}")
def api_delete_core_memory_self(
    mem_id: int, user: UserContext = Depends(require_authenticated_user)
):
    from database import get_core_memory_owner
    owner = get_core_memory_owner(mem_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Memory not found")
    if user.role != "admin" and owner != user.username:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this memory")
    success = delete_core_memory(mem_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete core memory")
    log_audit_event(
        username=user.username, action="memory.delete.core", details=f"id={mem_id}"
    )
    return {"status": "success"}



@router.get("/api/admin/core-memories")
def api_get_core_memories(user: UserContext = Depends(require_admin_user)):
    return {"core_memories": get_core_memories()}


@router.patch("/api/admin/core-memories/{mem_id}")
def api_admin_edit_core_memory(
    mem_id: int, request: dict, user: UserContext = Depends(require_admin_user)
):
    fact = (request.get("fact") or "").strip()
    if not fact:
        raise HTTPException(status_code=400, detail="fact is required")
    success = update_core_memory(mem_id, fact)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or unchanged")
    log_audit_event(
        username=user.username, action="memory.edit.core.admin", details=f"id={mem_id}"
    )
    return {"status": "success"}


@router.delete("/api/admin/core-memories/{mem_id}")
def api_delete_core_memory(
    mem_id: int, user: UserContext = Depends(require_admin_user)
):
    success = delete_core_memory(mem_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete core memory")
    return {"status": "success"}


# ── Vector Database Explorer (Admin Only) ────────────────────────────────────


@router.get("/api/admin/vector-memories")
def api_admin_list_vector_memories(user: UserContext = Depends(require_admin_user)):
    from database import vector_engine
    from sqlalchemy import text as sa_text
    try:
        with vector_engine.connect() as conn:
            query = sa_text(
                "SELECT e.id, e.document, e.cmetadata "
                "FROM langchain_pg_embedding e "
                "JOIN langchain_pg_collection c ON e.collection_id = c.uuid "
                "WHERE c.name = 'chat_memory' "
                "ORDER BY e.id DESC"
            )
            rows = conn.execute(query).fetchall()
        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "document": row[1],
                "cmetadata": row[2] or {}
            })
        return {"vector_memories": memories}
    except Exception as exc:
        logger.exception("api_admin_list_vector_memories failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/admin/vector-memories", status_code=201)
def api_admin_create_vector_memory(request: dict, user: UserContext = Depends(require_admin_user)):
    document = (request.get("document") or "").strip()
    if not document:
        raise HTTPException(status_code=400, detail="document text is required")
    try:
        from memory_indexer import MemoryIndexer
        indexer = MemoryIndexer()
        if not indexer.enabled:
            raise HTTPException(status_code=503, detail=f"Embedding provider disabled: {indexer.disabled_reason}")
        indexer.add_fact(document)
        log_audit_event(
            username=user.username,
            action="memory.vector.create",
            details=f"doc_len={len(document)}"
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("api_admin_create_vector_memory failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/api/admin/vector-memories/{mem_id}")
def api_admin_update_vector_memory(mem_id: str, request: dict, user: UserContext = Depends(require_admin_user)):
    document = (request.get("document") or "").strip()
    if not document:
        raise HTTPException(status_code=400, detail="document text is required")
    try:
        from memory_indexer import MemoryIndexer
        indexer = MemoryIndexer()
        if not indexer.enabled:
            raise HTTPException(status_code=503, detail=f"Embedding provider disabled: {indexer.disabled_reason}")
        
        # Generate new embedding
        embedding = indexer.embedding_model.embed_query(document)
        emb_str = "[" + ",".join(map(str, embedding)) + "]"
        
        from database import vector_engine
        from sqlalchemy import text as sa_text
        with vector_engine.connect() as conn:
            result = conn.execute(
                sa_text("UPDATE langchain_pg_embedding SET document = :doc, embedding = :emb WHERE id = :id"),
                {"doc": document, "emb": emb_str, "id": mem_id}
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Vector memory not found")
                
        log_audit_event(
            username=user.username,
            action="memory.vector.update",
            details=f"id={mem_id}"
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("api_admin_update_vector_memory failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/api/admin/vector-memories/{mem_id}")
def api_admin_delete_vector_memory(mem_id: str, user: UserContext = Depends(require_admin_user)):
    try:
        from database import vector_engine
        from sqlalchemy import text as sa_text
        with vector_engine.connect() as conn:
            result = conn.execute(
                sa_text("DELETE FROM langchain_pg_embedding WHERE id = :id"),
                {"id": mem_id}
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Vector memory not found")
                
        log_audit_event(
            username=user.username,
            action="memory.vector.delete",
            details=f"id={mem_id}"
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("api_admin_delete_vector_memory failed")
        raise HTTPException(status_code=500, detail=str(exc))



# ── Agent Memories ────────────────────────────────────────────────────────────


def _decode_pb_strings(data: bytes) -> list:
    """Best-effort Protocol Buffer decoder."""
    import struct

    results = []
    pos = 0

    def read_varint(d, p):
        result, shift = 0, 0
        while p < len(d):
            b = d[p]
            p += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return result, p

    while pos < len(data):
        try:
            tag_wire, pos = read_varint(data, pos)
            field_num = tag_wire >> 3
            wire_type = tag_wire & 0x7
            if wire_type == 0:
                _, pos = read_varint(data, pos)
            elif wire_type == 1:
                pos += 8
            elif wire_type == 5:
                pos += 4
            elif wire_type == 2:
                length, pos = read_varint(data, pos)
                raw = data[pos : pos + length]
                pos += length
                try:
                    text = raw.decode("utf-8")
                    if len(text) >= 10:
                        results.append({"field": field_num, "text": text})
                    else:
                        nested = _decode_pb_strings(raw)
                        results.extend(nested)
                except UnicodeDecodeError:
                    nested = _decode_pb_strings(raw)
                    results.extend(nested)
            else:
                break
        except Exception:
            break
    return results


@router.get("/api/agent-memories")
def get_agent_memories(
    current_user: UserContext = Depends(require_authenticated_user),
):
    import glob
    import os

    core = get_core_memories()
    candidate_dirs = [
        os.path.expanduser("~/.gemini/antigravity/implicit"),
        os.path.expandvars("$HOME/.gemini/antigravity/implicit"),
    ]
    env_dir = os.getenv("ANTIGRAVITY_MEMORY_DIR", "")
    if env_dir:
        candidate_dirs.insert(0, env_dir)

    pb_dir = None
    pb_dir_accessible = False
    for candidate in candidate_dirs:
        try:
            if os.path.isdir(candidate):
                os.listdir(candidate)
                pb_dir = candidate
                pb_dir_accessible = True
                break
        except PermissionError:
            pb_dir = candidate
        except Exception:
            pass

    pb_memories = []
    pb_file_count = 0
    pb_readable_count = 0

    if pb_dir_accessible:
        try:
            pb_files = sorted(glob.glob(os.path.join(pb_dir, "*.pb")))
            pb_file_count = len(pb_files)
            for fpath in pb_files:
                fname = os.path.basename(fpath)
                try:
                    with open(fpath, "rb") as f:
                        raw = f.read()
                    strings = _decode_pb_strings(raw)
                    seen = set()
                    texts = []
                    for item in strings:
                        t = item["text"].strip()
                        if t and t not in seen and len(t) >= 15:
                            seen.add(t)
                            texts.append({"field": item["field"], "text": t})
                    if texts:
                        pb_readable_count += 1
                    pb_memories.append(
                        {"file": fname, "size_bytes": len(raw), "strings": texts}
                    )
                except PermissionError:
                    pb_memories.append(
                        {
                            "file": fname,
                            "size_bytes": 0,
                            "strings": [],
                            "error": "permission_denied",
                        }
                    )
                except Exception as exc:
                    pb_memories.append(
                        {
                            "file": fname,
                            "size_bytes": 0,
                            "strings": [],
                            "error": str(exc)[:120],
                        }
                    )
        except Exception as exc:
            logger.warning("agent-memories: error reading pb dir: %s", exc)
    elif pb_dir:
        pb_memories = [
            {
                "file": "~/.gemini/antigravity/implicit/",
                "size_bytes": 0,
                "strings": [],
                "error": "permission_denied",
                "fix": (
                    "macOS TCC denies access to ~/.gemini/antigravity/implicit/. "
                    "Grant Full Disk Access to Terminal (or your Python/uvicorn process) "
                    "in System Preferences → Privacy & Security → Full Disk Access. "
                    "Or set the ANTIGRAVITY_MEMORY_DIR env var to a readable copy."
                ),
            }
        ]

    log_audit_event(
        username=current_user.username,
        action="memory.read.agent_memories",
        details=f"pb_files={pb_file_count};readable={pb_readable_count};core={len(core)};accessible={pb_dir_accessible}",
    )
    return {
        "core_memories": core,
        "agent_pb_memories": pb_memories,
        "pb_file_count": pb_file_count,
        "pb_readable_count": pb_readable_count,
        "pb_dir": pb_dir or "~/.gemini/antigravity/implicit",
        "pb_dir_accessible": pb_dir_accessible,
    }


# ── Nudges ────────────────────────────────────────────────────────────────────


@router.get("/api/nudges")
def get_nudges(
    session_id: Optional[str] = None,
    user: UserContext = Depends(require_authenticated_user),
):
    return {
        "nudges": list_curator_nudges(
            username=user.username, session_id=session_id, only_unacked=True, limit=50
        )
    }


@router.post("/api/nudges/ack")
def ack_nudge(
    request: CuratorNudgeAckRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    ok = acknowledge_curator_nudge(nudge_id=request.nudge_id, username=user.username)
    if not ok:
        raise HTTPException(status_code=404, detail="Nudge not found")
    return {"status": "ok"}


# ── Quick capture ─────────────────────────────────────────────────────────────


@router.post("/api/quick-capture")
def quick_capture(
    payload: Dict[str, str],
    current_user: UserContext = Depends(require_authenticated_user),
):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    session_id = (payload.get("session_id") or "quick_capture").strip()
    item = _create_memory_candidate(
        current_user.username, session_id, text, confidence=0.9
    )
    return {"status": "success", "item": item}


# ── Memory Groups ─────────────────────────────────────────────────────────────


@router.get("/api/memory-groups")
def get_memory_groups(
    current_user: UserContext = Depends(require_authenticated_user),
):
    return {"groups": list_memory_groups_for_user(current_user.username)}


@router.post("/api/admin/memory-groups")
def admin_create_memory_group(
    request: MemoryGroupCreateRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    group_id = create_memory_group(
        name=request.name.strip(),
        description=(request.description or "").strip(),
        created_by=current_user.username,
    )
    if not group_id:
        raise HTTPException(status_code=500, detail="Failed to create group")
    for member in request.members:
        member_name = (member or "").strip()
        if member_name:
            add_user_to_memory_group(group_id, member_name)
    return {"status": "success", "group_id": group_id}


@router.post("/api/admin/memory-groups/{group_id}/members/{username}")
def admin_add_group_member(
    group_id: int, username: str, _: UserContext = Depends(require_admin_user)
):
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if memory_group_membership_exists(group_id, clean_username):
        raise HTTPException(
            status_code=409, detail="User is already a member of this group"
        )
    if not add_user_to_memory_group(group_id, clean_username):
        raise HTTPException(status_code=500, detail="Failed to add member")
    return {"status": "success"}


@router.post("/api/admin/memory-groups/{group_id}/share")
def admin_share_session(
    group_id: int,
    request: MemoryGroupShareRequest,
    _: UserContext = Depends(require_admin_user),
):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    session_id = (request.session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    if memory_group_session_share_exists(group_id, session_id):
        raise HTTPException(
            status_code=409, detail="Session is already shared to this group"
        )
    if not share_session_to_group(group_id, session_id):
        raise HTTPException(status_code=500, detail="Failed to share session")
    return {"status": "success"}


@router.get("/api/admin/memory-groups/{group_id}/members")
def admin_get_group_members(
    group_id: int, _: UserContext = Depends(require_admin_user)
):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    return {"members": get_memory_group_members(group_id)}


@router.get("/api/admin/memory-groups/{group_id}/sessions")
def admin_get_group_sessions(
    group_id: int, _: UserContext = Depends(require_admin_user)
):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    return {"sessions": get_memory_group_sessions(group_id)}


@router.delete("/api/admin/memory-groups/{group_id}/members/{username}")
def admin_remove_group_member(
    group_id: int, username: str, _: UserContext = Depends(require_admin_user)
):
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if not remove_user_from_memory_group(group_id, clean_username):
        raise HTTPException(status_code=404, detail="Member not found in group")
    return {"status": "success"}


@router.delete("/api/admin/memory-groups/{group_id}/sessions/{session_id}")
def admin_unshare_group_session(
    group_id: int, session_id: str, _: UserContext = Depends(require_admin_user)
):
    clean_session_id = (session_id or "").strip()
    if not clean_session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if not unshare_session_from_group(group_id, clean_session_id):
        raise HTTPException(status_code=404, detail="Session share not found in group")
    return {"status": "success"}


# ── Chat Reply Notifications ──────────────────────────────────────────────────


@router.post("/api/notifications/chat-reply")
def notify_chat_reply(
    request: ChatReplyNotificationRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    prefs = get_effective_notification_preferences(current_user.username)
    interval_seconds = int(prefs.get("minimum_notify_interval_seconds") or 0)
    if _notification_throttle_active(
        current_user.username, request.session_id, interval_seconds
    ):
        return {"status": "throttled"}

    preview = (request.reply_preview or "").strip()
    if len(preview) > 500:
        preview = preview[:500] + "..."

    digest_mode = (prefs.get("digest_mode") or "immediate").strip().lower()
    if digest_mode == "periodic":
        queued = enqueue_pending_reply_notification(
            current_user.username, request.session_id, preview
        )
        return {"status": "queued" if queued else "queue_failed"}

    if not bool(prefs.get("email_notify_on_away_replies")):
        return {"status": "email_disabled"}

    sent = _send_resend_email(
        subject=f"AmpAI reply ready for {current_user.username}",
        body_text=f"User: {current_user.username}\nSession: {request.session_id}\n\nReply preview:\n{preview}",
    )
    return {"status": "sent" if sent else "not_sent"}


# ══════════════════════════════════════════════════════════════════════════════
# New Memory Endpoints (Task 6.2)
# Uses MemoryService and AuditLogger per design spec.
# ══════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field

from core.audit import (
    AuditLogger,
    ACTION_MEMORY_WRITE,
    ACTION_MEMORY_READ,
    ACTION_MEMORY_DELETE,
)
from database import engine as db_engine
from services.memory_service import MemoryService


# ── Request models ────────────────────────────────────────────────────────────


class ExplicitMemoryRequest(BaseModel):
    """Request body for POST /api/memory/core."""

    text: str = Field(..., min_length=1, max_length=1000)
    category: Optional[str] = None


class MemorySearchRequest(BaseModel):
    """Request body for POST /api/memory/search."""

    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=8)
    mode: str = Field(default="hybrid")
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    recency_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    char_budget: int = Field(default=1200, ge=200, le=4000)


class InboxActionRequest(BaseModel):
    """Request body for PATCH /api/memory/inbox/{id}."""

    action: str = Field(..., description="Must be 'approve' or 'reject'")
    edited_text: Optional[str] = None


# ── Service singletons ────────────────────────────────────────────────────────


def _get_memory_service() -> MemoryService:
    """Lazy-init MemoryService singleton."""
    return MemoryService(db_engine=db_engine)


def _get_audit_logger() -> AuditLogger:
    """Lazy-init AuditLogger singleton."""
    return AuditLogger(engine=db_engine)


# ── GET /api/memory/core — list core memories ─────────────────────────────────


@router.get("/api/memory/core")
def list_core_memories(
    current_user: UserContext = Depends(require_authenticated_user),
):
    """List all core memories for the authenticated user."""
    audit = _get_audit_logger()
    try:
        from sqlalchemy import text as sa_text

        with db_engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT id, username, fact, category, created_at "
                    "FROM core_memories WHERE username = :username "
                    "ORDER BY created_at DESC"
                ),
                {"username": current_user.username},
            ).fetchall()

        memories = [
            {
                "id": row[0],
                "username": row[1],
                "fact": row[2],
                "category": row[3],
                "created_at": str(row[4]) if row[4] else None,
            }
            for row in rows
        ]
    except Exception as exc:
        logger.warning("list_core_memories failed: %s", exc)
        memories = []

    audit.log(
        username=current_user.username,
        action_type=ACTION_MEMORY_READ,
        details={"operation": "list_core", "count": len(memories)},
    )
    return {"memories": memories, "total": len(memories)}


# ── POST /api/memory/core — add explicit memory ──────────────────────────────


@router.post("/api/memory/core", status_code=201)
def add_explicit_memory(
    request: ExplicitMemoryRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """Save an explicit memory to core memories."""
    svc = _get_memory_service()
    audit = _get_audit_logger()

    result = svc.save_explicit_memory(
        username=current_user.username,
        session_id=None,
        text=request.text,
        category=request.category,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to save memory")

    audit.log(
        username=current_user.username,
        action_type=ACTION_MEMORY_WRITE,
        details={
            "operation": "add_explicit",
            "memory_id": result.get("id"),
            "category": result.get("category"),
            "fact_length": len(request.text),
        },
    )
    return {"status": "success", "memory": result}


# ── DELETE /api/memory/core/{id} — delete/forget memory ───────────────────────


@router.delete("/api/memory/core/{memory_id}")
def delete_memory(
    memory_id: int,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """Delete a core memory by ID. Returns 404 if not found."""
    svc = _get_memory_service()
    audit = _get_audit_logger()

    deleted = svc.forget_memory(username=current_user.username, memory_id=memory_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")

    audit.log(
        username=current_user.username,
        action_type=ACTION_MEMORY_DELETE,
        details={"operation": "forget", "memory_id": memory_id},
    )
    return {"status": "success", "deleted_id": memory_id}


# ── GET /api/memory/inbox — list pending candidates ───────────────────────────


@router.get("/api/memory/inbox/pending")
def list_pending_candidates_v2(
    current_user: UserContext = Depends(require_authenticated_user),
):
    """
    List pending memory candidates (max 50, ordered by created_at DESC).

    Uses MemoryService backed by the memory_candidates database table.
    Provides the spec-required simple pending-only view (Requirement 5.6).
    """
    audit = _get_audit_logger()
    try:
        from sqlalchemy import text as sa_text

        with db_engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT id, username, session_id, candidate_text, source, "
                    "confidence, status, importance_score, created_at "
                    "FROM memory_candidates "
                    "WHERE username = :username AND status = 'pending' "
                    "ORDER BY created_at DESC "
                    "LIMIT 50"
                ),
                {"username": current_user.username},
            ).fetchall()

        candidates = [
            {
                "id": row[0],
                "username": row[1],
                "session_id": row[2],
                "candidate_text": row[3],
                "source": row[4],
                "confidence": row[5],
                "status": row[6],
                "importance_score": row[7],
                "created_at": str(row[8]) if row[8] else None,
            }
            for row in rows
        ]
    except Exception as exc:
        logger.warning("list_pending_candidates failed: %s", exc)
        candidates = []

    audit.log(
        username=current_user.username,
        action_type=ACTION_MEMORY_READ,
        details={"operation": "list_inbox_pending", "count": len(candidates)},
    )
    return {"candidates": candidates, "total": len(candidates)}


# ── PATCH /api/memory/inbox/{id} — approve/reject candidate ──────────────────


@router.patch("/api/memory/inbox/{candidate_id}/review")
def review_memory_candidate_v2(
    candidate_id: int,
    request: InboxActionRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """
    Approve or reject a memory candidate using MemoryService.

    - approve: promotes candidate to core memory + vector index
    - reject: marks candidate as rejected, excluded from retrieval

    Returns 404 if candidate not found or not in pending status.
    (Requirement 5.7, 5.8, 5.9)
    """
    svc = _get_memory_service()
    audit = _get_audit_logger()

    action = request.action.strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(
            status_code=400, detail="action must be 'approve' or 'reject'"
        )

    if action == "approve":
        result = svc.approve_candidate(
            candidate_id=candidate_id,
            edited_text=request.edited_text,
        )
        if not result:
            raise HTTPException(
                status_code=404, detail="Candidate not found or not pending"
            )
        audit.log(
            username=current_user.username,
            action_type=ACTION_MEMORY_WRITE,
            details={
                "operation": "approve_candidate",
                "candidate_id": candidate_id,
                "core_memory_id": result.get("core_memory_id"),
            },
        )
        return {"status": "approved", "result": result}
    else:
        result = svc.reject_candidate(candidate_id=candidate_id)
        if not result:
            raise HTTPException(
                status_code=404, detail="Candidate not found or not pending"
            )
        audit.log(
            username=current_user.username,
            action_type=ACTION_MEMORY_DELETE,
            details={
                "operation": "reject_candidate",
                "candidate_id": candidate_id,
            },
        )
        return {"status": "rejected", "result": result}


# ── POST /api/memory/search — hybrid memory search ───────────────────────────


@router.post("/api/memory/search")
def search_memory(
    request: MemorySearchRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """
    Perform hybrid memory search with configurable settings.

    Returns matching memories compressed to char_budget along with
    retrieval metadata (retrieved_count, context_chars, pipeline, latency_ms).
    """
    svc = _get_memory_service()
    audit = _get_audit_logger()

    search_result = svc.search_memory(
        username=current_user.username,
        query=request.query,
        limit=request.limit,
        mode=request.mode,
        category=request.category,
        date_from=request.date_from,
        date_to=request.date_to,
        recency_bias=request.recency_bias,
        char_budget=request.char_budget,
    )

    audit.log(
        username=current_user.username,
        action_type=ACTION_MEMORY_READ,
        details={
            "operation": "search",
            "query_length": len(request.query),
            "mode": request.mode,
            "retrieved_count": search_result.metadata.retrieved_count,
            "latency_ms": search_result.metadata.latency_ms,
        },
    )

    return {
        "memories": search_result.memories,
        "metadata": {
            "retrieved_count": search_result.metadata.retrieved_count,
            "context_chars": search_result.metadata.context_chars,
            "pipeline": search_result.metadata.pipeline,
            "latency_ms": search_result.metadata.latency_ms,
        },
    }


class CurateTextRequest(BaseModel):
    text: str
    model_type: Optional[str] = None


@router.post("/api/memory/curate-text")
def api_curate_text(
    request: CurateTextRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    """
    Extract memory facts from arbitrary text content (e.g. from an uploaded file).
    Uses the configured LLM or the specified model_type.
    Returns a list of extracted candidate facts.
    """
    from ampai_identity import get_file_memory_curation_prompt
    from memory_curator import _call_local_llm
    import json

    text_content = request.text.strip()
    if not text_content:
        return {"facts": []}

    model_type = request.model_type or get_config("default_model", "ollama")
    prompt = get_file_memory_curation_prompt(text_content, current_user.username)
    raw_response = _call_local_llm(prompt, model_type)

    facts = []
    try:
        cleaned = raw_response.strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start >= 0 and end > start:
            facts = json.loads(cleaned[start:end])
            facts = [f for f in facts if isinstance(f, str) and f.strip()]
    except Exception as exc:
        logger.debug("Failed to parse curate-text JSON from LLM: %s", exc)

    return {"facts": facts}
