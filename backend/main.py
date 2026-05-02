from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import hashlib
import json
import os
import base64
import json
import sqlite3
import tempfile
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
import shutil
import uuid
import urllib.parse
import urllib.request
import time
import re
import threading
import zipfile
from queue import Queue, Empty
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from zoneinfo import ZoneInfo

from auth import bootstrap_default_admin
from agent import chat_with_agent, get_llm, get_redis_history
from memory_indexer import MemoryIndexer
from database import (
    add_core_memory,
    add_network_target,
    create_task,
    delete_core_memory,
    delete_network_target,
    delete_session_metadata,
    delete_task,
    get_all_configs,
    get_all_sessions,
    get_config,
    get_core_memories,
    get_memory_candidate_by_id,
    get_network_targets,
    get_duplicate_message_counts,
    get_or_create_telegram_user,
    get_user,
    list_users as db_list_users,
    create_user as db_create_user,
    update_user as db_update_user,
    delete_user as db_delete_user,
    ensure_default_users,
    add_media_asset,
    list_media_assets,
    create_memory_group,
    add_user_to_memory_group,
    share_session_to_group,
    get_memory_group_members,
    get_memory_group_sessions,
    remove_user_from_memory_group,
    unshare_session_from_group,
    memory_group_membership_exists,
    memory_group_session_share_exists,
    session_exists,
    memory_group_exists,
    list_memory_groups_for_user,
    list_shared_sessions_for_user,
    get_session_owner,
    session_exists,
    set_session_owner,
    user_can_access_session,
    export_all_sessions_for_backup,
    ensure_session_owner,
    find_report_matches,
    build_session_report_card,
    get_accessible_session_ids,
    list_chat_messages,
    get_sql_chat_history,
    list_tasks,
    list_personas,
    migrate_app_config_encryption,
    set_config,
    set_session_archived,
    set_session_category,
    set_session_pinned,
    touch_session,
    touch_session_updated_at,
    update_memory_candidate_status,
    update_task,
    log_audit_event,
    apply_retention_policy,
    upsert_session_insight,
    get_session_insight,
    list_audit_events,
    get_memory_analytics,
    get_effective_notification_preferences,
    get_effective_memory_policy,
    get_effective_chat_preferences,
    list_backup_profiles,
    create_backup_profile,
    update_backup_profile,
    delete_backup_profile,
    get_backup_profile,
    create_backup_job,
    update_backup_job,
    list_backup_jobs,
    get_backup_job,
    get_backup_verification_kpis,
    create_restore_job,
    update_restore_job,
    list_restore_jobs,
    lookup_username_by_telegram_user_id,
    get_restore_job,
    upsert_user_notification_preferences,
    upsert_user_memory_policy,
    upsert_user_chat_preferences,
    enqueue_pending_reply_notification,
    create_persona,
    update_persona,
    delete_persona,
    get_memory_rollup_metrics,
    engine,
)
from memory_persistence import memory_persistence_manager
from integrations.telegram_api import get_me, set_webhook, delete_webhook, send_message
from integrations.gmail_api import (
    fetch_todays_messages as fetch_gmail_todays_messages,
    refresh_access_token as refresh_gmail_access_token,
)
from agent import chat_with_agent, get_redis_history
from scheduler import start_scheduler, run_network_sweep
from backup_helpers import (
    build_backup_payload,
    test_ftp_connection,
    test_smb_connection,
    write_backup_ftp,
    write_backup_local,
    write_backup_smb,
)
from langchain_community.chat_message_histories import SQLChatMessageHistory
# NOTE:
# This file provides the active auth endpoints used by the frontend app.
# We intentionally do not include auth.py routers to avoid duplicate/conflicting
# /api/auth and /api/admin/users route registrations.

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = logging.getLogger("ampai")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

USER_TOKEN = os.getenv("AMPAI_USER_TOKEN", "ampai-user")
ADMIN_TOKEN = os.getenv("AMPAI_ADMIN_TOKEN", "ampai-admin")
INSIGHT_QUEUE: "Queue[str]" = Queue(maxsize=1000)
BACKUP_JOB_QUEUE: "Queue[Dict[str, Any]]" = Queue(maxsize=200)
RESTORE_JOB_QUEUE: "Queue[Dict[str, Any]]" = Queue(maxsize=50)
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_CONFIG_KEYS = {
    "openai_api_key", "gemini_api_key", "anthropic_api_key",
    "openrouter_api_key", "anythingllm_api_key", "serpapi_api_key",
    "resend_api_key", "backup_ftp_password", "backup_smb_password",
    "bing_api_key", "generic_api_key",
    "telegram_bot_token", "telegram_webhook_secret",
}
RESTORE_PREFLIGHT_CACHE: Dict[str, Dict[str, Any]] = {}
RESTORE_PREFLIGHT_TTL_SECONDS = 15 * 60
RESTORE_SCHEMA_VERSION = "1.1"


class Attachment(BaseModel):
    filename: str
    url: str
    type: str
    extracted_text: Optional[str] = None


class TargetModel(BaseModel):
    name: str
    ip_address: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_type: str = "ollama"
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    memory_mode: str = "indexed"
    memory_top_k: int = 5
    memory_recency_bias: float = 0.0
    memory_category_filter: Optional[str] = ""
    persona_id: Optional[str] = None
    use_web_search: bool = False
    attachments: List[Attachment] = []
    memory_top_k: Optional[int] = None
    recency_bias: Optional[float] = None
    category_filter: Optional[str] = None
    chat_output_mode: Optional[str] = None


class MemoryInboxUpdateRequest(BaseModel):
    status: str
    edited_text: Optional[str] = ""


class TelegramIntegrationSaveRequest(BaseModel):
    bot_token: str = ""
    webhook_url: str = ""
    secret_token: Optional[str] = None
    enabled: bool = False


def _mask_telegram_token(token: str) -> str:
    normalized = (token or "").strip()
    if not normalized:
        return ""
    if len(normalized) <= 8:
        return "****"
    return f"{normalized[:4]}...{normalized[-4:]}"


