import os
import logging
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Dict, Tuple
from sqlalchemy import create_engine, MetaData, Table as SATable, Column, Integer, String, DateTime, Boolean, select, inspect, text
from cryptography.fernet import Fernet, InvalidToken
from langchain_community.chat_message_histories import SQLChatMessageHistory
from logging_utils import get_logger

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")
CHAT_HISTORY_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")

engine = None
metadata = MetaData()
ENCRYPTED_PREFIX = "enc::"
logger = get_logger(__name__)


def Table(*args, **kwargs):
    kwargs.setdefault("extend_existing", True)
    return SATable(*args, **kwargs)

# LangChain SQLChatMessageHistory compatibility table.
message_store = Table(
    'message_store', metadata,
    Column('id', Integer, primary_key=True),
    Column('session_id', String),
    Column('message', String)
)

session_metadata = Table(
    'session_metadata', metadata,
    Column('session_id', String, primary_key=True),
    Column('category', String, default='Uncategorized'),
    Column('pinned', Boolean, default=False),
    Column('archived', Boolean, default=False),
    Column('updated_at', String, default=lambda: datetime.now(timezone.utc).isoformat())
)

app_configs = Table(
    'app_configs', metadata,
    Column('config_key', String, primary_key=True),
    Column('config_value', String)
)

