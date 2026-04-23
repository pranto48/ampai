from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import shutil
import uuid
import imaplib
import email
from email.header import decode_header

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


def _build_user_store() -> Dict[str, Dict[str, str]]:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "password")
    persisted_admin_hash = get_config("admin_password_hash")

    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD", "user123")

    return {
        admin_username: {
            "role": "admin",
            "password_hash": persisted_admin_hash or pwd_context.hash(admin_password),
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


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user=Depends(require_authenticated_user)):
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

        return {"filename": file.filename, "url": f"/uploads/{unique_filename}", "type": file.content_type, "extracted_text": extracted_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def get_sessions(query: str = "", archived: bool = False, user=Depends(require_authenticated_user)):
    return {"sessions": get_all_sessions(query=query, include_archived=archived)}


@app.post("/api/sessions/{session_id}/pin")
def pin_session(session_id: str, request: SessionFlagsRequest, user=Depends(require_authenticated_user)):
    if not set_session_flags(session_id, pinned=request.value):
        raise HTTPException(status_code=500, detail="Failed to update pin")
    return {"status": "success"}


@app.post("/api/sessions/{session_id}/archive")
def archive_session(session_id: str, request: SessionFlagsRequest, user=Depends(require_authenticated_user)):
    if not set_session_flags(session_id, archived=request.value):
        raise HTTPException(status_code=500, detail="Failed to update archive")
    return {"status": "success"}


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
    user = USERS.get(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")

    if not pwd_context.verify(request.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(request.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    new_hash = pwd_context.hash(request.new_password)
    user["password_hash"] = new_hash
    set_config("admin_password_hash", new_hash)
    return {"status": "success"}

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
