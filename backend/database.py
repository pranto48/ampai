import os
import logging
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select, inspect, text, Boolean
from langchain_community.chat_message_histories import SQLChatMessageHistory


def get_logger(name: str):
    """Backward-compatible logger helper for older modules/import paths."""
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    return logging.getLogger(name)


logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")
CHAT_HISTORY_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")

engine = None
metadata = MetaData()
ENCRYPTED_PREFIX = "enc::"
logger = get_logger(__name__)

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
    'users', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('username', String, unique=True),
    Column('password_hash', String),
    Column('role', String, default='user'),
    Column('created_at', String, default=lambda: datetime.now(timezone.utc).isoformat())
)


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


def get_all_sessions(query: str = "", include_archived: bool = False):
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if not inspector.has_table(CHAT_HISTORY_TABLE):
                return []

            _ensure_session_metadata_columns(conn)

            # Canonical source: message_store table used by SQLChatMessageHistory.
            stmt_sessions = select(message_store.c.session_id).distinct()
            session_ids = [row[0] for row in conn.execute(stmt_sessions) if row[0]]

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
                if not include_archived and meta["archived"]:
                    continue
                if q and q not in s_id.lower() and q not in meta["category"].lower():
                    continue
                output.append({"session_id": s_id, **meta})

            output.sort(key=lambda x: (not x["pinned"], x.get("updated_at") or "", x["session_id"]), reverse=False)
            return output
    except Exception as e:
        logger.warning(f"Error fetching sessions: {e}")
        return []


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


def set_session_flags(session_id: str, pinned: bool = None, archived: bool = None):
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            _ensure_session_metadata_columns(conn)
            touch = _now_iso()
            existing = conn.execute(select(session_metadata).where(session_metadata.c.session_id == session_id)).first()
            category = existing.category if existing else "Uncategorized"
            curr_pinned = bool(existing.pinned) if existing else False
            curr_archived = bool(existing.archived) if existing else False
            upsert_stmt = text(
                "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at) VALUES (:s, :c, :p, :a, :u) "
                "ON CONFLICT (session_id) DO UPDATE SET pinned = EXCLUDED.pinned, archived = EXCLUDED.archived, updated_at = EXCLUDED.updated_at"
            )
            conn.execute(upsert_stmt, {
                "s": session_id,
                "c": category,
                "p": curr_pinned if pinned is None else pinned,
                "a": curr_archived if archived is None else archived,
                "u": touch,
            })
            conn.commit()
            return True
    except Exception as e:
        logger.warning(f"Error setting session flags: {e}")
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
        logger.warning(f"Error deleting session metadata: {e}")
        return False


def get_config(key: str, default=None):
    if not engine: return default
    try:
        with engine.connect() as conn:
            stmt = select(app_configs.c.config_value).where(app_configs.c.config_key == key)
            result = conn.execute(stmt).first()
            return result[0] if result else default
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
            return {row[0]: row[1] for row in conn.execute(stmt)}
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
            existing = conn.execute(select(users.c.id).where(users.c.username == username)).first()
            if existing:
                return False, 'username_exists'
            conn.execute(
                text("INSERT INTO users (username, password_hash, role, created_at) VALUES (:u, :p, :r, :c)"),
                {'u': username, 'p': _hash_password(password), 'r': role, 'c': _now_iso()}
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
                select(users.c.id, users.c.username, users.c.password_hash, users.c.role).where(users.c.username == username)
            ).first()
            if not row:
                return None
            if row.password_hash != _hash_password(password):
                return None
            return {'id': row.id, 'username': row.username, 'role': row.role}
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