backup_profiles = Table(
    "backup_profiles",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("include_database", Boolean, nullable=False, default=True),
    Column("include_uploads", Boolean, nullable=False, default=False),
    Column("include_configs", Boolean, nullable=False, default=False),
    Column("include_logs", Boolean, nullable=False, default=False),
    Column("destination_type", String, nullable=False, default="local"),
    Column("destination_path", String, nullable=True),
    Column("destination_host", String, nullable=True),
    Column("destination_port", Integer, nullable=True),
    Column("destination_username", String, nullable=True),
    Column("credential_key_ref", String, nullable=True),
    Column("schedule_cron", String, nullable=True),
    Column("schedule_interval_minutes", Integer, nullable=True),
    Column("retention_count", Integer, nullable=True),
    Column("retention_days", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

backup_jobs = Table(
    "backup_jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("profile_id", Integer, nullable=True),
    Column("status", String, nullable=False, default="queued"),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("bytes_written", Integer, nullable=False, default=0),
    Column("artifact_path", String, nullable=True),
    Column("verified", Boolean, nullable=False, default=False),
    Column("verification_error", String, nullable=True),
    Column("error_message", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

restore_jobs = Table(
    "restore_jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("status", String, nullable=False, default="queued"),
    Column("current_step", String, nullable=True),
    Column("progress_percent", Integer, nullable=False, default=0),
    Column("preflight_report", String, nullable=True),
    Column("snapshot_path", String, nullable=True),
    Column("result_summary", String, nullable=True),
    Column("log_lines", String, nullable=True),
    Column("error_message", String, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("created_by", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

core_memories = Table(
    'core_memories', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('fact', String)
)

memory_candidates = Table(
    "memory_candidates",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=False),
    Column("session_id", String, nullable=True),
    Column("candidate_text", String, nullable=False),
    Column("source_message_id", String, nullable=True),
    Column("source_offset", Integer, nullable=True),
    Column("confidence", String, nullable=True),
    Column("status", String, nullable=False, default="pending"),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
)

network_targets = Table(
    'network_targets', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('name', String),
    Column('ip_address', String)
)

media_assets = Table(
    "media_assets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=False),
    Column("session_id", String, nullable=True),
    Column("filename", String, nullable=False),
    Column("url", String, nullable=False),
    Column("mime_type", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

memory_groups = Table(
    "memory_groups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
    Column("created_by", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

memory_group_members = Table(
    "memory_group_members",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, nullable=False),
    Column("username", String, nullable=False),
)

memory_group_sessions = Table(
    "memory_group_sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, nullable=False),
    Column("session_id", String, nullable=False),
)

session_access = Table(
    "session_access",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("owner_username", String, nullable=False),
    Column("visibility", String, nullable=False, default="private"),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

tasks = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=False),
    Column("session_id", String, nullable=True),
    Column("filename", String, nullable=False),
    Column("url", String, nullable=False),
    Column("mime_type", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

memory_groups = Table(
    "memory_groups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=True),
    Column("created_by", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

memory_group_members = Table(
    "memory_group_members",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, nullable=False),
    Column("username", String, nullable=False),
)

memory_group_sessions = Table(
    "memory_group_sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("group_id", Integer, nullable=False),
    Column("session_id", String, nullable=False),
)

tasks = Table(
    'tasks', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('title', String),
    Column('description', String),
    Column('status', String, default='todo'),
    Column('priority', String, default='medium'),
    Column('due_at', String),
    Column('session_id', String),
    Column('created_at', String, default=lambda: datetime.now(timezone.utc).isoformat()),
    Column('updated_at', String, default=lambda: datetime.now(timezone.utc).isoformat())
)

users = Table(
    "users",
    metadata,
    Column("username", String, primary_key=True),
    Column("role", String, nullable=False, default="user"),
    Column("password_hash", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

users = Table(
    "users",
    metadata,
    Column("username", String, primary_key=True),
    Column("role", String, nullable=False, default="user"),
    Column("password_hash", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

users = Table(
    "users",
    metadata,
    Column("username", String, primary_key=True),
    Column("role", String, nullable=False, default="user"),
    Column("password_hash", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

telegram_identities = Table(
    "telegram_identities",
    metadata,
    Column("telegram_user_id", String, primary_key=True),
    Column("telegram_chat_id", String, nullable=True),
    Column("username", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

persona_presets = Table(
    "persona_presets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, nullable=True),
    Column("name", String, nullable=False),
    Column("system_prompt", String, nullable=False),
    Column("tags", String, nullable=True),
    Column("is_default", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

try:
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
except Exception:
    pass


def migrate_session_metadata_schema():
    if not engine:
        return
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if not inspector.has_table("session_metadata"):
                return
            columns = {col["name"] for col in inspector.get_columns("session_metadata")}
            if "pinned" not in columns:
                conn.execute(text("ALTER TABLE session_metadata ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"))
            if "archived" not in columns:
                conn.execute(text("ALTER TABLE session_metadata ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"))
            if "updated_at" not in columns:
                conn.execute(text("ALTER TABLE session_metadata ADD COLUMN updated_at TIMESTAMPTZ"))
                conn.execute(text("UPDATE session_metadata SET updated_at = NOW() WHERE updated_at IS NULL"))
            conn.commit()
    except Exception as e:
        print(f"Error migrating session metadata schema: {e}")


migrate_session_metadata_schema()


def migrate_memory_retrieval_indexes():
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memory_candidates_username ON memory_candidates (username)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memory_candidates_created_at ON memory_candidates (created_at DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memory_candidates_status ON memory_candidates (status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_session_metadata_category ON session_metadata (category)"))
            conn.commit()
    except Exception as e:
        print(f"Error creating memory retrieval indexes: {e}")


migrate_memory_retrieval_indexes()


def _load_fernet_keys() -> List[Fernet]:
    active_key = os.getenv("CONFIG_ENCRYPTION_KEY")
    previous_keys = os.getenv("CONFIG_ENCRYPTION_PREVIOUS_KEYS", "")

    keys = []
    if active_key:
        keys.append(active_key)
    if previous_keys:
        keys.extend([k.strip() for k in previous_keys.split(",") if k.strip()])

    fernets: List[Fernet] = []
    for key in keys:
        try:
            fernets.append(Fernet(key.encode()))
        except Exception:
            logger.warning("Invalid config encryption key provided; skipping key")
    return fernets


def encrypt_config_value(value: Optional[str]) -> str:
    """Encrypt app config values when CONFIG_ENCRYPTION_KEY is configured."""
    plain = "" if value is None else str(value)
    fernets = _load_fernet_keys()
    if not fernets:
        return plain
    try:
        token = fernets[0].encrypt(plain.encode("utf-8")).decode("utf-8")
        return f"{ENCRYPTED_PREFIX}{token}"
    except Exception as e:
        logger.warning(f"Failed encrypting config value: {e}")
        return plain


def decrypt_config_value(value: Optional[str]) -> str:
    """Decrypt config value if it is stored with the enc:: prefix."""
    if value is None:
        return ""
    raw = str(value)
    if not raw.startswith(ENCRYPTED_PREFIX):
        return raw
    token = raw[len(ENCRYPTED_PREFIX):]
    for fernet in _load_fernet_keys():
        try:
            return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            continue
        except Exception as e:
            logger.warning(f"Failed decrypting config value: {e}")
            break
    logger.warning("Could not decrypt config value; returning empty string")
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


try:
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
except Exception:
    pass


def get_sql_chat_history(session_id: str):
    """Compatibility helper used by older agent/main revisions."""
    return SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)


def _ensure_session_metadata_columns(conn):
    # Lightweight runtime migration for existing deployments.
    conn.execute(text("ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS updated_at VARCHAR"))
    conn.execute(text("ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS owner_username VARCHAR"))


def touch_session(session_id: str):
    if not engine:
        return
    try:
        with engine.connect() as conn:
            _ensure_session_metadata_columns(conn)
            upsert_stmt = text(
                "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at) "
                "VALUES (:s, :c, FALSE, FALSE, :u) "
                "ON CONFLICT (session_id) DO UPDATE SET updated_at = EXCLUDED.updated_at"
            )
            conn.execute(upsert_stmt, {"s": session_id, "c": "Uncategorized", "u": _now_iso()})
            conn.commit()
    except Exception as e:
        logger.warning(f"Error touching session: {e}")


def get_all_sessions(query: str = "", category: Optional[str] = None, archived: Optional[bool] = None):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if not inspector.has_table(CHAT_HISTORY_TABLE):
                return []

            session_rows = conn.execute(
                text(
                    f"SELECT DISTINCT session_id FROM {CHAT_HISTORY_TABLE} "
                    "WHERE session_id IS NOT NULL ORDER BY session_id ASC"
                )
            ).fetchall()
            session_ids = [row[0] for row in session_rows if row and row[0]]

            stmt_meta = select(
                session_metadata.c.session_id,
                session_metadata.c.category,
                session_metadata.c.pinned,
                session_metadata.c.archived,
                session_metadata.c.updated_at,
            )
            meta_map = {
                row[0]: {
                    "category": row[1] or "Uncategorized",
                    "pinned": bool(row[2]),
                    "archived": bool(row[3]),
                    "updated_at": row[4],
                }
                for row in conn.execute(stmt_meta)
            }

            output = []
            q = query.lower().strip()
            for s_id in session_ids:
                meta = meta_map.get(s_id, {
                    "category": "Uncategorized",
                    "pinned": False,
                    "archived": False,
                    "updated_at": None,
                })
                if archived is not None and meta["archived"] != bool(archived):
                    continue
                if q and q not in s_id.lower() and q not in meta["category"].lower():
                    continue
                if category and meta["category"] != category:
                    continue
                output.append({"session_id": s_id, **meta})

            output.sort(key=lambda x: (not x["pinned"], x.get("updated_at") or "", x["session_id"]), reverse=False)
            return output
    except Exception as e:
        logger.warning(f"Error fetching sessions: {e}")
        return []


def get_sql_chat_history(session_id: str) -> SQLChatMessageHistory:
    return SQLChatMessageHistory(
        session_id=session_id,
        connection_string=DATABASE_URL,
        table_name=CHAT_HISTORY_TABLE,
    )


def _parse_chat_payload(raw_message: str) -> Optional[Tuple[str, str]]:
    try:
        payload = json.loads(raw_message)
    except (TypeError, json.JSONDecodeError):
        return None

    msg_type = payload.get("type")
    content = ((payload.get("data") or {}).get("content")) if isinstance(payload, dict) else None
    if msg_type not in {"human", "ai"} or not isinstance(content, str):
        return None
    return msg_type, content


def list_chat_messages(session_id: str, dedupe: bool = True) -> List[Dict[str, str]]:
    """
    Read canonical SQL chat history with optional duplicate filtering.
    Duplicate key is (msg_type, content) within a session.
    """
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT message FROM {CHAT_HISTORY_TABLE} "
                    "WHERE session_id = :session_id ORDER BY id ASC"
                ),
                {"session_id": session_id},
            ).fetchall()

        messages: List[Dict[str, str]] = []
        seen = set()
        for (raw_message,) in rows:
            parsed = _parse_chat_payload(raw_message)
            if not parsed:
                continue
            msg_type, content = parsed
            fingerprint = (msg_type, content)
            if dedupe and fingerprint in seen:
                continue
            seen.add(fingerprint)
            messages.append({"type": msg_type, "content": content})
        return messages
    except Exception as e:
        logger.exception("Error listing chat messages", extra={"session_id": session_id}, exc_info=e)
        return []


def get_duplicate_message_counts() -> Dict[str, int]:
    if not engine:
        return {}
    duplicate_counts: Dict[str, int] = {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT session_id, message, COUNT(*) AS cnt "
                    f"FROM {CHAT_HISTORY_TABLE} "
                    "WHERE session_id IS NOT NULL "
                    "GROUP BY session_id, message HAVING COUNT(*) > 1"
                )
            ).fetchall()
        for session_id, _message, count in rows:
            duplicate_counts[session_id] = duplicate_counts.get(session_id, 0) + (int(count) - 1)
        return duplicate_counts
    except Exception as e:
        logger.exception("Error checking duplicate chat messages", exc_info=e)
        return {}

def set_session_category(session_id: str, category: str):
    return _upsert_session_metadata(session_id=session_id, category=category)


def set_session_pinned(session_id: str, value: bool):
    return _upsert_session_metadata(session_id=session_id, pinned=value)


def set_session_archived(session_id: str, value: bool):
    return _upsert_session_metadata(session_id=session_id, archived=value)


def touch_session_updated_at(session_id: str):
    return _upsert_session_metadata(session_id=session_id, touch_updated_at=True)


def set_session_pinned(session_id: str, pinned: bool):
    return _upsert_session_metadata(session_id, pinned=pinned, touch_updated_at=True)


def set_session_archived(session_id: str, archived: bool):
    return _upsert_session_metadata(session_id, archived=archived, touch_updated_at=True)


def touch_session_updated_at(session_id: str):
    return _upsert_session_metadata(session_id, touch_updated_at=True)


def set_session_flags(session_id: str, pinned: bool = None, archived: bool = None):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            _ensure_session_metadata_columns(conn)
            upsert_stmt = text(
                "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at) VALUES (:s, :c, FALSE, FALSE, :u) "
                "ON CONFLICT (session_id) DO UPDATE SET category = EXCLUDED.category, updated_at = EXCLUDED.updated_at"
            )
            conn.execute(upsert_stmt, {"s": session_id, "c": category, "u": _now_iso()})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error setting category: {e}")
        return False


def set_session_pinned(session_id: str, pinned: bool):
    return _upsert_session_metadata(session_id, pinned=pinned, touch_updated_at=True)


def set_session_archived(session_id: str, archived: bool):
    return _upsert_session_metadata(session_id, archived=archived, touch_updated_at=True)


def touch_session_updated_at(session_id: str):
    return _upsert_session_metadata(session_id, touch_updated_at=True)

def delete_session_metadata(session_id: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            del_stmt = text("DELETE FROM session_metadata WHERE session_id = :s")
            conn.execute(del_stmt, {"s": session_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error deleting session metadata: {e}")
        return False


def get_config(key: str, default=None):
    if not engine: return default
    try:
        with engine.connect() as conn:
            stmt = select(app_configs.c.config_value).where(app_configs.c.config_key == key)
            result = conn.execute(stmt).first()
            return decrypt_config_value(result[0]) if result else default
    except Exception as e:
        logger.warning(f"Error getting config {key}: {e}")
        return default


def set_config(key: str, value: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            upsert_stmt = text(
                "INSERT INTO app_configs (config_key, config_value) VALUES (:k, :v) "
                "ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value"
            )
            conn.execute(upsert_stmt, {"k": key, "v": encrypt_config_value(value)})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error setting config {key}: {e}")
        return False


def migrate_backup_profiles_schema() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS backup_profiles (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        include_database BOOLEAN NOT NULL DEFAULT TRUE,
                        include_uploads BOOLEAN NOT NULL DEFAULT FALSE,
                        include_configs BOOLEAN NOT NULL DEFAULT FALSE,
                        include_logs BOOLEAN NOT NULL DEFAULT FALSE,
                        destination_type VARCHAR NOT NULL DEFAULT 'local',
                        destination_path VARCHAR,
                        destination_host VARCHAR,
                        destination_port INTEGER,
                        destination_username VARCHAR,
                        credential_key_ref VARCHAR,
                        schedule_cron VARCHAR,
                        schedule_interval_minutes INTEGER,
                        retention_count INTEGER,
                        retention_days INTEGER,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Error migrating backup profiles schema: {e}")


migrate_backup_profiles_schema()


def migrate_backup_jobs_schema() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE backup_jobs ADD COLUMN IF NOT EXISTS verified BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.execute(text("ALTER TABLE backup_jobs ADD COLUMN IF NOT EXISTS verification_error VARCHAR"))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error migrating backup jobs schema: {e}")


migrate_backup_jobs_schema()


def migrate_restore_jobs_schema() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS restore_jobs (
                        id SERIAL PRIMARY KEY,
                        status VARCHAR NOT NULL DEFAULT 'queued',
                        current_step VARCHAR,
                        progress_percent INTEGER NOT NULL DEFAULT 0,
                        preflight_report TEXT,
                        snapshot_path VARCHAR,
                        result_summary TEXT,
                        log_lines TEXT,
                        error_message VARCHAR,
                        started_at TIMESTAMPTZ,
                        finished_at TIMESTAMPTZ,
                        created_by VARCHAR,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Error migrating restore jobs schema: {e}")


migrate_restore_jobs_schema()


def migrate_telegram_identities_schema() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_identities (
                        telegram_user_id VARCHAR PRIMARY KEY,
                        telegram_chat_id VARCHAR,
                        username VARCHAR NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_identities_username ON telegram_identities (username)"))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error migrating telegram identities schema: {e}")


migrate_telegram_identities_schema()


def get_or_create_telegram_user(telegram_user_id: Any, telegram_chat_id: Any = None, default_username: Optional[str] = None) -> Optional[str]:
    if not engine:
        return default_username
    user_id = str(telegram_user_id or "").strip()
    if not user_id:
        return default_username
    chat_id = str(telegram_chat_id).strip() if telegram_chat_id is not None else None
    fallback_username = (default_username or f"telegram-{user_id}").strip()
    if not fallback_username:
        fallback_username = f"telegram-{user_id}"
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT username FROM telegram_identities WHERE telegram_user_id = :uid"),
                {"uid": user_id},
            ).scalar()
            if existing:
                conn.execute(
                    text(
                        "UPDATE telegram_identities SET telegram_chat_id = :chat_id, updated_at = NOW() "
                        "WHERE telegram_user_id = :uid"
                    ),
                    {"uid": user_id, "chat_id": chat_id},
                )
                conn.commit()
                return str(existing)

            conn.execute(
                text(
                    "INSERT INTO telegram_identities (telegram_user_id, telegram_chat_id, username, created_at, updated_at) "
                    "VALUES (:uid, :chat_id, :username, NOW(), NOW())"
                ),
                {"uid": user_id, "chat_id": chat_id, "username": fallback_username},
            )
            conn.commit()
            return fallback_username
    except Exception as e:
        logger.warning(f"Error upserting telegram user identity: {e}")
        return fallback_username


def lookup_username_by_telegram_user_id(telegram_user_id: Any) -> Optional[str]:
    if not engine:
        return None
    user_id = str(telegram_user_id or "").strip()
    if not user_id:
        return None
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT username FROM telegram_identities WHERE telegram_user_id = :uid"),
                {"uid": user_id},
            ).scalar()
            return str(result) if result else None
    except Exception as e:
        logger.warning(f"Error looking up telegram user identity: {e}")
        return None


def list_backup_profiles() -> List[Dict[str, Any]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            stmt = text(
                """
                SELECT id, name, enabled, include_database, include_uploads, include_configs, include_logs,
                       destination_type, destination_path, destination_host, destination_port,
                       destination_username, credential_key_ref, schedule_cron, schedule_interval_minutes,
                       retention_count, retention_days, created_at, updated_at
                FROM backup_profiles
                ORDER BY id DESC
                """
            )
            rows = conn.execute(stmt).fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "enabled": bool(row[2]),
                    "include_database": bool(row[3]),
                    "include_uploads": bool(row[4]),
                    "include_configs": bool(row[5]),
                    "include_logs": bool(row[6]),
                    "destination_type": row[7] or "local",
                    "destination_path": row[8] or "",
                    "destination_host": row[9] or "",
                    "destination_port": row[10],
                    "destination_username": row[11] or "",
                    "credential_key_ref": row[12] or "",
                    "schedule_cron": row[13] or "",
                    "schedule_interval_minutes": row[14],
                    "retention_count": row[15],
                    "retention_days": row[16],
                    "created_at": row[17].isoformat() if getattr(row[17], "isoformat", None) else str(row[17] or ""),
                    "updated_at": row[18].isoformat() if getattr(row[18], "isoformat", None) else str(row[18] or ""),
                }
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Error listing backup profiles: {e}")
        return []


def create_backup_profile(payload: Dict[str, Any]) -> Optional[int]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            stmt = text(
                """
                INSERT INTO backup_profiles (
                    name, enabled, include_database, include_uploads, include_configs, include_logs,
                    destination_type, destination_path, destination_host, destination_port,
                    destination_username, credential_key_ref, schedule_cron, schedule_interval_minutes,
                    retention_count, retention_days, created_at, updated_at
                ) VALUES (
                    :name, :enabled, :include_database, :include_uploads, :include_configs, :include_logs,
                    :destination_type, :destination_path, :destination_host, :destination_port,
                    :destination_username, :credential_key_ref, :schedule_cron, :schedule_interval_minutes,
                    :retention_count, :retention_days, NOW(), NOW()
                )
                RETURNING id
                """
            )
            profile_id = conn.execute(stmt, payload).scalar()
            conn.commit()
            return int(profile_id) if profile_id is not None else None
    except Exception as e:
        logger.warning(f"Error creating backup profile: {e}")
        return None


def update_backup_profile(profile_id: int, payload: Dict[str, Any]) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            stmt = text(
                """
                UPDATE backup_profiles
                SET name=:name,
                    enabled=:enabled,
                    include_database=:include_database,
                    include_uploads=:include_uploads,
                    include_configs=:include_configs,
                    include_logs=:include_logs,
                    destination_type=:destination_type,
                    destination_path=:destination_path,
                    destination_host=:destination_host,
                    destination_port=:destination_port,
                    destination_username=:destination_username,
                    credential_key_ref=:credential_key_ref,
                    schedule_cron=:schedule_cron,
                    schedule_interval_minutes=:schedule_interval_minutes,
                    retention_count=:retention_count,
                    retention_days=:retention_days,
                    updated_at=NOW()
                WHERE id=:id
                """
            )
            result = conn.execute(stmt, {**payload, "id": profile_id})
            conn.commit()
            return (result.rowcount or 0) > 0
    except Exception as e:
        logger.warning(f"Error updating backup profile: {e}")
        return False


def delete_backup_profile(profile_id: int) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM backup_profiles WHERE id = :id"), {"id": profile_id})
            conn.commit()
            return (result.rowcount or 0) > 0
    except Exception as e:
        logger.warning(f"Error deleting backup profile: {e}")
        return False


def get_backup_profile(profile_id: int) -> Optional[Dict[str, Any]]:
    rows = [p for p in list_backup_profiles() if p.get("id") == profile_id]
    return rows[0] if rows else None


def create_backup_job(profile_id: Optional[int], status: str = "queued") -> Optional[int]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            job_id = conn.execute(
                text(
                    """
                    INSERT INTO backup_jobs (profile_id, status, created_at)
                    VALUES (:profile_id, :status, NOW())
                    RETURNING id
                    """
                ),
                {"profile_id": profile_id, "status": status},
            ).scalar()
            conn.commit()
            return int(job_id) if job_id is not None else None
    except Exception as e:
        logger.warning(f"Error creating backup job: {e}")
        return None


def update_backup_job(job_id: int, **updates: Any) -> bool:
    if not engine:
        return False
    allowed = {"status", "started_at", "finished_at", "bytes_written", "artifact_path", "verified", "verification_error", "error_message"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return False
    set_sql = ", ".join([f"{k} = :{k}" for k in fields.keys()])
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"UPDATE backup_jobs SET {set_sql} WHERE id = :id"),
                {"id": job_id, **fields},
            )
            conn.commit()
            return (result.rowcount or 0) > 0
    except Exception as e:
        logger.warning(f"Error updating backup job {job_id}: {e}")
        return False


def list_backup_jobs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    if not engine:
        return []
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, profile_id, status, started_at, finished_at, bytes_written,
                           artifact_path, verified, verification_error, error_message, created_at
                    FROM backup_jobs
                    ORDER BY id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": safe_limit, "offset": safe_offset},
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "profile_id": row[1],
                    "status": row[2],
                    "started_at": row[3].isoformat() if getattr(row[3], "isoformat", None) else None,
                    "finished_at": row[4].isoformat() if getattr(row[4], "isoformat", None) else None,
                    "bytes_written": int(row[5] or 0),
                    "artifact_path": row[6] or "",
                    "verified": bool(row[7]),
                    "verification_error": row[8] or "",
                    "error_message": row[9] or "",
                    "created_at": row[10].isoformat() if getattr(row[10], "isoformat", None) else str(row[10] or ""),
                }
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Error listing backup jobs: {e}")
        return []


def get_backup_job(job_id: int) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, profile_id, status, started_at, finished_at, bytes_written,
                           artifact_path, verified, verification_error, error_message, created_at
                    FROM backup_jobs
                    WHERE id = :id
                    """
                ),
                {"id": job_id},
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "profile_id": row[1],
                "status": row[2],
                "started_at": row[3].isoformat() if getattr(row[3], "isoformat", None) else None,
                "finished_at": row[4].isoformat() if getattr(row[4], "isoformat", None) else None,
                "bytes_written": int(row[5] or 0),
                "artifact_path": row[6] or "",
                "verified": bool(row[7]),
                "verification_error": row[8] or "",
                "error_message": row[9] or "",
                "created_at": row[10].isoformat() if getattr(row[10], "isoformat", None) else str(row[10] or ""),
            }
    except Exception as e:
        logger.warning(f"Error getting backup job {job_id}: {e}")
        return None


def get_backup_verification_kpis() -> Dict[str, Any]:
    if not engine:
        return {
            "last_successful_backup": None,
            "last_successful_restore_test": None,
            "backup_success_rate_7d": 0.0,
            "backup_success_rate_30d": 0.0,
        }
    try:
        with engine.connect() as conn:
            last_successful_backup = conn.execute(
                text("SELECT MAX(finished_at) FROM backup_jobs WHERE status = 'success'")
            ).scalar()
            last_successful_restore_test = conn.execute(
                text("SELECT MAX(finished_at) FROM backup_jobs WHERE status = 'success' AND verified = TRUE")
            ).scalar()
            counts_7d = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                        COUNT(*) AS total_count
                    FROM backup_jobs
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    """
                )
            ).fetchone()
            counts_30d = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'success') AS success_count,
                        COUNT(*) AS total_count
                    FROM backup_jobs
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    """
                )
            ).fetchone()
            s7 = int((counts_7d[0] if counts_7d else 0) or 0)
            t7 = int((counts_7d[1] if counts_7d else 0) or 0)
            s30 = int((counts_30d[0] if counts_30d else 0) or 0)
            t30 = int((counts_30d[1] if counts_30d else 0) or 0)
            return {
                "last_successful_backup": last_successful_backup.isoformat() if getattr(last_successful_backup, "isoformat", None) else None,
                "last_successful_restore_test": last_successful_restore_test.isoformat() if getattr(last_successful_restore_test, "isoformat", None) else None,
                "backup_success_rate_7d": round((s7 / t7) * 100.0, 2) if t7 else 0.0,
                "backup_success_rate_30d": round((s30 / t30) * 100.0, 2) if t30 else 0.0,
            }
    except Exception as e:
        logger.warning(f"Error getting backup verification kpis: {e}")
        return {
            "last_successful_backup": None,
            "last_successful_restore_test": None,
            "backup_success_rate_7d": 0.0,
            "backup_success_rate_30d": 0.0,
        }


def create_restore_job(created_by: str, preflight_report: Dict[str, Any], status: str = "queued") -> Optional[int]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            job_id = conn.execute(
                text(
                    """
                    INSERT INTO restore_jobs (status, current_step, progress_percent, preflight_report, log_lines, created_by, created_at)
                    VALUES (:status, :current_step, :progress_percent, :preflight_report, :log_lines, :created_by, NOW())
                    RETURNING id
                    """
                ),
                {
                    "status": status,
                    "current_step": "queued",
                    "progress_percent": 0,
                    "preflight_report": json.dumps(preflight_report or {}),
                    "log_lines": json.dumps([]),
                    "created_by": created_by,
                },
            ).scalar()
            conn.commit()
            return int(job_id) if job_id is not None else None
    except Exception as e:
        logger.warning(f"Error creating restore job: {e}")
        return None


def update_restore_job(job_id: int, **updates: Any) -> bool:
    if not engine:
        return False
    allowed = {
        "status",
        "current_step",
        "progress_percent",
        "preflight_report",
        "snapshot_path",
        "result_summary",
        "log_lines",
        "error_message",
        "started_at",
        "finished_at",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return False
    normalized = {}
    for key, value in fields.items():
        if key in {"preflight_report", "result_summary", "log_lines"} and value is not None and not isinstance(value, str):
            normalized[key] = json.dumps(value)
        else:
            normalized[key] = value
    set_sql = ", ".join([f"{k} = :{k}" for k in normalized.keys()])
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"UPDATE restore_jobs SET {set_sql} WHERE id = :id"),
                {"id": job_id, **normalized},
            )
            conn.commit()
            return (result.rowcount or 0) > 0
    except Exception as e:
        logger.warning(f"Error updating restore job {job_id}: {e}")
        return False


def _parse_json_text(raw: Any, fallback: Any):
    if raw is None:
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def list_restore_jobs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    if not engine:
        return []
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, status, current_step, progress_percent, preflight_report, snapshot_path,
                           result_summary, log_lines, error_message, started_at, finished_at, created_by, created_at
                    FROM restore_jobs
                    ORDER BY id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": safe_limit, "offset": safe_offset},
            ).fetchall()
            return [
                {
                    "id": row[0],
                    "status": row[1],
                    "current_step": row[2] or "",
                    "progress_percent": int(row[3] or 0),
                    "preflight_report": _parse_json_text(row[4], {}),
                    "snapshot_path": row[5] or "",
                    "result_summary": _parse_json_text(row[6], {}),
                    "log_lines": _parse_json_text(row[7], []),
                    "error_message": row[8] or "",
                    "started_at": row[9].isoformat() if getattr(row[9], "isoformat", None) else None,
                    "finished_at": row[10].isoformat() if getattr(row[10], "isoformat", None) else None,
                    "created_by": row[11] or "",
                    "created_at": row[12].isoformat() if getattr(row[12], "isoformat", None) else str(row[12] or ""),
                }
                for row in rows
            ]
    except Exception as e:
        logger.warning(f"Error listing restore jobs: {e}")
        return []


def get_restore_job(job_id: int) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, status, current_step, progress_percent, preflight_report, snapshot_path,
                           result_summary, log_lines, error_message, started_at, finished_at, created_by, created_at
                    FROM restore_jobs
                    WHERE id = :id
                    """
                ),
                {"id": job_id},
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "status": row[1],
                "current_step": row[2] or "",
                "progress_percent": int(row[3] or 0),
                "preflight_report": _parse_json_text(row[4], {}),
                "snapshot_path": row[5] or "",
                "result_summary": _parse_json_text(row[6], {}),
                "log_lines": _parse_json_text(row[7], []),
                "error_message": row[8] or "",
                "started_at": row[9].isoformat() if getattr(row[9], "isoformat", None) else None,
                "finished_at": row[10].isoformat() if getattr(row[10], "isoformat", None) else None,
                "created_by": row[11] or "",
                "created_at": row[12].isoformat() if getattr(row[12], "isoformat", None) else str(row[12] or ""),
            }
    except Exception as e:
        logger.warning(f"Error getting restore job {job_id}: {e}")
        return None


def get_all_configs():
    if not engine: return {}
    try:
        with engine.connect() as conn:
            if not inspect(engine).has_table("app_configs"):
                return {}
            stmt = select(app_configs.c.config_key, app_configs.c.config_value)
            return {row[0]: decrypt_config_value(row[1]) for row in conn.execute(stmt)}
    except Exception as e:
        logger.warning(f"Error getting all configs: {e}")
        return {}


def add_core_memory(fact: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO core_memories (fact) VALUES (:f)"), {"f": fact})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error adding core memory: {e}")
        return False


def get_core_memories():
    if not engine: return []
    try:
        with engine.connect() as conn:
            if not inspect(engine).has_table("core_memories"):
                return []
            stmt = select(core_memories.c.id, core_memories.c.fact)
            return [{"id": row[0], "fact": row[1]} for row in conn.execute(stmt)]
    except Exception as e:
        logger.warning(f"Error getting core memories: {e}")
        return []


def delete_core_memory(mem_id: int):
    if not engine: return False
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM core_memories WHERE id = :id"), {"id": mem_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error deleting core memory: {e}")
        return False


def update_core_memory(mem_id: int, fact: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE core_memories SET fact = :f WHERE id = :id"),
                {"f": fact, "id": mem_id}
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.warning(f"Error updating core memory {mem_id}: {e}")
        return False


def get_network_targets():
    if not engine: return []
    try:
        with engine.connect() as conn:
            if not inspect(engine).has_table("network_targets"):
                return []
            stmt = select(network_targets.c.id, network_targets.c.name, network_targets.c.ip_address)
            return [{"id": row[0], "name": row[1], "ip_address": row[2]} for row in conn.execute(stmt)]
    except Exception as e:
        logger.warning(f"Error getting network targets: {e}")
        return []


def add_network_target(name: str, ip_address: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO network_targets (name, ip_address) VALUES (:n, :i)"), {"n": name, "i": ip_address})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error adding network target: {e}")
        return False


def delete_network_target(target_id: int):
    if not engine: return False
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM network_targets WHERE id = :id"), {"id": target_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error deleting network target: {e}")
        return False


def create_task(title: str, description: str = "", priority: str = "medium", due_at: str = None, session_id: str = None):
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            now = _now_iso()
            stmt = text(
                "INSERT INTO tasks (title, description, status, priority, due_at, session_id, created_at, updated_at) "
                "VALUES (:t, :d, 'todo', :p, :due, :sid, :c, :u) RETURNING id"
            )
            res = conn.execute(stmt, {"t": title, "d": description, "p": priority, "due": due_at, "sid": session_id, "c": now, "u": now})
            task_id = res.scalar()
            conn.commit()
            return task_id
    except Exception as e:
        logger.warning(f"Error creating task: {e}")
        return None


def list_tasks(status: str = None):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            query = select(tasks)
            if status:
                query = query.where(tasks.c.status == status)
            rows = conn.execute(query).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.warning(f"Error listing tasks: {e}")
        return []


def update_task(task_id: int, updates: dict):
    if not engine:
        return False
    try:
        allowed = {"title", "description", "status", "priority", "due_at", "session_id"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not safe_updates:
            return False
        safe_updates["updated_at"] = _now_iso()
        set_clause = ", ".join([f"{k} = :{k}" for k in safe_updates.keys()])
        safe_updates["id"] = task_id
        with engine.connect() as conn:
            conn.execute(text(f"UPDATE tasks SET {set_clause} WHERE id = :id"), safe_updates)
            conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Error updating task: {e}")
        return False


def delete_task(task_id: int):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error deleting task: {e}")
        return False



def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_user(username: str, password: str, role: str = 'user'):
    if not engine:
        return False, 'db_unavailable'
    username = (username or '').strip()
    if not username or not password:
        return False, 'username_password_required'
    if len(password) < 4:
        return False, 'password_too_short'
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM users WHERE username = :u LIMIT 1"),
                {"u": username},
            ).first()
            if existing:
                return False, 'username_exists'
            conn.execute(
                text(
                    "INSERT INTO users (username, password_hash, role, created_at, updated_at) "
                    "VALUES (:u, :p, :r, :c, :u2)"
                ),
                {'u': username, 'p': _hash_password(password), 'r': role, 'c': _now_iso(), 'u2': _now_iso()}
            )
            conn.commit()
            return True, 'created'
    except Exception as e:
        logger.warning(f"Error creating user: {e}")
        return False, 'create_failed'


def ensure_default_admin(username: str, password: str):
    return create_user(username=username, password=password, role='admin')


def verify_user_credentials(username: str, password: str):
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, password_hash, role FROM users WHERE username = :username"
                ),
                {"username": username},
            ).first()
            if not row:
                return None
            if row[1] != _hash_password(password):
                return None
            return {'id': 0, 'username': row[0], 'role': row[2]}
    except Exception as e:
        logger.warning(f"Error verifying user credentials: {e}")
        return None


def list_users():
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(select(users.c.id, users.c.username, users.c.role, users.c.created_at)).fetchall()
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.warning(f"Error listing users: {e}")
        return []


def set_user_role(user_id: int, role: str):
    if not engine:
        return False
    if role not in {'admin', 'user'}:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text('UPDATE users SET role = :r WHERE id = :id'), {'r': role, 'id': user_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error setting user role: {e}")
        return False


def delete_user(user_id: int):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text('DELETE FROM users WHERE id = :id'), {'id': user_id})
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error deleting user: {e}")
        return False


def ensure_default_users(default_users: List[Dict[str, str]]) -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            for entry in default_users:
                username = (entry.get("username") or "").strip()
                role = (entry.get("role") or "user").strip().lower()
                password_hash = entry.get("password_hash")
                if not username or role not in {"admin", "user"} or not password_hash:
                    continue
                conn.execute(
                    text(
                        "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                        "VALUES (:username, :role, :password_hash, NOW(), NOW()) "
                        "ON CONFLICT (username) DO NOTHING"
                    ),
                    {"username": username, "role": role, "password_hash": password_hash},
                )
            conn.commit()
    except Exception as e:
        logger.exception("Error ensuring default users", exc_info=e)


def get_user(username: str) -> Optional[Dict[str, str]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, role, password_hash, created_at, updated_at "
                    "FROM users WHERE username = :username"
                ),
                {"username": username},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Error fetching user", extra={"username": username}, exc_info=e)
        return None


def list_users() -> List[Dict[str, str]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT username, role, created_at, updated_at "
                    "FROM users ORDER BY username ASC"
                )
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error listing users", exc_info=e)
        return []


def create_user(username: str, role: str, password_hash: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                    "VALUES (:username, :role, :password_hash, NOW(), NOW())"
                ),
                {"username": username, "role": role, "password_hash": password_hash},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error creating user", extra={"username": username}, exc_info=e)
        return False


def update_user(username: str, role: Optional[str] = None, password_hash: Optional[str] = None) -> bool:
    if not engine:
        return False
    if role is None and password_hash is None:
        return True
    try:
        params = {"username": username}
        set_parts = ["updated_at = NOW()"]
        if role is not None:
            set_parts.append("role = :role")
            params["role"] = role
        if password_hash is not None:
            set_parts.append("password_hash = :password_hash")
            params["password_hash"] = password_hash

        with engine.connect() as conn:
            result = conn.execute(
                text(f"UPDATE users SET {', '.join(set_parts)} WHERE username = :username"),
                params,
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error updating user", extra={"username": username}, exc_info=e)
        return False


def delete_user(username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM users WHERE username = :username"), {"username": username})
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error deleting user", extra={"username": username}, exc_info=e)
        return False


def ensure_default_users(default_users: List[Dict[str, str]]) -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            for entry in default_users:
                username = (entry.get("username") or "").strip()
                role = (entry.get("role") or "user").strip().lower()
                password_hash = entry.get("password_hash")
                if not username or role not in {"admin", "user"} or not password_hash:
                    continue
                conn.execute(
                    text(
                        "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                        "VALUES (:username, :role, :password_hash, NOW(), NOW()) "
                        "ON CONFLICT (username) DO NOTHING"
                    ),
                    {"username": username, "role": role, "password_hash": password_hash},
                )
            conn.commit()
    except Exception as e:
        logger.exception("Error ensuring default users", exc_info=e)


def get_user(username: str) -> Optional[Dict[str, str]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, role, password_hash, created_at, updated_at "
                    "FROM users WHERE username = :username"
                ),
                {"username": username},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Error fetching user", extra={"username": username}, exc_info=e)
        return None


def list_users() -> List[Dict[str, str]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT username, role, created_at, updated_at "
                    "FROM users ORDER BY username ASC"
                )
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error listing users", exc_info=e)
        return []


def create_user(username: str, role: str, password_hash: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                    "VALUES (:username, :role, :password_hash, NOW(), NOW())"
                ),
                {"username": username, "role": role, "password_hash": password_hash},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error creating user", extra={"username": username}, exc_info=e)
        return False


def update_user(username: str, role: Optional[str] = None, password_hash: Optional[str] = None) -> bool:
    if not engine:
        return False
    if role is None and password_hash is None:
        return True
    try:
        params = {"username": username}
        set_parts = ["updated_at = NOW()"]
        if role is not None:
            set_parts.append("role = :role")
            params["role"] = role
        if password_hash is not None:
            set_parts.append("password_hash = :password_hash")
            params["password_hash"] = password_hash

        with engine.connect() as conn:
            result = conn.execute(
                text(f"UPDATE users SET {', '.join(set_parts)} WHERE username = :username"),
                params,
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error updating user", extra={"username": username}, exc_info=e)
        return False


def delete_user(username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM users WHERE username = :username"), {"username": username})
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error deleting user", extra={"username": username}, exc_info=e)
        return False


def create_memory_group(name: str, description: str, created_by: str):
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            group_id = conn.execute(
                text(
                    "INSERT INTO memory_groups (name, description, created_by, created_at) "
                    "VALUES (:name, :description, :created_by, NOW()) RETURNING id"
                ),
                {"name": name, "description": description, "created_by": created_by},
            ).scalar()
            conn.execute(
                text("INSERT INTO memory_group_members (group_id, username) VALUES (:group_id, :username)"),
                {"group_id": group_id, "username": created_by},
            )
            conn.commit()
            return group_id
    except Exception as e:
        logger.exception("Error creating memory group", exc_info=e)
        return None


def add_user_to_memory_group(group_id: int, username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO memory_group_members (group_id, username) "
                    "SELECT :group_id, :username "
                    "WHERE NOT EXISTS (SELECT 1 FROM memory_group_members WHERE group_id = :group_id AND username = :username)"
                ),
                {"group_id": group_id, "username": username},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding user to memory group", exc_info=e)
        return False


def share_session_to_group(group_id: int, session_id: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO memory_group_sessions (group_id, session_id) "
                    "SELECT :group_id, :session_id "
                    "WHERE NOT EXISTS (SELECT 1 FROM memory_group_sessions WHERE group_id = :group_id AND session_id = :session_id)"
                ),
                {"group_id": group_id, "session_id": session_id},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error sharing session to group", exc_info=e)
        return False


def list_memory_groups_for_user(username: str):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT g.id, g.name, g.description, g.created_by, g.created_at "
                    "FROM memory_groups g "
                    "JOIN memory_group_members m ON m.group_id = g.id "
                    "WHERE m.username = :username "
                    "ORDER BY g.id DESC"
                ),
                {"username": username},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.exception("Error listing memory groups", exc_info=e)
        return []


def list_shared_sessions_for_user(username: str):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT s.session_id "
                    "FROM memory_group_sessions s "
                    "JOIN memory_group_members m ON m.group_id = s.group_id "
                    "WHERE m.username = :username ORDER BY s.session_id"
                ),
                {"username": username},
            ).fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.exception("Error listing shared sessions", exc_info=e)
        return []


def memory_group_exists(group_id: int) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM memory_groups WHERE id = :group_id"), {"group_id": group_id}).first()
            return bool(exists)
    except Exception as e:
        logger.exception("Error checking memory group", exc_info=e)
        return False


def session_exists(session_id: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(f"SELECT 1 FROM {CHAT_HISTORY_TABLE} WHERE session_id = :session_id LIMIT 1"),
                {"session_id": session_id},
            ).first()
            return bool(exists)
    except Exception as e:
        logger.exception("Error checking session existence", exc_info=e)
        return False


def get_session_owner(session_id: str) -> Optional[str]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT owner_username FROM session_access WHERE session_id = :session_id"),
                {"session_id": session_id},
            ).first()
            return row[0] if row and row[0] else None
    except Exception:
        return None


def set_session_owner(session_id: str, owner_username: str, visibility: str = "private") -> bool:
    if not engine:
        return False
    try:
        vis = visibility if visibility in {"private", "shared"} else "private"
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO session_access (session_id, owner_username, visibility, created_at, updated_at)
                    VALUES (:session_id, :owner_username, :visibility, NOW(), NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        owner_username = EXCLUDED.owner_username,
                        visibility = EXCLUDED.visibility,
                        updated_at = NOW()
                    """
                ),
                {"session_id": session_id, "owner_username": owner_username, "visibility": vis},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error setting session owner", exc_info=e)
        return False


def ensure_session_owner(session_id: str, owner_username: str) -> bool:
    if get_session_owner(session_id):
        return True
    return set_session_owner(session_id=session_id, owner_username=owner_username, visibility="private")


def get_accessible_session_ids(username: str, is_admin: bool = False) -> List[str]:
    if not engine:
        return []
    if is_admin:
        try:
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT session_id FROM session_access")).fetchall()
                return [r[0] for r in rows if r and r[0]]
        except Exception:
            return []
    try:
        shared_ids = set(list_shared_sessions_for_user(username))
        with engine.connect() as conn:
            own_rows = conn.execute(
                text("SELECT session_id FROM session_access WHERE owner_username = :username"),
                {"username": username},
            ).fetchall()
            own_ids = {r[0] for r in own_rows if r and r[0]}
            return sorted(own_ids.union(shared_ids))
    except Exception:
        return []


def user_can_access_session(session_id: str, username: str, role: str = "user") -> bool:
    if role == "admin":
        return True
    accessible_ids = set(get_accessible_session_ids(username=username, is_admin=False))
    return session_id in accessible_ids


def memory_group_membership_exists(group_id: int, username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM memory_group_members "
                    "WHERE group_id = :group_id AND username = :username"
                ),
                {"group_id": group_id, "username": username},
            ).first()
            return bool(exists)
    except Exception as e:
        logger.exception("Error checking memory group membership", exc_info=e)
        return False


def memory_group_session_share_exists(group_id: int, session_id: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM memory_group_sessions "
                    "WHERE group_id = :group_id AND session_id = :session_id"
                ),
                {"group_id": group_id, "session_id": session_id},
            ).first()
            return bool(exists)
    except Exception as e:
        logger.exception("Error checking memory group session share", exc_info=e)
        return False


def get_memory_group_members(group_id: int):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT username FROM memory_group_members "
                    "WHERE group_id = :group_id ORDER BY username"
                ),
                {"group_id": group_id},
            ).fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.exception("Error listing memory group members", exc_info=e)
        return []


def get_memory_group_sessions(group_id: int):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT session_id FROM memory_group_sessions "
                    "WHERE group_id = :group_id ORDER BY session_id"
                ),
                {"group_id": group_id},
            ).fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.exception("Error listing memory group sessions", exc_info=e)
        return []


def remove_user_from_memory_group(group_id: int, username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM memory_group_members "
                    "WHERE group_id = :group_id AND username = :username"
                ),
                {"group_id": group_id, "username": username},
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error removing memory group member", exc_info=e)
        return False


def unshare_session_from_group(group_id: int, session_id: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "DELETE FROM memory_group_sessions "
                    "WHERE group_id = :group_id AND session_id = :session_id"
                ),
                {"group_id": group_id, "session_id": session_id},
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error unsharing memory group session", exc_info=e)
        return False


def add_media_asset(username: str, session_id: Optional[str], filename: str, url: str, mime_type: Optional[str]) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO media_assets (username, session_id, filename, url, mime_type, created_at) "
                    "VALUES (:username, :session_id, :filename, :url, :mime_type, NOW())"
                ),
                {
                    "username": username,
                    "session_id": session_id,
                    "filename": filename,
                    "url": url,
                    "mime_type": mime_type,
                },
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding media asset", exc_info=e)
        return False


def ensure_default_users(default_users: List[Dict[str, str]]) -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            for entry in default_users:
                username = (entry.get("username") or "").strip()
                role = (entry.get("role") or "user").strip().lower()
                password_hash = entry.get("password_hash")
                if not username or role not in {"admin", "user"} or not password_hash:
                    continue
                conn.execute(
                    text(
                        "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                        "VALUES (:username, :role, :password_hash, NOW(), NOW()) "
                        "ON CONFLICT (username) DO NOTHING"
                    ),
                    {"username": username, "role": role, "password_hash": password_hash},
                )
            conn.commit()
    except Exception as e:
        logger.exception("Error ensuring default users", exc_info=e)


def get_user(username: str) -> Optional[Dict[str, str]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, role, password_hash, created_at, updated_at "
                    "FROM users WHERE username = :username"
                ),
                {"username": username},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Error fetching user", extra={"username": username}, exc_info=e)
        return None


def list_users() -> List[Dict[str, str]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT username, role, created_at, updated_at "
                    "FROM users ORDER BY username ASC"
                )
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error listing users", exc_info=e)
        return []


def create_user(username: str, role: str, password_hash: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                    "VALUES (:username, :role, :password_hash, NOW(), NOW())"
                ),
                {"username": username, "role": role, "password_hash": password_hash},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error creating user", extra={"username": username}, exc_info=e)
        return False


def update_user(username: str, role: Optional[str] = None, password_hash: Optional[str] = None) -> bool:
    if not engine:
        return False
    if role is None and password_hash is None:
        return True
    try:
        params = {"username": username}
        set_parts = ["updated_at = NOW()"]
        if role is not None:
            set_parts.append("role = :role")
            params["role"] = role
        if password_hash is not None:
            set_parts.append("password_hash = :password_hash")
            params["password_hash"] = password_hash

        with engine.connect() as conn:
            result = conn.execute(
                text(f"UPDATE users SET {', '.join(set_parts)} WHERE username = :username"),
                params,
            )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error updating user", extra={"username": username}, exc_info=e)
        return False


def delete_user(username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM users WHERE username = :username"), {"username": username})
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error deleting user", extra={"username": username}, exc_info=e)
        return False


def create_memory_group(name: str, description: str, created_by: str):
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            group_id = conn.execute(
                text(
                    "INSERT INTO memory_groups (name, description, created_by, created_at) "
                    "VALUES (:name, :description, :created_by, NOW()) RETURNING id"
                ),
                {"name": name, "description": description, "created_by": created_by},
            ).scalar()
            conn.execute(
                text("INSERT INTO memory_group_members (group_id, username) VALUES (:group_id, :username)"),
                {"group_id": group_id, "username": created_by},
            )
            conn.commit()
            return group_id
    except Exception as e:
        logger.exception("Error creating memory group", exc_info=e)
        return None


def add_user_to_memory_group(group_id: int, username: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO memory_group_members (group_id, username) "
                    "SELECT :group_id, :username "
                    "WHERE NOT EXISTS (SELECT 1 FROM memory_group_members WHERE group_id = :group_id AND username = :username)"
                ),
                {"group_id": group_id, "username": username},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding user to memory group", exc_info=e)
        return False


def share_session_to_group(group_id: int, session_id: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO memory_group_sessions (group_id, session_id) "
                    "SELECT :group_id, :session_id "
                    "WHERE NOT EXISTS (SELECT 1 FROM memory_group_sessions WHERE group_id = :group_id AND session_id = :session_id)"
                ),
                {"group_id": group_id, "session_id": session_id},
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error sharing session to group", exc_info=e)
        return False


def list_memory_groups_for_user(username: str):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT g.id, g.name, g.description, g.created_by, g.created_at "
                    "FROM memory_groups g "
                    "JOIN memory_group_members m ON m.group_id = g.id "
                    "WHERE m.username = :username "
                    "ORDER BY g.id DESC"
                ),
                {"username": username},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.exception("Error listing memory groups", exc_info=e)
        return []


def list_shared_sessions_for_user(username: str):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT s.session_id "
                    "FROM memory_group_sessions s "
                    "JOIN memory_group_members m ON m.group_id = s.group_id "
                    "WHERE m.username = :username ORDER BY s.session_id"
                ),
                {"username": username},
            ).fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.exception("Error listing shared sessions", exc_info=e)
        return []


def add_media_asset(username: str, session_id: Optional[str], filename: str, url: str, mime_type: Optional[str]) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO media_assets (username, session_id, filename, url, mime_type, created_at) "
                    "VALUES (:username, :session_id, :filename, :url, :mime_type, NOW())"
                ),
                {
                    "username": username,
                    "session_id": session_id,
                    "filename": filename,
                    "url": url,
                    "mime_type": mime_type,
                },
            )
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding media asset", exc_info=e)
        return False


def list_media_assets(username: Optional[str] = None):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            if username:
                rows = conn.execute(
                    text(
                        "SELECT id, username, session_id, filename, url, mime_type, created_at "
                        "FROM media_assets WHERE username = :username ORDER BY id DESC"
                    ),
                    {"username": username},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text(
                        "SELECT id, username, session_id, filename, url, mime_type, created_at "
                        "FROM media_assets ORDER BY id DESC"
                    )
                ).mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.exception("Error listing media assets", exc_info=e)
        return []


def auto_complete_due_tasks() -> int:
    if not engine:
        return 0
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "UPDATE tasks SET status = 'done', updated_at = NOW() "
                    "WHERE due_at IS NOT NULL AND due_at <= NOW() "
                    "AND LOWER(COALESCE(status, '')) NOT IN ('done','completed','cancelled')"
                )
            )
            conn.commit()
            return int(result.rowcount or 0)
    except Exception as e:
        logger.exception("Error auto-completing due tasks", exc_info=e)
        return 0


def export_all_sessions_for_backup():
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT session_id, message FROM {CHAT_HISTORY_TABLE} "
                    "WHERE session_id IS NOT NULL ORDER BY id ASC"
                )
            ).fetchall()
        data: Dict[str, List[str]] = {}
        for session_id, message in rows:
            data.setdefault(session_id, []).append(message)
        return [{"session_id": s, "messages": msgs} for s, msgs in data.items()]
    except Exception as e:
        logger.exception("Error exporting sessions for backup", exc_info=e)
        return []


def migrate_notification_preferences_schema() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_notification_preferences (
                        username VARCHAR PRIMARY KEY,
                        browser_notify_on_away_replies BOOLEAN NOT NULL DEFAULT TRUE,
                        email_notify_on_away_replies BOOLEAN NOT NULL DEFAULT FALSE,
                        minimum_notify_interval_seconds INTEGER NOT NULL DEFAULT 300,
                        digest_mode VARCHAR NOT NULL DEFAULT 'immediate',
                        digest_interval_minutes INTEGER NOT NULL DEFAULT 30,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS pending_reply_notifications (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR NOT NULL,
                        session_id VARCHAR NOT NULL,
                        reply_preview TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        delivered_at TIMESTAMPTZ
                    )
                    """
                )
            )
            conn.commit()
    except Exception as exc:
        logger.exception("Failed migrating notification preference schema", exc_info=exc)


migrate_notification_preferences_schema()


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_default_memory_policy() -> Dict[str, object]:
    categories_raw = get_config("memory_policy_default_allowed_categories", "")
    categories = [c.strip() for c in str(categories_raw or "").split(",") if c.strip()]
    return {
        "auto_capture_enabled": _as_bool(get_config("memory_policy_default_auto_capture_enabled", "true"), True),
        "require_approval": _as_bool(get_config("memory_policy_default_require_approval", "false"), False),
        "pii_strict_mode": _as_bool(get_config("memory_policy_default_pii_strict_mode", "false"), False),
        "retention_days": max(1, int(get_config("memory_policy_default_retention_days", "365") or 365)),
        "allowed_categories": categories,
    }


def get_effective_memory_policy(username: str) -> Dict[str, object]:
    defaults = get_default_memory_policy()
    raw = get_config(f"user:{username}:memory_policy", "")
    if not raw:
        return defaults
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return defaults
        merged = {**defaults, **parsed}
        merged["auto_capture_enabled"] = bool(merged.get("auto_capture_enabled", defaults["auto_capture_enabled"]))
        merged["require_approval"] = bool(merged.get("require_approval", defaults["require_approval"]))
        merged["pii_strict_mode"] = bool(merged.get("pii_strict_mode", defaults["pii_strict_mode"]))
        merged["retention_days"] = max(1, int(merged.get("retention_days", defaults["retention_days"])))
        categories = merged.get("allowed_categories")
        if isinstance(categories, list):
            merged["allowed_categories"] = [str(c).strip() for c in categories if str(c).strip()]
        else:
            merged["allowed_categories"] = defaults["allowed_categories"]
        return merged
    except Exception as exc:
        logger.warning(f"Error loading memory policy for user {username}: {exc}")
        return defaults


def upsert_user_memory_policy(
    username: str,
    auto_capture_enabled: bool,
    require_approval: bool,
    pii_strict_mode: bool,
    retention_days: int,
    allowed_categories: List[str],
) -> bool:
    payload = {
        "auto_capture_enabled": bool(auto_capture_enabled),
        "require_approval": bool(require_approval),
        "pii_strict_mode": bool(pii_strict_mode),
        "retention_days": max(1, int(retention_days)),
        "allowed_categories": [str(c).strip() for c in (allowed_categories or []) if str(c).strip()],
    }
    return set_config(f"user:{username}:memory_policy", json.dumps(payload))


def get_effective_chat_preferences(username: str) -> Dict[str, object]:
    default_mode = (get_config("chat_output_mode", "normal") or "normal").strip().lower()
    if default_mode not in {"compact", "normal"}:
        default_mode = "normal"
    defaults = {
        "chat_output_mode": default_mode,
        "low_token_mode": default_mode == "compact",
    }
    raw = get_config(f"user:{username}:chat_preferences", "")
    if not raw:
        return defaults
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return defaults
        merged = {**defaults, **parsed}
        low_token_mode = bool(merged.get("low_token_mode"))
        mode = "compact" if low_token_mode else "normal"
        merged["chat_output_mode"] = mode
        merged["low_token_mode"] = low_token_mode
        return merged
    except Exception as exc:
        logger.warning(f"Error loading chat preferences for user {username}: {exc}")
        return defaults


def upsert_user_chat_preferences(username: str, low_token_mode: bool) -> bool:
    payload = {
        "low_token_mode": bool(low_token_mode),
        "chat_output_mode": "compact" if bool(low_token_mode) else "normal",
    }
    return set_config(f"user:{username}:chat_preferences", json.dumps(payload))


def get_effective_notification_preferences(username: str) -> Dict[str, object]:
    defaults = {
        "browser_notify_on_away_replies": _as_bool(get_config("notification_default_browser_notify_on_away_replies", "true"), True),
        "email_notify_on_away_replies": _as_bool(
            get_config("notification_default_email_notify_on_away_replies", get_config("chat_reply_email_notifications", "false")),
            False,
        ),
        "minimum_notify_interval_seconds": max(0, int(get_config("notification_default_minimum_notify_interval_seconds", "300") or "300")),
        "digest_mode": (get_config("notification_default_digest_mode", "immediate") or "immediate").strip().lower(),
        "digest_interval_minutes": max(1, int(get_config("notification_default_digest_interval_minutes", "30") or "30")),
    }

    if defaults["digest_mode"] not in {"immediate", "periodic"}:
        defaults["digest_mode"] = "immediate"

    if not engine:
        return defaults

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT browser_notify_on_away_replies, email_notify_on_away_replies,
                           minimum_notify_interval_seconds, digest_mode, digest_interval_minutes
                    FROM user_notification_preferences WHERE username = :username
                    """
                ),
                {"username": username},
            ).mappings().first()
            if not row:
                return defaults
            merged = {**defaults, **dict(row)}
            merged["digest_mode"] = (merged.get("digest_mode") or "immediate").strip().lower()
            if merged["digest_mode"] not in {"immediate", "periodic"}:
                merged["digest_mode"] = "immediate"
            merged["minimum_notify_interval_seconds"] = max(0, int(merged.get("minimum_notify_interval_seconds") or 0))
            merged["digest_interval_minutes"] = max(1, int(merged.get("digest_interval_minutes") or 30))
            return merged
    except Exception as exc:
        logger.exception("Error loading effective notification preferences", extra={"username": username}, exc_info=exc)
        return defaults


def upsert_user_notification_preferences(
    username: str,
    browser_notify_on_away_replies: bool,
    email_notify_on_away_replies: bool,
    minimum_notify_interval_seconds: int,
    digest_mode: str,
    digest_interval_minutes: int,
) -> bool:
    if not engine:
        return False

    normalized_mode = (digest_mode or "immediate").strip().lower()
    if normalized_mode not in {"immediate", "periodic"}:
        normalized_mode = "immediate"

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO user_notification_preferences (
                        username,
                        browser_notify_on_away_replies,
                        email_notify_on_away_replies,
                        minimum_notify_interval_seconds,
                        digest_mode,
                        digest_interval_minutes,
                        created_at,
                        updated_at
                    ) VALUES (
                        :username, :browser_notify_on_away_replies, :email_notify_on_away_replies,
                        :minimum_notify_interval_seconds, :digest_mode, :digest_interval_minutes, NOW(), NOW()
                    )
                    ON CONFLICT (username) DO UPDATE SET
                        browser_notify_on_away_replies = EXCLUDED.browser_notify_on_away_replies,
                        email_notify_on_away_replies = EXCLUDED.email_notify_on_away_replies,
                        minimum_notify_interval_seconds = EXCLUDED.minimum_notify_interval_seconds,
                        digest_mode = EXCLUDED.digest_mode,
                        digest_interval_minutes = EXCLUDED.digest_interval_minutes,
                        updated_at = NOW()
                    """
                ),
                {
                    "username": username,
                    "browser_notify_on_away_replies": bool(browser_notify_on_away_replies),
                    "email_notify_on_away_replies": bool(email_notify_on_away_replies),
                    "minimum_notify_interval_seconds": max(0, int(minimum_notify_interval_seconds)),
                    "digest_mode": normalized_mode,
                    "digest_interval_minutes": max(1, int(digest_interval_minutes)),
                },
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.exception("Error upserting notification preferences", extra={"username": username}, exc_info=exc)
        return False


def enqueue_pending_reply_notification(username: str, session_id: str, reply_preview: str) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO pending_reply_notifications (username, session_id, reply_preview, created_at)
                    VALUES (:username, :session_id, :reply_preview, NOW())
                    """
                ),
                {
                    "username": username,
                    "session_id": session_id,
                    "reply_preview": (reply_preview or "")[:500],
                },
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.exception("Error enqueuing pending reply notification", exc_info=exc)
        return False


def list_pending_reply_notifications_for_digest(max_age_minutes: int = 30) -> List[Dict[str, object]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, username, session_id, reply_preview, created_at
                    FROM pending_reply_notifications
                    WHERE delivered_at IS NULL
                      AND created_at <= NOW() - make_interval(mins => :max_age_minutes)
                    ORDER BY username ASC, created_at ASC
                    """
                ),
                {"max_age_minutes": max(1, int(max_age_minutes))},
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.exception("Error listing pending reply notifications", exc_info=exc)
        return []


def mark_pending_reply_notifications_delivered(ids: List[int]) -> int:
    if not engine or not ids:
        return 0
    clean_ids = [int(i) for i in ids]
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE pending_reply_notifications SET delivered_at = NOW() WHERE id = ANY(:ids)"),
                {"ids": clean_ids},
            )
            conn.commit()
            return int(result.rowcount or 0)
    except Exception as exc:
        logger.exception("Error marking pending reply notifications delivered", exc_info=exc)
        return 0


def list_personas(username: str, include_global: bool = True) -> List[Dict[str, Any]]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            if include_global:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, username, name, system_prompt, tags, is_default, created_at
                        FROM persona_presets
                        WHERE username = :username OR username IS NULL
                        ORDER BY is_default DESC, created_at DESC, id DESC
                        """
                    ),
                    {"username": username},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, username, name, system_prompt, tags, is_default, created_at
                        FROM persona_presets
                        WHERE username = :username
                        ORDER BY is_default DESC, created_at DESC, id DESC
                        """
                    ),
                    {"username": username},
                ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.exception("Error listing personas", exc_info=exc)
        return []


def create_persona(username: Optional[str], name: str, system_prompt: str, tags: str = "", is_default: bool = False) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    owner = username if username else None
    try:
        with engine.connect() as conn:
            if is_default:
                conn.execute(
                    text("UPDATE persona_presets SET is_default = FALSE WHERE username IS NOT DISTINCT FROM :owner"),
                    {"owner": owner},
                )
            row = conn.execute(
                text(
                    """
                    INSERT INTO persona_presets (username, name, system_prompt, tags, is_default, created_at)
                    VALUES (:username, :name, :system_prompt, :tags, :is_default, NOW())
                    RETURNING id, username, name, system_prompt, tags, is_default, created_at
                    """
                ),
                {
                    "username": owner,
                    "name": (name or "").strip()[:120],
                    "system_prompt": (system_prompt or "").strip()[:8000],
                    "tags": (tags or "").strip()[:500],
                    "is_default": bool(is_default),
                },
            ).mappings().first()
            conn.commit()
            return dict(row) if row else None
    except Exception as exc:
        logger.exception("Error creating persona", exc_info=exc)
        return None


def update_persona(persona_id: int, actor_username: str, is_admin: bool, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    allowed = {"name", "system_prompt", "tags", "is_default"}
    payload = {k: v for k, v in (updates or {}).items() if k in allowed and v is not None}
    if not payload:
        return None
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id, username FROM persona_presets WHERE id = :id"),
                {"id": int(persona_id)},
            ).mappings().first()
            if not existing:
                return None
            owner = existing.get("username")
            if not is_admin and owner != actor_username:
                return None
            if payload.get("is_default") is True:
                conn.execute(
                    text("UPDATE persona_presets SET is_default = FALSE WHERE username IS NOT DISTINCT FROM :owner"),
                    {"owner": owner},
                )
            set_clauses = []
            params: Dict[str, Any] = {"id": int(persona_id)}
            for key, value in payload.items():
                set_clauses.append(f"{key} = :{key}")
                if key == "name":
                    params[key] = str(value).strip()[:120]
                elif key == "system_prompt":
                    params[key] = str(value).strip()[:8000]
                elif key == "tags":
                    params[key] = str(value).strip()[:500]
                elif key == "is_default":
                    params[key] = bool(value)
                else:
                    params[key] = value
            row = conn.execute(
                text(
                    f"""
                    UPDATE persona_presets
                    SET {', '.join(set_clauses)}
                    WHERE id = :id
                    RETURNING id, username, name, system_prompt, tags, is_default, created_at
                    """
                ),
                params,
            ).mappings().first()
            conn.commit()
            return dict(row) if row else None
    except Exception as exc:
        logger.exception("Error updating persona", exc_info=exc)
        return None


def delete_persona(persona_id: int, actor_username: str, is_admin: bool) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT username FROM persona_presets WHERE id = :id"),
                {"id": int(persona_id)},
            ).mappings().first()
            if not existing:
                return False
            owner = existing.get("username")
            if not is_admin and owner != actor_username:
                return False
            result = conn.execute(text("DELETE FROM persona_presets WHERE id = :id"), {"id": int(persona_id)})
            conn.commit()
            return bool(result.rowcount)
    except Exception as exc:
        logger.exception("Error deleting persona", exc_info=exc)
        return False


def get_persona_for_user(persona_id: int, username: str, is_admin: bool = False) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, username, name, system_prompt, tags, is_default, created_at
                    FROM persona_presets
                    WHERE id = :id
                    """
                ),
                {"id": int(persona_id)},
            ).mappings().first()
            if not row:
                return None
            data = dict(row)
            owner = data.get("username")
            if is_admin or owner is None or owner == username:
                return data
            return None
    except Exception:
        return None


def ensure_enterprise_tables() -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id BIGSERIAL PRIMARY KEY,
                        username VARCHAR,
                        action VARCHAR NOT NULL,
                        session_id VARCHAR,
                        category VARCHAR,
                        details TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS session_insights (
                        session_id VARCHAR PRIMARY KEY,
                        summary TEXT,
                        tags TEXT,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS memory_summary_nodes (
                        id BIGSERIAL PRIMARY KEY,
                        username VARCHAR NOT NULL,
                        topic VARCHAR NOT NULL,
                        window_start TIMESTAMPTZ NOT NULL,
                        window_end TIMESTAMPTZ NOT NULL,
                        bullet_summary TEXT NOT NULL,
                        source_count INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS persona_presets (
                        id BIGSERIAL PRIMARY KEY,
                        username VARCHAR NULL,
                        name VARCHAR NOT NULL,
                        system_prompt TEXT NOT NULL,
                        tags TEXT,
                        is_default BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(text("ALTER TABLE memory_candidates ADD COLUMN IF NOT EXISTS summarized_at TIMESTAMPTZ"))
            conn.execute(text("ALTER TABLE memory_candidates ADD COLUMN IF NOT EXISTS summary_node_id BIGINT"))
            conn.execute(text("ALTER TABLE memory_candidates ADD COLUMN IF NOT EXISTS retrieval_priority DOUBLE PRECISION NOT NULL DEFAULT 1.0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memory_candidates_summarized_at ON memory_candidates (summarized_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_memory_summary_nodes_username_created_at ON memory_summary_nodes (username, created_at DESC)"))
            conn.commit()
    except Exception as exc:
        logger.exception("Error ensuring enterprise tables", exc_info=exc)


def list_memory_candidates(
    username: str,
    status: Optional[str] = "pending",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    if not engine:
        return []
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))
    cleaned_status = (status or "").strip().lower()
    try:
        with engine.connect() as conn:
            where_sql = "WHERE username = :username"
            params: Dict[str, Any] = {"username": username, "limit": safe_limit, "offset": safe_offset}
            if cleaned_status:
                where_sql += " AND status = :status"
                params["status"] = cleaned_status
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, username, session_id, candidate_text, source_message_id, source_offset,
                           confidence, status, created_at, reviewed_at
                    FROM memory_candidates
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.exception("Error listing memory candidates", exc_info=exc)
        return []


def update_memory_candidate_status(id: int, status: str, edited_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    clean_status = (status or "").strip().lower()
    if clean_status not in {"pending", "approved", "rejected"}:
        return None
    try:
        with engine.connect() as conn:
            params: Dict[str, Any] = {"id": int(id), "status": clean_status}
            set_sql = "status = :status, reviewed_at = NOW()"
            if edited_text is not None and edited_text.strip():
                params["candidate_text"] = edited_text.strip()
                set_sql += ", candidate_text = :candidate_text"
            row = conn.execute(
                text(
                    f"""
                    UPDATE memory_candidates
                    SET {set_sql}
                    WHERE id = :id
                    RETURNING id, username, session_id, candidate_text, source_message_id, source_offset,
                              confidence, status, created_at, reviewed_at
                    """
                ),
                params,
            ).mappings().first()
            conn.commit()
            return dict(row) if row else None
    except Exception as exc:
        logger.exception("Error updating memory candidate status", exc_info=exc)
        return None


def get_memory_candidate_by_id(id: int) -> Optional[Dict[str, Any]]:
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, username, session_id, candidate_text, source_message_id, source_offset,
                           confidence, status, created_at, reviewed_at
                    FROM memory_candidates
                    WHERE id = :id
                    """
                ),
                {"id": int(id)},
            ).mappings().first()
            return dict(row) if row else None
    except Exception as exc:
        logger.exception("Error getting memory candidate", exc_info=exc)
        return None


def log_audit_event(username: str, action: str, session_id: Optional[str] = None, category: Optional[str] = None, details: Optional[str] = None) -> None:
    if not engine:
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO audit_events (username, action, session_id, category, details, created_at)
                    VALUES (:username, :action, :session_id, :category, :details, NOW())
                    """
                ),
                {
                    "username": username,
                    "action": action,
                    "session_id": session_id,
                    "category": category,
                    "details": (details or "")[:2000],
                },
            )
            conn.commit()
    except Exception:
        # do not fail user flow on audit logging
        pass


def list_audit_events(limit: int = 200) -> List[Dict[str, Any]]:
    if not engine:
        return []
    safe_limit = max(1, min(int(limit), 1000))
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, username, action, session_id, category, details, created_at
                    FROM audit_events
                    ORDER BY id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": safe_limit},
            ).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _normalize_analytics_scope(scope: Optional[str]) -> str:
    normalized = (scope or "mine").strip().lower()
    return normalized if normalized in {"mine", "shared", "all"} else "mine"


def _parse_analytics_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def get_memory_analytics(
    username: str,
    is_admin: bool,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    owner_scope: str = "mine",
    stale_days: int = 30,
    top_n: int = 8,
) -> Dict[str, Any]:
    if not engine:
        return {
            "kpis": {"memory_writes_total": 0, "retrieval_hits_total": 0, "stale_memories_count": 0},
            "memory_writes_per_day": [],
            "retrieval_hits_per_day": [],
            "top_categories": [],
            "stale_memories": [],
        }

    scope = _normalize_analytics_scope(owner_scope)
    if not is_admin and scope == "all":
        scope = "mine"

    from_dt = _parse_analytics_dt(date_from)
    to_dt = _parse_analytics_dt(date_to)
    if not to_dt:
        to_dt = datetime.now(timezone.utc)
    if not from_dt:
        from_dt = to_dt - timedelta(days=30)
    if from_dt > to_dt:
        from_dt, to_dt = to_dt, from_dt

    stale_days = max(1, int(stale_days))
    top_n = max(1, min(int(top_n), 20))

    accessible_ids = set(get_accessible_session_ids(username=username, is_admin=is_admin))
    shared_ids = set(list_shared_sessions_for_user(username))
    if not is_admin and not accessible_ids:
        return {
            "kpis": {"memory_writes_total": 0, "retrieval_hits_total": 0, "stale_memories_count": 0},
            "memory_writes_per_day": [],
            "retrieval_hits_per_day": [],
            "top_categories": [],
            "stale_memories": [],
            "scope": scope,
            "date_from": from_dt.isoformat(),
            "date_to": to_dt.isoformat(),
            "stale_days": stale_days,
        }

    audit_scope_sql = ""
    metadata_scope_sql = ""
    params: Dict[str, Any] = {
        "from_dt": from_dt,
        "to_dt": to_dt,
        "stale_days": stale_days,
        "top_n": top_n,
    }

    if is_admin:
        if scope == "mine":
            audit_scope_sql = "AND ae.username = :username"
            metadata_scope_sql = "AND sa.owner_username = :username"
            params["username"] = username
    else:
        session_ids = sorted(accessible_ids)
        if scope == "mine":
            session_ids = [sid for sid in session_ids if sid not in shared_ids]
        elif scope == "shared":
            session_ids = [sid for sid in session_ids if sid in shared_ids]
        params["session_ids"] = session_ids
        if not session_ids:
            return {
                "kpis": {"memory_writes_total": 0, "retrieval_hits_total": 0, "stale_memories_count": 0},
                "memory_writes_per_day": [],
                "retrieval_hits_per_day": [],
                "top_categories": [],
                "stale_memories": [],
                "scope": scope,
                "date_from": from_dt.isoformat(),
                "date_to": to_dt.isoformat(),
                "stale_days": stale_days,
            }
        audit_scope_sql = "AND (ae.session_id = ANY(:session_ids) OR ae.username = :username)"
        metadata_scope_sql = "AND sm.session_id = ANY(:session_ids)"
        params["username"] = username

    try:
        with engine.connect() as conn:
            writes_rows = conn.execute(
                text(
                    f"""
                    SELECT DATE_TRUNC('day', ae.created_at) AS day, COUNT(*) AS count
                    FROM audit_events ae
                    LEFT JOIN session_access sa ON sa.session_id = ae.session_id
                    WHERE ae.action = 'memory.write.chat'
                      AND ae.created_at >= :from_dt
                      AND ae.created_at <= :to_dt
                      {audit_scope_sql}
                    GROUP BY 1
                    ORDER BY 1 ASC
                    """
                ),
                params,
            ).mappings().all()

            retrieval_rows = conn.execute(
                text(
                    f"""
                    SELECT DATE_TRUNC('day', ae.created_at) AS day, COUNT(*) AS count
                    FROM audit_events ae
                    LEFT JOIN session_access sa ON sa.session_id = ae.session_id
                    WHERE ae.action IN ('memory.read.history', 'memory.read.explorer')
                      AND ae.created_at >= :from_dt
                      AND ae.created_at <= :to_dt
                      {audit_scope_sql}
                    GROUP BY 1
                    ORDER BY 1 ASC
                    """
                ),
                params,
            ).mappings().all()

            categories_rows = conn.execute(
                text(
                    f"""
                    SELECT COALESCE(sm.category, 'Uncategorized') AS category, COUNT(*) AS count
                    FROM session_metadata sm
                    LEFT JOIN session_access sa ON sa.session_id = sm.session_id
                    WHERE 1=1
                      {metadata_scope_sql}
                    GROUP BY 1
                    ORDER BY count DESC, category ASC
                    LIMIT :top_n
                    """
                ),
                params,
            ).mappings().all()

            stale_rows = conn.execute(
                text(
                    f"""
                    SELECT
                        sm.session_id,
                        COALESCE(sm.category, 'Uncategorized') AS category,
                        COALESCE(sa.owner_username, 'unknown') AS owner,
                        sm.updated_at,
                        (
                            SELECT MAX(ae.created_at)
                            FROM audit_events ae
                            WHERE ae.session_id = sm.session_id
                              AND ae.action IN ('memory.read.history', 'memory.read.explorer')
                        ) AS last_retrieval_at
                    FROM session_metadata sm
                    LEFT JOIN session_access sa ON sa.session_id = sm.session_id
                    WHERE sm.updated_at IS NOT NULL
                      AND sm.updated_at::timestamptz <= NOW() - make_interval(days => :stale_days)
                      AND (
                          (
                              SELECT MAX(ae.created_at)
                              FROM audit_events ae
                              WHERE ae.session_id = sm.session_id
                                AND ae.action IN ('memory.read.history', 'memory.read.explorer')
                          ) IS NULL
                          OR
                          (
                              SELECT MAX(ae.created_at)
                              FROM audit_events ae
                              WHERE ae.session_id = sm.session_id
                                AND ae.action IN ('memory.read.history', 'memory.read.explorer')
                          ) <= NOW() - make_interval(days => :stale_days)
                      )
                      {metadata_scope_sql}
                    ORDER BY sm.updated_at ASC
                    LIMIT 200
                    """
                ),
                params,
            ).mappings().all()
    except Exception as exc:
        logger.exception("Error building memory analytics", exc_info=exc)
        return {
            "kpis": {"memory_writes_total": 0, "retrieval_hits_total": 0, "stale_memories_count": 0},
            "memory_writes_per_day": [],
            "retrieval_hits_per_day": [],
            "top_categories": [],
            "stale_memories": [],
            "scope": scope,
            "date_from": from_dt.isoformat(),
            "date_to": to_dt.isoformat(),
            "stale_days": stale_days,
        }

    writes = [{"day": r["day"].date().isoformat(), "count": int(r["count"] or 0)} for r in writes_rows]
    retrieval = [{"day": r["day"].date().isoformat(), "count": int(r["count"] or 0)} for r in retrieval_rows]
    top_categories_rows = [{"category": r["category"], "count": int(r["count"] or 0)} for r in categories_rows]
    stale_memories = []
    for row in stale_rows:
        updated_at = row.get("updated_at")
        last_retrieval = row.get("last_retrieval_at")
        stale_memories.append(
            {
                "session_id": row.get("session_id"),
                "category": row.get("category") or "Uncategorized",
                "owner": row.get("owner") or "unknown",
                "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                "last_retrieval_at": last_retrieval.isoformat() if hasattr(last_retrieval, "isoformat") else (str(last_retrieval) if last_retrieval else None),
            }
        )

    return {
        "kpis": {
            "memory_writes_total": sum(item["count"] for item in writes),
            "retrieval_hits_total": sum(item["count"] for item in retrieval),
            "stale_memories_count": len(stale_memories),
        },
        "memory_writes_per_day": writes,
        "retrieval_hits_per_day": retrieval,
        "top_categories": top_categories_rows,
        "stale_memories": stale_memories,
        "scope": scope,
        "date_from": from_dt.isoformat(),
        "date_to": to_dt.isoformat(),
        "stale_days": stale_days,
    }


def upsert_session_insight(session_id: str, summary: str, tags: List[str]) -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO session_insights (session_id, summary, tags, updated_at)
                    VALUES (:session_id, :summary, :tags, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        tags = EXCLUDED.tags,
                        updated_at = NOW()
                    """
                ),
                {
                    "session_id": session_id,
                    "summary": (summary or "")[:4000],
                    "tags": ",".join([t.strip() for t in tags if t.strip()])[:1000],
                },
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.exception("Error upserting session insight", exc_info=exc)
        return False


def get_session_insight(session_id: str) -> Dict[str, str]:
    if not engine:
        return {}
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT summary, tags, updated_at FROM session_insights WHERE session_id = :session_id"),
                {"session_id": session_id},
            ).mappings().first()
            return dict(row) if row else {}
    except Exception:
        return {}


def _canonical_bullet_summary(rows: List[Dict[str, Any]], *, max_bullets: int = 10) -> str:
    ordered = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
    bullets: List[str] = []
    seen = set()
    for row in ordered:
        raw = " ".join(str(row.get("candidate_text") or "").split())
        if not raw:
            continue
        normalized = raw.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if len(raw) > 180:
            raw = raw[:177].rstrip() + "..."
        bullets.append(f"- {raw}")
        if len(bullets) >= max(5, min(max_bullets, 10)):
            break
    return "\n".join(bullets)


def summarize_approved_memories(min_age_days: int = 14, min_group_size: int = 3, max_groups: int = 100) -> Dict[str, int]:
    if not engine:
        return {"groups_created": 0, "sources_marked": 0}
    safe_age = max(1, int(min_age_days))
    safe_group_size = max(2, int(min_group_size))
    safe_max_groups = max(1, min(int(max_groups), 500))
    groups_created = 0
    sources_marked = 0
    try:
        with engine.connect() as conn:
            candidate_groups = conn.execute(
                text(
                    """
                    SELECT
                        mc.username,
                        COALESCE(sm.category, 'general') AS topic,
                        DATE_TRUNC('week', mc.created_at) AS week_start,
                        COUNT(*) AS memory_count
                    FROM memory_candidates mc
                    LEFT JOIN session_metadata sm ON sm.session_id = mc.session_id
                    WHERE mc.status = 'approved'
                      AND mc.summarized_at IS NULL
                      AND mc.created_at <= NOW() - make_interval(days => :min_age_days)
                    GROUP BY 1, 2, 3
                    HAVING COUNT(*) >= :min_group_size
                    ORDER BY week_start ASC, memory_count DESC
                    LIMIT :max_groups
                    """
                ),
                {"min_age_days": safe_age, "min_group_size": safe_group_size, "max_groups": safe_max_groups},
            ).mappings().all()

            for group in candidate_groups:
                username = str(group["username"])
                topic = str(group["topic"] or "general")
                week_start = group["week_start"]
                if not week_start:
                    continue
                window_start = week_start
                window_end = week_start + timedelta(days=7)
                source_rows = conn.execute(
                    text(
                        """
                        SELECT id, candidate_text, created_at
                        FROM memory_candidates
                        WHERE username = :username
                          AND status = 'approved'
                          AND summarized_at IS NULL
                          AND created_at >= :window_start
                          AND created_at < :window_end
                        ORDER BY created_at ASC, id ASC
                        """
                    ),
                    {
                        "username": username,
                        "window_start": window_start,
                        "window_end": window_end,
                    },
                ).mappings().all()
                if len(source_rows) < safe_group_size:
                    continue
                summary_text = _canonical_bullet_summary([dict(r) for r in source_rows], max_bullets=10)
                if not summary_text:
                    continue

                node = conn.execute(
                    text(
                        """
                        INSERT INTO memory_summary_nodes (username, topic, window_start, window_end, bullet_summary, source_count, created_at)
                        VALUES (:username, :topic, :window_start, :window_end, :bullet_summary, :source_count, NOW())
                        RETURNING id
                        """
                    ),
                    {
                        "username": username,
                        "topic": topic,
                        "window_start": window_start,
                        "window_end": window_end,
                        "bullet_summary": summary_text,
                        "source_count": len(source_rows),
                    },
                ).mappings().first()
                if not node:
                    continue
                summary_node_id = int(node["id"])
                ids = [int(r["id"]) for r in source_rows]
                update_result = conn.execute(
                    text(
                        """
                        UPDATE memory_candidates
                        SET summarized_at = NOW(),
                            summary_node_id = :summary_node_id,
                            retrieval_priority = LEAST(COALESCE(retrieval_priority, 1.0), 0.25)
                        WHERE id = ANY(:ids)
                        """
                    ),
                    {"summary_node_id": summary_node_id, "ids": ids},
                )
                groups_created += 1
                sources_marked += int(update_result.rowcount or 0)
            conn.commit()
    except Exception as exc:
        logger.exception("Error summarizing approved memories", exc_info=exc)
    return {"groups_created": groups_created, "sources_marked": sources_marked}


def get_memory_rollup_metrics(username: Optional[str] = None) -> Dict[str, Any]:
    if not engine:
        return {"raw_memory_count": 0, "summary_node_count": 0, "avg_injected_memory_chars": 0, "avg_injected_memory_tokens": 0}
    try:
        with engine.connect() as conn:
            params: Dict[str, Any] = {}
            user_filter_candidates = ""
            user_filter_nodes = ""
            user_filter_audit = ""
            if username:
                params["username"] = username
                user_filter_candidates = "AND username = :username"
                user_filter_nodes = "AND username = :username"
                user_filter_audit = "AND username = :username"
            raw_count = conn.execute(
                text(f"SELECT COUNT(*) FROM memory_candidates WHERE status = 'approved' {user_filter_candidates}"),
                params,
            ).scalar() or 0
            summary_count = conn.execute(
                text(f"SELECT COUNT(*) FROM memory_summary_nodes WHERE 1=1 {user_filter_nodes}"),
                params,
            ).scalar() or 0
            averages = conn.execute(
                text(
                    f"""
                    SELECT
                        COALESCE(AVG(NULLIF(split_part(split_part(details, 'chars=', 2), ',', 1), '')::FLOAT), 0) AS avg_chars,
                        COALESCE(AVG(NULLIF(split_part(split_part(details, 'tokens=', 2), ',', 1), '')::FLOAT), 0) AS avg_tokens
                    FROM audit_events
                    WHERE action = 'memory.read.injected'
                      {user_filter_audit}
                    """
                ),
                params,
            ).mappings().first() or {}
            return {
                "raw_memory_count": int(raw_count),
                "summary_node_count": int(summary_count),
                "avg_injected_memory_chars": round(float(averages.get("avg_chars") or 0), 2),
                "avg_injected_memory_tokens": round(float(averages.get("avg_tokens") or 0), 2),
            }
    except Exception as exc:
        logger.exception("Error computing memory rollup metrics", exc_info=exc)
        return {"raw_memory_count": 0, "summary_node_count": 0, "avg_injected_memory_chars": 0, "avg_injected_memory_tokens": 0}


def redact_pii_text(text_value: str) -> str:
    text_value = text_value or ""
    # email
    redacted = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]", text_value)
    # phone
    redacted = re.sub(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b", "[REDACTED_PHONE]", redacted)
    # ssn-like
    redacted = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", redacted)
    # credit-card like 13-19 digits
    redacted = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[REDACTED_CARD]", redacted)
    return redacted


def apply_retention_policy(max_age_days: int = 365, archive_only: bool = True) -> Dict[str, int]:
    if not engine:
        return {"archived": 0, "deleted": 0}
    max_age_days = max(1, int(max_age_days))
    archived = 0
    deleted = 0
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT session_id
                    FROM session_metadata
                    WHERE updated_at IS NOT NULL
                      AND updated_at::timestamptz < NOW() - make_interval(days => :days)
                    """
                ),
                {"days": max_age_days},
            ).fetchall()
            stale_ids = [r[0] for r in rows if r and r[0]]
            if not stale_ids:
                return {"archived": 0, "deleted": 0}
            if archive_only:
                result = conn.execute(
                    text("UPDATE session_metadata SET archived = TRUE WHERE session_id = ANY(:ids)"),
                    {"ids": stale_ids},
                )
                archived = int(result.rowcount or 0)
            else:
                conn.execute(text(f"DELETE FROM {CHAT_HISTORY_TABLE} WHERE session_id = ANY(:ids)"), {"ids": stale_ids})
                result = conn.execute(text("DELETE FROM session_metadata WHERE session_id = ANY(:ids)"), {"ids": stale_ids})
                deleted = int(result.rowcount or 0)
            conn.commit()
    except Exception as exc:
        logger.exception("Retention policy failed", exc_info=exc)
    return {"archived": archived, "deleted": deleted}


def find_report_matches(
    username: str,
    is_admin: bool,
    keyword: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    shared_only: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    # Lightweight fallback implementation to keep API stable in deployments with mixed schema versions.
    matches: List[Dict[str, Any]] = []
    if not keyword:
        return matches
    accessible = set(get_accessible_session_ids(username=username, is_admin=is_admin))
    for sid in sorted(accessible):
        if session_id and sid != session_id:
            continue
        msgs = list_chat_messages(sid, dedupe=True)
        for msg in msgs:
            content = (msg.get("content") or "")
            if keyword.lower() in content.lower():
                matches.append(
                    {
                        "session_id": sid,
                        "type": msg.get("type"),
                        "content": content[:500],
                    }
                )
                if len(matches) >= max(1, int(limit)):
                    return matches
    return matches


def build_session_report_card(session_id: str, username: str, is_admin: bool) -> Dict[str, Any]:
    if not user_can_access_session(session_id=session_id, username=username, role="admin" if is_admin else "user"):
        return {}
    messages = list_chat_messages(session_id, dedupe=True)
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "preview": messages[-5:] if messages else [],
        "insight": get_session_insight(session_id),
    }


def migrate_app_config_encryption() -> Dict[str, Any]:
    # Compatibility no-op for older branches where encryption migration may not be present.
    return {"migrated": 0, "skipped": 0}


ensure_enterprise_tables()

# ---------------------------------------------------------------------------
# Compatibility wrappers
# ---------------------------------------------------------------------------

def create_user(
    username: str,
    password: Optional[str] = None,
    role: str = "user",
    password_hash: Optional[str] = None,
):
    """
    Backward-compatible create_user.

    Supports both call styles used across this codebase:
    1) create_user(username, password, role="user") -> (ok: bool, reason: str)
    2) create_user(username=..., role=..., password_hash=...) -> bool
    """
    if not engine:
        return (False, "db_unavailable") if password_hash is None else False

    username = (username or "").strip()
    if not username:
        return (False, "username_required") if password_hash is None else False

    tuple_mode = password_hash is None
    if password_hash is None:
        if not password:
            return False, "username_password_required"
        if len(password) < 4:
            return False, "password_too_short"
        password_hash = _hash_password(password)

    role = (role or "user").strip().lower()
    if role not in {"admin", "user"}:
        role = "user"

    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM users WHERE username = :username LIMIT 1"),
                {"username": username},
            ).first()
            if existing:
                return (False, "username_exists") if tuple_mode else False

            conn.execute(
                text(
                    "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                    "VALUES (:username, :role, :password_hash, NOW(), NOW())"
                ),
                {"username": username, "role": role, "password_hash": password_hash},
            )
            conn.commit()
        return (True, "created") if tuple_mode else True
    except Exception as e:
        logger.exception("Error creating user", extra={"username": username}, exc_info=e)
        return (False, "create_failed") if tuple_mode else False


def ensure_default_admin(username: str, password: str):
    # idempotent startup helper for auth.bootstrap_default_admin
    result = create_user(username=username, password=password, role="admin")
    if isinstance(result, tuple):
        return result[0]
    return bool(result)


def delete_user(user_identifier):
    """
    Backward-compatible delete_user.
    Accepts either numeric user id or username.
    """
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            if isinstance(user_identifier, int):
                result = conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_identifier})
            else:
                result = conn.execute(
                    text("DELETE FROM users WHERE username = :username"),
                    {"username": str(user_identifier)},
                )
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error deleting user", exc_info=e)
        return False


def ensure_curator_nudges_table() -> None:
    if not engine:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS curator_nudges (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                session_id TEXT,
                nudge_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                delivered_at TIMESTAMPTZ,
                acknowledged_at TIMESTAMPTZ
            )
        """))


