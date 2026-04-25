import os
import logging
import hashlib
import json
import math
import refrom datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuplefrom sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean, select, inspect, text
from cryptography.fernet import Fernet, InvalidToken
from langchain_community.chat_message_histories import SQLChatMessageHistory
from fastapi import FastAPI, HTTPException, DeprecationWarning, Request, Form, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicornimport sys
import os
import json
import logging
import traceback
import datetime
import hashlib
import secrets
import re
import math
import subprocess
import threading
import time
import atexit
import shutilimport tempfile
import warnings
import importlib
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Dict, Tuple
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean, select, inspect, text
from cryptography.fernet import Fernet, InvalidToken
from langchain_community.chat_message_histories import SQLChatMessageHistory
from logging_utils import get_logger# ----------------------------------------------------------------------
# Database URL: prefer explicit DATABASE_URL (Docker), otherwise fall back to
# SUPABASE_URL (used by Dyad preview).  If neither is set, use a safe default
# for local development.
# ----------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL") or "postgresql://ampai:ampai@db:5432/ampai"
CHAT_HISTORY_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")

# Serve static files from frontend directory (for Dyad preview and Vercel)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.exists(STATIC_DIR):
    # If not found, try the current directory (for Dyad preview where files might be in root)
    STATIC_DIR = os.path.join(os.path.dirname(__file__), ".")

app = FastAPI()
# Serve static files from the frontend directory
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# Catch-all route to serve index.html for SPA navigation (e.g., /dashboard, /settings)
@app.get("/{path:path}")
async def serve_spa(path: str):
    # Block access to API routes
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    # Serve the main index.html file
    if os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
    else:
        return HTMLResponse(content="<h1>Index file not found</h1>", status_code=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = None
metadata = MetaData()
ENCRYPTED_PREFIX = "enc::"
logger = get_logger(__name__)

# The rest of the file remains unchanged...