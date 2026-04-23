import os
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select, inspect, text

# Allow overriding for local testing vs docker
# Default to Postgres container format
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")

engine = None
metadata = MetaData()

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

try:
    engine = create_engine(DATABASE_URL)
    metadata.create_all(engine)
except Exception:
    pass

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
        print(f"Error fetching sessions: {e}")
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
        print(f"Error setting category: {e}")
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
        print(f"Error deleting session metadata: {e}")
        return False

def get_config(key: str, default=None):
    if not engine: return default
    try:
        with engine.connect() as conn:
            stmt = select(app_configs.c.config_value).where(app_configs.c.config_key == key)
            result = conn.execute(stmt).first()
            if result:
                return result[0]
            return default
    except Exception as e:
        print(f"Error getting config {key}: {e}")
        return default

def set_config(key: str, value: str):
    if not engine: return False
    try:
        with engine.connect() as conn:
            upsert_stmt = text(
                "INSERT INTO app_configs (config_key, config_value) VALUES (:k, :v) "
                "ON CONFLICT (config_key) DO UPDATE SET config_value = EXCLUDED.config_value"
            )
            conn.execute(upsert_stmt, {"k": key, "v": value})
            conn.commit()
            return True
    except Exception as e:
        print(f"Error setting config {key}: {e}")
        return False

def get_all_configs():
    if not engine: return {}
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect
            if not inspect(engine).has_table("app_configs"): return {}
            stmt = select(app_configs.c.config_key, app_configs.c.config_value)
            result = conn.execute(stmt)
            return {row[0]: row[1] for row in result}
    except Exception as e:
        print(f"Error getting all configs: {e}")
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
        print(f"Error adding core memory: {e}")
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
        print(f"Error getting core memories: {e}")
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
        print(f"Error deleting core memory: {e}")
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
        print(f"Error getting network targets: {e}")
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
        print(f"Error adding network target: {e}")
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
        print(f"Error deleting network target: {e}")
        return False