def create_curator_nudge(username: str, session_id: Optional[str], nudge_type: str, payload: Dict[str, Any]) -> Optional[int]:
    if not engine:
        return None
    ensure_curator_nudges_table()
    dedupe_key = str((payload or {}).get("task_id") or (payload or {}).get("message") or "").strip()
    with engine.begin() as conn:
        if dedupe_key:
            existing = conn.execute(
                text(
                    """
                    SELECT id
                    FROM curator_nudges
                    WHERE username = :username
                      AND nudge_type = :nudge_type
                      AND acknowledged_at IS NULL
                      AND payload_json LIKE :needle
                      AND created_at >= NOW() - INTERVAL '12 hours'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "username": username,
                    "nudge_type": nudge_type,
                    "needle": f"%{dedupe_key}%",
                },
            ).first()
            if existing:
                return int(existing[0])
        row = conn.execute(
            text(
                """
                INSERT INTO curator_nudges (username, session_id, nudge_type, payload_json)
                VALUES (:username, :session_id, :nudge_type, :payload_json)
                RETURNING id
                """
            ),
            {
                "username": username,
                "session_id": session_id,
                "nudge_type": nudge_type,
                "payload_json": json.dumps(payload or {}),
            },
        ).first()
    return int(row[0]) if row else None


def list_curator_nudges(username: str, session_id: Optional[str] = None, only_unacked: bool = True, limit: int = 25) -> List[Dict[str, Any]]:
    if not engine:
        return []
    ensure_curator_nudges_table()
    where = ["username = :username"]
    params: Dict[str, Any] = {"username": username, "limit": max(1, min(limit, 200))}
    if session_id:
        where.append("session_id = :session_id")
        params["session_id"] = session_id
    if only_unacked:
        where.append("acknowledged_at IS NULL")
    sql = text(f"""
        SELECT id, username, session_id, nudge_type, payload_json, created_at, delivered_at, acknowledged_at
        FROM curator_nudges
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, params).mappings().all()
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
        except Exception:
            item["payload"] = {}
        output.append(item)
    return output


def acknowledge_curator_nudge(nudge_id: int, username: str) -> bool:
    if not engine:
        return False
    ensure_curator_nudges_table()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE curator_nudges
                SET acknowledged_at = NOW(), delivered_at = COALESCE(delivered_at, NOW())
                WHERE id = :id AND username = :username
                """
            ),
            {"id": int(nudge_id), "username": username},
        )
    return result.rowcount > 0


def ensure_skill_registry_tables() -> None:
    if not engine:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_skills (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                trigger_patterns TEXT NOT NULL DEFAULT '[]',
                instructions TEXT NOT NULL,
                tool_requirements TEXT NOT NULL DEFAULT '[]',
                confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                quality_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'draft',
                source_session_id TEXT,
                created_by TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS skill_versions (
                id SERIAL PRIMARY KEY,
                skill_id INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                instructions TEXT NOT NULL,
                trigger_patterns TEXT NOT NULL DEFAULT '[]',
                quality_score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                change_note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS skill_runs (
                id SERIAL PRIMARY KEY,
                skill_id INTEGER NOT NULL,
                skill_version_id INTEGER,
                username TEXT,
                session_id TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                latency_ms INTEGER,
                user_feedback INTEGER,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))


def create_agent_skill(
    name: str,
    instructions: str,
    trigger_patterns: List[str],
    tool_requirements: List[str],
    confidence: float = 0.6,
    quality_score: float = 0.5,
    status: str = "draft",
    source_session_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[int]:
    if not engine:
        return None
    ensure_skill_registry_tables()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO agent_skills
            (name, trigger_patterns, instructions, tool_requirements, confidence, quality_score, status, source_session_id, created_by, updated_at)
            VALUES (:name, :trigger_patterns, :instructions, :tool_requirements, :confidence, :quality_score, :status, :source_session_id, :created_by, NOW())
            RETURNING id
        """), {
            "name": name.strip() or "Unnamed Skill",
            "trigger_patterns": json.dumps(trigger_patterns or []),
            "instructions": instructions.strip() or "No instructions provided.",
            "tool_requirements": json.dumps(tool_requirements or []),
            "confidence": max(0.0, min(float(confidence), 1.0)),
            "quality_score": max(0.0, min(float(quality_score), 1.0)),
            "status": (status or "draft").strip().lower(),
            "source_session_id": source_session_id,
            "created_by": created_by,
        }).first()
        skill_id = int(row[0]) if row else None
        if skill_id:
            conn.execute(text("""
                INSERT INTO skill_versions (skill_id, version, instructions, trigger_patterns, quality_score, change_note)
                VALUES (:skill_id, 1, :instructions, :trigger_patterns, :quality_score, :change_note)
            """), {
                "skill_id": skill_id,
                "instructions": instructions.strip() or "No instructions provided.",
                "trigger_patterns": json.dumps(trigger_patterns or []),
                "quality_score": max(0.0, min(float(quality_score), 1.0)),
                "change_note": "Initial skill synthesis",
            })
    return skill_id


