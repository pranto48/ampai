import json
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from redis import Redis
from zoneinfo import ZoneInfo

from agent import chat_with_agent, get_redis_history, get_llm
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
    get_sql_chat_history,
    list_tasks,
    migrate_app_config_encryption,
    set_config,
    set_session_archived,
    set_session_category,
    set_session_pinned,
    touch_session_updated_at,
    update_task,
    engine,
)
from logging_utils import configure_logging, get_logger, reset_request_id, set_request_id
from memory_indexer import MemoryIndexer
from integrations.gmail_api import (
    fetch_todays_messages as fetch_gmail_todays_messages,
    refresh_access_token as refresh_gmail_access_token,
)
from integrations.outlook_graph import (
    fetch_todays_messages as fetch_outlook_todays_messages,
    refresh_access_token as refresh_outlook_access_token,
)
from scheduler import get_scheduler_diagnostics, run_email_digest_job, run_network_sweep, start_scheduler

from sqlalchemy import text
from logging_utils import configure_logging, get_logger, reset_request_id, set_request_id

configure_logging()
logger = get_logger(__name__)
app = FastAPI()
CLEAR_VALUE_SENTINEL = "__CLEAR__"
SECRET_CONFIG_KEYS = {
    "generic_api_key",
    "openai_api_key",
    "gemini_api_key",
    "anthropic_api_key",
    "openrouter_api_key",
    "anythingllm_api_key",
    "serpapi_api_key",
    "bing_api_key",
    "custom_web_search_api_key",
    "integration_email_gmail_credentials",
    "integration_email_outlook_credentials",
}

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Attachment(BaseModel):
    filename: str
    url: str
    type: str
    extracted_text: Optional[str] = None


class TargetModel(BaseModel):
    name: str
    ip_address: str

@app.on_event("startup")
def startup_event():
    start_scheduler()
    migrate_app_config_encryption()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = set_request_id(request_id)
    request.state.request_id = request_id
    started = datetime.now(timezone.utc)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("HTTP request failed", extra={"path": request.url.path, "method": request.method})
        reset_request_id(token)
        raise
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info(
        "HTTP request completed",
        extra={"path": request.url.path, "method": request.method, "status_code": response.status_code, "elapsed_ms": elapsed_ms},
    )
    reset_request_id(token)
    response.headers["X-Request-ID"] = request_id
    return response

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


class SessionStateRequest(BaseModel):
    value: bool = True


class ImportMessage(BaseModel):
    type: str
    content: str


class ImportRequest(BaseModel):
    session_id: str
    category: str
    messages: List[ImportMessage]


class ConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    status: str = "todo"
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


class EmailSummaryTodayRequest(BaseModel):
    provider: str = "outlook"
    timezone: str = "UTC"
    max_results: int = 25
    model_type: Optional[str] = None
    api_key: Optional[str] = None
    session_id: str = "system_email_reports"


class UserLoginResponse(BaseModel):
    username: str
    role: str


class UserContext(BaseModel):
    username: str
    role: str


def _build_user_store() -> Dict[str, Dict[str, str]]:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD", "user123")

    return {
        admin_username: {
            "role": "admin",
            "password_hash": pwd_context.hash(admin_password),
        },
        user_username: {
            "role": "user",
            "password_hash": pwd_context.hash(user_password),
        },
    }


USERS = _build_user_store()


def _load_integration_credentials(provider: str) -> Dict[str, str]:
    raw = get_config(f"integration_email_{provider}_credentials", "{}")
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_integration_credentials(provider: str, credentials: Dict[str, str]) -> None:
    set_config(f"integration_email_{provider}_credentials", json.dumps(credentials))


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


def _check_model_provider_health() -> dict:
    provider = (get_all_configs().get("default_model") or "ollama").strip().lower()
    try:
        get_llm(provider)
        return {"ok": True, "provider": provider}
    except Exception as exc:
        return {"ok": False, "provider": provider, "details": str(exc)}


def _check_search_provider_health() -> dict:
    configs = get_all_configs()
    fallback = (configs.get("web_search_secondary_provider") or configs.get("web_fallback_provider") or "").strip().lower()
    if fallback == "serpapi":
        return {"ok": bool(configs.get("serpapi_api_key")), "provider": "serpapi"}
    if fallback == "bing":
        return {"ok": bool(configs.get("bing_api_key")), "provider": "bing"}
    if fallback == "custom":
        return {"ok": bool(configs.get("custom_web_search_url")), "provider": "custom"}
    return {"ok": True, "provider": "duckduckgo"}


def _check_vector_index_health() -> dict:
    model_type = (get_all_configs().get("default_model") or "ollama").strip().lower()
    try:
        indexer = MemoryIndexer(model_type=model_type)
        if not getattr(indexer, "enabled", False):
            return {"ok": False, "details": "Vector index unavailable", "provider": model_type}
        return {"ok": True, "provider": model_type}
    except Exception as exc:
        return {"ok": False, "provider": model_type, "details": str(exc)}


