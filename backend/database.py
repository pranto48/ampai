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

core_memories = Table(
    'core_memories', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('fact', String)
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
            conn.commit()
    except Exception as exc:
        logger.exception("Error ensuring enterprise tables", exc_info=exc)


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