def list_agent_skills(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    if not engine:
        return []
    ensure_skill_registry_tables()
    query = """
        SELECT id, name, trigger_patterns, instructions, tool_requirements, confidence, quality_score, status, source_session_id, created_by, created_at, updated_at
        FROM agent_skills
    """
    params: Dict[str, Any] = {"limit": max(1, min(limit, 500))}
    if status:
        query += " WHERE status = :status"
        params["status"] = status
    query += " ORDER BY updated_at DESC LIMIT :limit"
    with engine.begin() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["trigger_patterns"] = json.loads(item.get("trigger_patterns") or "[]")
        item["tool_requirements"] = json.loads(item.get("tool_requirements") or "[]")
        items.append(item)
    return items


def record_skill_run(
    skill_id: int,
    skill_version_id: Optional[int],
    username: Optional[str],
    session_id: Optional[str],
    status: str,
    latency_ms: Optional[int] = None,
    user_feedback: Optional[int] = None,
    notes: Optional[str] = None,
) -> Optional[int]:
    if not engine:
        return None
    ensure_skill_registry_tables()
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO skill_runs (skill_id, skill_version_id, username, session_id, status, latency_ms, user_feedback, notes)
            VALUES (:skill_id, :skill_version_id, :username, :session_id, :status, :latency_ms, :user_feedback, :notes)
            RETURNING id
        """), {
            "skill_id": int(skill_id),
            "skill_version_id": skill_version_id,
            "username": username,
            "session_id": session_id,
            "status": (status or "success").strip().lower(),
            "latency_ms": latency_ms,
            "user_feedback": user_feedback,
            "notes": notes,
        }).first()
    return int(row[0]) if row else None


def get_skill_performance(skill_id: int, lookback_days: int = 14) -> Dict[str, Any]:
    if not engine:
        return {"runs": 0, "success_rate": 0.0, "avg_feedback": 0.0}
    ensure_skill_registry_tables()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT
                COUNT(*) AS runs,
                AVG(CASE WHEN status IN ('success','ok') THEN 1.0 ELSE 0.0 END) AS success_rate,
                AVG(COALESCE(user_feedback, 0)) AS avg_feedback
            FROM skill_runs
            WHERE skill_id = :skill_id
              AND created_at >= NOW() - (:lookback_days || ' days')::interval
        """), {"skill_id": int(skill_id), "lookback_days": max(1, int(lookback_days))}).mappings().first()
    return {
        "runs": int((row or {}).get("runs") or 0),
        "success_rate": float((row or {}).get("success_rate") or 0.0),
        "avg_feedback": float((row or {}).get("avg_feedback") or 0.0),
    }