def _telegram_api_call(method: str, bot_token: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    token = (bot_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is not configured")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            parsed = json.loads((resp.read() or b"{}").decode("utf-8"))
    except Exception:
        logger.exception("telegram api call failed: method=%s token=%s", method, _mask_telegram_token(token))
        raise
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Invalid Telegram API response")
    return parsed


class MemoryPolicyRequest(BaseModel):
    auto_capture_enabled: bool = True
    require_approval: bool = True
    pii_strict_mode: bool = True
    retention_days: int = 365
    allowed_categories: List[str] = []


class ChatPreferencesUpdateRequest(BaseModel):
    low_token_mode: bool = False


class PersonaCreateRequest(BaseModel):
    name: str
    system_prompt: str
    tags: List[str] = []
    is_default: bool = False


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    tags: Optional[List[str]] = None
    is_default: Optional[bool] = None


class MemoryInboxUpdateRequest(BaseModel):
    status: str
    edited_text: Optional[str] = ""


class MemoryPolicyRequest(BaseModel):
    auto_capture_enabled: bool = True
    require_approval: bool = True
    pii_strict_mode: bool = True
    retention_days: int = 365
    allowed_categories: List[str] = []


class PersonaCreateRequest(BaseModel):
    name: str
    system_prompt: str
    tags: List[str] = []
    is_default: bool = False


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    tags: Optional[List[str]] = None
    is_default: Optional[bool] = None


class WorkspaceCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    members: List[Dict[str, str]] = []


class WorkspaceMemberUpdateRequest(BaseModel):
    role: str


class WorkspaceShareSessionRequest(BaseModel):
    session_id: str


class CategoryRequest(BaseModel):
    category: str


class SessionFlagsRequest(BaseModel):
    value: bool


class ImportMessage(BaseModel):
    type: str
    content: str


class ImportRequest(BaseModel):
    session_id: str
    category: str
    messages: List[ImportMessage]


class ConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]

class OrphanAdoptionRunRequest(BaseModel):
    force: bool = False


class MemoryExplorerQuery(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = ""
    owner_scope: Optional[str] = "mine"  # mine|shared|all
    date_from: Optional[str] = ""
    date_to: Optional[str] = ""
    limit: int = 50
    offset: int = 0


class MemoryInboxUpdateRequest(BaseModel):
    status: str
    edited_text: Optional[str] = None


class AdminPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class AdminUserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class AdminUserUpdateRequest(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None


class MemoryGroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    members: List[str] = []


class MemoryGroupShareRequest(BaseModel):
    session_id: str


class ChatReplyNotificationRequest(BaseModel):
    session_id: str
    reply_preview: str


class NotificationPreferencesUpdateRequest(BaseModel):
    browser_notify_on_away_replies: bool = True
    email_notify_on_away_replies: bool = False
    minimum_notify_interval_seconds: int = 300
    digest_mode: str = "immediate"
    digest_interval_minutes: int = 30


class MemoryPolicyUpdateRequest(BaseModel):
    auto_capture_enabled: bool = True
    require_approval: bool = False
    pii_strict_mode: bool = False
    retention_days: int = 365
    allowed_categories: List[str] = []


class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    due_at: Optional[str] = None
    session_id: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[str] = None
    session_id: Optional[str] = None


class SuggestionTaskCreateRequest(BaseModel):
    session_id: Optional[str] = None


class EmailSummaryRequest(BaseModel):
    model_type: str = "ollama"
    api_key: Optional[str] = None
    session_id: str = "system_email_reports"


class EmailSummaryTodayRequest(BaseModel):
    provider: str = "outlook"
    timezone: str = "UTC"
    max_results: int = 50
    model_type: str = "ollama"
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    session_id: str = "system_email_reports"


class BackupRestoreRequest(BaseModel):
    backup_json: str
    dry_run: bool = True


class RestorePreflightRequest(BaseModel):
    backup_json: str


class RestoreStartRequest(BaseModel):
    backup_json: str
    preflight_id: str
    confirm_restore: bool = False


class BackupConnectionTestRequest(BaseModel):
    mode: str
    host: Optional[str] = ""
    user: Optional[str] = ""
    password: Optional[str] = ""
    path: Optional[str] = "/"
    share: Optional[str] = ""
    domain: Optional[str] = ""


class RetentionRunRequest(BaseModel):
    max_age_days: int = 365
    archive_only: bool = True


class BackupProfileDestination(BaseModel):
    type: str = "local"
    path: Optional[str] = ""
    host: Optional[str] = ""
    port: Optional[int] = None
    username: Optional[str] = ""
    credential: Optional[str] = ""
    credential_key_ref: Optional[str] = ""


class BackupProfileSchedule(BaseModel):
    cron: Optional[str] = ""
    interval_minutes: Optional[int] = None


class BackupProfileCreateRequest(BaseModel):
    name: str
    enabled: bool = True
    include_database: bool = True
    include_uploads: bool = False
    include_configs: bool = False
    include_logs: bool = False
    destination: BackupProfileDestination
    schedule: BackupProfileSchedule = BackupProfileSchedule()
    retention_count: Optional[int] = None
    retention_days: Optional[int] = None


class BackupProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    include_database: Optional[bool] = None
    include_uploads: Optional[bool] = None
    include_configs: Optional[bool] = None
    include_logs: Optional[bool] = None
    destination: Optional[BackupProfileDestination] = None
    schedule: Optional[BackupProfileSchedule] = None
    retention_count: Optional[int] = None
    retention_days: Optional[int] = None


class UserLoginResponse(BaseModel):
    username: str
    role: str
    token: str


class UserRegisterRequest(BaseModel):
    username: str
    password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserContext(BaseModel):
    username: str
    role: str


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


def _workspace_store() -> List[Dict[str, Any]]:
    return _load_config_list("team_workspaces")


def _save_workspace_store(rows: List[Dict[str, Any]]) -> None:
    _save_config_list("team_workspaces", rows[:300])


def _can_manage_workspace(user: UserContext, workspace: Dict[str, Any]) -> bool:
    if user.role == "admin":
        return True
    for member in workspace.get("members", []):
        if member.get("username") == user.username and member.get("role") in {"owner", "admin"}:
            return True
    return False


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
        "require_approval": True,
        "pii_strict_mode": True,
        "retention_days": 365,
        "allowed_categories": [],
    }


def _create_memory_candidate(username: str, session_id: str, text: str, confidence: float = 0.5) -> Dict[str, Any]:
    candidate = {
        "id": str(uuid.uuid4()),
        "username": username,
        "session_id": session_id,
        "candidate_text": (text or "").strip()[:1000],
        "confidence": round(float(confidence), 2),
        "status": "pending",
        "edited_text": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": "",
    }
    return _append_config_item("memory_inbox_candidates", candidate)


def _bootstrap_default_users() -> None:
    admin_username = os.getenv("ADMIN_USERNAME") or os.getenv("AMPAI_DEFAULT_ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD") or os.getenv("AMPAI_DEFAULT_ADMIN_PASSWORD", "P@ssw0rd")

    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD", "user123")

    ensure_default_users(
        [
            {
                "username": admin_username,
                "role": "admin",
                "password_hash": pwd_context.hash(admin_password),
            },
            {
                "username": user_username,
                "role": "user",
                "password_hash": pwd_context.hash(user_password),
            },
        ]
    )
    # Enforce configured/default admin credentials on startup for predictable first login.
    db_update_user(admin_username, role="admin", password_hash=pwd_context.hash(admin_password))


def _load_integration_credentials(provider: str) -> Dict[str, str]:
    raw = get_config(f"integration_email_{provider}_credentials", "{}")
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_integration_credentials(provider: str, credentials: Dict[str, str]) -> None:
    set_config(f"integration_email_{provider}_credentials", json.dumps(credentials))


def _send_resend_email(subject: str, body_text: str) -> bool:
    api_key = (get_config("resend_api_key") or "").strip()
    from_email = (get_config("resend_from_email") or "").strip()
    to_email = (get_config("notification_email_to") or "").strip()
    if not api_key or not from_email or not to_email:
        return False

    payload = json.dumps({"from": from_email, "to": [to_email], "subject": subject, "text": body_text}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def _record_backup_status(entry: Dict) -> None:
    raw = get_config("backup_status_history", "[]") or "[]"
    try:
        history = json.loads(raw)
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    history.insert(0, entry)
    set_config("backup_status_history", json.dumps(history[:100]))


def _profile_destination_password(profile: Dict[str, Any]) -> str:
    credential_ref = (profile.get("credential_key_ref") or "").strip()
    if not credential_ref:
        return ""
    return get_config(credential_ref, "") or ""


def _profile_from_legacy_configs() -> Dict[str, Any]:
    mode = (get_config("backup_mode", "local") or "local").strip().lower()
    if mode == "ftp":
        return {
            "id": None,
            "name": "Legacy Backup",
            "destination_type": "ftp",
            "destination_host": get_config("backup_ftp_host", ""),
            "destination_username": get_config("backup_ftp_user", ""),
            "destination_path": get_config("backup_ftp_path", "/"),
            "credential_key_ref": "backup_ftp_password",
        }
    if mode == "smb":
        return {
            "id": None,
            "name": "Legacy Backup",
            "destination_type": "smb",
            "destination_host": get_config("backup_smb_host", ""),
            "destination_username": get_config("backup_smb_user", ""),
            "destination_path": get_config("backup_smb_path", "/"),
            "credential_key_ref": "backup_smb_password",
        }
    return {
        "id": None,
        "name": "Legacy Backup",
        "destination_type": "local",
        "destination_path": get_config("backup_local_path", "/tmp/ampai_backups"),
    }


def _execute_backup(actor: str, trigger: str = "manual", profile: Optional[Dict[str, Any]] = None) -> Dict:
    backup_profile = profile or _profile_from_legacy_configs()
    backup_mode = (backup_profile.get("destination_type") or "local").strip().lower()
    sessions = export_all_sessions_for_backup()
    serialized, manifest = build_backup_payload(sessions=sessions, actor=actor)
    payload_bytes = len(serialized.encode("utf-8"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"ampai_backup_{timestamp}.json"

    try:
        if backup_mode == "ftp":
            host = backup_profile.get("destination_host")
            user = backup_profile.get("destination_username")
            password = _profile_destination_password(backup_profile)
            remote_path = backup_profile.get("destination_path", "/")
            if not host or not user or not password:
                raise ValueError("FTP backup is not fully configured")
            outcome = write_backup_ftp(host, user, password, remote_path, filename, serialized, manifest)
        elif backup_mode == "smb":
            host = backup_profile.get("destination_host")
            share = (backup_profile.get("destination_path") or "").split("/", 1)[0]
            remote_path = ""
            if "/" in (backup_profile.get("destination_path") or ""):
                remote_path = (backup_profile.get("destination_path") or "").split("/", 1)[1]
            user = backup_profile.get("destination_username")
            password = _profile_destination_password(backup_profile)
            domain = ""
            if not host or not share or not user or not password:
                raise ValueError("SMB backup is not fully configured")
            outcome = write_backup_smb(host, share, remote_path, user, password, domain, filename, serialized, manifest)
        else:
            local_dir = backup_profile.get("destination_path") or "/tmp/ampai_backups"
            outcome = write_backup_local(local_dir, filename, serialized, manifest)

        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "success",
                "profile_id": backup_profile.get("id"),
                "profile_name": backup_profile.get("name"),
                "mode": outcome.get("mode", backup_mode),
                "target": outcome.get("path") or outcome.get("file") or "",
                "manifest_checksum": manifest["checksum_sha256"],
                "session_count": manifest["session_count"],
                "message_count": manifest["message_count"],
            }
        )
        return {"status": "success", **outcome, "manifest": manifest, "bytes_written": payload_bytes, "serialized_payload": serialized}
    except Exception as exc:
        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "failed",
                "profile_id": backup_profile.get("id"),
                "profile_name": backup_profile.get("name"),
                "mode": backup_mode,
                "error": str(exc),
            }
        )
        raise


def _run_backup_verification(serialized_payload: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    payload_checksum = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()
    expected_checksum = (manifest.get("checksum_sha256") or "").strip()
    if not expected_checksum or payload_checksum != expected_checksum:
        raise ValueError("checksum verify failed")

    try:
        archive_json = json.loads(serialized_payload)
    except Exception as exc:
        raise ValueError(f"archive open/read test failed: {exc}") from exc
    if not isinstance(archive_json, dict):
        raise ValueError("archive open/read test failed: root is not an object")

    if not isinstance(manifest, dict) or not manifest.get("schema_version") or not manifest.get("timestamp"):
        raise ValueError("manifest parse failed")

    sessions = archive_json.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("restore smoke test failed: sessions is not an array")

    with sqlite3.connect(":memory:") as temp_conn:
        temp_conn.execute("CREATE TABLE restore_sessions (session_id TEXT PRIMARY KEY, message_count INTEGER NOT NULL)")
        for row in sessions[:10]:
            if not isinstance(row, dict):
                continue
            session_id = str(row.get("session_id") or "").strip()
            if not session_id:
                continue
            messages = row.get("messages")
            message_count = len(messages) if isinstance(messages, list) else 0
            temp_conn.execute(
                "INSERT OR REPLACE INTO restore_sessions (session_id, message_count) VALUES (?, ?)",
                (session_id, message_count),
            )
        restored_count = int(temp_conn.execute("SELECT COUNT(*) FROM restore_sessions").fetchone()[0] or 0)
        valid_count = int(temp_conn.execute("SELECT COUNT(*) FROM restore_sessions WHERE message_count >= 0").fetchone()[0] or 0)
    if restored_count != valid_count:
        raise ValueError("restore smoke test failed: validation query mismatch")
    return {"ok": True, "restored_sample_rows": restored_count}


def _alert_backup_verification_failure(job_id: int, error_message: str, actor: str) -> None:
    subject = f"AmpAI Backup Verification Failed (job #{job_id})"
    body = "\n".join(
        [
            "Backup verification failed.",
            f"job_id: {job_id}",
            f"actor: {actor}",
            f"time_utc: {datetime.now(timezone.utc).isoformat()}",
            f"error: {error_message}",
        ]
    )
    _send_resend_email(subject, body)


def _enqueue_backup_job(actor: str, trigger: str, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    backup_profile = profile or _profile_from_legacy_configs()
    job_id = create_backup_job(profile_id=backup_profile.get("id"), status="queued")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue backup job")
    try:
        BACKUP_JOB_QUEUE.put_nowait(
            {
                "job_id": job_id,
                "actor": actor,
                "trigger": trigger,
                "profile": backup_profile,
            }
        )
    except Exception as exc:
        update_backup_job(job_id, status="failed", finished_at=datetime.now(timezone.utc), error_message=f"Queue full: {exc}")
        raise HTTPException(status_code=503, detail="Backup queue is full, try again shortly") from exc
    return {"job_id": job_id, "status": "queued"}


def _backup_job_worker() -> None:
    while True:
        try:
            payload = BACKUP_JOB_QUEUE.get(timeout=2)
        except Empty:
            continue
        job_id = int(payload.get("job_id"))
        actor = payload.get("actor", "system")
        trigger = payload.get("trigger", "manual")
        profile = payload.get("profile")
        started_at = datetime.now(timezone.utc)
        update_backup_job(job_id, status="running", started_at=started_at, error_message=None)
        log_audit_event(username=actor, action="admin.backup.run.start", details=f"job_id={job_id} trigger={trigger}")
        try:
            result = _execute_backup(actor=actor, trigger=trigger, profile=profile)
            artifact_path = result.get("path") or result.get("file") or ""
            bytes_written = int(result.get("bytes_written") or 0)
            _run_backup_verification(
                serialized_payload=result.get("serialized_payload", ""),
                manifest=result.get("manifest") or {},
            )
            update_backup_job(
                job_id,
                status="success",
                finished_at=datetime.now(timezone.utc),
                bytes_written=bytes_written,
                artifact_path=artifact_path,
                verified=True,
                verification_error=None,
                error_message=None,
            )
            log_audit_event(username=actor, action="admin.backup.run.finish", details=f"job_id={job_id} artifact={artifact_path}")
        except Exception as exc:
            update_backup_job(
                job_id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                verified=False,
                verification_error=str(exc),
                error_message=str(exc),
            )
            _alert_backup_verification_failure(job_id=job_id, error_message=str(exc), actor=actor)
            log_audit_event(username=actor, action="admin.backup.run.failure", details=f"job_id={job_id} error={exc}")
        finally:
            BACKUP_JOB_QUEUE.task_done()


def _normalize_restore_archive(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {"manifest": {}, "payload": {}}
    manifest = raw_payload.get("manifest") or raw_payload.get("_manifest") or {}
    payload = raw_payload.get("payload")
    if not isinstance(payload, dict):
        payload = raw_payload
    if not isinstance(manifest, dict):
        manifest = {}
    return {"manifest": manifest, "payload": payload}


def _build_restore_preflight_report(raw_json: str) -> Dict[str, Any]:
    try:
        archive_root = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid backup JSON: {exc}") from exc

    normalized = _normalize_restore_archive(archive_root)
    manifest = normalized["manifest"]
    payload = normalized["payload"]
    payload_text = json.dumps(payload, sort_keys=True)
    payload_checksum = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    expected_checksum = (manifest.get("checksum_sha256") or payload.get("checksum_sha256") or "").strip()
    sessions = payload.get("sessions")
    uploads = payload.get("uploads")
    configs = payload.get("configs")

    checks: List[Dict[str, Any]] = []
    checks.append(
        {
            "name": "archive_checksum",
            "ok": bool(expected_checksum) and expected_checksum == payload_checksum,
            "expected": expected_checksum,
            "actual": payload_checksum,
            "detail": "checksum matches manifest",
        }
    )
    checks.append(
        {
            "name": "manifest_schema_version",
            "ok": (manifest.get("schema_version") or payload.get("schema_version")) == RESTORE_SCHEMA_VERSION,
            "value": manifest.get("schema_version") or payload.get("schema_version"),
            "expected": RESTORE_SCHEMA_VERSION,
        }
    )
    checks.append(
        {
            "name": "manifest_app_version",
            "ok": bool(manifest.get("app_version") or payload.get("app_version")),
            "value": manifest.get("app_version") or payload.get("app_version"),
        }
    )
    checks.append(
        {
            "name": "manifest_timestamp",
            "ok": bool(manifest.get("timestamp") or payload.get("created_at")),
            "value": manifest.get("timestamp") or payload.get("created_at"),
        }
    )
    checks.append(
        {
            "name": "sessions_array",
            "ok": isinstance(sessions, list),
            "detail": "sessions must be an array",
        }
    )
    db_ok = _check_db_health().get("ok", False)
    checks.append({"name": "db_connectivity", "ok": bool(db_ok), "detail": "database ping"})

    archive_bytes = len(raw_json.encode("utf-8"))
    free_bytes = shutil.disk_usage(UPLOAD_DIR).free
    required_bytes = archive_bytes * 2
    checks.append(
        {
            "name": "destination_free_space",
            "ok": free_bytes >= required_bytes,
            "required_bytes": required_bytes,
            "free_bytes": free_bytes,
            "detail": "requires at least 2x archive size",
        }
    )

    ok = all(bool(c.get("ok")) for c in checks)
    return {
        "ok": ok,
        "checks": checks,
        "manifest": {
            "schema_version": manifest.get("schema_version") or payload.get("schema_version"),
            "app_version": manifest.get("app_version") or payload.get("app_version"),
            "timestamp": manifest.get("timestamp") or payload.get("created_at"),
            "checksum_sha256": expected_checksum,
        },
        "summary": {
            "session_count": len(sessions) if isinstance(sessions, list) else 0,
            "upload_count": len(uploads) if isinstance(uploads, list) else 0,
            "config_count": len(configs) if isinstance(configs, dict) else 0,
            "archive_size_bytes": archive_bytes,
            "restore_order": ["database", "uploads", "configs"],
        },
        "payload_checksum_sha256": payload_checksum,
    }


def _store_restore_preflight(report: Dict[str, Any], payload_checksum: str) -> str:
    preflight_id = uuid.uuid4().hex
    RESTORE_PREFLIGHT_CACHE[preflight_id] = {
        "report": report,
        "payload_checksum": payload_checksum,
        "expires_at": time.time() + RESTORE_PREFLIGHT_TTL_SECONDS,
    }
    return preflight_id


def _create_pre_restore_snapshot(actor: str) -> Dict[str, Any]:
    snapshot_root = os.path.join(os.path.dirname(__file__), "..", "data", "restore_snapshots")
    os.makedirs(snapshot_root, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = os.path.join(snapshot_root, f"snapshot_{ts}_{uuid.uuid4().hex[:8]}.json")
    data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": actor,
        "sessions": export_all_sessions_for_backup(),
        "configs": get_all_configs(),
    }
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"snapshot_path": snapshot_path, "bytes_written": os.path.getsize(snapshot_path)}


def _append_restore_log(logs: List[Dict[str, Any]], level: str, step: str, message: str) -> None:
    logs.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "step": step,
            "message": message,
        }
    )


def _restore_job_worker() -> None:
    while True:
        try:
            payload = RESTORE_JOB_QUEUE.get(timeout=2)
        except Empty:
            continue
        job_id = int(payload.get("job_id"))
        actor = payload.get("actor", "system")
        backup_json = payload.get("backup_json", "")
        logs: List[Dict[str, Any]] = []
        snapshot_path = ""
        try:
            update_restore_job(job_id, status="running", current_step="maintenance_on", progress_percent=5, started_at=datetime.now(timezone.utc), error_message=None)
            set_config("maintenance_mode_enabled", "true")
            _append_restore_log(logs, "info", "maintenance_on", "Maintenance mode enabled")
            update_restore_job(job_id, log_lines=logs)

            update_restore_job(job_id, current_step="snapshot", progress_percent=20)
            snapshot = _create_pre_restore_snapshot(actor)
            snapshot_path = snapshot["snapshot_path"]
            _append_restore_log(logs, "info", "snapshot", f"Snapshot captured at {snapshot_path}")
            update_restore_job(job_id, log_lines=logs, snapshot_path=snapshot_path)

            update_restore_job(job_id, current_step="restore_database", progress_percent=40)
            archive = json.loads(backup_json)
            normalized = _normalize_restore_archive(archive)
            restore_payload = normalized["payload"]
            sessions = restore_payload.get("sessions") if isinstance(restore_payload.get("sessions"), list) else []
            summary = {"session_count": 0, "message_count": 0, "invalid_sessions": 0}
            for session in sessions:
                session_id = (session or {}).get("session_id")
                messages = (session or {}).get("messages")
                if not session_id or not isinstance(messages, list):
                    summary["invalid_sessions"] += 1
                    continue
                summary["session_count"] += 1
                summary["message_count"] += len(messages)
                history = get_sql_chat_history(session_id)
                for raw in messages:
                    if not isinstance(raw, str):
                        continue
                    try:
                        msg = json.loads(raw)
                        kind = msg.get("type")
                        content = ((msg.get("data") or {}).get("content")) if isinstance(msg, dict) else None
                        if kind == "human" and isinstance(content, str):
                            history.add_user_message(content)
                        elif kind == "ai" and isinstance(content, str):
                            history.add_ai_message(content)
                    except Exception:
                        continue
                set_session_category(session_id, "Restored Backup")
            _append_restore_log(logs, "info", "restore_database", f"Restored {summary['session_count']} sessions")
            update_restore_job(job_id, log_lines=logs)

            update_restore_job(job_id, current_step="restore_uploads", progress_percent=65)
            uploads = restore_payload.get("uploads")
            if isinstance(uploads, list):
                restored_uploads = 0
                for item in uploads:
                    if not isinstance(item, dict):
                        continue
                    file_name = (item.get("filename") or "").strip()
                    content_b64 = item.get("content_base64")
                    if not file_name or not isinstance(content_b64, str):
                        continue
                    try:
                        file_bytes = base64.b64decode(content_b64.encode("utf-8"))
                        safe_name = f"{uuid.uuid4().hex}_{os.path.basename(file_name)}"
                        output_path = os.path.join(UPLOAD_DIR, safe_name)
                        with open(output_path, "wb") as f:
                            f.write(file_bytes)
                        restored_uploads += 1
                    except Exception:
                        continue
                _append_restore_log(logs, "info", "restore_uploads", f"Restored {restored_uploads} uploaded files")
            else:
                _append_restore_log(logs, "info", "restore_uploads", "No uploads found in archive")
            update_restore_job(job_id, log_lines=logs)

            update_restore_job(job_id, current_step="restore_configs", progress_percent=80)
            configs = restore_payload.get("configs")
            if isinstance(configs, dict):
                updated = 0
                for key, value in sorted(configs.items(), key=lambda kv: kv[0]):
                    if not isinstance(key, str) or key in {"maintenance_mode_enabled"}:
                        continue
                    if value is None:
                        continue
                    set_config(key, str(value))
                    updated += 1
                _append_restore_log(logs, "info", "restore_configs", f"Restored {updated} config keys")
            else:
                _append_restore_log(logs, "info", "restore_configs", "No configs found in archive")

            update_restore_job(
                job_id,
                status="success",
                current_step="completed",
                progress_percent=100,
                finished_at=datetime.now(timezone.utc),
                result_summary=summary,
                log_lines=logs,
                error_message=None,
            )
            log_audit_event(username=actor, action="admin.restore.run.finish", details=f"job_id={job_id} snapshot={snapshot_path}")
        except Exception as exc:
            _append_restore_log(logs, "error", "failed", str(exc))
            update_restore_job(
                job_id,
                status="failed",
                current_step="failed",
                progress_percent=100,
                finished_at=datetime.now(timezone.utc),
                log_lines=logs,
                snapshot_path=snapshot_path,
                error_message=f"{exc}; snapshot preserved at {snapshot_path}" if snapshot_path else str(exc),
            )
            log_audit_event(username=actor, action="admin.restore.run.failure", details=f"job_id={job_id} error={exc}")
        finally:
            set_config("maintenance_mode_enabled", "false")
            RESTORE_JOB_QUEUE.task_done()


def _ensure_valid_email_access_token(provider: str) -> str:
    credentials = _load_integration_credentials(provider)
    if not credentials:
        raise HTTPException(status_code=400, detail=f"{provider} integration is not configured")

    expires_at = int(credentials.get("expires_at") or 0)
    if credentials.get("access_token") and expires_at > int(time.time()) + 60:
        return credentials["access_token"]

    if provider == "gmail":
        refreshed = refresh_gmail_access_token(credentials)
    elif provider == "outlook":
        refreshed = refresh_outlook_access_token(credentials)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    _save_integration_credentials(provider, refreshed)
    return refreshed["access_token"]


def _fetch_todays_email_messages(provider: str, timezone_name: str, max_results: int) -> List[Dict[str, str]]:
    access_token = _ensure_valid_email_access_token(provider)
    if provider == "gmail":
        return fetch_gmail_todays_messages(access_token=access_token, tz=timezone_name, max_results=max_results)
    if provider == "outlook":
        return fetch_outlook_todays_messages(access_token=access_token, tz=timezone_name, max_results=max_results)
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


def _create_access_token(data: Dict[str, str]) -> str:
    payload = data.copy()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload.update({"exp": expiry})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


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


def _notification_throttle_active(username: str, session_id: str, interval_seconds: int) -> bool:
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


def _check_model_provider_health() -> dict:
    provider = (get_all_configs().get("default_model") or "ollama").strip().lower()
    try:
        get_llm(provider)
        return {"ok": True, "provider": provider}
    except Exception as exc:
        return {"ok": False, "provider": provider, "details": str(exc)}


def _check_search_provider_health() -> dict:
    configs = get_all_configs()
    fallback = (configs.get("web_fallback_provider") or "").strip().lower()
    if fallback == "serpapi":
        return {"ok": bool(configs.get("serpapi_api_key")), "provider": "serpapi"}
    if fallback == "bing":
        return {"ok": bool(configs.get("bing_api_key")), "provider": "bing"}
    if fallback == "custom":
        return {"ok": bool(configs.get("custom_web_search_url")), "provider": "custom"}
    return {"ok": True, "provider": "duckduckgo"}


def _get_current_user(access_token: Optional[str] = None) -> UserContext:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(access_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or role not in {"admin", "user"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return UserContext(username=username, role=role)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def get_current_user_from_cookie(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("access_token")
    return _get_current_user(token)


def require_authenticated_user(current_user: UserContext = Depends(get_current_user_from_cookie)) -> UserContext:
    return current_user


def require_admin_user(current_user: UserContext = Depends(get_current_user_from_cookie)) -> UserContext:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@app.post("/api/auth/login", response_model=UserLoginResponse)
def login(payload: UserLoginRequest):
    admin_username = os.getenv("ADMIN_USERNAME") or os.getenv("AMPAI_DEFAULT_ADMIN_USERNAME", "admin")
    configured_admin_password = os.getenv("ADMIN_PASSWORD") or os.getenv("AMPAI_DEFAULT_ADMIN_PASSWORD", "P@ssw0rd")
    fallback_admin_passwords = {
        configured_admin_password,
        os.getenv("AMPAI_DEFAULT_ADMIN_PASSWORD", "P@ssw0rd"),
        "P@ssw0rd",
        "admin123",
    }
    admin_override = payload.username == admin_username and payload.password in fallback_admin_passwords

    user = get_user(payload.username)
    if admin_override:
        # Ensure admin user exists with the supplied password
        if not user:
            db_create_user(username=admin_username, role="admin", password_hash=pwd_context.hash(payload.password))
        db_update_user(admin_username, role="admin", password_hash=pwd_context.hash(payload.password))
        user = get_user(admin_username)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # If admin_override is True, skip further verification — credentials already confirmed above
    if not admin_override:
        stored_hash = user.get("password_hash") or ""
        password_ok = False
        try:
            password_ok = pwd_context.verify(payload.password, stored_hash)
        except Exception:
            # Backward compatibility: legacy SHA256 hashes from older create_user code paths.
            password_ok = hashlib.sha256(payload.password.encode("utf-8")).hexdigest() == stored_hash
            if password_ok:
                db_update_user(user["username"], password_hash=pwd_context.hash(payload.password))
        if not password_ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    effective_username = admin_username if admin_override else user["username"]
    effective_role = "admin" if admin_override else user["role"]
    token = _create_access_token({"sub": effective_username, "role": effective_role})
    body = UserLoginResponse(username=effective_username, role=effective_role, token=token)
    response = Response(content=body.model_dump_json(), media_type="application/json")
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=JWT_EXPIRY_MINUTES * 60,
    )
    return response


@app.post("/api/auth/register")
def register(payload: UserRegisterRequest):
    username = (payload.username or "").strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    if get_user(username):
        raise HTTPException(status_code=400, detail="Username already exists")

    ok = db_create_user(username=username, role="user", password_hash=pwd_context.hash(payload.password))
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to create user")
    return {"status": "success"}


@app.get("/api/auth/whoami")
def whoami(current_user: UserContext = Depends(require_authenticated_user)):
    return {"username": current_user.username, "role": current_user.role}


@app.get("/api/auth/me")
def me(current_user: UserContext = Depends(require_authenticated_user)):
    return {"username": current_user.username, "role": current_user.role}


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({"status": "success"})
    response.delete_cookie("access_token")
    return response

@app.on_event("startup")
def startup_event():
    try:
        _bootstrap_default_users()
    except Exception as exc:
        logger.warning("Skipping default-user bootstrap due to startup error: %s", exc)
    bootstrap_default_admin()
    start_scheduler()
    # Initialize memory persistence manager
    memory_persistence_manager.initialize()
    worker = threading.Thread(target=_insight_worker, daemon=True, name="ampai-insight-worker")
    worker.start()
    backup_worker = threading.Thread(target=_backup_job_worker, daemon=True, name="ampai-backup-worker")
    backup_worker.start()
    restore_worker = threading.Thread(target=_restore_job_worker, daemon=True, name="ampai-restore-worker")
    restore_worker.start()
    _start_telegram_poller_if_enabled()


def _enforce_session_access_or_403(session_id: str, current_user: UserContext) -> None:
    if user_can_access_session(session_id, current_user.username, current_user.role):
        return
    if session_exists(session_id):
        raise HTTPException(status_code=403, detail="Forbidden: you do not have permission to access this session")
    raise HTTPException(status_code=404, detail="Session not found")


def _ensure_session_owner_for_user(session_id: str, current_user: UserContext) -> None:
    if current_user.role == "admin":
        return
    if get_session_owner(session_id):
        return
    set_session_owner(session_id=session_id, owner_username=current_user.username, visibility="private")


def _build_lightweight_insight(session_id: str) -> None:
    messages = list_chat_messages(session_id, dedupe=False)
    if not messages:
        return
    last_ai = ""
    user_words: List[str] = []
    for msg in messages[-50:]:
        content = (msg.get("content") or "").strip()
        if msg.get("type") == "ai" and content:
            last_ai = content
        elif msg.get("type") == "human":
            user_words.extend([w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", content)])

    stop_words = {"the", "and", "for", "with", "that", "this", "from", "have", "about", "your", "you", "are"}
    freq: Dict[str, int] = {}
    for word in user_words:
        if word in stop_words:
            continue
        freq[word] = freq.get(word, 0) + 1
    top_tags = [k for k, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:8]]
    summary = (last_ai or "No AI summary yet.")[:500]
    upsert_session_insight(session_id=session_id, summary=summary, tags=top_tags)


def _insight_worker() -> None:
    while True:
        try:
            session_id = INSIGHT_QUEUE.get(timeout=2)
        except Empty:
            continue
        try:
            _build_lightweight_insight(session_id)
        except Exception:
            logger.exception("Insight worker failed for %s", session_id)
        finally:
            INSIGHT_QUEUE.task_done()


@app.get("/api/personas")
def api_list_personas(user: UserContext = Depends(require_authenticated_user)):
    personas = list_personas(user.username, include_global=True)
    return {"personas": personas}


@app.post("/api/personas")
def api_create_persona(request: PersonaCreateRequest, user: UserContext = Depends(require_authenticated_user)):
    owner_username = None if (request.is_global and user.role == "admin") else user.username
    persona = create_persona(
        username=owner_username,
        name=request.name,
        system_prompt=request.system_prompt,
        tags=request.tags or "",
        is_default=bool(request.is_default),
    )
    if not persona:
        raise HTTPException(status_code=500, detail="Failed to create persona")
    return persona


@app.patch("/api/personas/{persona_id}")
def api_update_persona(persona_id: int, request: PersonaUpdateRequest, user: UserContext = Depends(require_authenticated_user)):
    updated = update_persona(
        persona_id=persona_id,
        actor_username=user.username,
        is_admin=(user.role == "admin"),
        updates=request.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Persona not found or not editable")
    return updated


@app.delete("/api/personas/{persona_id}")
def api_delete_persona(persona_id: int, user: UserContext = Depends(require_authenticated_user)):
    deleted = delete_persona(persona_id=persona_id, actor_username=user.username, is_admin=(user.role == "admin"))
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found or not deletable")
    return {"status": "success"}


def _config_bool(key: str, default: bool = False) -> bool:
    raw = (get_config(key, "true" if default else "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _extract_telegram_update_fields(update: Dict[str, Any]) -> Dict[str, Any]:
    message_obj = update.get("message") or update.get("edited_message") or {}
    from_obj = message_obj.get("from") or {}
    chat_obj = message_obj.get("chat") or {}
    text = (message_obj.get("text") or "").strip()
    return {
        "user_id": from_obj.get("id"),
        "chat_id": chat_obj.get("id"),
        "text": text,
        "is_text_update": bool(text),
    }


def _resolve_telegram_username(user_id: Any) -> str:
    user_id_str = str(user_id or "").strip()
    if not user_id_str:
        return "telegram-bot"
    strategy = (get_config("telegram_user_mapping_mode", "per_user") or "per_user").strip().lower()
    if strategy == "service_account":
        return "telegram-bot"
    return f"telegram-{user_id_str}"


def _send_telegram_message(bot_token: str, chat_id: Any, text: str) -> None:
    if not bot_token or not chat_id or not text:
        return
    text = str(text)[:3500]
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        logger.exception("telegram sendMessage failed: chat_id=%s token=%s", chat_id, _mask_telegram_token(bot_token))
        raise


TELEGRAM_MAX_MESSAGE_CHARS = 4000
TELEGRAM_MAX_WEBHOOK_BYTES = 1024 * 1024  # 1MB
TELEGRAM_RATE_LIMIT_COUNT = 8
TELEGRAM_RATE_LIMIT_WINDOW_SECONDS = 20
TELEGRAM_GENERIC_FAILURE_TEXT = "Sorry, something went wrong while processing your message."
TELEGRAM_POLL_TIMEOUT_SECONDS = 25
TELEGRAM_POLL_SLEEP_SECONDS = 1.5
_telegram_rate_limit_lock = threading.Lock()
_telegram_rate_limit_buckets: Dict[str, List[float]] = {}
_telegram_poller_started = False
_telegram_poller_lock = threading.Lock()
_telegram_offset_lock = threading.Lock()
_telegram_next_update_offset = 0
_telegram_processed_update_ids: set[int] = set()


def _sanitize_telegram_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text).strip()
    if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
        text = text[:TELEGRAM_MAX_MESSAGE_CHARS]
    return text


def _is_rate_limited(user_id: Any, chat_id: Any) -> bool:
    now = time.time()
    key = f"{user_id}:{chat_id}"
    with _telegram_rate_limit_lock:
        bucket = _telegram_rate_limit_buckets.get(key, [])
        bucket = [ts for ts in bucket if now - ts < TELEGRAM_RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= TELEGRAM_RATE_LIMIT_COUNT:
            _telegram_rate_limit_buckets[key] = bucket
            return True
        bucket.append(now)
        _telegram_rate_limit_buckets[key] = bucket
    return False


def _process_telegram_update(update: Dict[str, Any]) -> None:
    fields = _extract_telegram_update_fields(update)
    user_id = fields.get("user_id")
    chat_id = fields.get("chat_id")
    incoming_text = _sanitize_telegram_text(fields.get("text"))
    if not fields.get("is_text_update") or not user_id or not chat_id or not incoming_text:
        return
    if _is_rate_limited(user_id, chat_id):
        return

    session_id = f"tg_{chat_id}_{user_id}"
    resolved_username = _resolve_telegram_username(user_id)
    mapped_username = lookup_username_by_telegram_user_id(user_id)
    username = mapped_username or get_or_create_telegram_user(
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        default_username=resolved_username,
    ) or resolved_username
    if not get_user(username):
        db_create_user(username=username, role="user", password_hash=pwd_context.hash(uuid.uuid4().hex))

    model_type = (get_config("default_model", "ollama") or "ollama").strip().lower()
    policy = _get_memory_policy(username)
    try:
        result = chat_with_agent(
            session_id=session_id,
            message=incoming_text,
            model_type=model_type,
            api_key=None,
            model_name=None,
            memory_mode="indexed",
            memory_top_k=5,
            recency_bias=0.6,
            category_filter="",
            use_web_search=False,
            attachments=[],
            chat_output_mode="normal",
            username=username,
            is_admin=False,
            allowed_memory_categories=policy.get("allowed_categories") or [],
            persist_memory=bool(policy.get("auto_capture_enabled", True)),
            require_memory_approval=bool(policy.get("require_approval", False)),
            pii_strict_mode=bool(policy.get("pii_strict_mode", True)),
        )
        response_text = str((result or {}).get("response") or "").strip()
        if response_text:
            try:
                _send_telegram_message((get_config("telegram_bot_token") or "").strip(), chat_id, response_text)
            except Exception:
                logger.exception("telegram provider send failure")
                log_audit_event(username=username, action="integration.telegram.provider_send_failure", session_id=session_id)
                raise
        ensure_session_owner(session_id, username)
        touch_session(session_id)
        log_audit_event(username=username, action="integration.telegram.message_processed", session_id=session_id)
    except Exception:
        logger.exception("telegram update processing failed")
        try:
            _send_telegram_message((get_config("telegram_bot_token") or "").strip(), chat_id, TELEGRAM_GENERIC_FAILURE_TEXT)
        except Exception:
            logger.exception("telegram provider send failure")
            log_audit_event(username=username, action="integration.telegram.provider_send_failure", session_id=session_id)


def _mark_telegram_update_processed(update_id: Any) -> bool:
    try:
        normalized = int(update_id)
    except (TypeError, ValueError):
        return True
    with _telegram_offset_lock:
        if normalized in _telegram_processed_update_ids:
            return False
        _telegram_processed_update_ids.add(normalized)
        if len(_telegram_processed_update_ids) > 2000:
            floor = max(_telegram_next_update_offset - 2000, 0)
            _telegram_processed_update_ids.difference_update({uid for uid in _telegram_processed_update_ids if uid < floor})
    return True


def _poll_telegram_updates_forever() -> None:
    global _telegram_next_update_offset
    logger.info("Starting Telegram polling worker")
    while True:
        try:
            if not _config_bool("telegram_enabled", default=False) or not _config_bool("telegram_polling_enabled", default=False):
                time.sleep(3)
                continue
            bot_token = (get_config("telegram_bot_token") or "").strip()
            if not bot_token:
                time.sleep(5)
                continue
            with _telegram_offset_lock:
                offset = max(0, int(_telegram_next_update_offset or 0))
            params = urllib.parse.urlencode({
                "timeout": TELEGRAM_POLL_TIMEOUT_SECONDS,
                "offset": offset,
                "allowed_updates": json.dumps(["message", "edited_message", "callback_query"]),
            })
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates?{params}"
            with urllib.request.urlopen(url, timeout=TELEGRAM_POLL_TIMEOUT_SECONDS + 10) as resp:
                payload = json.loads((resp.read() or b"{}").decode("utf-8"))
            if not isinstance(payload, dict) or not payload.get("ok"):
                time.sleep(TELEGRAM_POLL_SLEEP_SECONDS)
                continue
            for update in payload.get("result") or []:
                update_id = update.get("update_id")
                if not _mark_telegram_update_processed(update_id):
                    continue
                if isinstance(update_id, int):
                    with _telegram_offset_lock:
                        _telegram_next_update_offset = max(_telegram_next_update_offset, update_id + 1)
                _process_telegram_update(update or {})
        except Exception:
            logger.exception("telegram polling worker iteration failed")
            time.sleep(TELEGRAM_POLL_SLEEP_SECONDS)


def _start_telegram_poller_if_enabled() -> None:
    global _telegram_poller_started
    if not _config_bool("telegram_polling_enabled", default=False):
        return
    with _telegram_poller_lock:
        if _telegram_poller_started:
            return
        worker = threading.Thread(target=_poll_telegram_updates_forever, daemon=True, name="ampai-telegram-poller")
        worker.start()
        _telegram_poller_started = True




@app.get("/api/admin/integrations/telegram/status")
def admin_telegram_status(current_user: UserContext = Depends(require_admin_user)):
    bot_token = (get_config("telegram_bot_token") or "").strip()
    webhook_url = (get_config("telegram_webhook_url") or "").strip()
    enabled = _config_bool("telegram_enabled", default=False)
    log_audit_event(username=current_user.username, action="integration.telegram.admin_status")
    return {
        "ok": True,
        "enabled": enabled,
        "webhook_url": webhook_url,
        "token_configured": bool(bot_token),
        "token_masked": _mask_telegram_token(bot_token),
        "secret_configured": bool((get_config("telegram_webhook_secret") or "").strip()),
    }


@app.post("/api/admin/integrations/telegram/save")
def admin_telegram_save(request: TelegramIntegrationSaveRequest, current_user: UserContext = Depends(require_admin_user)):
    set_config("telegram_bot_token", request.bot_token or "")
    set_config("telegram_webhook_url", (request.webhook_url or "").strip())
    set_config("telegram_webhook_secret", (request.secret_token or "").strip())
    set_config("telegram_enabled", "true" if request.enabled else "false")
    log_audit_event(username=current_user.username, action="integration.telegram.admin_save")
    return {
        "ok": True,
        "enabled": bool(request.enabled),
        "webhook_url": (request.webhook_url or "").strip(),
        "token_configured": bool((request.bot_token or "").strip()),
        "token_masked": _mask_telegram_token(request.bot_token or ""),
    }


@app.post("/api/admin/integrations/telegram/test")
def admin_telegram_test(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    try:
        payload = get_me(token)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(status_code=502, detail=f"Telegram getMe failed: {detail or exc.reason}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Telegram getMe failed") from exc
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=str(payload.get("description") or "Telegram getMe failed"))
    result = payload.get("result") or {}
    log_audit_event(username=current_user.username, action="integration.telegram.admin_test")
    return {"ok": True, "bot_username": result.get("username"), "bot_id": result.get("id")}


@app.post("/api/admin/integrations/telegram/connect")
def admin_telegram_connect(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    webhook_url = (get_config("telegram_webhook_url") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Telegram webhook URL is not configured")
    secret_token = (get_config("telegram_webhook_secret") or "").strip()
    try:
        payload = set_webhook(token, webhook_url, secret_token=secret_token or None)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(status_code=502, detail=f"Telegram setWebhook failed: {detail or exc.reason}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Telegram setWebhook failed") from exc
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=str(payload.get("description") or "Telegram setWebhook failed"))
    log_audit_event(username=current_user.username, action="integration.telegram.admin_connect")
    return {"ok": True, "description": payload.get("description", "Webhook connected")}


@app.post("/api/admin/integrations/telegram/disconnect")
def admin_telegram_disconnect(current_user: UserContext = Depends(require_admin_user)):
    token = (get_config("telegram_bot_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")
    try:
        payload = delete_webhook(token)
    except urllib.error.HTTPError as exc:
        detail = (exc.read() or b"").decode("utf-8", errors="ignore")[:500]
        raise HTTPException(status_code=502, detail=f"Telegram deleteWebhook failed: {detail or exc.reason}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Telegram deleteWebhook failed") from exc
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=str(payload.get("description") or "Telegram deleteWebhook failed"))
    log_audit_event(username=current_user.username, action="integration.telegram.admin_disconnect")
    return {"ok": True, "description": payload.get("description", "Webhook disconnected")}

@app.post("/api/integrations/telegram/webhook")
def telegram_webhook(
    payload: Dict[str, Any],
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
):
    if not _config_bool("telegram_enabled", default=False):
        return {"status": "ignored", "reason": "disabled"}
    bot_token = (get_config("telegram_bot_token") or "").strip()
    if not bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token is required")

    expected_secret = (get_config("telegram_webhook_secret") or "").strip()
    if expected_secret and (x_telegram_bot_api_secret_token or "").strip() != expected_secret:
        logger.warning("telegram webhook rejected: invalid secret")
        return {"status": "ok"}

    fields = _extract_telegram_update_fields(payload or {})
    chat_id = fields.get("chat_id")
    incoming_text = _sanitize_telegram_text(fields.get("text"))
    if not fields.get("is_text_update") or not chat_id or not incoming_text:
        return {"status": "ok"}

    session_id = f"tg_{chat_id}"
    username = "telegram-bot"
    model_type = (get_config("default_model", "ollama") or "ollama").strip().lower()

    try:
        result = chat_with_agent(
            session_id=session_id,
            message=incoming_text,
            model_type=model_type,
            api_key=None,
            model_name=None,
            memory_mode="indexed",
            memory_top_k=5,
            recency_bias=0.6,
            category_filter="",
            use_web_search=False,
            attachments=[],
            chat_output_mode="normal",
            username=username,
            is_admin=False,
            allowed_memory_categories=[],
            persist_memory=True,
            require_memory_approval=False,
            pii_strict_mode=True,
        )
        response_text = str((result or {}).get("response") or "").strip()
        if response_text:
            send_message(bot_token, chat_id, response_text)
        ensure_session_owner(session_id, username)
        touch_session(session_id)
        log_audit_event(username=username, action="integration.telegram.webhook_processed", session_id=session_id)
    except Exception:
        logger.exception("telegram webhook processing failed")
        log_audit_event(username=username, action="integration.telegram.webhook.process_failure", session_id=session_id)

    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest, user=Depends(require_authenticated_user)):
    try:
        logger.info("CHAT REQUEST model_type=%s, model_name=%s, memory_mode=%s, user=%s",
                     request.model_type, request.model_name, request.memory_mode, user.username)

        # Auto-resolve model_type: if frontend sends "ollama" but no Ollama is
        # running, prefer the admin-configured default_model or any provider
        # that has a valid API key.
        effective_model_type = (request.model_type or "ollama").strip().lower()
        if effective_model_type == "ollama":
            configured_default = (get_config("default_model") or "").strip().lower()
            if configured_default and configured_default != "ollama":
                effective_model_type = configured_default
                logger.info("Auto-resolved model_type from 'ollama' to configured default '%s'", effective_model_type)
            else:
                # Check if Ollama is reachable; if not, try to find an alternative
                ollama_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
                try:
                    import urllib.request as _ur
                    _ur.urlopen(ollama_url, timeout=2)
                except Exception:
                    # Ollama not reachable — try known providers in priority order
                    provider_keys = [
                        ("openrouter", "openrouter_api_key"),
                        ("openai", "openai_api_key"),
                        ("gemini", "gemini_api_key"),
                        ("anthropic", "anthropic_api_key"),
                        ("generic", "generic_api_key"),
                    ]
                    for prov, key_name in provider_keys:
                        if get_config(key_name):
                            effective_model_type = prov
                            logger.info("Ollama unreachable; auto-resolved model_type to '%s'", prov)
                            break
        request.model_type = effective_model_type

        _ensure_session_owner_for_user(request.session_id, user)
        persona_prompt = ""
        if request.persona_id:
            personas = _load_config_list("personas_library")
            persona = next((p for p in personas if p.get("id") == request.persona_id), None)
            if persona and persona.get("system_prompt"):
                persona_prompt = str(persona.get("system_prompt")).strip()
        message_for_agent = request.message
        if persona_prompt:
            message_for_agent = f"[Persona Instructions]\n{persona_prompt}\n\n[User Message]\n{request.message}"
        effective_chat_prefs = get_effective_chat_preferences(user.username)
        requested_mode = (request.chat_output_mode or "").strip().lower()
        if requested_mode not in {"compact", "normal"}:
            requested_mode = str(effective_chat_prefs.get("chat_output_mode") or "normal").strip().lower()
        if requested_mode not in {"compact", "normal"}:
            requested_mode = "normal"
        low_token_mode = bool(effective_chat_prefs.get("low_token_mode"))
        requested_memory_mode = (request.memory_mode or "").strip().lower()
        if requested_memory_mode not in {"indexed", "full"}:
            requested_memory_mode = "indexed"
        effective_memory_mode = requested_memory_mode if user.role == "admin" else "indexed"
        requested_top_k = request.memory_top_k if request.memory_top_k is not None else 5
        max_top_k = 3 if low_token_mode else 5
        clamped_top_k = max(1, min(max_top_k, int(requested_top_k or 5)))
        raw_recency_bias = request.recency_bias if request.recency_bias is not None else request.memory_recency_bias
        effective_recency_bias = float(raw_recency_bias if raw_recency_bias is not None else 0.6)
        effective_recency_bias = max(0.0, min(1.0, effective_recency_bias))
        category_filter_value = (request.category_filter or request.memory_category_filter or "").strip()
        policy = _get_memory_policy(user.username)
        result = chat_with_agent(
            session_id=request.session_id,
            message=message_for_agent,
            model_type=request.model_type,
            api_key=request.api_key,
            model_name=request.model_name,
            memory_mode=effective_memory_mode,
            memory_top_k=clamped_top_k,
            recency_bias=effective_recency_bias,
            category_filter=category_filter_value,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments],
            chat_output_mode=requested_mode,
            username=user.username,
            is_admin=(user.role == "admin"),
            allowed_memory_categories=policy.get("allowed_categories") or [],
            persist_memory=bool(policy.get("auto_capture_enabled", True)),
            require_memory_approval=bool(policy.get("require_approval", False)),
            pii_strict_mode=bool(policy.get("pii_strict_mode", True)),
        )
        memory_action = (result.get("memory_action") or "").strip().lower()
        memory_fact = (result.get("memory_fact") or "").strip()
        if memory_action == "pending_approval" and memory_fact:
            _create_memory_candidate(user.username, request.session_id, memory_fact, confidence=0.9)
        elif memory_action == "saved" and memory_fact:
            try:
                add_core_memory(memory_fact)
            except Exception:
                logger.exception("chat saved-memory core write failed")
            try:
                MemoryIndexer(request.model_type).add_fact(memory_fact)
            except Exception:
                logger.exception("chat saved-memory index write failed")

        response_text = str(result.get("response") or "")
        retrieval_meta = result.get("retrieval") or {}
        injected_chars = int(retrieval_meta.get("context_chars") or 0)
        injected_tokens = max(0, injected_chars // 4)
        log_audit_event(
            username=user.username,
            action="memory.read.injected",
            session_id=request.session_id,
            details=f"chars={injected_chars},tokens={injected_tokens},mode={effective_memory_mode}",
        )
        suggestions: List[Dict[str, Any]] = []
        for match in re.finditer(r"\[CREATE_TASK:\s*(.*?)\]", response_text, re.IGNORECASE | re.DOTALL):
            raw = match.group(1)
            fields: Dict[str, str] = {}
            for part in raw.split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    fields[k.strip().lower()] = v.strip()
            title = (fields.get("title") or "").strip()
            if not title:
                continue
            suggestion = {
                "id": str(uuid.uuid4()),
                "username": user.username,
                "session_id": request.session_id,
                "title": title[:200],
                "description": (fields.get("description") or "")[:1000],
                "priority": (fields.get("priority") or "medium").lower(),
                "due_at": fields.get("due") or None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            suggestions.append(suggestion)
        if suggestions:
            all_suggestions = _load_config_list("task_suggestions")
            all_suggestions = suggestions + all_suggestions
            _save_config_list("task_suggestions", all_suggestions[:500])
            result["task_suggestions"] = suggestions
            cleaned = re.sub(r"\[CREATE_TASK:\s*.*?\]", "", response_text, flags=re.IGNORECASE | re.DOTALL).strip()
            result["response"] = cleaned or response_text
        if policy.get("auto_capture_enabled") and policy.get("require_approval"):
            user_msg = (request.message or "").strip()
            if user_msg and re.search(r"\b(remember|preference|my name is|i prefer|always)\b", user_msg, re.IGNORECASE):
                _create_memory_candidate(user.username, request.session_id, user_msg, confidence=0.65)
        ensure_session_owner(request.session_id, user.username)
        touch_session(request.session_id)
        created_suggestions = _append_session_suggestions(request.session_id, result.get("task_suggestions") or [])
        result["task_suggestions"] = created_suggestions
        log_audit_event(username=user.username, action="memory.write.chat", session_id=request.session_id, details=f"model={request.model_type}")
        if created_suggestions:
            log_audit_event(
                username=user.username,
                action="task.suggestion.detected",
                session_id=request.session_id,
                details=f"count={len(created_suggestions)}",
            )
        result["memory_status"] = {
            "memory_action": memory_action or None,
            "memory_fact": memory_fact or None,
        }
        try:
            INSIGHT_QUEUE.put_nowait(request.session_id)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/inbox")
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
    scoped = [r for r in rows if current_user.role == "admin" or r.get("username") == current_user.username]
    status_value = (status or "").strip().lower()
    if status_value and status_value != "all":
        scoped = [r for r in scoped if (r.get("status") or "").lower() == status_value]

    clean_session = (session_id or "").strip()
    if clean_session:
        scoped = [r for r in scoped if (r.get("session_id") or "") == clean_session]

    query_text = (q or "").strip().lower()
    if query_text:
        scoped = [
            r for r in scoped
            if query_text in (r.get("candidate_text") or "").lower()
            or query_text in (r.get("edited_text") or "").lower()
            or query_text in (r.get("session_id") or "").lower()
        ]

    from_dt = _parse_iso_dt(date_from)
    to_dt = _parse_iso_dt(date_to)
    if from_dt:
        scoped = [r for r in scoped if r.get("created_at") and str(r["created_at"]) >= from_dt]
    if to_dt:
        scoped = [r for r in scoped if r.get("created_at") and str(r["created_at"]) <= to_dt]

    scoped = sorted(scoped, key=lambda r: r.get("created_at") or "", reverse=True)
    page = scoped[offset: offset + limit]
    return {
        "items": page,
        "candidates": page,
        "status": status_value or "pending",
        "offset": offset,
        "limit": limit,
        "total": len(scoped),
        "has_more": (offset + limit) < len(scoped),
    }


@app.post("/api/memory/inbox/capture")
def capture_memory_candidate(payload: Dict[str, str], current_user: UserContext = Depends(require_authenticated_user)):
    text = (payload.get("text") or "").strip()
    session_id = (payload.get("session_id") or "").strip() or "manual"
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    item = _create_memory_candidate(current_user.username, session_id, text, confidence=0.8)
    return {"status": "success", "item": item}


@app.patch("/api/memory/inbox/{candidate_id}")
def update_memory_inbox(candidate_id: str, request: MemoryInboxUpdateRequest, current_user: UserContext = Depends(require_authenticated_user)):
    next_status = (request.status or "").strip().lower()
    if next_status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="status must be approved, rejected, or pending")
    rows = _load_config_list("memory_inbox_candidates")
    updated = None
    for row in rows:
        if row.get("id") != candidate_id:
            continue
        if current_user.role != "admin" and row.get("username") != current_user.username:
            raise HTTPException(status_code=403, detail="Forbidden")
        row["status"] = next_status
        row["edited_text"] = (request.edited_text or "").strip()
        row["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        if next_status == "approved":
            approved_text = row["edited_text"] or row.get("candidate_text") or ""
            if approved_text:
                try:
                    add_core_memory(approved_text)
                except Exception:
                    logger.exception("Failed to persist approved memory candidate")
        updated = row
        break
    if not updated:
        raise HTTPException(status_code=404, detail="Candidate not found")
    _save_config_list("memory_inbox_candidates", rows)
    log_audit_event(username=current_user.username, action=f"memory.review.{next_status}", session_id=updated.get("session_id"), details=updated.get("id"))
    return {"status": "success", "item": updated}


@app.delete("/api/memory/inbox/{candidate_id}")
def delete_memory_inbox(candidate_id: str, current_user: UserContext = Depends(require_authenticated_user)):
    rows = _load_config_list("memory_inbox_candidates")
    kept: List[Dict[str, Any]] = []
    removed: Optional[Dict[str, Any]] = None
    for row in rows:
        if str(row.get("id")) != str(candidate_id):
            kept.append(row)
            continue
        if current_user.role != "admin" and row.get("username") != current_user.username:
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


@app.post("/api/notifications/chat-reply")
def notify_chat_reply(request: ChatReplyNotificationRequest, current_user: UserContext = Depends(require_authenticated_user)):
    prefs = get_effective_notification_preferences(current_user.username)
    interval_seconds = int(prefs.get("minimum_notify_interval_seconds") or 0)
    if _notification_throttle_active(current_user.username, request.session_id, interval_seconds):
        return {"status": "throttled"}

    preview = (request.reply_preview or "").strip()
    if len(preview) > 500:
        preview = preview[:500] + "..."

    digest_mode = (prefs.get("digest_mode") or "immediate").strip().lower()
    if digest_mode == "periodic":
        queued = enqueue_pending_reply_notification(current_user.username, request.session_id, preview)
        return {"status": "queued" if queued else "queue_failed"}

    if not bool(prefs.get("email_notify_on_away_replies")):
        return {"status": "email_disabled"}

    sent = _send_resend_email(
        subject=f"AmpAI reply ready for {current_user.username}",
        body_text=f"User: {current_user.username}\nSession: {request.session_id}\n\nReply preview:\n{preview}",
    )
    return {"status": "sent" if sent else "not_sent"}


@app.get("/api/users/me/notification-preferences")
def get_my_notification_preferences(current_user: UserContext = Depends(require_authenticated_user)):
    return get_effective_notification_preferences(current_user.username)


@app.put("/api/users/me/notification-preferences")
def update_my_notification_preferences(
    request: NotificationPreferencesUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    digest_mode = (request.digest_mode or "immediate").strip().lower()
    if digest_mode not in {"immediate", "periodic"}:
        raise HTTPException(status_code=400, detail="digest_mode must be immediate or periodic")

    ok = upsert_user_notification_preferences(
        username=current_user.username,
        browser_notify_on_away_replies=bool(request.browser_notify_on_away_replies),
        email_notify_on_away_replies=bool(request.email_notify_on_away_replies),
        minimum_notify_interval_seconds=max(0, int(request.minimum_notify_interval_seconds)),
        digest_mode=digest_mode,
        digest_interval_minutes=max(1, int(request.digest_interval_minutes)),
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save notification preferences")
    return {"status": "success", "preferences": get_effective_notification_preferences(current_user.username)}


@app.get("/api/users/me/memory-policy")
def get_my_memory_policy(current_user: UserContext = Depends(require_authenticated_user)):
    return _get_memory_policy(current_user.username)


@app.get("/api/users/me/chat-preferences")
def get_my_chat_preferences(current_user: UserContext = Depends(require_authenticated_user)):
    return get_effective_chat_preferences(current_user.username)


@app.put("/api/users/me/chat-preferences")
def update_my_chat_preferences(
    request: ChatPreferencesUpdateRequest,
    current_user: UserContext = Depends(require_authenticated_user),
):
    ok = upsert_user_chat_preferences(
        username=current_user.username,
        low_token_mode=bool(request.low_token_mode),
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save chat preferences")
    return {"status": "success", "preferences": get_effective_chat_preferences(current_user.username)}


@app.put("/api/users/me/memory-policy")
def update_my_memory_policy(request: MemoryPolicyRequest, current_user: UserContext = Depends(require_authenticated_user)):
    payload = {
        "auto_capture_enabled": bool(request.auto_capture_enabled),
        "require_approval": bool(request.require_approval),
        "pii_strict_mode": bool(request.pii_strict_mode),
        "retention_days": max(1, int(request.retention_days)),
        "allowed_categories": [c.strip() for c in (request.allowed_categories or []) if c and c.strip()],
    }
    set_config(f"memory_policy_{current_user.username}", json.dumps(payload))
    return {"status": "success", **payload}


@app.get("/api/workspaces")
def list_workspaces(current_user: UserContext = Depends(require_authenticated_user)):
    rows = _workspace_store()
    scoped = []
    for row in rows:
        members = row.get("members", [])
        if current_user.role == "admin" or any(m.get("username") == current_user.username for m in members):
            scoped.append(row)
    return {"workspaces": scoped[:200]}


@app.post("/api/workspaces")
def create_workspace(request: WorkspaceCreateRequest, current_user: UserContext = Depends(require_authenticated_user)):
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


@app.post("/api/workspaces/{workspace_id}/members/{username}")
def upsert_workspace_member(workspace_id: str, username: str, request: WorkspaceMemberUpdateRequest, current_user: UserContext = Depends(require_authenticated_user)):
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


@app.delete("/api/workspaces/{workspace_id}/members/{username}")
def remove_workspace_member(workspace_id: str, username: str, current_user: UserContext = Depends(require_authenticated_user)):
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


@app.post("/api/workspaces/{workspace_id}/share-session")
def share_session_to_workspace(workspace_id: str, request: WorkspaceShareSessionRequest, current_user: UserContext = Depends(require_authenticated_user)):
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


@app.get("/api/daily-brief")
def get_daily_brief(current_user: UserContext = Depends(require_authenticated_user)):
    all_tasks = list_tasks()
    open_tasks = [t for t in all_tasks if (t.get("status") or "todo") != "done"][:10]
    memories = get_core_memories()[:8]
    pending_replies_raw = get_config(f"pending_reply_notifications_{current_user.username}", "[]") or "[]"
    try:
        pending_replies = json.loads(pending_replies_raw)
        if not isinstance(pending_replies, list):
            pending_replies = []
    except Exception:
        pending_replies = []
    candidates = _load_config_list("memory_inbox_candidates")
    pending_candidates = [c for c in candidates if c.get("username") == current_user.username and c.get("status") == "pending"][:8]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "open_tasks": open_tasks,
        "recent_memories": memories,
        "pending_replies": pending_replies[:10],
        "pending_memory_candidates": pending_candidates,
    }


@app.post("/api/integrations/context/pull")
def pull_external_context(payload: Dict[str, Any], current_user: UserContext = Depends(require_authenticated_user)):
    provider = (payload.get("provider") or "email").strip().lower()
    if provider not in {"email", "calendar"}:
        raise HTTPException(status_code=400, detail="provider must be email or calendar")
    summary = ""
    if provider == "email":
        timezone_name = (payload.get("timezone") or "UTC").strip() or "UTC"
        messages = _fetch_todays_email_messages(provider="outlook", timezone_name=timezone_name, max_results=20)
        summary = "\n".join([f"- {(m.get('subject') or '(no subject)')} | {(m.get('from') or '')}" for m in messages[:15]])
    else:
        calendar_feed = (get_config("calendar_feed_url") or "").strip()
        summary = f"Calendar connector configured: {'yes' if calendar_feed else 'no'}; events sync placeholder."
    session_id = (payload.get("session_id") or "external_context").strip()
    created = _create_memory_candidate(current_user.username, session_id, f"[{provider.upper()} CONTEXT]\n{summary}", confidence=0.7)
    return {"status": "success", "provider": provider, "candidate": created}


@app.post("/api/quick-capture")
def quick_capture(payload: Dict[str, str], current_user: UserContext = Depends(require_authenticated_user)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    session_id = (payload.get("session_id") or "quick_capture").strip()
    item = _create_memory_candidate(current_user.username, session_id, text, confidence=0.9)
    return {"status": "success", "item": item}

@app.get("/api/sessions/{session_id}/task-suggestions")
def list_session_task_suggestions(session_id: str, current_user: UserContext = Depends(require_authenticated_user)):
    rows = _load_config_list("task_suggestions")
    scoped = [
        r for r in rows
        if r.get("session_id") == session_id and (current_user.role == "admin" or r.get("username") == current_user.username)
    ]
    return {"suggestions": scoped[:200]}


@app.post("/api/tasks/from-suggestion/{suggestion_id}")
def create_task_from_suggestion(suggestion_id: str, current_user: UserContext = Depends(require_authenticated_user)):
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


@app.get("/api/memory/analytics")
def get_memory_analytics(days: int = 30, current_user: UserContext = Depends(require_authenticated_user)):
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
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00")) if isinstance(raw, str) else None
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
        candidates = [c for c in candidates if c.get("username") == current_user.username]
        suggestions = [s for s in suggestions if s.get("username") == current_user.username]
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
        "task_suggestion_conversion_rate": round((converted_count / total_suggestions), 3) if total_suggestions else 0.0,
    }


@app.post("/api/integrations/email/summary-today")
def summarize_todays_email(request: EmailSummaryTodayRequest, _: UserContext = Depends(require_authenticated_user)):
    provider = request.provider.strip().lower()
    tz_name = request.timezone.strip() or "UTC"
    try:
        ZoneInfo(tz_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz_name}") from exc

    messages = _fetch_todays_email_messages(
        provider=provider,
        timezone_name=tz_name,
        max_results=max(1, min(request.max_results, 100)),
    )

    if not messages:
        return {"status": "success", "summary": "No messages found for today.", "messages_count": 0}

    digest_lines = []
    for idx, msg in enumerate(messages, 1):
        digest_lines.append(
            f"{idx}. From: {msg.get('from', '')}\n"
            f"   Subject: {msg.get('subject', '(No subject)')}\n"
            f"   Date: {msg.get('date', '')}\n"
            f"   Snippet: {msg.get('snippet', '')}"
        )

    date_label = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
    prompt = (
        f"Summarize my {provider.title()} email inbox for {date_label} ({tz_name}). "
        "Provide: (1) key topics, (2) urgent follow-ups, (3) calendar/time-sensitive items, "
        "(4) a concise executive digest.\n\n"
        "Today's messages:\n"
        + "\n\n".join(digest_lines)
    )

    model_type = request.model_type or get_config("default_model", "ollama")
    result = chat_with_agent(
        session_id=request.session_id,
        message=prompt,
        model_type=model_type,
        api_key=request.api_key,
        memory_mode="full",
        use_web_search=False,
        attachments=[],
    )
    return {
        "status": "success",
        "provider": provider,
        "timezone": tz_name,
        "messages_count": len(messages),
        "summary": result.get("content", ""),
        "session_id": request.session_id,
    }


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    current_user: UserContext = Depends(require_authenticated_user),
):
    try:
        owner_username = current_user.username
        if session_id:
            _enforce_session_access_or_403(session_id, current_user)
            owner_username = get_session_owner(session_id) or current_user.username
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        extracted_text = None
        if file_ext.lower() == ".pdf":
            try:
                import PyPDF2

                with open(file_path, "rb") as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            except Exception as e:
                logger.warning("PDF parsing error: %s", e)
        elif file_ext.lower() in [".txt", ".csv", ".json", ".md", ".py", ".js", ".html", ".css"]:
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


@app.get("/api/media")
def get_media_assets(
    username: Optional[str] = Query(default=None),
    current_user: UserContext = Depends(require_authenticated_user),
):
    if current_user.role != "admin":
        username = current_user.username
    return {"media": list_media_assets(username=username)}


def _can_access_session(session_id: str, current_user: UserContext) -> bool:
    if current_user.role == "admin":
        return True
    return session_id in get_accessible_session_ids(username=current_user.username, is_admin=False)


def _ensure_task_suggestion_column() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS task_suggestions TEXT"))
            conn.commit()
    except Exception:
        logger.exception("Failed to ensure task_suggestions column")


def _load_session_suggestions(session_id: str) -> List[Dict]:
    _ensure_task_suggestion_column()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT task_suggestions FROM session_metadata WHERE session_id = :session_id"),
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


@app.get("/api/reports/find")
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


@app.get("/api/reports/session-summary/{session_id}")
def get_session_summary_report(session_id: str, current_user: UserContext = Depends(require_authenticated_user)):
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




@app.get("/api/sessions")
def get_sessions(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    archived: Optional[bool] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserContext = Depends(require_authenticated_user),
):
    sessions = get_all_sessions(query=query, category=category, archived=archived)
    if current_user.role != "admin":
        accessible_ids = set(get_accessible_session_ids(username=current_user.username, is_admin=False))
        orphan_session_ids = [s.get("session_id") for s in sessions if s.get("session_id") and s.get("session_id") not in accessible_ids]
        adopted_any = _run_orphan_adoption(
            actor_username=current_user.username,
            orphan_session_ids=orphan_session_ids,
            sessions=sessions,
            explicit=False,
        )
        if adopted_any:
            accessible_ids = set(get_accessible_session_ids(username=current_user.username, is_admin=False))

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
    paged_sessions = sessions[offset: offset + limit]
    for sess in paged_sessions:
        sess["tier"] = _classify_tier(sess.get("updated_at"))
    return {
        "sessions": paged_sessions,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "categories": category_counts,
        "saved_facts": saved_facts,
        "pending_candidates": pending_candidates,
    }


def _session_matches_migration_criteria(session_id: str, session_row: Dict[str, Any]) -> bool:
    # Keep criteria explicit and deterministic so admins can manually run one-time migrations.
    return session_id.startswith("tg_") or bool(session_row.get("archived"))


def _run_orphan_adoption(actor_username: str, orphan_session_ids: List[str], sessions: List[Dict[str, Any]], explicit: bool, force: bool = False) -> bool:
    raw_cutoff = (get_config("auth_orphan_adoption_cutoff_datetime", "") or "").strip()
    cutoff_dt = _parse_iso_dt(raw_cutoff)
    if raw_cutoff and not cutoff_dt:
        logger.warning("Invalid auth_orphan_adoption_cutoff_datetime config value: %s", raw_cutoff)

    adopted_any = False
    adopted_count = 0
    skipped_processed = 0
    skipped_newer = 0
    sessions_map = {(s.get("session_id") or ""): s for s in sessions}
    for sid in orphan_session_ids:
        if not sid:
            continue
        marker_key = f"auth_orphan_adoption_processed:{sid}"
        if get_config(marker_key, "0") == "1" and not force:
            skipped_processed += 1
            continue
        row = sessions_map.get(sid, {})
        updated_dt = _parse_iso_dt(row.get("updated_at"))
        meets_cutoff = bool(cutoff_dt and updated_dt and updated_dt <= cutoff_dt)
        matches_migration = _session_matches_migration_criteria(sid, row)
        if not (meets_cutoff or matches_migration or force):
            skipped_newer += 1
            continue
        if not get_session_owner(sid) and ensure_session_owner(sid, actor_username):
            adopted_any = True
            adopted_count += 1
            log_audit_event(
                username=actor_username,
                action="session.orphan_adoption.adopted",
                session_id=sid,
                details=f"explicit={explicit};cutoff={raw_cutoff or 'none'}",
            )
        set_config(marker_key, "1")
    if explicit or adopted_count > 0 or skipped_processed > 0 or skipped_newer > 0:
        log_audit_event(
            username=actor_username,
            action="session.orphan_adoption.run",
            details=(
                f"explicit={explicit};force={force};adopted={adopted_count};"
                f"skipped_processed={skipped_processed};skipped_newer={skipped_newer};"
                f"cutoff={raw_cutoff or 'none'}"
            ),
        )
    return adopted_any


@app.post("/api/admin/sessions/orphan-adoption/run")
def admin_run_orphan_adoption(request: OrphanAdoptionRunRequest, user: UserContext = Depends(require_admin_user)):
    already_run = (get_config("auth_orphan_adoption_manual_run_completed", "0") == "1")
    if already_run and not request.force:
        return {"status": "skipped", "reason": "already_completed"}
    sessions = get_all_sessions()
    orphan_session_ids = [s.get("session_id") for s in sessions if s.get("session_id") and not get_session_owner(s.get("session_id"))]
    adopted_any = _run_orphan_adoption(
        actor_username=user.username,
        orphan_session_ids=orphan_session_ids,
        sessions=sessions,
        explicit=True,
        force=request.force,
    )
    set_config("auth_orphan_adoption_manual_run_completed", "1")
    return {"status": "success", "adopted_any": adopted_any, "processed": len(orphan_session_ids)}


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
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


@app.post("/api/memory/explorer")
def memory_explorer(request: MemoryExplorerQuery, current_user: UserContext = Depends(require_authenticated_user)):
    query = (request.query or "").strip()
    category = (request.category or "").strip() or None
    owner_scope = (request.owner_scope or "mine").strip().lower()
    limit = max(1, min(int(request.limit), 200))
    offset = max(0, int(request.offset))
    date_from = _parse_iso_dt(request.date_from)
    date_to = _parse_iso_dt(request.date_to)

    if owner_scope not in {"mine", "shared", "all"}:
        raise HTTPException(status_code=400, detail="owner_scope must be mine, shared, or all")
    if owner_scope == "all" and current_user.role != "admin":
        owner_scope = "mine"

    sessions = get_all_sessions(query=query, category=category, archived=False)
    shared_ids = set(list_shared_sessions_for_user(current_user.username))
    accessible_ids = set(get_accessible_session_ids(username=current_user.username, is_admin=current_user.role == "admin"))

    filtered = []
    for session in sessions:
        session_id = session.get("session_id")
        if not session_id or session_id not in accessible_ids:
            continue
        owner = get_session_owner(session_id) or "unknown"
        is_owned = owner == current_user.username
        is_shared = session_id in shared_ids

        if owner_scope == "mine" and not is_owned:
            continue
        if owner_scope == "shared" and not is_shared:
            continue

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
                "visibility": "shared" if is_shared else ("mine" if is_owned else "other"),
                "tier": _classify_tier(updated_at_raw),
                "insight": get_session_insight(session_id),
            }
        )

    total = len(filtered)
    page = filtered[offset: offset + limit]
    category_counts: Dict[str, int] = {}
    for item in filtered:
        cat = item.get("category") or "Uncategorized"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    memory_rows = _load_config_list("memory_inbox_candidates")
    pending_candidates = [
        row for row in memory_rows
        if (current_user.role == "admin" or row.get("username") == current_user.username)
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


@app.get("/api/history/{session_id}")
def get_history(session_id: str, user=Depends(require_authenticated_user)):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    try:
        _enforce_session_access_or_403(session_id, user)
        messages = list_chat_messages(session_id, dedupe=True)
        log_audit_event(username=user.username, action="memory.read.history", session_id=session_id, details=f"count={len(messages)}")
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@app.get("/api/sessions/{session_id}/task-suggestions")
def get_session_task_suggestions(session_id: str, user=Depends(require_authenticated_user)):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    suggestions = _load_session_suggestions(session_id)
    unresolved = [s for s in suggestions if not bool(s.get("resolved"))]
    return {"session_id": session_id, "suggestions": unresolved}


@app.post("/api/tasks/from-suggestion/{suggestion_id}")
def create_task_from_suggestion(
    suggestion_id: str,
    request: SuggestionTaskCreateRequest,
    user=Depends(require_authenticated_user),
):
    search_sessions = [request.session_id] if request.session_id else [
        s.get("session_id") for s in get_all_sessions() if s.get("session_id")
    ]
    search_sessions = [sid for sid in search_sessions if sid]
    for session_id in search_sessions:
        if not _can_access_session(session_id, user):
            continue
        suggestions = _load_session_suggestions(session_id)
        for idx, item in enumerate(suggestions):
            if str(item.get("id")) != str(suggestion_id):
                continue
            if bool(item.get("resolved")):
                raise HTTPException(status_code=409, detail="Suggestion already resolved")
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


@app.post("/api/sessions/{session_id}/category")
def update_category(session_id: str, request: CategoryRequest, user=Depends(require_authenticated_user)):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    success = set_session_category(session_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category")
    log_audit_event(username=user.username, action="memory.update.category", session_id=session_id, category=request.category)
    return {"status": "success"}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(require_authenticated_user)):
    if not _can_access_session(session_id, user):
        raise HTTPException(status_code=403, detail="Forbidden session")
    try:
        _enforce_session_access_or_403(session_id, user)
        delete_session_metadata(session_id)
        SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL).clear()
        get_redis_history(session_id).clear()
        log_audit_event(username=user.username, action="memory.delete.session", session_id=session_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{session_id}")
def export_session(session_id: str, user=Depends(require_authenticated_user)):
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/import")
def import_session(request: ImportRequest, user=Depends(require_authenticated_user)):
    try:
        ensure_session_owner(request.session_id, user.username)
        history = get_sql_chat_history(request.session_id)
        existing_messages = {(msg["type"], msg["content"]) for msg in list_chat_messages(request.session_id, dedupe=False)}
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/history/duplicates")
def get_history_duplicates(_: UserContext = Depends(require_admin_user)):
    duplicates = get_duplicate_message_counts()
    return {
        "sessions_with_duplicates": len(duplicates),
        "duplicate_messages": sum(duplicates.values()),
        "by_session": duplicates,
    }


@app.get("/api/admin/configs")
def get_admin_configs(user=Depends(require_admin_user)):
    raw_configs = get_all_configs()
    result = {}
    for k, v in raw_configs.items():
        v = v or ""
        # Mask secret keys so they don't leak to the browser
        if v and (k in SECRET_CONFIG_KEYS or "api_key" in k or "password" in k):
            result[k] = (v[:4] + "..." + v[-4:]) if len(v) > 8 else "****"
        else:
            result[k] = v
    return result


@app.post("/api/admin/configs")
def update_admin_configs(request: ConfigUpdateRequest, user=Depends(require_admin_user)):
    saved = []
    skipped = []
    for k, v in request.configs.items():
        if not k:
            continue
        if k == "backup_mode":
            mode = (v or "").strip().lower()
            if mode not in {"local", "ftp", "smb"}:
                raise HTTPException(status_code=400, detail="backup_mode must be local, ftp, or smb")
        # Skip masked values (contain '...') — means the frontend sent back the masked placeholder
        if v and "..." in v:
            skipped.append(k)
            continue
        set_config(k, v or "")
        saved.append(k)
    log_audit_event(username=user.username, action="admin.configs.update", details=f"saved={len(saved)};skipped={len(skipped)}")
    return {"status": "success", "saved": saved, "skipped": skipped}


@app.post("/api/admin/change-password")
def admin_change_password(
    request: AdminPasswordChangeRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    user = get_user(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    if not pwd_context.verify(request.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(request.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    new_hash = pwd_context.hash(request.new_password)
    if not db_update_user(current_user.username, password_hash=new_hash):
        raise HTTPException(status_code=500, detail="Failed to update admin password")
    set_config("admin_password_hash", new_hash)
    return {"status": "success"}


@app.get("/api/admin/users")
def admin_list_users(_: UserContext = Depends(require_admin_user)):
    return {"users": db_list_users()}


@app.post("/api/admin/users")
def admin_create_user(request: AdminUserCreateRequest, _: UserContext = Depends(require_admin_user)):
    username = (request.username or "").strip()
    role = (request.role or "user").strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(request.password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    if get_user(username):
        raise HTTPException(status_code=409, detail="User already exists")
    if not db_create_user(username=username, role=role, password_hash=pwd_context.hash(request.password)):
        raise HTTPException(status_code=500, detail="Failed to create user")
    return {"status": "success"}


@app.patch("/api/admin/users/{username}")
def admin_update_user(username: str, request: AdminUserUpdateRequest, current_user: UserContext = Depends(require_admin_user)):
    username = username.strip()
    existing = get_user(username)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    role = request.role.strip().lower() if request.role is not None else None
    if role is not None and role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    if request.password is not None and len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if existing["username"] == current_user.username and role == "user":
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role")

    password_hash = pwd_context.hash(request.password) if request.password else None
    if not db_update_user(username=username, role=role, password_hash=password_hash):
        raise HTTPException(status_code=500, detail="Failed to update user")
    return {"status": "success"}


@app.delete("/api/admin/users/{username}")
def admin_delete_user(username: str, current_user: UserContext = Depends(require_admin_user)):
    username = username.strip()
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    existing = get_user(username)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    if not db_delete_user(username):
        raise HTTPException(status_code=500, detail="Failed to delete user")
    return {"status": "success"}


@app.post("/api/admin/memory-groups")
def admin_create_memory_group(request: MemoryGroupCreateRequest, current_user: UserContext = Depends(require_admin_user)):
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


@app.get("/api/memory-groups")
def get_memory_groups(current_user: UserContext = Depends(require_authenticated_user)):
    return {"groups": list_memory_groups_for_user(current_user.username)}


@app.post("/api/admin/memory-groups/{group_id}/members/{username}")
def admin_add_group_member(group_id: int, username: str, _: UserContext = Depends(require_admin_user)):
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if memory_group_membership_exists(group_id, clean_username):
        raise HTTPException(status_code=409, detail="User is already a member of this group")
    if not add_user_to_memory_group(group_id, clean_username):
        raise HTTPException(status_code=500, detail="Failed to add member")
    return {"status": "success"}


@app.post("/api/admin/memory-groups/{group_id}/share")
def admin_share_session(group_id: int, request: MemoryGroupShareRequest, _: UserContext = Depends(require_admin_user)):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    session_id = (request.session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    if memory_group_session_share_exists(group_id, session_id):
        raise HTTPException(status_code=409, detail="Session is already shared to this group")
    if not share_session_to_group(group_id, session_id):
        raise HTTPException(status_code=500, detail="Failed to share session")
    return {"status": "success"}


@app.get("/api/admin/memory-groups/{group_id}/members")
def admin_get_group_members(group_id: int, _: UserContext = Depends(require_admin_user)):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    return {"members": get_memory_group_members(group_id)}


@app.get("/api/admin/memory-groups/{group_id}/sessions")
def admin_get_group_sessions(group_id: int, _: UserContext = Depends(require_admin_user)):
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    return {"sessions": get_memory_group_sessions(group_id)}


@app.delete("/api/admin/memory-groups/{group_id}/members/{username}")
def admin_remove_group_member(group_id: int, username: str, _: UserContext = Depends(require_admin_user)):
    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if not remove_user_from_memory_group(group_id, clean_username):
        raise HTTPException(status_code=404, detail="Member not found in group")
    return {"status": "success"}


@app.delete("/api/admin/memory-groups/{group_id}/sessions/{session_id}")
def admin_unshare_group_session(group_id: int, session_id: str, _: UserContext = Depends(require_admin_user)):
    clean_session_id = (session_id or "").strip()
    if not clean_session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not memory_group_exists(group_id):
        raise HTTPException(status_code=404, detail="Memory group not found")
    if not unshare_session_from_group(group_id, clean_session_id):
        raise HTTPException(status_code=404, detail="Session share not found in group")
    return {"status": "success"}


def _profile_row_to_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name", ""),
        "enabled": bool(row.get("enabled")),
        "include_database": bool(row.get("include_database")),
        "include_uploads": bool(row.get("include_uploads")),
        "include_configs": bool(row.get("include_configs")),
        "include_logs": bool(row.get("include_logs")),
        "destination": {
            "type": row.get("destination_type", "local"),
            "path": row.get("destination_path", ""),
            "host": row.get("destination_host", ""),
            "port": row.get("destination_port"),
            "username": row.get("destination_username", ""),
            "credential_key_ref": row.get("credential_key_ref", ""),
            "has_credential": bool(get_config(row.get("credential_key_ref", ""), "")) if row.get("credential_key_ref") else False,
        },
        "schedule": {
            "cron": row.get("schedule_cron", ""),
            "interval_minutes": row.get("schedule_interval_minutes"),
        },
        "retention_count": row.get("retention_count"),
        "retention_days": row.get("retention_days"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_profile_payload(request: BackupProfileCreateRequest | BackupProfileUpdateRequest, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    destination = request.destination
    schedule = request.schedule
    destination_type = (destination.type if destination else (existing or {}).get("destination_type", "local") or "local").strip().lower()
    if destination_type not in {"local", "ftp", "smb"}:
        raise HTTPException(status_code=400, detail="destination.type must be local, ftp, or smb")

    credential_key_ref = (destination.credential_key_ref if destination else "") or (existing or {}).get("credential_key_ref") or ""
    if destination and destination.credential:
        credential_key_ref = credential_key_ref or f"backup_profile_cred_{uuid.uuid4().hex}"
        set_config(credential_key_ref, destination.credential)

    return {
        "name": (request.name if request.name is not None else (existing or {}).get("name") or "").strip(),
        "enabled": bool(request.enabled if request.enabled is not None else (existing or {}).get("enabled", True)),
        "include_database": bool(request.include_database if request.include_database is not None else (existing or {}).get("include_database", True)),
        "include_uploads": bool(request.include_uploads if request.include_uploads is not None else (existing or {}).get("include_uploads", False)),
        "include_configs": bool(request.include_configs if request.include_configs is not None else (existing or {}).get("include_configs", False)),
        "include_logs": bool(request.include_logs if request.include_logs is not None else (existing or {}).get("include_logs", False)),
        "destination_type": destination_type,
        "destination_path": (destination.path if destination else (existing or {}).get("destination_path", "")) or "",
        "destination_host": (destination.host if destination else (existing or {}).get("destination_host", "")) or "",
        "destination_port": destination.port if destination else (existing or {}).get("destination_port"),
        "destination_username": (destination.username if destination else (existing or {}).get("destination_username", "")) or "",
        "credential_key_ref": credential_key_ref,
        "schedule_cron": (schedule.cron if schedule else (existing or {}).get("schedule_cron", "")) or "",
        "schedule_interval_minutes": schedule.interval_minutes if schedule else (existing or {}).get("schedule_interval_minutes"),
        "retention_count": request.retention_count if request.retention_count is not None else (existing or {}).get("retention_count"),
        "retention_days": request.retention_days if request.retention_days is not None else (existing or {}).get("retention_days"),
    }


@app.get("/api/backups/profiles")
def get_backup_profiles(_: UserContext = Depends(require_admin_user)):
    return {"profiles": [_profile_row_to_response(row) for row in list_backup_profiles()]}


@app.post("/api/backups/profiles")
def create_backup_profiles_api(request: BackupProfileCreateRequest, user: UserContext = Depends(require_admin_user)):
    payload = _normalize_profile_payload(request)
    if not payload["name"]:
        raise HTTPException(status_code=400, detail="Profile name is required")
    profile_id = create_backup_profile(payload)
    if not profile_id:
        raise HTTPException(status_code=500, detail="Failed to create backup profile")
    log_audit_event(username=user.username, action="admin.backup_profile.create", details=f"profile_id={profile_id}")
    profile = get_backup_profile(profile_id)
    return {"status": "success", "profile": _profile_row_to_response(profile or {"id": profile_id, **payload})}


@app.patch("/api/backups/profiles/{profile_id}")
def update_backup_profiles_api(profile_id: int, request: BackupProfileUpdateRequest, user: UserContext = Depends(require_admin_user)):
    existing = get_backup_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    payload = _normalize_profile_payload(request, existing=existing)
    if not payload["name"]:
        raise HTTPException(status_code=400, detail="Profile name is required")
    if not update_backup_profile(profile_id, payload):
        raise HTTPException(status_code=500, detail="Failed to update backup profile")
    log_audit_event(username=user.username, action="admin.backup_profile.update", details=f"profile_id={profile_id}")
    updated = get_backup_profile(profile_id)
    return {"status": "success", "profile": _profile_row_to_response(updated or {"id": profile_id, **payload})}


@app.delete("/api/backups/profiles/{profile_id}")
def delete_backup_profiles_api(profile_id: int, user: UserContext = Depends(require_admin_user)):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not delete_backup_profile(profile_id):
        raise HTTPException(status_code=500, detail="Failed to delete backup profile")
    log_audit_event(username=user.username, action="admin.backup_profile.delete", details=f"profile_id={profile_id}")
    return {"status": "success"}


@app.post("/api/backups/profiles/{profile_id}/run")
def run_backup_profile_now(profile_id: int, current_user: UserContext = Depends(require_admin_user)):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not profile.get("enabled"):
        raise HTTPException(status_code=400, detail="Backup profile is disabled")
    return _enqueue_backup_job(actor=current_user.username, trigger="manual-profile", profile=profile)


@app.post("/api/backups/run/{profile_id}")
def run_backup_profile_job(profile_id: int, current_user: UserContext = Depends(require_admin_user)):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not profile.get("enabled"):
        raise HTTPException(status_code=400, detail="Backup profile is disabled")
    return _enqueue_backup_job(actor=current_user.username, trigger="manual-profile", profile=profile)


@app.get("/api/backups/jobs")
def get_backup_jobs(limit: int = Query(default=20), offset: int = Query(default=0), _: UserContext = Depends(require_admin_user)):
    return {"jobs": list_backup_jobs(limit=limit, offset=offset)}


@app.get("/api/backups/kpis")
def get_backup_kpis(_: UserContext = Depends(require_admin_user)):
    return {"kpis": get_backup_verification_kpis()}


@app.get("/api/admin/backup/download-instant")
def backup_download_instant(_: UserContext = Depends(require_admin_user)):
    try:
        from backup_helpers import build_backup_payload
        sessions = export_all_sessions_for_backup()
        serialized, manifest = build_backup_payload(sessions=sessions, actor="admin_download_instant")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"ampai_full_backup_{timestamp}.json"
        return Response(
            content=serialized,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Instant backup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backups/download")
def backup_download(path: str = Query(...), _: UserContext = Depends(require_admin_user)):
    normalized = (path or "").strip()
    if not normalized or not os.path.isabs(normalized):
        raise HTTPException(status_code=400, detail="A valid absolute local path is required")
    if not os.path.isfile(normalized):
        raise HTTPException(status_code=404, detail="Backup artifact not found")
    filename = os.path.basename(normalized) or "backup.json"
    return FileResponse(normalized, media_type="application/json", filename=filename)


@app.get("/api/backups/download-all")
def backup_download_all(_: UserContext = Depends(require_admin_user)):
    local_root = (get_config("backup_local_path", "/tmp/ampai_backups") or "/tmp/ampai_backups").strip()
    if not os.path.isdir(local_root):
        raise HTTPException(status_code=404, detail="Local backup directory not found")
    files = sorted(
        [
            os.path.join(local_root, name)
            for name in os.listdir(local_root)
            if name.endswith(".json") or name.endswith(".manifest.json")
        ]
    )
    if not files:
        raise HTTPException(status_code=404, detail="No local backup artifacts found")
    archive_name = f"ampai_backups_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=os.path.basename(file_path))
    return FileResponse(archive_path, media_type="application/zip", filename=archive_name)


@app.get("/api/backups/jobs/{job_id}")
def get_backup_job_details(job_id: int, _: UserContext = Depends(require_admin_user)):
    job = get_backup_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backup job not found")
    return {"job": job}


@app.post("/api/admin/backup/run")
def run_backup(profile_id: Optional[int] = Query(default=None), current_user: UserContext = Depends(require_admin_user)):
    profile = get_backup_profile(profile_id) if profile_id else None
    if profile_id and not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    return _enqueue_backup_job(actor=current_user.username, trigger="manual", profile=profile)


@app.get("/api/admin/backup/status-history")
def get_backup_status_history(_: UserContext = Depends(require_admin_user)):
    raw = get_config("backup_status_history", "[]") or "[]"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = []
    if not isinstance(parsed, list):
        parsed = []
    return {"history": parsed}


@app.post("/api/admin/backup")
def run_backup_compat(profile_id: Optional[int] = Query(default=None), current_user: UserContext = Depends(require_admin_user)):
    return run_backup(profile_id=profile_id, current_user=current_user)


@app.get("/api/admin/backup/history")
def get_backup_history_compat(user: UserContext = Depends(require_admin_user)):
    return get_backup_status_history(user)


@app.post("/api/admin/backup/test-connection")
def test_backup_connection(request: BackupConnectionTestRequest, _: UserContext = Depends(require_admin_user)):
    mode = (request.mode or "").strip().lower()
    if mode == "ftp":
        ok, detail = test_ftp_connection(
            host=(request.host or "").strip(),
            user=(request.user or "").strip(),
            password=request.password or "",
            remote_path=(request.path or "/").strip(),
        )
    elif mode == "smb":
        ok, detail = test_smb_connection(
            host=(request.host or "").strip(),
            share=(request.share or "").strip(),
            username=(request.user or "").strip(),
            password=request.password or "",
            domain=(request.domain or "").strip(),
        )
    else:
        raise HTTPException(status_code=400, detail="mode must be ftp or smb")
    if not ok:
        raise HTTPException(status_code=400, detail=detail)
    return {"status": "success", "detail": detail}


@app.post("/api/admin/backup/restore")
def restore_backup(request: BackupRestoreRequest, user: UserContext = Depends(require_admin_user)):
    report = _build_restore_preflight_report(request.backup_json)
    if request.dry_run:
        preflight_id = _store_restore_preflight(report, report.get("payload_checksum_sha256", ""))
        return {"status": "success", "phase": "preflight", "preflight_id": preflight_id, "report": report}
    if not report.get("ok"):
        raise HTTPException(status_code=400, detail="Preflight checks failed; run dry-run and fix issues before restore")
    preflight_id = _store_restore_preflight(report, report.get("payload_checksum_sha256", ""))
    job_id = create_restore_job(created_by=user.username, preflight_report=report, status="queued")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue restore job")
    RESTORE_JOB_QUEUE.put_nowait({"job_id": job_id, "actor": user.username, "backup_json": request.backup_json, "preflight_id": preflight_id})
    return {"status": "queued", "job_id": job_id, "preflight_id": preflight_id}


@app.post("/api/restores/preflight")
def restore_preflight(request: RestorePreflightRequest, _: UserContext = Depends(require_admin_user)):
    report = _build_restore_preflight_report(request.backup_json)
    preflight_id = _store_restore_preflight(report, report.get("payload_checksum_sha256", ""))
    return {"status": "success", "preflight_id": preflight_id, "report": report}


@app.post("/api/restores/start")
def restore_start(request: RestoreStartRequest, user: UserContext = Depends(require_admin_user)):
    preflight = RESTORE_PREFLIGHT_CACHE.get(request.preflight_id)
    if not preflight:
        raise HTTPException(status_code=400, detail="Preflight ID not found or expired")
    if preflight.get("expires_at", 0) < time.time():
        RESTORE_PREFLIGHT_CACHE.pop(request.preflight_id, None)
        raise HTTPException(status_code=400, detail="Preflight ID expired; run preflight again")
    if not request.confirm_restore:
        raise HTTPException(status_code=400, detail="confirm_restore must be true")
    report = preflight.get("report") or {}
    if not report.get("ok"):
        raise HTTPException(status_code=400, detail="Preflight checks failed; restore blocked")
    checksum = hashlib.sha256(json.dumps(_normalize_restore_archive(json.loads(request.backup_json))["payload"], sort_keys=True).encode("utf-8")).hexdigest()
    if checksum != preflight.get("payload_checksum"):
        raise HTTPException(status_code=400, detail="Backup payload changed since preflight; re-run preflight")

    job_id = create_restore_job(created_by=user.username, preflight_report=report, status="queued")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue restore job")
    try:
        RESTORE_JOB_QUEUE.put_nowait({"job_id": job_id, "actor": user.username, "backup_json": request.backup_json, "preflight_id": request.preflight_id})
    except Exception as exc:
        update_restore_job(job_id, status="failed", finished_at=datetime.now(timezone.utc), error_message=f"Queue full: {exc}")
        raise HTTPException(status_code=503, detail="Restore queue is full; retry shortly") from exc
    log_audit_event(username=user.username, action="admin.restore.run.start", details=f"job_id={job_id} preflight={request.preflight_id}")
    return {"status": "queued", "job_id": job_id}


@app.get("/api/restores/jobs")
def get_restore_jobs(limit: int = Query(default=20), offset: int = Query(default=0), _: UserContext = Depends(require_admin_user)):
    return {"jobs": list_restore_jobs(limit=limit, offset=offset)}


@app.get("/api/restores/jobs/{job_id}")
def get_restore_job_details(job_id: int, _: UserContext = Depends(require_admin_user)):
    job = get_restore_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Restore job not found")
    return job

@app.post("/api/admin/configs/migrate")
def migrate_admin_configs():
    result = migrate_app_config_encryption()
    return {"status": "success", **result}


@app.post("/api/admin/retention/run")
def run_retention_now(request: RetentionRunRequest, current_user: UserContext = Depends(require_admin_user)):
    result = apply_retention_policy(max_age_days=request.max_age_days, archive_only=bool(request.archive_only))
    log_audit_event(
        username=current_user.username,
        action="governance.retention.run",
        details=f"max_age_days={request.max_age_days};archive_only={request.archive_only};result={result}",
    )
    return {"status": "success", **result}


@app.get("/api/admin/audit/events")
def admin_audit_events(limit: int = 200, _: UserContext = Depends(require_admin_user)):
    return {"events": list_audit_events(limit=limit)}

@app.get("/api/configs/status")
def get_configs_status(user=Depends(require_authenticated_user)):
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
        "notification_default_browser_notify_on_away_replies": configs.get("notification_default_browser_notify_on_away_replies", "true"),
        "notification_default_email_notify_on_away_replies": configs.get("notification_default_email_notify_on_away_replies", configs.get("chat_reply_email_notifications", "false")),
        "notification_default_minimum_notify_interval_seconds": configs.get("notification_default_minimum_notify_interval_seconds", "300"),
        "notification_default_digest_mode": configs.get("notification_default_digest_mode", "immediate"),
        "notification_default_digest_interval_minutes": configs.get("notification_default_digest_interval_minutes", "30"),
    }


def _parse_config_list(raw_value: Optional[str], defaults: List[str]) -> List[str]:
    if not raw_value:
        return defaults
    values = [item.strip() for item in str(raw_value).replace(",", "\n").splitlines()]
    cleaned = [value for value in values if value]
    return cleaned or defaults


@app.get("/api/models/options")
def get_model_options(_: UserContext = Depends(require_authenticated_user)):
    configs = get_all_configs()
    return {
        "providers": [
            {"value": "ollama", "label": "Ollama (Local)"},
            {"value": "generic", "label": "LM Studio / OpenAI-Compatible (Local)"},
            {"value": "anythingllm", "label": "AnythingLLM (Local Workspace)"},
            {"value": "openrouter", "label": "OpenRouter (Free Models)"},
            {"value": "openai", "label": "OpenAI"},
            {"value": "gemini", "label": "Google Gemini"},
            {"value": "anthropic", "label": "Anthropic"},
        ],
        "models": {
            "ollama": _parse_config_list(
                configs.get("ollama_model_list"),
                ["llama3.2", "gemma", "mistral", "qwen2.5"],
            ),
            "generic": _parse_config_list(
                configs.get("generic_model_list"),
                ["local-model", "llama-3.1-8b-instruct", "qwen2.5-7b-instruct"],
            ),
            "anythingllm": _parse_config_list(
                configs.get("anythingllm_workspace_list"),
                ["my-workspace"],
            ),
            "openrouter": _parse_config_list(
                configs.get("openrouter_model_list"),
                [
                    "meta-llama/llama-3.3-8b-instruct:free",
                    "qwen/qwen3-4b:free",
                    "deepseek/deepseek-r1-0528:free",
                ],
            ),
        },
    }


@app.get("/api/admin/core-memories")
def api_get_core_memories(user=Depends(require_admin_user)):
    return {"core_memories": get_core_memories()}


@app.delete("/api/admin/core-memories/{mem_id}")
def api_delete_core_memory(mem_id: int, user=Depends(require_admin_user)):
    success = delete_core_memory(mem_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete core memory")
    return {"status": "success"}


@app.get("/api/targets")
def get_targets(user=Depends(require_admin_user)):
    return get_network_targets()


@app.post("/api/targets")
def create_target(target: TargetModel, user=Depends(require_admin_user)):
    success = add_network_target(target.name, target.ip_address)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add target")


@app.delete("/api/targets/{target_id}")
def remove_target(target_id: int, user=Depends(require_admin_user)):
    success = delete_network_target(target_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete target")


@app.post("/api/targets/run")
def run_sweep_now(user=Depends(require_admin_user)):
    run_network_sweep()
    return {"status": "success"}


@app.post("/api/tasks")
def api_create_task(request: TaskCreateRequest, user=Depends(require_authenticated_user)):
    task_id = create_task(request.title, request.description, request.priority, request.due_at, request.session_id)
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return {"status": "success", "id": task_id}


@app.get("/api/tasks")
def api_list_tasks(status: Optional[str] = None, user=Depends(require_authenticated_user)):
    return {"tasks": list_tasks(status=status)}


@app.patch("/api/tasks/{task_id}")
def api_update_task(task_id: int, request: TaskUpdateRequest, user=Depends(require_authenticated_user)):
    if not update_task(task_id, request.dict()):
        raise HTTPException(status_code=500, detail="Failed to update task")
    return {"status": "success"}


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: int, user=Depends(require_authenticated_user)):
    if not delete_task(task_id):
        raise HTTPException(status_code=500, detail="Failed to delete task")
    return {"status": "success"}


def _decode_subject(raw_subject) -> str:
    if not raw_subject:
        return "(No Subject)"
    parts = decode_header(raw_subject)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(chunk)
    return "".join(out)


@app.post("/api/email/summary/today")
def summarize_today_email(request: EmailSummaryRequest, user=Depends(require_authenticated_user)):
    configs = get_all_configs()
    host = configs.get("imap_host")
    username = configs.get("imap_username")
    password = configs.get("imap_password")
    if not host or not username or not password:
        raise HTTPException(status_code=400, detail="Set imap_host, imap_username, imap_password in admin configs")

    today = datetime.now().strftime("%d-%b-%Y")
    items = []
    try:
        with imaplib.IMAP4_SSL(host) as mail:
            mail.login(username, password)
            mail.select("INBOX")
            status, data = mail.search(None, f'(SINCE "{today}")')
            if status != "OK":
                raise HTTPException(status_code=500, detail="Failed to query mailbox")
            for num in data[0].split()[-50:]:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                frm = msg.get("From", "Unknown")
                subject = _decode_subject(msg.get("Subject", ""))
                date = msg.get("Date", "")
                items.append(f"From: {frm}\nSubject: {subject}\nDate: {date}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email fetch error: {e}")

    if not items:
        return {"summary": "No emails found for today.", "email_count": 0}

    prompt = (
        "Summarize today's emails into: key updates, urgent actions, follow-ups, and decisions.\n\n" +
        "\n\n---\n\n".join(items)
    )
    result = chat_with_agent(
        session_id="system_email_reports",
        message=prompt,
        model_type=request.model_type,
        api_key=request.api_key,
        memory_mode="indexed",
        use_web_search=False,
        attachments=[]
    )
    return {"summary": result.get("response") if isinstance(result, dict) else result, "email_count": len(items)}




@app.get("/", include_in_schema=False)
def root_page():
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>AmpAI</h1><p>Frontend not found.</p>")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/health")
def health(user=Depends(require_admin_user)):
    db_check    = _check_db_health()
    redis_check = _check_redis_health()
    model_check = _check_model_provider_health()
    search_check= _check_search_provider_health()
    from scheduler import get_scheduler_diagnostics
    try:
        sched_check = get_scheduler_diagnostics()
    except Exception:
        sched_check = {"running": False, "jobs": [], "last_run": {}}
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "db":             db_check,
            "redis":          redis_check,
            "model_provider": model_check,
            "search_provider":search_check,
            "scheduler":      sched_check,
        },
    }


def get_latest_mtime(directories):
    latest = 0
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".pyc") or "__pycache__" in root or file.endswith(".db") or file.endswith(".db-journal"):
                    continue
                filepath = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(filepath)
                    if mtime > latest:
                        latest = mtime
                except OSError:
                    pass
    return latest


@app.get("/api/status")
def get_status(user=Depends(require_authenticated_user)):
    backend_path = os.path.dirname(__file__)
    frontend_path = os.path.join(backend_path, "..", "frontend")
    latest_mtime = get_latest_mtime([backend_path, frontend_path])
    return {"latest_mtime": latest_mtime}


# ─────────────────────────────────────────────────────
# TASKS — extra endpoints (create/list already exist)
# ─────────────────────────────────────────────────────
@app.get("/api/tasks")
def list_tasks_api(status: Optional[str] = Query(default=None), user=Depends(require_authenticated_user)):
    tasks = list_tasks(status=status)
    return {"tasks": tasks}


@app.post("/api/tasks")
def create_task_api(request: TaskCreateRequest, user=Depends(require_authenticated_user)):
    task_id = create_task(
        title=request.title,
        description=request.description,
        priority=request.priority,
        due_at=request.due_at,
        session_id=request.session_id,
    )
    if not task_id:
        raise HTTPException(status_code=500, detail="Failed to create task")
    log_audit_event(username=user.username, action="task.create", details=f"id={task_id};title={request.title}")
    return {"status": "success", "id": task_id}


@app.patch("/api/tasks/{task_id}")
def update_task_api(task_id: int, request: TaskUpdateRequest, user=Depends(require_authenticated_user)):
    updates = {k: v for k, v in request.dict().items() if v is not None}
    ok = update_task(task_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or update failed")
    return {"status": "success"}


@app.delete("/api/tasks/{task_id}")
def delete_task_api(task_id: int, user=Depends(require_authenticated_user)):
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}


# ─────────────────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────────────────
class NoteCreateRequest(BaseModel):
    title: str = "Untitled"
    body: str = ""
    tag: Optional[str] = ""


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tag: Optional[str] = None


def _notes_table_ready() -> bool:
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect as sq_inspect
            return sq_inspect(engine).has_table("notes")
    except Exception:
        return False


def _ensure_notes_table():
    try:
        with engine.connect() as conn:
            conn.execute(text("""
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
            """))
            conn.commit()
    except Exception as exc:
        logger.warning("Could not create notes table: %s", exc)


@app.get("/api/notes")
def list_notes(q: Optional[str] = Query(default=None), user=Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            if q:
                rows = conn.execute(
                    text("SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes "
                         "WHERE owner_username=:u AND (title ILIKE :q OR body ILIKE :q) ORDER BY pinned DESC,updated_at DESC LIMIT 100"),
                    {"u": user.username, "q": f"%{q}%"}
                ).mappings().all()
            else:
                rows = conn.execute(
                    text("SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes "
                         "WHERE owner_username=:u ORDER BY pinned DESC,updated_at DESC LIMIT 100"),
                    {"u": user.username}
                ).mappings().all()
        return {"notes": [dict(r) for r in rows]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/notes")
def create_note(request: NoteCreateRequest, user=Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("INSERT INTO notes (owner_username,title,body,tag) VALUES (:u,:t,:b,:g) RETURNING id"),
                {"u": user.username, "t": request.title or "Untitled", "b": request.body, "g": request.tag or ""}
            ).first()
            conn.commit()
        return {"status": "success", "id": row[0]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/notes/{note_id}")
def get_note(note_id: int, user=Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id,title,body,tag,pinned,created_at,updated_at FROM notes WHERE id=:id AND owner_username=:u"),
                {"id": note_id, "u": user.username}
            ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/notes/{note_id}")
def update_note(note_id: int, request: NoteUpdateRequest, user=Depends(require_authenticated_user)):
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
                text(f"UPDATE notes SET {','.join(parts)},updated_at=:now WHERE id=:id AND owner_username=:u"),
                updates
            )
            conn.commit()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int, user=Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM notes WHERE id=:id AND owner_username=:u"), {"id": note_id, "u": user.username})
            conn.commit()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/notes/{note_id}/pin")
def pin_note(note_id: int, user=Depends(require_authenticated_user)):
    _ensure_notes_table()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("UPDATE notes SET pinned=NOT pinned,updated_at=NOW() WHERE id=:id AND owner_username=:u RETURNING pinned"),
                {"id": note_id, "u": user.username}
            ).first()
            conn.commit()
        return {"status": "success", "pinned": bool(row[0]) if row else False}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────
# NETWORK MONITOR — extra endpoints
# ─────────────────────────────────────────────────────
@app.get("/api/network/targets")
def net_list_targets(user=Depends(require_authenticated_user)):
    return {"targets": get_network_targets()}


@app.post("/api/network/targets")
def net_add_target(request: TargetModel, user=Depends(require_admin_user)):
    ok = add_network_target(request.name, request.ip_address)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add target")
    return {"status": "success"}


@app.delete("/api/network/targets/{target_id}")
def net_delete_target(target_id: int, user=Depends(require_admin_user)):
    ok = delete_network_target(target_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"status": "success"}


@app.get("/api/network/ping/{target_id}")
def net_ping(target_id: int, user=Depends(require_authenticated_user)):
    from scheduler import ping_target
    targets = get_network_targets()
    t = next((x for x in targets if x["id"] == target_id), None)
    if not t:
        raise HTTPException(status_code=404, detail="Target not found")
    result = ping_target(t["ip_address"])
    return result


@app.post("/api/network/sweep")
def net_sweep(user=Depends(require_admin_user)):
    try:
        run_network_sweep()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────
@app.get("/api/analytics/summary")
def analytics_summary(user=Depends(require_authenticated_user)):
    try:
        sessions = get_all_sessions()
        if user.role != "admin":
            accessible = set(get_accessible_session_ids(username=user.username, is_admin=False))
            sessions = [s for s in sessions if s.get("session_id") in accessible]
        total_messages = 0
        try:
            with engine.connect() as conn:
                q = text("SELECT COUNT(*) FROM message_store")
                if user.role != "admin":
                    q = text("SELECT COUNT(*) FROM message_store WHERE session_id = ANY(:ids)")
                    total_messages = conn.execute(q, {"ids": [s["session_id"] for s in sessions]}).scalar() or 0
                else:
                    total_messages = conn.execute(q).scalar() or 0
        except Exception:
            total_messages = len(sessions) * 5
        rollup_metrics = get_memory_rollup_metrics(None if user.role == "admin" else user.username)
        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "total_memories": len(get_core_memories()),
            "raw_memory_count": int(rollup_metrics.get("raw_memory_count", 0)),
            "summary_node_count": int(rollup_metrics.get("summary_node_count", 0)),
            "avg_injected_memory_chars": float(rollup_metrics.get("avg_injected_memory_chars", 0)),
            "avg_injected_memory_tokens": float(rollup_metrics.get("avg_injected_memory_tokens", 0)),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _memory_analytics_to_csv(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("section,key,value")
    kpis = payload.get("kpis") or {}
    for key in ["memory_writes_total", "retrieval_hits_total", "stale_memories_count"]:
        lines.append(f"kpi,{key},{kpis.get(key, 0)}")

    lines.append("")
    lines.append("memory_writes_per_day,day,count")
    for row in payload.get("memory_writes_per_day") or []:
        lines.append(f"memory_writes_per_day,{row.get('day','')},{row.get('count',0)}")

    lines.append("")
    lines.append("retrieval_hits_per_day,day,count")
    for row in payload.get("retrieval_hits_per_day") or []:
        lines.append(f"retrieval_hits_per_day,{row.get('day','')},{row.get('count',0)}")

    lines.append("")
    lines.append("top_categories,category,count")
    for row in payload.get("top_categories") or []:
        category = str(row.get("category", "")).replace('"', '""')
        lines.append(f'top_categories,"{category}",{row.get("count",0)}')

    lines.append("")
    lines.append("stale_memories,session_id,category,owner,updated_at,last_retrieval_at")
    for row in payload.get("stale_memories") or []:
        category = str(row.get("category", "")).replace('"', '""')
        owner = str(row.get("owner", "")).replace('"', '""')
        lines.append(
            f'stale_memories,{row.get("session_id","")},"{category}","{owner}",{row.get("updated_at","")},{row.get("last_retrieval_at","") or ""}'
        )
    return "\n".join(lines) + "\n"


@app.get("/api/memory/analytics")
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
        raise HTTPException(status_code=400, detail="owner_scope must be mine, shared, or all")
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
            headers={"Content-Disposition": "attachment; filename=memory-analytics.csv"},
        )
    return payload


# ═══════════════════════════════════════════════════════════
# FULL BACKUP / RESTORE ENDPOINTS
# ═══════════════════════════════════════════════════════════
from full_backup import (
    build_full_backup,
    save_full_backup_to_disk,
    list_full_backups,
    restore_full_backup,
    FULL_BACKUP_DIR,
    SLOT_SIZE_BYTES,
)
import threading as _fb_threading
_fb_lock = _fb_threading.Lock()


class FullRestoreRequest(BaseModel):
    filename: str
    restore_chats: bool = True
    restore_memories: bool = True
    restore_core_memories: bool = True
    restore_users: bool = True
    restore_configs: bool = True
    restore_personas: bool = True
    restore_tasks: bool = True


@app.post("/api/admin/fullbackup/create")
def api_fullbackup_create(user: UserContext = Depends(require_admin_user)):
    """Build a full backup and save it to disk. Returns manifest + file info."""
    if not _fb_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A full backup is already running")
    try:
        bundle = build_full_backup(actor=user.username)
        zip_path = save_full_backup_to_disk(bundle)
        manifest = bundle["manifest"]
        log_audit_event(username=user.username, action="admin.fullbackup.create",
                        details=f"file={os.path.basename(zip_path)}")
        return {
            "ok": True,
            "filename": os.path.basename(zip_path),
            "manifest": manifest,
            "slot_size_bytes": SLOT_SIZE_BYTES,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _fb_lock.release()


@app.get("/api/admin/fullbackup/list")
def api_fullbackup_list(user: UserContext = Depends(require_admin_user)):
    """List all saved full-backup zip files."""
    backups = list_full_backups()
    return {"backups": backups, "total": len(backups)}


@app.get("/api/admin/fullbackup/download/{filename}")
def api_fullbackup_download(filename: str, user: UserContext = Depends(require_admin_user)):
    """Download a saved full-backup zip file."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.delete("/api/admin/fullbackup/{filename}")
def api_fullbackup_delete(filename: str, user: UserContext = Depends(require_admin_user)):
    """Delete a saved full-backup zip file."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    os.remove(zip_path)
    log_audit_event(username=user.username, action="admin.fullbackup.delete", details=f"file={filename}")
    return {"deleted": filename}


@app.post("/api/admin/fullbackup/restore")
def api_fullbackup_restore(request: FullRestoreRequest, user: UserContext = Depends(require_admin_user)):
    """Restore from a saved full-backup zip. Selective restore via boolean flags."""
    if "/" in request.filename or ".." in request.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, request.filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    opts = {
        "restore_chats": request.restore_chats,
        "restore_memories": request.restore_memories,
        "restore_core_memories": request.restore_core_memories,
        "restore_users": request.restore_users,
        "restore_configs": request.restore_configs,
        "restore_personas": request.restore_personas,
        "restore_tasks": request.restore_tasks,
    }
    result = restore_full_backup(zip_path, opts)
    log_audit_event(username=user.username, action="admin.fullbackup.restore",
                    details=f"file={request.filename} ok={result['ok']}")
    if not result["ok"] and not result.get("summary"):
        raise HTTPException(status_code=500, detail="; ".join(result.get("errors", ["Unknown error"])))
    return result




@app.post("/api/admin/fullbackup/restore-upload")
async def api_fullbackup_restore_upload(
    backup_file: UploadFile = File(...),
    restore_chats: bool = Form(True),
    restore_memories: bool = Form(True),
    restore_core_memories: bool = Form(True),
    restore_users: bool = Form(True),
    restore_configs: bool = Form(True),
    restore_personas: bool = Form(True),
    restore_tasks: bool = Form(True),
    user: UserContext = Depends(require_admin_user),
):
    """Restore from an uploaded full-backup zip file (no server-side pre-save required)."""
    filename = (backup_file.filename or "").strip()
    if not filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Please upload a .zip full backup file")

    tmp_dir = tempfile.mkdtemp(prefix="ampai_restore_")
    tmp_zip = os.path.join(tmp_dir, "uploaded_full_backup.zip")
    try:
        content = await backup_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded backup file is empty")
        with open(tmp_zip, "wb") as f:
            f.write(content)

        opts = {
            "restore_chats": restore_chats,
            "restore_memories": restore_memories,
            "restore_core_memories": restore_core_memories,
            "restore_users": restore_users,
            "restore_configs": restore_configs,
            "restore_personas": restore_personas,
            "restore_tasks": restore_tasks,
        }
        result = restore_full_backup(tmp_zip, opts)
        log_audit_event(username=user.username, action="admin.fullbackup.restore.upload",
                        details=f"file={filename} ok={result.get('ok')}")
        if not result.get("ok") and not result.get("summary"):
            raise HTTPException(status_code=500, detail="; ".join(result.get("errors", ["Unknown restore error"])))
        return result
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@app.get("/api/admin/fullbackup/memory-categories")
def api_fullbackup_memory_categories(user: UserContext = Depends(require_admin_user)):
    """Return memory category stats (count of sessions and candidates per category)."""
    from full_backup import _fetch_sessions_by_category, _fetch_memories_by_category
    sessions_by_cat = _fetch_sessions_by_category()
    memories_by_cat = _fetch_memories_by_category()
    all_cats = sorted(set(list(sessions_by_cat.keys()) + list(memories_by_cat.keys())))
    rows = []
    for cat in all_cats:
        sessions = sessions_by_cat.get(cat, [])
        mems = memories_by_cat.get(cat, [])
        total_msgs = sum(len(s.get("messages", [])) for s in sessions)
        rows.append({
            "category": cat,
            "session_count": len(sessions),
            "message_count": total_msgs,
            "memory_count": len(mems),
        })
    return {"categories": rows}


# ═══════════════════════════════════════════════════════════
# DOCKER / CODE UPDATE ENDPOINTS

# Admin-only: check version, trigger update, manage backups
# ═══════════════════════════════════════════════════════════

CODE_BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "code_backups")
REPO_URL = os.getenv("AMPAI_REPO_URL", "https://github.com/pranto48/ampai.git")
_update_lock = threading.Lock()
_update_log_lines: List[str] = []
_update_status: Dict[str, Any] = {"state": "idle", "started_at": None, "finished_at": None, "error": None}


def _update_log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    _update_log_lines.append(line)
    if len(_update_log_lines) > 500:
        _update_log_lines.pop(0)
    logger.info("[UPDATE] %s", msg)


def _get_current_git_commit() -> str:
    """Return the HEAD commit hash of the deployed code, or 'unknown'."""
    try:
        # The host directory is mounted into /app_host inside the container
        for candidate in [
            os.path.join(os.path.dirname(__file__), "..", "..", ".git"),
            os.path.join(os.path.dirname(__file__), "..", ".git"),
            "/app_host/.git",
        ]:
            if os.path.isdir(candidate):
                git_head = os.path.join(candidate, "HEAD")
                if os.path.exists(git_head):
                    with open(git_head) as f:
                        ref = f.read().strip()
                    if ref.startswith("ref: "):
                        ref_file = os.path.join(candidate, ref[5:])
                        if os.path.exists(ref_file):
                            with open(ref_file) as f:
                                return f.read().strip()[:12]
                    return ref[:12]
    except Exception:
        pass
    return "unknown"




def _extract_github_slug(repo_url: str) -> Optional[str]:
    url = (repo_url or "").strip()
    if not url:
        return None
    if url.startswith("git@github.com:"):
        slug = url.split(":", 1)[1]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    slug = slug.strip().rstrip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    parts = [p for p in slug.split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"

def _fetch_remote_commit() -> str:
    """Fetch the latest commit hash from GitHub without cloning."""
    slug = _extract_github_slug(REPO_URL)
    if not slug:
        return "unknown"
    for branch in ["main", "master"]:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{slug}/commits/{branch}",
                headers={"Accept": "application/vnd.github.sha", "User-Agent": "ampai-updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode().strip()[:12]
        except Exception:
            continue
    return "unknown"


def _list_code_backups() -> List[Dict[str, Any]]:
    """Return list of code backups sorted newest-first."""
    os.makedirs(CODE_BACKUP_DIR, exist_ok=True)
    backups = []
    for name in sorted(os.listdir(CODE_BACKUP_DIR), reverse=True):
        full = os.path.join(CODE_BACKUP_DIR, name)
        if not os.path.isdir(full):
            continue
        size = 0
        for dirpath, _, filenames in os.walk(full):
            for fname in filenames:
                try:
                    size += os.path.getsize(os.path.join(dirpath, fname))
                except Exception:
                    pass
        commit_file = os.path.join(full, "git_commit.txt")
        commit = "unknown"
        if os.path.exists(commit_file):
            with open(commit_file) as f:
                commit = f.read().strip()[:12]
        backups.append({
            "name": name,
            "path": full,
            "created_at": name,  # name is the timestamp
            "size_bytes": size,
            "commit": commit,
        })
    return backups


def _do_update_in_thread(actor: str) -> None:
    """Run the update process in a background thread."""
    global _update_status
    _update_status = {"state": "running", "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None, "error": None}
    _update_log_lines.clear()

    try:
        import subprocess
        _update_log("Starting AmpAI code update…")
        _update_log(f"Triggered by: {actor}")
        _update_log(f"Repo: {REPO_URL}")

        # ── Step 1: Create code backup ────────────────────
        _update_log("--- Step 1: Creating code backup ---")
        os.makedirs(CODE_BACKUP_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = os.path.join(CODE_BACKUP_DIR, ts)
        os.makedirs(backup_path, exist_ok=True)

        backend_src = os.path.join(os.path.dirname(__file__))
        frontend_src = os.path.join(os.path.dirname(__file__), "..", "frontend")

        if os.path.isdir(backend_src):
            shutil.copytree(backend_src, os.path.join(backup_path, "backend"), dirs_exist_ok=True)
            _update_log("Backed up: backend/")
        if os.path.isdir(frontend_src):
            shutil.copytree(frontend_src, os.path.join(backup_path, "frontend"), dirs_exist_ok=True)
            _update_log("Backed up: frontend/")

        # Save current commit
        current_commit = _get_current_git_commit()
        with open(os.path.join(backup_path, "git_commit.txt"), "w") as f:
            f.write(current_commit)
        _update_log(f"Backup created at: {backup_path} (commit: {current_commit})")

        # ── Step 2: Pull latest code ───────────────────────
        _update_log("--- Step 2: Pulling latest code from GitHub ---")

        # Candidate paths for the host-mounted git repo
        host_git_candidates = [
            os.path.join(os.path.dirname(__file__), "..", ".."),  # /app/../ → host mount
            "/app_host",
        ]
        repo_root = None
        for c in host_git_candidates:
            if os.path.isdir(os.path.join(c, ".git")):
                repo_root = os.path.abspath(c)
                break

        if repo_root:
            _update_log(f"Found git repo at {repo_root}")
            result = subprocess.run(
                ["git", "-C", repo_root, "fetch", "origin"],
                capture_output=True, text=True, timeout=120
            )
            _update_log(f"git fetch: {result.stdout.strip() or result.stderr.strip() or 'ok'}")

            for branch in ["main", "master"]:
                r = subprocess.run(
                    ["git", "-C", repo_root, "reset", "--hard", f"origin/{branch}"],
                    capture_output=True, text=True, timeout=60
                )
                if r.returncode == 0:
                    _update_log(f"Reset to origin/{branch}: {r.stdout.strip()}")
                    break
                _update_log(f"Branch {branch} not found, trying next…")

            new_commit = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10
            ).stdout.strip()
            _update_log(f"Updated to commit: {new_commit}")
        else:
            # Fallback: download code via GitHub archive API
            _update_log("No git repo found on mounted volume. Downloading via GitHub archive…")
            import tempfile

            archive_url = REPO_URL.rstrip("/").replace(".git", "") + "/archive/refs/heads/main.zip"
            _update_log(f"Downloading: {archive_url}")
            temp_zip = tempfile.mktemp(suffix=".zip")
            urllib.request.urlretrieve(archive_url, temp_zip)
            _update_log("Download complete. Extracting…")

            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(temp_dir)
            os.remove(temp_zip)

            # Find extracted root (ampai-main/ or similar)
            extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
            if not extracted_dirs:
                raise RuntimeError("Archive extraction yielded no directory")
            extracted_root = os.path.join(temp_dir, extracted_dirs[0])

            # Copy backend and frontend
            new_backend = os.path.join(extracted_root, "backend")
            new_frontend = os.path.join(extracted_root, "frontend")

            if os.path.isdir(new_backend):
                shutil.copytree(new_backend, backend_src, dirs_exist_ok=True)
                _update_log("Copied new backend/")
            if os.path.isdir(new_frontend):
                shutil.copytree(new_frontend, frontend_src, dirs_exist_ok=True)
                _update_log("Copied new frontend/")

            shutil.rmtree(temp_dir)
            _update_log("Archive update complete.")
            new_commit = "downloaded"

        # ── Step 3: Install dependencies ──────────────────
        _update_log("--- Step 3: Installing Python dependencies ---")
        req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        if os.path.exists(req_file):
            result = subprocess.run(
                ["pip", "install", "--no-cache-dir", "-q", "-r", req_file],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                _update_log("Dependencies installed successfully.")
            else:
                _update_log(f"pip warning: {result.stderr.strip()[:400]}")
        else:
            _update_log("No requirements.txt found, skipping.")

        # ── Step 4: Signal server to reload ───────────────
        _update_log("--- Step 4: Signaling server reload ---")
        _update_log("Update complete! Restarting uvicorn in 3 seconds…")

        _update_status["state"] = "success"
        _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        _update_status["error"] = None
        log_audit_event(username=actor, action="admin.docker.update.success", details=f"backup={backup_path}")

        # Delay then restart uvicorn via os.execv to reload all modules
        def _restart_server():
            import time as _t
            _t.sleep(3)
            _update_log("Restarting server now…")
            os.execv("/usr/local/bin/uvicorn", [
                "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"
            ])

        threading.Thread(target=_restart_server, daemon=True).start()

    except Exception as exc:
        _update_log(f"ERROR: {exc}")
        _update_status["state"] = "error"
        _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        _update_status["error"] = str(exc)
        log_audit_event(username=actor, action="admin.docker.update.failure", details=str(exc))


@app.get("/api/admin/update/version")
def update_check_version(user: UserContext = Depends(require_admin_user)):
    """Return current and latest commit hashes."""
    current = _get_current_git_commit()
    latest = _fetch_remote_commit()
    check_ok = current != "unknown" and latest != "unknown"
    up_to_date = (check_ok and current == latest[:len(current)])
    return {
        "current_commit": current,
        "latest_commit": latest,
        "up_to_date": up_to_date,
        "check_ok": check_ok,
        "repo_url": REPO_URL,
    }


@app.post("/api/admin/update/trigger")
def update_trigger(user: UserContext = Depends(require_admin_user)):
    """Kick off the update process in a background thread (admin only)."""
    if not _update_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An update is already in progress")
    try:
        t = threading.Thread(target=_do_update_in_thread, args=(user.username,), daemon=True)
        t.start()
        # release lock after thread is done
        threading.Thread(target=lambda: (t.join(), _update_lock.release()), daemon=True).start()
    except Exception as e:
        _update_lock.release()
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "started", "message": "Update started. Poll /api/admin/update/status for progress."}


@app.get("/api/admin/update/status")
def update_status_endpoint(user: UserContext = Depends(require_admin_user)):
    """Return current update state and recent log lines."""
    return {
        **_update_status,
        "log_lines": list(_update_log_lines),
    }


@app.get("/api/admin/update/backups")
def update_list_backups(user: UserContext = Depends(require_admin_user)):
    """List all code backups."""
    backups = _list_code_backups()
    return {"backups": backups, "total": len(backups)}


@app.delete("/api/admin/update/backups/{backup_name}")
def update_delete_backup(backup_name: str, user: UserContext = Depends(require_admin_user)):
    """Delete a specific code backup by name (timestamp folder)."""
    # Security: only allow simple timestamp names, no path traversal
    if "/" in backup_name or ".." in backup_name:
        raise HTTPException(status_code=400, detail="Invalid backup name")
    full_path = os.path.join(CODE_BACKUP_DIR, backup_name)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    shutil.rmtree(full_path)
    log_audit_event(username=user.username, action="admin.docker.backup.delete", details=f"backup={backup_name}")
    return {"deleted": backup_name}



if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static-assets")

# SPA catch-all: serve index.html for any unmatched route so
# client-side hash-router works on direct navigation / reload.
@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    # Let /api/* and /uploads/* pass through (already handled above)
    if full_path.startswith("api/") or full_path.startswith("uploads/"):
        raise HTTPException(status_code=404)
    fp = os.path.join(os.path.dirname(__file__), "..", "frontend", full_path)
    if os.path.exists(fp) and os.path.isfile(fp):
        import mimetypes
        mt, _ = mimetypes.guess_type(fp)
        with open(fp, "rb") as f:
            return Response(f.read(), media_type=mt or "application/octet-stream")
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    raise HTTPException(status_code=404)
