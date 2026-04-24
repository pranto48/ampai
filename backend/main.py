import os
import logging
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict, Tuple
from sqlalchemy import create_engine, MetaData, Table as SATable, Column, Integer, String, DateTime, Boolean, select, inspect, text
from cryptography.fernet import Fernet, InvalidToken
from langchain_community.chat_message_histories import SQLChatMessageHistory
from logging_utils import get_logger

# ----------------------------------------------------------------------
# Database URL: prefer explicit DATABASE_URL (Docker), otherwise fall back to
# SUPABASE_URL (used by Dyad preview).  If neither is set, use a safe default
# for local development.
# ----------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL") or "postgresql://ampai:ampai@db:5432/ampai"
CHAT_HISTORY_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")

engine = None
metadata = MetaData()
ENCRYPTED_PREFIX = "enc::"
logger = get_logger(__name__)

# The rest of the file remains unchanged...