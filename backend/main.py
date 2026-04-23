from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import os
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import shutil
import uuid
import ftplib
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text
from zoneinfo import ZoneInfo

from auth import UserContext, auth_context_middleware, require_admin_user, require_authenticated_user, router as auth_router
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
    list_memory_groups_for_user,
    list_shared_sessions_for_user,
    export_all_sessions_for_backup,
    list_chat_messages,
    get_sql_chat_history,
    list_tasks,
    migrate_app_config_encryption,
    set_config,
    set_session_archived,
    set_session_category,
    set_session_pinned,
    touch_session_updated_at,
    update_task,
    get_effective_notification_preferences,
    upsert_user_notification_preferences,
    enqueue_pending_reply_notification,
)
from integrations.gmail_api import (
    fetch_todays_messages as fetch_gmail_todays_messages,
    refresh_access_token as refresh_gmail_access_token,
)
from agent import chat_with_agent, get_redis_history
from scheduler import start_scheduler, run_network_sweep
from langchain_community.chat_message_histories import SQLChatMessageHistory
from auth import (
    router as auth_router,
    admin_router as admin_users_router,
    require_authenticated_user,
    require_admin_user,
    bootstrap_default_admin,
)

app = FastAPI()
logger = logging.getLogger("ampai")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

USER_TOKEN = os.getenv("AMPAI_USER_TOKEN", "ampai-user")
ADMIN_TOKEN = os.getenv("AMPAI_ADMIN_TOKEN", "ampai-admin")


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


class UserLoginResponse(BaseModel):
    username: str
    role: str


class UserContext(BaseModel):
    username: str
    role: str


def _bootstrap_default_users() -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "password")
    persisted_admin_hash = get_config("admin_password_hash")

    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD", "user123")

    ensure_default_users(
        [
            {
                "username": admin_username,
                "role": "admin",
                "password_hash": persisted_admin_hash or pwd_context.hash(admin_password),
            },
            {
                "username": user_username,
                "role": "user",
                "password_hash": pwd_context.hash(user_password),
            },
        ]
    )


_bootstrap_default_users()


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
    token = request.cookies.get("access_token")
    return _get_current_user(token)


def require_authenticated_user(current_user: UserContext = Depends(get_current_user_from_cookie)) -> UserContext:
    return current_user


def require_admin_user(current_user: UserContext = Depends(get_current_user_from_cookie)) -> UserContext:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@app.post("/api/auth/login", response_model=UserLoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = _create_access_token({"sub": user["username"], "role": user["role"]})
    response = Response(content=UserLoginResponse(username=form_data.username, role=user["role"]).model_dump_json(), media_type="application/json")
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=JWT_EXPIRY_MINUTES * 60,
    )
    return response

@app.on_event("startup")
def startup_event():
    bootstrap_default_admin()
    start_scheduler()


app.include_router(auth_router)
app.include_router(admin_users_router)



@app.post("/api/chat")
def chat(request: ChatRequest, user=Depends(require_authenticated_user)):
    try:
        result = chat_with_agent(
            session_id=request.session_id,
            message=request.message,
            model_type=request.model_type,
            api_key=request.api_key,
            memory_mode=request.memory_mode,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments],
        )
        touch_session(request.session_id)
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
            username=current_user.username,
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


@app.get("/api/sessions")
def get_sessions(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    archived: Optional[bool] = Query(default=None),
    current_user: UserContext = Depends(require_authenticated_user),
):
    sessions = get_all_sessions(query=query, category=category, archived=archived)
    if current_user.role != "admin":
        shared_ids = set(list_shared_sessions_for_user(current_user.username))
        for session in sessions:
            if session["session_id"] in shared_ids:
                session["shared_via_group"] = True
    return {"sessions": sessions}


@app.get("/api/history/{session_id}")
def get_history(session_id: str, user=Depends(require_authenticated_user)):
    try:
        messages = list_chat_messages(session_id, dedupe=True)
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@app.post("/api/sessions/{session_id}/category")
def update_category(session_id: str, request: CategoryRequest, user=Depends(require_authenticated_user)):
    success = set_session_category(session_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category")
    return {"status": "success"}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user=Depends(require_authenticated_user)):
    try:
        delete_session_metadata(session_id)
        SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL).clear()
        get_redis_history(session_id).clear()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{session_id}")
def export_session(session_id: str, user=Depends(require_authenticated_user)):
    try:
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
    if not add_user_to_memory_group(group_id, username.strip()):
        raise HTTPException(status_code=500, detail="Failed to add member")
    return {"status": "success"}


@app.post("/api/admin/memory-groups/{group_id}/share")
def admin_share_session(group_id: int, request: MemoryGroupShareRequest, _: UserContext = Depends(require_admin_user)):
    if not share_session_to_group(group_id, request.session_id):
        raise HTTPException(status_code=500, detail="Failed to share session")
    return {"status": "success"}


@app.post("/api/admin/backup/run")
def run_backup(current_user: UserContext = Depends(require_admin_user)):
    backup_mode = (get_config("backup_mode", "local") or "local").strip().lower()
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "by": current_user.username,
        "sessions": export_all_sessions_for_backup(),
    }
    serialized = json.dumps(snapshot, indent=2)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"ampai_backup_{timestamp}.json"

    if backup_mode == "ftp":
        host = get_config("backup_ftp_host")
        user = get_config("backup_ftp_user")
        password = get_config("backup_ftp_password")
        remote_path = get_config("backup_ftp_path", "/")
        if not host or not user or not password:
            raise HTTPException(status_code=400, detail="FTP backup is not fully configured")
        try:
            with ftplib.FTP(host) as ftp:
                ftp.login(user=user, passwd=password)
                ftp.cwd(remote_path)
                from io import BytesIO
                ftp.storbinary(f"STOR {filename}", BytesIO(serialized.encode("utf-8")))
            return {"status": "success", "mode": "ftp", "file": filename}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"FTP backup failed: {exc}") from exc

    local_dir = get_config("backup_local_path", "/tmp/ampai_backups")
    os.makedirs(local_dir, exist_ok=True)
    path = os.path.join(local_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(serialized)
    return {"status": "success", "mode": "local", "path": path}

@app.post("/api/admin/configs/migrate")
def migrate_admin_configs():
    result = migrate_app_config_encryption()
    return {"status": "success", **result}

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
