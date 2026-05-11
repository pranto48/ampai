"""System router: health, identity, upload, notes, network, analytics."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent import get_llm
from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.helpers import _check_db_health, _check_redis_health, _classify_tier
from core.models import NoteCreateRequest, NoteUpdateRequest, TargetModel
from database import (
    add_media_asset,
    add_network_target,
    delete_network_target,
    engine,
    ensure_session_owner,
    get_accessible_session_ids,
    get_all_configs,
    get_all_sessions,
    get_config,
    get_core_memories,
    get_memory_rollup_metrics,
    get_network_targets,
    get_session_owner,
    log_audit_event,
)
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import text

router = APIRouter(tags=["system"])
logger = logging.getLogger("ampai")

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "..", "data", "uploads"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/api/health")
def health(user: UserContext = Depends(require_admin_user)):
    db_check = _check_db_health()
    redis_check = _check_redis_health()

    # Model provider check
    provider = (get_all_configs().get("default_model") or "ollama").strip().lower()
    try:
        get_llm(provider)
        model_check = {"ok": True, "provider": provider}
    except Exception as exc:
        model_check = {"ok": False, "provider": provider, "details": str(exc)}

    # Search provider check
    configs = get_all_configs()
    fallback = (configs.get("web_fallback_provider") or "").strip().lower()
    if fallback == "serpapi":
        search_check = {
            "ok": bool(configs.get("serpapi_api_key")),
            "provider": "serpapi",
        }
    elif fallback == "bing":
        search_check = {"ok": bool(configs.get("bing_api_key")), "provider": "bing"}
    elif fallback == "custom":
        search_check = {
            "ok": bool(configs.get("custom_web_search_url")),
            "provider": "custom",
        }
    else:
        search_check = {"ok": True, "provider": "duckduckgo"}

    try:
        from scheduler import get_scheduler_diagnostics

        sched_check = get_scheduler_diagnostics()
    except Exception:
        sched_check = {"running": False, "jobs": [], "last_run": {}}

    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "db": db_check,
            "redis": redis_check,
            "model_provider": model_check,
            "search_provider": search_check,
            "scheduler": sched_check,
        },
    }


# ── Config status ─────────────────────────────────────────────────────────────


@router.get("/api/configs/status")
def get_configs_status(user: UserContext = Depends(require_authenticated_user)):
    configs = get_all_configs()
    return {
        "openai": bool(configs.get("openai_api_key")),
        "gemini": bool(configs.get("gemini_api_key")),
        "anthropic": bool(configs.get("anthropic_api_key")),
        "generic": bool(configs.get("generic_base_url")),
        "openrouter": bool(configs.get("openrouter_api_key")),
        "anythingllm": bool(configs.get("anythingllm_base_url")),
        "default_model": configs.get("default_model"),
        "chat_agent_name": configs.get("chat_agent_name") or "AI Agent",
        "chat_agent_avatar_url": configs.get("chat_agent_avatar_url") or "",
        "notification_default_browser_notify_on_away_replies": configs.get(
            "notification_default_browser_notify_on_away_replies", "true"
        ),
        "notification_default_email_notify_on_away_replies": configs.get(
            "notification_default_email_notify_on_away_replies",
            configs.get("chat_reply_email_notifications", "false"),
        ),
        "notification_default_minimum_notify_interval_seconds": configs.get(
            "notification_default_minimum_notify_interval_seconds", "300"
        ),
        "notification_default_digest_mode": configs.get(
            "notification_default_digest_mode", "immediate"
        ),
        "notification_default_digest_interval_minutes": configs.get(
            "notification_default_digest_interval_minutes", "30"
        ),
        "local_only_mode": configs.get("local_only_mode", "true"),
        "curator_nudges_enabled": configs.get("curator_nudges_enabled", "true"),
        "memory_embedding_enabled": configs.get("memory_embedding_enabled", "false"),
        "memory_embedding_provider": configs.get("memory_embedding_provider", "ollama"),
        "memory_embedding_model": configs.get(
            "memory_embedding_model", "nomic-embed-text"
        ),
        "memory_hybrid_retrieval_enabled": configs.get(
            "memory_hybrid_retrieval_enabled", "false"
        ),
    }


# ── AmpAI identity / Ollama health ────────────────────────────────────────────


@router.get("/api/ampai/identity")
def get_ampai_identity():
    from ampai_identity import get_identity_info

    return get_identity_info()


@router.get("/api/ampai/health/ollama")
def check_ollama_health():
    from ampai_identity import (
        check_ollama_alive,
        get_available_local_models,
        get_recommended_local_model,
    )

    alive = check_ollama_alive()
    models = get_available_local_models() if alive else []
    return {
        "alive": alive,
        "models": models,
        "recommended": get_recommended_local_model() if alive else None,
    }


# ── File upload / media ───────────────────────────────────────────────────────


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    current_user: UserContext = Depends(require_authenticated_user),
):
    from core.helpers import _enforce_session_access_or_403

    try:
        owner_username = current_user.username
        if session_id:
            _enforce_session_access_or_403(session_id, current_user)
            owner_username = get_session_owner(session_id) or current_user.username
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{__import__('uuid').uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        extracted_text = None
        if file_ext.lower() == ".pdf":
            try:
                import PyPDF2

                with open(file_path, "rb") as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    extracted_text = "\n".join(
                        [
                            page.extract_text()
                            for page in reader.pages
                            if page.extract_text()
                        ]
                    )
            except Exception as e:
                logger.warning("PDF parsing error: %s", e)
        elif file_ext.lower() in [
            ".txt",
            ".csv",
            ".json",
            ".md",
            ".py",
            ".js",
            ".html",
            ".css",
        ]:
            with open(file_path, "r", encoding="utf-8") as text_file:
                extracted_text = text_file.read()
        payload = {
            "filename": file.filename,
            "url": f"/uploads/{unique_filename}",
            "type": file.content_type,
            "extracted_text": extracted_text,
        }
        add_media_asset(
            username=owner_username,
            session_id=session_id,
            filename=file.filename,
            url=payload["url"],
            mime_type=file.content_type,
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/media")
def get_media_assets(
    username: Optional[str] = Query(default=None),
    current_user: UserContext = Depends(require_authenticated_user),
):
    from database import list_media_assets

    if current_user.role != "admin":
        username = current_user.username
    return {"media": list_media_assets(username=username)}


# ── Network targets ───────────────────────────────────────────────────────────


@router.get("/api/targets")
def get_targets(user: UserContext = Depends(require_admin_user)):
    return get_network_targets()


@router.post("/api/targets")
def create_target(target: TargetModel, user: UserContext = Depends(require_admin_user)):
    success = add_network_target(target.name, target.ip_address)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add target")


@router.delete("/api/targets/{target_id}")
def remove_target(target_id: int, user: UserContext = Depends(require_admin_user)):
    success = delete_network_target(target_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete target")


@router.post("/api/targets/run")
def run_sweep_now(user: UserContext = Depends(require_admin_user)):
    from scheduler import run_network_sweep

    run_network_sweep()
    return {"status": "success"}


@router.get("/api/network/targets")
def net_list_targets(user: UserContext = Depends(require_authenticated_user)):
    return {"targets": get_network_targets()}


@router.post("/api/network/targets")
def net_add_target(
    request: TargetModel, user: UserContext = Depends(require_admin_user)
):
    ok = add_network_target(request.name, request.ip_address)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add target")
    return {"status": "success"}


@router.delete("/api/network/targets/{target_id}")
def net_delete_target(target_id: int, user: UserContext = Depends(require_admin_user)):
    ok = delete_network_target(target_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"status": "success"}


@router.get("/api/network/ping/{target_id}")
def net_ping(target_id: int, user: UserContext = Depends(require_authenticated_user)):
    from scheduler import ping_target

    targets = get_network_targets()
    t = next((x for x in targets if x["id"] == target_id), None)
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    result = ping_target(t["ip_address"])
    return result


@router.post("/api/network/sweep")
def net_sweep(user: UserContext = Depends(require_admin_user)):
    from scheduler import run_network_sweep

    try:
        run_network_sweep()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Analytics ─────────────────────────────────────────────────────────────────


@router.get("/api/analytics/summary")
def analytics_summary(user: UserContext = Depends(require_authenticated_user)):
    try:
        sessions = get_all_sessions()
        if user.role != "admin":
            accessible = set(
                get_accessible_session_ids(username=user.username, is_admin=False)
            )
            sessions = [s for s in sessions if s.get("session_id") in accessible]
        total_messages = 0
        try:
            with engine.connect() as conn:
                if user.role != "admin":
                    total_messages = (
                        conn.execute(
                            text(
                                "SELECT COUNT(*) FROM message_store WHERE session_id = ANY(:ids)"
                            ),
                            {"ids": [s["session_id"] for s in sessions]},
                        ).scalar()
                        or 0
                    )
                else:
                    total_messages = (
                        conn.execute(
                            text("SELECT COUNT(*) FROM message_store")
                        ).scalar()
                        or 0
                    )
        except Exception:
            total_messages = len(sessions) * 5
        rollup_metrics = get_memory_rollup_metrics(
            None if user.role == "admin" else user.username
        )
        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "total_memories": len(get_core_memories()),
            "raw_memory_count": int(rollup_metrics.get("raw_memory_count", 0)),
            "summary_node_count": int(rollup_metrics.get("summary_node_count", 0)),
            "avg_injected_memory_chars": float(
                rollup_metrics.get("avg_injected_memory_chars", 0)
            ),
            "avg_injected_memory_tokens": float(
                rollup_metrics.get("avg_injected_memory_tokens", 0)
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Notes CRUD ────────────────────────────────────────────────────────────────


def _ensure_notes_table():
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    owner_username VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Untitled',
                    body TEXT NOT NULL DEFAULT '',
                    tag VARCHAR(64) DEFAULT '',
                    pinned BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not create notes table: %s", exc)


@router.get("/api/notes")
def list_notes(
    q: Optional[str] = Query(default=None),
    user: UserContext = Depends(require_authenticated_user),
):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            if q:
                rows = (
                    conn.execute(
                        text(
                            "SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes "
                            "WHERE owner_username=:u AND (title ILIKE :q OR body ILIKE :q) ORDER BY pinned DESC,updated_at DESC LIMIT 100"
                        ),
                        {"u": user.username, "q": f"%{q}%"},
                    )
                    .mappings()
                    .all()
                )
            else:
                rows = (
                    conn.execute(
                        text(
                            "SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes "
                            "WHERE owner_username=:u ORDER BY pinned DESC,updated_at DESC LIMIT 100"
                        ),
                        {"u": user.username},
                    )
                    .mappings()
                    .all()
                )
        return {"notes": [dict(r) for r in rows]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/notes")
def create_note(
    request: NoteCreateRequest, user: UserContext = Depends(require_authenticated_user)
):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "INSERT INTO notes (owner_username,title,body,tag) VALUES (:u,:t,:b,:g) RETURNING id"
                ),
                {
                    "u": user.username,
                    "t": request.title or "Untitled",
                    "b": request.body,
                    "g": request.tag or "",
                },
            ).first()
            conn.commit()
        return {"status": "success", "id": row[0]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/notes/{note_id}")
def get_note(note_id: int, user: UserContext = Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes WHERE id=:id AND owner_username=:u"
                    ),
                    {"id": note_id, "u": user.username},
                )
                .mappings()
                .first()
            )
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/api/notes/{note_id}")
def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    _ensure_notes_table()
    updates = {k: v for k, v in request.dict().items() if v is not None}
    if not updates:
        return {"status": "no_change"}
    parts = [f"{k}=:{k}" for k in updates]
    updates["id"] = note_id
    updates["u"] = user.username
    updates["now"] = datetime.now(timezone.utc).isoformat()
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"UPDATE notes SET {','.join(parts)},updated_at=:now WHERE id=:id AND owner_username=:u"
                ),
                updates,
            )
            conn.commit()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/api/notes/{note_id}")
def delete_note(note_id: int, user: UserContext = Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM notes WHERE id=:id AND owner_username=:u"),
                {"id": note_id, "u": user.username},
            )
            conn.commit()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/notes/{note_id}/pin")
def pin_note(note_id: int, user: UserContext = Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "UPDATE notes SET pinned=NOT pinned,updated_at=NOW() WHERE id=:id AND owner_username=:u RETURNING pinned"
                ),
                {"id": note_id, "u": user.username},
            ).first()
            conn.commit()
        return {"status": "success", "pinned": bool(row[0]) if row else False}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
