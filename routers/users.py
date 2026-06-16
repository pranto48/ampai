"""Users router: notification prefs, memory policy, chat prefs, workspaces."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.deps import UserContext, require_authenticated_user
from core.helpers import (
    _can_manage_workspace,
    _save_workspace_store,
    _workspace_store,
)
from core.models import (
    ChatPreferencesUpdateRequest,
    MemoryPolicyRequest,
    NotificationPreferencesUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceMemberUpdateRequest,
    WorkspaceShareSessionRequest,
    UserProfileUpdateRequest,
)
from database import (
    get_config,
    get_effective_chat_preferences,
    get_effective_notification_preferences,
    set_config,
    upsert_user_chat_preferences,
    upsert_user_memory_policy,
    upsert_user_notification_preferences,
    update_user,
    get_user,
)
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile

router = APIRouter(tags=["users"])


# ── Notification Preferences ──────────────────────────────────────────────────


@router.get("/api/users/me/notification-preferences")
def get_my_notification_preferences(
    current_user: UserContext = Depends(require_authenticated_user),
):
    return get_effective_notification_preferences(current_user.username)


@router.put("/api/users/me/notification-preferences")
def update_my_notification_preferences(
    request: NotificationPreferencesUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    digest_mode = (request.digest_mode or "immediate").strip().lower()
    if digest_mode not in {"immediate", "periodic"}:
        raise HTTPException(
            status_code=400, detail="digest_mode must be immediate or periodic"
        )
    ok = upsert_user_notification_preferences(
        username=current_user.username,
        browser_notify_on_away_replies=bool(request.browser_notify_on_away_replies),
        email_notify_on_away_replies=bool(request.email_notify_on_away_replies),
        minimum_notify_interval_seconds=max(
            0, int(request.minimum_notify_interval_seconds)
        ),
        digest_mode=digest_mode,
        digest_interval_minutes=max(1, int(request.digest_interval_minutes)),
    )
    if not ok:
        raise HTTPException(
            status_code=500, detail="Failed to save notification preferences"
        )
    return {
        "status": "success",
        "preferences": get_effective_notification_preferences(current_user.username),
    }


# ── Memory Policy ─────────────────────────────────────────────────────────────


@router.get("/api/users/me/memory-policy")
def get_my_memory_policy(
    current_user: UserContext = Depends(require_authenticated_user),
):
    from core.helpers import _get_memory_policy

    return _get_memory_policy(current_user.username)


@router.put("/api/users/me/memory-policy")
def update_my_memory_policy(
    request: MemoryPolicyRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    payload = {
        "auto_capture_enabled": bool(request.auto_capture_enabled),
        "require_approval": bool(request.require_approval),
        "pii_strict_mode": bool(request.pii_strict_mode),
        "retention_days": max(1, int(request.retention_days)),
        "allowed_categories": [
            c.strip() for c in (request.allowed_categories or []) if c and c.strip()
        ],
    }
    set_config(f"memory_policy_{current_user.username}", json.dumps(payload))
    return {"status": "success", **payload}


# ── Chat Preferences ──────────────────────────────────────────────────────────


@router.get("/api/users/me/chat-preferences")
def get_my_chat_preferences(
    current_user: UserContext = Depends(require_authenticated_user),
):
    return get_effective_chat_preferences(current_user.username)


@router.put("/api/users/me/chat-preferences")
def update_my_chat_preferences(
    request: ChatPreferencesUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    ok = upsert_user_chat_preferences(
        username=current_user.username,
        low_token_mode=bool(request.low_token_mode),
        retrieval_default_preset=request.retrieval_default_preset,
        retrieval_scope=request.retrieval_scope,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save chat preferences")
    return {
        "status": "success",
        "preferences": get_effective_chat_preferences(current_user.username),
    }


# ── Workspaces ────────────────────────────────────────────────────────────────


@router.get("/api/workspaces")
def list_workspaces(current_user: UserContext = Depends(require_authenticated_user)):
    rows = _workspace_store()
    scoped = []
    for row in rows:
        members = row.get("members", [])
        if current_user.role == "admin" or any(
            m.get("username") == current_user.username for m in members
        ):
            scoped.append(row)
    return {"workspaces": scoped[:200]}


@router.post("/api/workspaces")
def create_workspace(
    request: WorkspaceCreateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    name = (request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    rows = _workspace_store()
    workspace = {
        "id": str(uuid.uuid4()),
        "name": name[:120],
        "description": (request.description or "")[:400],
        "members": [{"username": current_user.username, "role": "owner"}],
        "session_ids": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    for member in request.members or []:
        username = (member.get("username") or "").strip()
        role = (member.get("role") or "viewer").strip().lower()
        if not username or role not in {"owner", "admin", "editor", "viewer"}:
            continue
        if any(m.get("username") == username for m in workspace["members"]):
            continue
        workspace["members"].append({"username": username, "role": role})
    rows.insert(0, workspace)
    _save_workspace_store(rows)
    return {"status": "success", "workspace": workspace}


@router.post("/api/workspaces/{workspace_id}/members/{username}")
def upsert_workspace_member(
    workspace_id: str,
    username: str,
    request: WorkspaceMemberUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    role = (request.role or "").strip().lower()
    if role not in {"owner", "admin", "editor", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    rows = _workspace_store()
    target = None
    for row in rows:
        if row.get("id") == workspace_id:
            target = row
            break
    if not target:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not _can_manage_workspace(current_user, target):
        raise HTTPException(status_code=403, detail="Forbidden")
    clean_username = username.strip()
    members = target.setdefault("members", [])
    existing = next((m for m in members if m.get("username") == clean_username), None)
    if existing:
        existing["role"] = role
    else:
        members.append({"username": clean_username, "role": role})
    _save_workspace_store(rows)
    return {"status": "success", "workspace": target}


@router.delete("/api/workspaces/{workspace_id}/members/{username}")
def remove_workspace_member(
    workspace_id: str,
    username: str,
    current_user: UserContext = Depends(require_authenticated_user),
):
    rows = _workspace_store()
    target = None
    for row in rows:
        if row.get("id") == workspace_id:
            target = row
            break
    if not target:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not _can_manage_workspace(current_user, target):
        raise HTTPException(status_code=403, detail="Forbidden")
    members = target.get("members", [])
    target["members"] = [m for m in members if m.get("username") != username.strip()]
    _save_workspace_store(rows)
    return {"status": "success", "workspace": target}


@router.post("/api/workspaces/{workspace_id}/share-session")
def share_session_to_workspace(
    workspace_id: str,
    request: WorkspaceShareSessionRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    rows = _workspace_store()
    target = None
    for row in rows:
        if row.get("id") == workspace_id:
            target = row
            break
    if not target:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not _can_manage_workspace(current_user, target):
        raise HTTPException(status_code=403, detail="Forbidden")
    session_id = (request.session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    session_ids = target.setdefault("session_ids", [])
    if session_id not in session_ids:
        session_ids.append(session_id)
    _save_workspace_store(rows)
    return {"status": "success", "workspace": target}


# ── User self-profile updates ───────────────────────────────────────────────

from passlib.context import CryptContext
import os
import shutil

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "uploads"
)


@router.patch("/api/users/me")
def update_my_profile(
    request: UserProfileUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user)
):
    email = request.email
    password = request.password
    avatar = request.avatar
    
    password_hash = None
    if password:
        password = password.strip()
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        password_hash = pwd_context.hash(password)

    if email is not None:
        email = email.strip() or None

    success = update_user(
        username=current_user.username,
        password_hash=password_hash,
        email=email,
        avatar=avatar
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update profile or nothing changed")
    
    return {"status": "success", "user": get_user(current_user.username)}


@router.post("/api/users/me/avatar")
def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(require_authenticated_user)
):
    os.makedirs(os.path.join(UPLOAD_DIR, "avatars"), exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"avatar_{current_user.username}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, "avatars", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    avatar_url = f"/uploads/avatars/{filename}"
    update_user(username=current_user.username, avatar=avatar_url)
    return {"status": "success", "avatar_url": avatar_url}