def _build_config_sanity() -> dict:
    configs = get_all_configs()
    default_model = (configs.get("default_model") or "ollama").strip().lower()
    required_keys = {
        "openai": ["openai_api_key"],
        "gemini": ["gemini_api_key"],
        "anthropic": ["anthropic_api_key"],
        "openrouter": ["openrouter_api_key"],
        "anythingllm": ["anythingllm_base_url"],
        "generic": ["generic_base_url"],
    }.get(default_model, [])
    missing = [key for key in required_keys if not (configs.get(key) or "").strip()]

    digest_hour = int(configs.get("email_digest_hour") or 7)
    digest_minute = int(configs.get("email_digest_minute") or 30)
    schedule_ok = 0 <= digest_hour <= 23 and 0 <= digest_minute <= 59
    return {
        "default_model": default_model,
        "required_keys_ok": not missing,
        "missing_required_keys": missing,
        "digest_schedule_ok": schedule_ok,
        "email_digest_hour": digest_hour,
        "email_digest_minute": digest_minute,
    }


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
    user = USERS.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = _create_access_token({"sub": form_data.username, "role": user["role"]})
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


@app.post("/api/auth/logout")
def logout():
    response = Response(content='{"status":"success"}', media_type="application/json")
    response.delete_cookie("access_token")
    return response


@app.get("/api/auth/me", response_model=UserContext)
def auth_me(current_user: UserContext = Depends(require_authenticated_user)):
    return current_user


