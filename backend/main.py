from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import os
import shutil
import uuid

from database import (
    get_all_sessions, set_session_category, delete_session_metadata, get_sql_chat_history,
    get_all_configs, set_config, get_core_memories, delete_core_memory,
    get_network_targets, add_network_target, delete_network_target, migrate_app_config_encryption
)
from agent import chat_with_agent, get_redis_history
from scheduler import start_scheduler, run_network_sweep
from passlib.context import CryptContext
from pydantic import BaseModel

from agent import chat_with_agent, get_redis_history
from database import (
    add_network_target,
    create_task,
    delete_core_memory,
    delete_network_target,
    delete_task,
    delete_session_metadata,
    get_all_configs,
    get_all_sessions,
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
)
from scheduler import run_network_sweep, start_scheduler

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


@app.on_event("startup")
def startup_event():
    start_scheduler()
    migrate_app_config_encryption()


def _create_access_token(data: Dict[str, str]) -> str:
    payload = data.copy()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload.update({"exp": expiry})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                print(f"PDF Parsing error: {e}")
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


if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
