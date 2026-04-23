import os
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, select, inspect, text
from cryptography.fernet import Fernet, InvalidToken

from logging_utils import get_logger

# Allow overriding for local testing vs docker
# Default to Postgres container format
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")

engine = None
metadata = MetaData()
ENCRYPTED_PREFIX = "enc::"
logger = get_logger(__name__)

message_store = Table(
    'message_store', metadata,
    Column('id', Integer, primary_key=True),
    Column('session_id', String),
    Column('message', String)
)

session_metadata = Table(
    'session_metadata', metadata,
    Column('session_id', String, primary_key=True),
    Column('category', String, default='Uncategorized')
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

tasks = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String, nullable=False),
    Column("description", String),
    Column("status", String, nullable=False, default="todo"),
    Column("priority", String, nullable=False, default="medium"),
    Column("due_at", DateTime(timezone=True), nullable=True),
    Column("session_id", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    Column("updated_at", DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
)

try:
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
except Exception:
    pass


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


def encrypt_config_value(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return value
    if value.startswith(ENCRYPTED_PREFIX):
        return value

    fernets = _load_fernet_keys()
    if not fernets:
        return value

    token = fernets[0].encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_config_value(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return value
    if not value.startswith(ENCRYPTED_PREFIX):
        return value

    token = value[len(ENCRYPTED_PREFIX):]
    fernets = _load_fernet_keys()
    for f in fernets:
        try:
            return f.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            continue
        except Exception:
            continue
    return None


def migrate_app_config_encryption() -> dict:
    if not engine:
        return {"updated": 0, "failed": 0, "checked": 0}

    updated = 0
    failed = 0
    checked = 0

    try:
        with engine.connect() as conn:
            stmt = select(app_configs.c.config_key, app_configs.c.config_value)
            rows = conn.execute(stmt).fetchall()
            for key, value in rows:
                checked += 1
                if value is None or value == "":
                    continue

                current_plain = decrypt_config_value(value)
                if current_plain is None:
                    failed += 1
                    continue

                reencrypted = encrypt_config_value(current_plain)
                if reencrypted != value:
                    upsert_stmt = text(
                        "INSERT INTO app_configs (config_key, config_value) VALUES (:k, :v) "
                        "ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value"
                    )
                    conn.execute(upsert_stmt, {"k": key, "v": reencrypted})
                    updated += 1
            conn.commit()
    except Exception as e:
        logger.exception("Error migrating app config encryption", exc_info=e)

    return {"updated": updated, "failed": failed, "checked": checked}

def get_all_sessions():
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if not inspector.has_table("message_store"):
                return []
                
            # Fetch all distinct sessions
            stmt_sessions = select(message_store.c.session_id).distinct()
            sessions_result = conn.execute(stmt_sessions)
            session_ids = [row[0] for row in sessions_result]
            
            # Fetch categories
            stmt_cats = select(session_metadata.c.session_id, session_metadata.c.category)
            cats_result = conn.execute(stmt_cats)
            cats_map = {row[0]: row[1] for row in cats_result}
            
            output = []
            for s_id in session_ids:
                output.append({
                    "session_id": s_id,
                    "category": cats_map.get(s_id, "Uncategorized")
                })
            return output
    except Exception as e:
        logger.exception("Error fetching sessions", exc_info=e)
        return []

def set_session_category(session_id: str, category: str):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            # Upsert logic for sqlite: INSERT OR REPLACE
            upsert_stmt = text(
                "INSERT INTO session_metadata (session_id, category) VALUES (:s, :c) "
                "ON CONFLICT (session_id) DO UPDATE SET category = EXCLUDED.category"
            )
            conn.execute(upsert_stmt, {"s": session_id, "c": category})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error setting category", exc_info=e)
        return False

def delete_session_metadata(session_id: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            del_stmt = text("DELETE FROM session_metadata WHERE session_id = :s")
            conn.execute(del_stmt, {"s": session_id})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error deleting session metadata", exc_info=e)
        return False

def get_config(key: str, default=None):
    if not engine: return default
    try:
        with engine.connect() as conn:
            stmt = select(app_configs.c.config_value).where(app_configs.c.config_key == key)
            result = conn.execute(stmt).first()
            if result:
                decrypted = decrypt_config_value(result[0])
                return decrypted if decrypted is not None else default
            return default
    except Exception as e:
        logger.exception("Error getting config", extra={"config_key": key}, exc_info=e)
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
        logger.exception("Error setting config", extra={"config_key": key}, exc_info=e)
        return False

def get_all_configs():
    if not engine: return {}
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect
            if not inspect(engine).has_table("app_configs"): return {}
            stmt = select(app_configs.c.config_key, app_configs.c.config_value)
            result = conn.execute(stmt)
            output = {}
            for row in result:
                decrypted = decrypt_config_value(row[1])
                output[row[0]] = decrypted if decrypted is not None else ""
            return output
    except Exception as e:
        logger.exception("Error getting all configs", exc_info=e)
        return {}

def add_core_memory(fact: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            stmt = text("INSERT INTO core_memories (fact) VALUES (:f)")
            conn.execute(stmt, {"f": fact})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding core memory", exc_info=e)
        return False

def get_core_memories():
    if not engine: return []
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect
            if not inspect(engine).has_table("core_memories"): return []
            stmt = select(core_memories.c.id, core_memories.c.fact)
            result = conn.execute(stmt)
            return [{"id": row[0], "fact": row[1]} for row in result]
    except Exception as e:
        logger.exception("Error getting core memories", exc_info=e)
        return []

def delete_core_memory(mem_id: int):
    if not engine: return False
    try:
        with engine.connect() as conn:
            stmt = text("DELETE FROM core_memories WHERE id = :id")
            conn.execute(stmt, {"id": mem_id})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error deleting core memory", exc_info=e)
        return False

def get_network_targets():
    if not engine: return []
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect
            if not inspect(engine).has_table("network_targets"): return []
            stmt = select(network_targets.c.id, network_targets.c.name, network_targets.c.ip_address)
            result = conn.execute(stmt)
            return [{"id": row[0], "name": row[1], "ip_address": row[2]} for row in result]
    except Exception as e:
        logger.exception("Error getting network targets", exc_info=e)
        return []

def add_network_target(name: str, ip_address: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            stmt = text("INSERT INTO network_targets (name, ip_address) VALUES (:n, :i)")
            conn.execute(stmt, {"n": name, "i": ip_address})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error adding network target", exc_info=e)
        return False

def delete_network_target(target_id: int):
    if not engine: return False
    try:
        with engine.connect() as conn:
            stmt = text("DELETE FROM network_targets WHERE id = :id")
            conn.execute(stmt, {"id": target_id})
            conn.commit()
            return True
    except Exception as e:
        logger.exception("Error deleting network target", exc_info=e)
        return False


def _parse_iso_datetime(value: Optional[str]):
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def create_task(title: str, description: str = "", status: str = "todo", priority: str = "medium", due_at: Optional[str] = None, session_id: Optional[str] = None):
    if not engine:
        return None
    try:
        now = datetime.now(timezone.utc)
        due_dt = _parse_iso_datetime(due_at)
        with engine.connect() as conn:
            stmt = text(
                "INSERT INTO tasks (title, description, status, priority, due_at, session_id, created_at, updated_at) "
                "VALUES (:title, :description, :status, :priority, :due_at, :session_id, :created_at, :updated_at) "
                "RETURNING id"
            )
            result = conn.execute(stmt, {
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "due_at": due_dt,
                "session_id": session_id,
                "created_at": now,
                "updated_at": now,
            })
            task_id = result.scalar()
            conn.commit()
            return get_task_by_id(task_id)
    except Exception as e:
        logger.exception("Error creating task", exc_info=e)
        return None


def get_task_by_id(task_id: int):
    if not engine:
        return None
    try:
        with engine.connect() as conn:
            stmt = text("SELECT id, title, description, status, priority, due_at, session_id, created_at, updated_at FROM tasks WHERE id = :id")
            row = conn.execute(stmt, {"id": task_id}).mappings().first()
            if not row:
                return None
            return dict(row)
    except Exception as e:
        logger.exception("Error fetching task by id", exc_info=e)
        return None


def list_tasks(status: Optional[str] = None, priority: Optional[str] = None, session_id: Optional[str] = None, due_before: Optional[str] = None, due_after: Optional[str] = None):
    if not engine:
        return []
    try:
        where_parts = []
        params = {}
        if status:
            where_parts.append("status = :status")
            params["status"] = status
        if priority:
            where_parts.append("priority = :priority")
            params["priority"] = priority
        if session_id:
            where_parts.append("session_id = :session_id")
            params["session_id"] = session_id
        if due_before:
            parsed = _parse_iso_datetime(due_before)
            if parsed:
                where_parts.append("due_at <= :due_before")
                params["due_before"] = parsed
        if due_after:
            parsed = _parse_iso_datetime(due_after)
            if parsed:
                where_parts.append("due_at >= :due_after")
                params["due_after"] = parsed

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        query = (
            "SELECT id, title, description, status, priority, due_at, session_id, created_at, updated_at "
            f"FROM tasks {where_sql} ORDER BY COALESCE(due_at, created_at) ASC, id DESC"
        )
        with engine.connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error listing tasks", exc_info=e)
        return []


def update_task(task_id: int, title: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None, priority: Optional[str] = None, due_at: Optional[str] = None, session_id: Optional[str] = None):
    if not engine:
        return None
    try:
        set_parts = ["updated_at = :updated_at"]
        params = {"id": task_id, "updated_at": datetime.now(timezone.utc)}

        if title is not None:
            set_parts.append("title = :title")
            params["title"] = title
        if description is not None:
            set_parts.append("description = :description")
            params["description"] = description
        if status is not None:
            set_parts.append("status = :status")
            params["status"] = status
        if priority is not None:
            set_parts.append("priority = :priority")
            params["priority"] = priority
        if due_at is not None:
            params["due_at"] = _parse_iso_datetime(due_at) if due_at else None
            set_parts.append("due_at = :due_at")
        if session_id is not None:
            set_parts.append("session_id = :session_id")
            params["session_id"] = session_id

        with engine.connect() as conn:
            stmt = text(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = :id")
            result = conn.execute(stmt, params)
            conn.commit()
            if result.rowcount == 0:
                return None
            return get_task_by_id(task_id)
    except Exception as e:
        logger.exception("Error updating task", exc_info=e)
        return None


def delete_task(task_id: int):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            stmt = text("DELETE FROM tasks WHERE id = :id")
            result = conn.execute(stmt, {"id": task_id})
            conn.commit()
            return result.rowcount > 0
    except Exception as e:
        logger.exception("Error deleting task", exc_info=e)
        return False
