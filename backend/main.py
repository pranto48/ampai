from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from typing import List, Dict, Optional
import json
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import shutil

from database import (
    get_all_sessions, set_session_category, delete_session_metadata, DATABASE_URL,
    get_all_configs, set_config, get_core_memories, delete_core_memory,
    get_network_targets, add_network_target, delete_network_target
)
from agent import chat_with_agent, get_redis_history
from scheduler import start_scheduler, run_network_sweep
from langchain_community.chat_message_histories import SQLChatMessageHistory

import uuid
import os

app = FastAPI()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

class ImportMessage(BaseModel):
    type: str
    content: str

class ImportRequest(BaseModel):
    session_id: str
    category: str
    messages: List[ImportMessage]

class ConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]

@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        response = chat_with_agent(
            session_id=request.session_id,
            message=request.message,
            model_type=request.model_type,
            api_key=request.api_key,
            memory_mode=request.memory_mode,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments]
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
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
            "extracted_text": extracted_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
def get_sessions():
    return {"sessions": get_all_sessions()}

@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    try:
        history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
        messages = []
        for msg in history.messages:
            messages.append({
                "type": msg.type, # "human" or "ai"
                "content": msg.content
            })
        return {"messages": messages}
    except Exception as e:
        return {"messages": [], "error": str(e)}

@app.post("/api/sessions/{session_id}/category")
def update_category(session_id: str, request: CategoryRequest):
    success = set_session_category(session_id, request.category)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update category")
    return {"status": "success"}

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        delete_session_metadata(session_id)
        
        sql_history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
        sql_history.clear()
        
        redis_history = get_redis_history(session_id)
        redis_history.clear()
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/{session_id}")
def export_session(session_id: str):
    try:
        history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
        messages = [{"type": msg.type, "content": msg.content} for msg in history.messages]
        
        sessions = get_all_sessions()
        category = "Uncategorized"
        for s in sessions:
            if s["session_id"] == session_id:
                category = s["category"]
                break
                
        return {
            "session_id": session_id,
            "category": category,
            "messages": messages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/import")
def import_session(request: ImportRequest):
    try:
        history = SQLChatMessageHistory(session_id=request.session_id, connection_string=DATABASE_URL)
        
        for msg in request.messages:
            if msg.type == "human":
                history.add_user_message(msg.content)
            elif msg.type == "ai":
                history.add_ai_message(msg.content)
        
        set_session_category(request.session_id, request.category)
        return {"status": "success", "session_id": request.session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/configs")
def get_admin_configs():
    configs = get_all_configs()
    masked = {}
    for k, v in configs.items():
        if "api_key" in k and v and len(v) > 8:
            masked[k] = v[:4] + "..." + v[-4:]
        else:
            masked[k] = v
    return masked

@app.post("/api/admin/configs")
def update_admin_configs(request: ConfigUpdateRequest):
    for k, v in request.configs.items():
        if v and "..." not in v: # Dont save masked passwords
            set_config(k, v)
    return {"status": "success"}

@app.get("/api/configs/status")
def get_configs_status():
    configs = get_all_configs()
    return {
        "openai": bool(configs.get("openai_api_key")),
        "gemini": bool(configs.get("gemini_api_key")),
        "anthropic": bool(configs.get("anthropic_api_key")),
        "generic": bool(configs.get("generic_base_url")),
        "openrouter": bool(configs.get("openrouter_api_key")),
        "anythingllm": bool(configs.get("anythingllm_base_url")),
        "default_model": configs.get("default_model")
    }

@app.get("/api/admin/core-memories")
def api_get_core_memories():
    return {"core_memories": get_core_memories()}

@app.delete("/api/admin/core-memories/{mem_id}")
def api_delete_core_memory(mem_id: int):
    success = delete_core_memory(mem_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete core memory")
    return {"status": "success"}

# --- Network Targets API ---
@app.get("/api/targets")
def get_targets():
    return get_network_targets()

@app.post("/api/targets")
def create_target(target: TargetModel):
    success = add_network_target(target.name, target.ip_address)
    if success: return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add target")

@app.delete("/api/targets/{target_id}")
def remove_target(target_id: int):
    success = delete_network_target(target_id)
    if success: return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete target")

@app.post("/api/targets/run")
def run_sweep_now():
    # Run synchronously for immediate feedback
    run_network_sweep()
    return {"status": "success"}

def get_latest_mtime(directories):
    latest = 0
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.pyc') or '__pycache__' in root or file.endswith('.db') or file.endswith('.db-journal'):
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
def get_status():
    backend_path = os.path.dirname(__file__)
    frontend_path = os.path.join(backend_path, "..", "frontend")
    latest_mtime = get_latest_mtime([backend_path, frontend_path])
    return {"latest_mtime": latest_mtime}

# Mount static files
if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