def create_skill_version(skill_id: int, instructions: str, trigger_patterns: List[str], quality_score: float, change_note: str) -> Optional[int]:
    if not engine:
        return None
    ensure_skill_registry_tables()
    with engine.begin() as conn:
        version_row = conn.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM skill_versions WHERE skill_id = :skill_id"),
            {"skill_id": int(skill_id)},
        ).mappings().first()
        next_version = int((version_row or {}).get("next_version") or 1)
        row = conn.execute(text("""
            INSERT INTO skill_versions (skill_id, version, instructions, trigger_patterns, quality_score, change_note)
            VALUES (:skill_id, :version, :instructions, :trigger_patterns, :quality_score, :change_note)
            RETURNING id
        """), {
            "skill_id": int(skill_id),
            "version": next_version,
            "instructions": instructions,
            "trigger_patterns": json.dumps(trigger_patterns or []),
            "quality_score": max(0.0, min(float(quality_score), 1.0)),
            "change_note": change_note,
        }).first()
        conn.execute(text("""
            UPDATE agent_skills
            SET instructions = :instructions,
                trigger_patterns = :trigger_patterns,
                quality_score = :quality_score,
                updated_at = NOW()
            WHERE id = :skill_id
        """), {
            "skill_id": int(skill_id),
            "instructions": instructions,
            "trigger_patterns": json.dumps(trigger_patterns or []),
            "quality_score": max(0.0, min(float(quality_score), 1.0)),
        })
    return int(row[0]) if row else None