@app.post("/api/chat")
def chat(request: ChatRequest, _: UserContext = Depends(require_authenticated_user)):
    try:
        response = chat_with_agent(
            session_id=request.session_id,
            message=request.message,
            model_type=request.model_type,
            api_key=request.api_key,
            memory_mode=request.memory_mode,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments],
        )
        touch_session_updated_at(request.session_id)
        return {
            "response": response.get("content", ""),
            "web_search_status": response.get("web_search_status"),
            "search_metadata": response.get("web_search_status"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    touch_session_updated_at(request.session_id)
    return {
        "status": "success",
        "provider": provider,
        "timezone": tz_name,
        "messages_count": len(messages),
        "summary": result.get("content", ""),
        "session_id": request.session_id,
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), _: UserContext = Depends(require_authenticated_user)):
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
                logger.exception("PDF parsing error", exc_info=e)
        elif file_ext.lower() in [".txt", ".csv", ".json", ".md", ".py", ".js", ".html", ".css"]:
            with open(file_path, "r", encoding="utf-8") as text_file:
                extracted_text = text_file.read()

        return {
            "filename": file.filename,
            "url": f"/uploads/{unique_filename}",
            "type": file.content_type,
            "extracted_text": extracted_text,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def get_sessions(
    query: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    archived: Optional[bool] = Query(default=None),
    _: UserContext = Depends(require_authenticated_user),
):
    return {"sessions": get_all_sessions(query=query, category=category, archived=archived)}


@app.get("/api/history/{session_id}")
def get_history(session_id: str, _: UserContext = Depends(require_authenticated_user)):
    try:
        history = get_sql_chat_history(session_id)
        messages = []
        for msg in history.messages:
            messages.append({"type": msg.type, "content": msg.content})
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@app.post("/api/sessions/{session_id}/category")
def update_category(session_id: str, request: CategoryRequest, _: UserContext = Depends(require_authenticated_user)):
    success = set_session_category(session_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category")
    return {"status": "success"}


@app.patch("/api/sessions/{session_id}/pin")
def update_pin(session_id: str, request: SessionStateRequest, _: UserContext = Depends(require_authenticated_user)):
    if not set_session_pinned(session_id, request.value):
        raise HTTPException(status_code=500, detail="Failed to update pin state")
    return {"status": "success"}


@app.patch("/api/sessions/{session_id}/archive")
def update_archive(session_id: str, request: SessionStateRequest, _: UserContext = Depends(require_authenticated_user)):
    if not set_session_archived(session_id, request.value):
        raise HTTPException(status_code=500, detail="Failed to update archive state")
    return {"status": "success"}


@app.post("/api/sessions/{session_id}/unarchive")
def unarchive_session(session_id: str, _: UserContext = Depends(require_authenticated_user)):
    if not set_session_archived(session_id, False):
        raise HTTPException(status_code=500, detail="Failed to unarchive session")
    return {"status": "success"}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, _: UserContext = Depends(require_authenticated_user)):
    try:
        delete_session_metadata(session_id)

        sql_history = get_sql_chat_history(session_id)
        sql_history.clear()

        redis_history = get_redis_history(session_id)
        redis_history.clear()

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{session_id}")
def export_session(session_id: str, _: UserContext = Depends(require_authenticated_user)):
    try:
        history = get_sql_chat_history(session_id)
        messages = [{"type": msg.type, "content": msg.content} for msg in history.messages]

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
def import_session(request: ImportRequest, _: UserContext = Depends(require_authenticated_user)):
    try:
        history = get_sql_chat_history(request.session_id)
        existing_messages = {(msg.type, msg.content) for msg in history.messages}
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
                inserted += 1
            else:
                skipped += 1
                continue
            existing_messages.add(key)

        set_session_category(request.session_id, request.category)
        if inserted > 0:
            touch_session_updated_at(request.session_id)
        return {"status": "success", "session_id": request.session_id, "inserted": inserted, "skipped": skipped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/configs")
def get_admin_configs(_: UserContext = Depends(require_admin_user)):
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
def update_admin_configs(request: ConfigUpdateRequest, _: UserContext = Depends(require_admin_user)):
    for k, v in request.configs.items():
        if v == CLEAR_VALUE_SENTINEL:
            set_config(k, "")
        elif v and "..." not in v: # Dont save masked passwords
            set_config(k, v)
    return {"status": "success"}

@app.post("/api/admin/configs/migrate")
def migrate_admin_configs():
    result = migrate_app_config_encryption()
    return {"status": "success", **result}

@app.get("/api/configs/status")
def get_configs_status(_: UserContext = Depends(require_authenticated_user)):
    configs = get_all_configs()
    return {
        "openai": bool(configs.get("openai_api_key")),
        "gemini": bool(configs.get("gemini_api_key")),
        "anthropic": bool(configs.get("anthropic_api_key")),
        "generic": bool(configs.get("generic_base_url")),
        "openrouter": bool(configs.get("openrouter_api_key")),
        "anythingllm": bool(configs.get("anythingllm_base_url")),
        "default_model": configs.get("default_model"),
    }


@app.get("/api/admin/core-memories")
def api_get_core_memories(_: UserContext = Depends(require_admin_user)):
    return {"core_memories": get_core_memories()}


@app.delete("/api/admin/core-memories/{mem_id}")
def api_delete_core_memory(mem_id: int, _: UserContext = Depends(require_admin_user)):
    success = delete_core_memory(mem_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete core memory")
    return {"status": "success"}


@app.get("/api/targets")
def get_targets(_: UserContext = Depends(require_admin_user)):
    return get_network_targets()


@app.post("/api/tasks")
def api_create_task(request: TaskCreateRequest, _: UserContext = Depends(require_authenticated_user)):
    task = create_task(
        title=request.title,
        description=request.description or "",
        status=request.status,
        priority=request.priority,
        due_at=request.due_at,
        session_id=request.session_id,
    )
    if not task:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return {"task": task}


@app.get("/api/tasks")
def api_get_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    session_id: Optional[str] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
    _: UserContext = Depends(require_authenticated_user),
):
    return {
        "tasks": list_tasks(
            status=status,
            priority=priority,
            session_id=session_id,
            due_before=due_before,
            due_after=due_after,
        )
    }


@app.patch("/api/tasks/{task_id}")
def api_patch_task(task_id: int, request: TaskUpdateRequest, _: UserContext = Depends(require_authenticated_user)):
    task = update_task(
        task_id=task_id,
        title=request.title,
        description=request.description,
        status=request.status,
        priority=request.priority,
        due_at=request.due_at,
        session_id=request.session_id,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: int, _: UserContext = Depends(require_authenticated_user)):
    if not delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}


@app.post("/api/targets")
def create_target(target: TargetModel, _: UserContext = Depends(require_admin_user)):
    success = add_network_target(target.name, target.ip_address)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add target")


@app.delete("/api/targets/{target_id}")
def remove_target(target_id: int, _: UserContext = Depends(require_admin_user)):
    success = delete_network_target(target_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete target")


@app.post("/api/targets/run")
def run_sweep_now(_: UserContext = Depends(require_admin_user)):
    run_network_sweep()
    return {"status": "success"}


@app.post("/api/admin/integrations/email/digest/run")
def run_email_digest_now(_: UserContext = Depends(require_admin_user)):
    run_email_digest_job()
    return {"status": "success"}


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
def get_status(_: UserContext = Depends(require_authenticated_user)):
    backend_path = os.path.dirname(__file__)
    frontend_path = os.path.join(backend_path, "..", "frontend")
    latest_mtime = get_latest_mtime([backend_path, frontend_path])
    return {"latest_mtime": latest_mtime}


@app.get("/api/health")
def get_health(_: UserContext = Depends(require_admin_user)):
    db_health = _check_db_health()
    redis_health = _check_redis_health()
    vector_health = _check_vector_index_health()
    search_health = _check_search_provider_health()
    scheduler_health = get_scheduler_diagnostics()
    overall_ok = all([
        db_health.get("ok"),
        redis_health.get("ok"),
        vector_health.get("ok"),
        search_health.get("ok"),
    ])
    return {
        "ok": overall_ok,
        "checks": {
            "db": db_health,
            "redis": redis_health,
            "vector_index": vector_health,
            "search_provider": search_health,
            "scheduler": scheduler_health,
        },
    }


@app.get("/api/admin/diagnostics")
def get_admin_diagnostics(_: UserContext = Depends(require_admin_user)):
    scheduler_diag = get_scheduler_diagnostics()
    errors = [v for v in (scheduler_diag.get("last_errors") or {}).values() if v]
    return {
        "recent_scheduler_run": scheduler_diag.get("last_run", {}),
        "last_errors": scheduler_diag.get("last_errors", {}),
        "config_sanity": _build_config_sanity(),
        "status": "ok" if not errors else "warning",
    }


if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
