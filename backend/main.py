from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import hashlib
import json
import os
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import shutil
import uuid
import urllib.request
import time
import re
import threading
from queue import Queue, Empty
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from zoneinfo import ZoneInfo

from auth import bootstrap_default_admin
from agent import chat_with_agent, get_llm, get_redis_history
from database import (
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
    get_network_targets,
    get_duplicate_message_counts,
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
    migrate_app_config_encryption,
    set_config,
    set_session_archived,
    set_session_category,
    set_session_pinned,
    touch_session,
    touch_session_updated_at,
    update_task,
    log_audit_event,
    apply_retention_policy,
    upsert_session_insight,
    get_session_insight,
    list_audit_events,
    get_effective_notification_preferences,
    upsert_user_notification_preferences,
    enqueue_pending_reply_notification,
    engine,
)
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

app = FastAPI()
logger = logging.getLogger("ampai")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

USER_TOKEN = os.getenv("AMPAI_USER_TOKEN", "ampai-user")
ADMIN_TOKEN = os.getenv("AMPAI_ADMIN_TOKEN", "ampai-admin")
INSIGHT_QUEUE: "Queue[str]" = Queue(maxsize=1000)
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


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
    memory_mode: str = "full"
    use_web_search: bool = False
    attachments: List[Attachment] = []


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


class MemoryExplorerQuery(BaseModel):
    query: Optional[str] = ""
    category: Optional[str] = ""
    owner_scope: Optional[str] = "mine"  # mine|shared|all
    date_from: Optional[str] = ""
    date_to: Optional[str] = ""
    limit: int = 50
    offset: int = 0


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


def _bootstrap_default_users() -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "P@ssw0rd")

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


def _execute_backup(actor: str, trigger: str = "manual") -> Dict:
    backup_mode = (get_config("backup_mode", "local") or "local").strip().lower()
    sessions = export_all_sessions_for_backup()
    serialized, manifest = build_backup_payload(sessions=sessions, actor=actor)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"ampai_backup_{timestamp}.json"

    try:
        if backup_mode == "ftp":
            host = get_config("backup_ftp_host")
            user = get_config("backup_ftp_user")
            password = get_config("backup_ftp_password")
            remote_path = get_config("backup_ftp_path", "/")
            if not host or not user or not password:
                raise ValueError("FTP backup is not fully configured")
            outcome = write_backup_ftp(host, user, password, remote_path, filename, serialized, manifest)
        elif backup_mode == "smb":
            host = get_config("backup_smb_host")
            share = get_config("backup_smb_share")
            remote_path = get_config("backup_smb_path", "/")
            user = get_config("backup_smb_user")
            password = get_config("backup_smb_password")
            domain = get_config("backup_smb_domain", "")
            if not host or not share or not user or not password:
                raise ValueError("SMB backup is not fully configured")
            outcome = write_backup_smb(host, share, remote_path, user, password, domain, filename, serialized, manifest)
        else:
            local_dir = get_config("backup_local_path", "/tmp/ampai_backups")
            outcome = write_backup_local(local_dir, filename, serialized, manifest)

        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "success",
                "mode": outcome.get("mode", backup_mode),
                "target": outcome.get("path") or outcome.get("file") or "",
                "manifest_checksum": manifest["checksum_sha256"],
                "session_count": manifest["session_count"],
                "message_count": manifest["message_count"],
            }
        )
        return {"status": "success", **outcome, "manifest": manifest}
    except Exception as exc:
        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "failed",
                "mode": backup_mode,
                "error": str(exc),
            }
        )
        raise


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
    user = get_user(payload.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

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

    token = _create_access_token({"sub": user["username"], "role": user["role"]})
    body = UserLoginResponse(username=user["username"], role=user["role"], token=token)
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
        raise HTTPException(status_code=400, detail="username_password_required")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="password_too_short")
    if get_user(username):
        raise HTTPException(status_code=400, detail="username_exists")

    result = db_create_user(username=username, role="user", password_hash=pwd_context.hash(payload.password))
    if isinstance(result, tuple):
        ok, reason = result
    else:
        ok, reason = bool(result), "create_failed"
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
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
    worker = threading.Thread(target=_insight_worker, daemon=True, name="ampai-insight-worker")
    worker.start()


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


@app.post("/api/chat")
def chat(request: ChatRequest, user=Depends(require_authenticated_user)):
    try:
        _ensure_session_owner_for_user(request.session_id, user)
        result = chat_with_agent(
            session_id=request.session_id,
            message=request.message,
            model_type=request.model_type,
            api_key=request.api_key,
            model_name=request.model_name,
            memory_mode=request.memory_mode,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments],
        )
        ensure_session_owner(request.session_id, user.username)
        touch_session(request.session_id)
        log_audit_event(username=user.username, action="memory.write.chat", session_id=request.session_id, details=f"model={request.model_type}")
        try:
            INSIGHT_QUEUE.put_nowait(request.session_id)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e))


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
        accessible_ids = get_accessible_session_ids(username=current_user.username, is_admin=False)
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
    }


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
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
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


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
    configs = get_all_configs()
    masked = {}
    for k, v in configs.items():
        if k in SECRET_CONFIG_KEYS and v:
            if len(v) > 8:
                masked[k] = v[:4] + "..." + v[-4:]
            else:
                masked[k] = "****"
        elif "api_key" in k and v and len(v) > 8:
            masked[k] = v[:4] + "..." + v[-4:]
        else:
            masked[k] = v
    return masked


@app.post("/api/admin/configs")
def update_admin_configs(request: ConfigUpdateRequest, user=Depends(require_admin_user)):
    for k, v in request.configs.items():
        if k == "backup_mode":
            mode = (v or "").strip().lower()
            if mode not in {"local", "ftp", "smb"}:
                raise HTTPException(status_code=400, detail="backup_mode must be local, ftp, or smb")
        if v and "..." not in v:
            set_config(k, v)
    return {"status": "success"}


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


@app.post("/api/admin/backup/run")
def run_backup(current_user: UserContext = Depends(require_admin_user)):
    try:
        return _execute_backup(actor=current_user.username, trigger="manual")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}") from exc


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
    try:
        payload = json.loads(request.backup_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid backup JSON: {exc}") from exc
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        raise HTTPException(status_code=400, detail="Backup payload must contain a sessions array")

    summary = {"session_count": 0, "message_count": 0, "invalid_sessions": 0}
    for session in sessions:
        session_id = (session or {}).get("session_id")
        messages = (session or {}).get("messages")
        if not session_id or not isinstance(messages, list):
            summary["invalid_sessions"] += 1
            continue
        summary["session_count"] += 1
        summary["message_count"] += len(messages)
        if request.dry_run:
            continue
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

    _record_backup_status(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": "restore-dry-run" if request.dry_run else "restore",
            "status": "success",
            "mode": "restore",
            "target": f"uploaded by {user.username}",
            **summary,
        }
    )
    return {"status": "success", "dry_run": request.dry_run, "summary": summary}

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


@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/health")
def health(user=Depends(require_admin_user)):
    configs = get_all_configs()
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "database_url_set": bool(DATABASE_URL),
        "redis_url_set": bool(os.getenv("REDIS_URL")),
        "web_search_ready": True,
        "imap_ready": bool(configs.get("imap_host") and configs.get("imap_username") and configs.get("imap_password"))
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


if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
