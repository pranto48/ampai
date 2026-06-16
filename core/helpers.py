"""Shared helper utilities used across multiple AmpAI routers."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from database import (
    engine,
    get_accessible_session_ids,
    get_config,
    get_session_owner,
    session_exists,
    set_config,
    user_can_access_session,
    _auto_infer_memory_category,
)
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import text

logger = logging.getLogger("ampai")

# ── Config list helpers ───────────────────────────────────────────────────────


def _load_config_list(key: str) -> List[Dict[str, Any]]:
    raw = get_config(key, "[]") or "[]"
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _save_config_list(key: str, value: List[Dict[str, Any]]) -> None:
    set_config(key, json.dumps(value))


def _append_config_item(key: str, item: Dict[str, Any]) -> Dict[str, Any]:
    rows = _load_config_list(key)
    rows.insert(0, item)
    _save_config_list(key, rows[:500])
    return item


# ── Workspace helpers ─────────────────────────────────────────────────────────


def _workspace_store() -> List[Dict[str, Any]]:
    return _load_config_list("team_workspaces")


def _save_workspace_store(rows: List[Dict[str, Any]]) -> None:
    _save_config_list("team_workspaces", rows[:300])


def _can_manage_workspace(user: Any, workspace: Dict[str, Any]) -> bool:
    if user.role == "admin":
        return True
    for member in workspace.get("members", []):
        if member.get("username") == user.username and member.get("role") in {
            "owner",
            "admin",
        }:
            return True
    return False


# ── Memory helpers ────────────────────────────────────────────────────────────


def _get_memory_policy(username: str) -> Dict[str, Any]:
    key = f"memory_policy_{username}"
    raw = get_config(key, "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {
        "auto_capture_enabled": True,
        "require_approval": False,
        "pii_strict_mode": False,
        "retention_days": 365,
        "allowed_categories": [],
    }


def _create_memory_candidate(
    username: str, session_id: str, text: str, confidence: float = 0.5
) -> Dict[str, Any]:
    candidate = {
        "id": str(uuid.uuid4()),
        "username": username,
        "session_id": session_id,
        "candidate_text": (text or "").strip()[:1000],
        "category": _auto_infer_memory_category(text),
        "confidence": round(float(confidence), 2),
        "status": "pending",
        "edited_text": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": "",
    }
    return _append_config_item("memory_inbox_candidates", candidate)


# ── Session access helpers ────────────────────────────────────────────────────


def _can_access_session(session_id: str, current_user: Any) -> bool:
    if current_user.role == "admin":
        return True
    return session_id in get_accessible_session_ids(
        username=current_user.username, is_admin=False
    )


def _enforce_session_access_or_403(session_id: str, current_user: Any) -> None:
    if user_can_access_session(session_id, current_user.username, current_user.role):
        return
    if session_exists(session_id):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: you do not have permission to access this session",
        )
    raise HTTPException(status_code=404, detail="Session not found")


def _ensure_session_owner_for_user(session_id: str, current_user: Any) -> None:
    from database import set_session_owner

    if current_user.role == "admin":
        return
    if get_session_owner(session_id):
        return
    set_session_owner(
        session_id=session_id,
        owner_username=current_user.username,
        visibility="private",
    )


# ── Session suggestion helpers ────────────────────────────────────────────────


def _ensure_task_suggestion_column() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS task_suggestions TEXT"
                )
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to ensure task_suggestions column")


def _load_session_suggestions(session_id: str) -> List[Dict]:
    _ensure_task_suggestion_column()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT task_suggestions FROM session_metadata WHERE session_id = :session_id"
                ),
                {"session_id": session_id},
            ).first()
            raw = row[0] if row else None
            parsed = json.loads(raw) if raw else []
            return parsed if isinstance(parsed, list) else []
    except Exception:
        logger.exception("Failed to load suggestions", extra={"session_id": session_id})
        return []


def _save_session_suggestions(session_id: str, suggestions: List[Dict]) -> bool:
    _ensure_task_suggestion_column()
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at, task_suggestions) "
                    "VALUES (:session_id, 'Uncategorized', FALSE, FALSE, NOW()::text, :task_suggestions) "
                    "ON CONFLICT (session_id) DO UPDATE SET "
                    "task_suggestions = EXCLUDED.task_suggestions, updated_at = EXCLUDED.updated_at"
                ),
                {"session_id": session_id, "task_suggestions": json.dumps(suggestions)},
            )
            conn.commit()
        return True
    except Exception:
        logger.exception("Failed to save suggestions", extra={"session_id": session_id})
        return False


def _append_session_suggestions(session_id: str, suggestions: List[Dict]) -> List[Dict]:
    if not suggestions:
        return _load_session_suggestions(session_id)
    existing = _load_session_suggestions(session_id)
    existing_ids = {str(item.get("id")) for item in existing}
    now = datetime.now(timezone.utc).isoformat()
    appended: List[Dict] = []
    for suggestion in suggestions:
        sid = str(suggestion.get("id") or uuid.uuid4())
        if sid in existing_ids:
            continue
        payload = {
            "id": sid,
            "title": (suggestion.get("title") or "").strip()[:180],
            "description": (suggestion.get("description") or "").strip(),
            "priority": (suggestion.get("priority") or "medium").strip().lower(),
            "due_at": suggestion.get("due_at"),
            "source": suggestion.get("source") or "unknown",
            "created_at": now,
            "resolved": False,
            "task_id": None,
            "resolved_at": None,
        }
        existing.append(payload)
        appended.append(payload)
    _save_session_suggestions(session_id, existing)
    return appended


# ── Date helpers ──────────────────────────────────────────────────────────────


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _classify_tier(updated_at_raw: Optional[str]) -> str:
    dt = _parse_iso_dt(updated_at_raw)
    if not dt:
        return "warm"
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = (now - dt).days
    hot_days = int(get_config("tier_hot_days", "30") or "30")
    warm_days = int(get_config("tier_warm_days", "180") or "180")
    if age_days <= hot_days:
        return "hot"
    if age_days <= warm_days:
        return "warm"
    return "cold"


# ── Email / notification helpers ──────────────────────────────────────────────


def send_email(to_email: str, subject: str, body_text: str) -> bool:
    api_key = (get_config("resend_api_key") or "").strip()
    from_email = (get_config("resend_from_email") or "").strip()
    recipient = (to_email or "").strip() or (get_config("notification_email_to") or "").strip()
    if not api_key or not from_email or not recipient:
        return False

    payload = json.dumps(
        {"from": from_email, "to": [recipient], "subject": subject, "text": body_text}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def _send_resend_email(subject: str, body_text: str) -> bool:
    api_key = (get_config("resend_api_key") or "").strip()
    from_email = (get_config("resend_from_email") or "").strip()
    to_email = (get_config("notification_email_to") or "").strip()
    if not api_key or not from_email or not to_email:
        return False

    payload = json.dumps(
        {"from": from_email, "to": [to_email], "subject": subject, "text": body_text}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def _notification_throttle_active(
    username: str, session_id: str, interval_seconds: int
) -> bool:
    if interval_seconds <= 0:
        return False
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = Redis.from_url(redis_url, socket_timeout=2)
        key = f"notify:chat-reply:{username}:{session_id}"
        added = redis_client.set(key, "1", ex=interval_seconds, nx=True)
        return not bool(added)
    except Exception:
        return False


# ── Health checks ─────────────────────────────────────────────────────────────


def _check_db_health() -> dict:
    try:
        if not engine:
            return {"ok": False, "details": "DB engine unavailable"}
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        logger.exception("DB health check failed", exc_info=exc)
        return {"ok": False, "details": str(exc)}


def _check_redis_health() -> dict:
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = Redis.from_url(redis_url, socket_timeout=2)
        redis_client.ping()
        return {"ok": True}
    except Exception as exc:
        logger.exception("Redis health check failed", exc_info=exc)
        return {"ok": False, "details": str(exc)}


# ── Integration credentials ───────────────────────────────────────────────────


def _load_integration_credentials(provider: str) -> Dict[str, str]:
    raw = get_config(f"integration_email_{provider}_credentials", "{}")
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_integration_credentials(provider: str, credentials: Dict[str, str]) -> None:
    set_config(f"integration_email_{provider}_credentials", json.dumps(credentials))


# ── Config bool ───────────────────────────────────────────────────────────────


def _config_bool(key: str, default: bool = False) -> bool:
    raw = (get_config(key, "true" if default else "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _to_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
