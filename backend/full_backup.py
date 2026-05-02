"""
full_backup.py
==============
Categorised memory backup (5 GB max per slot) + full-system backup/restore.

Full backup includes:
  - All chat session messages (grouped by category)
  - Memory candidates (approved, grouped by category)
  - Core memories
  - Users (username, role, hashed password)
  - AI model API keys & all app_configs settings
  - Personas
  - Tasks
  - Network targets
  - Backup manifest / metadata
"""

import gzip
import hashlib
import json
import os
import zipfile
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from database import engine, CHAT_HISTORY_TABLE, decrypt_config_value

SCHEMA_VERSION = "2.0"
SLOT_SIZE_BYTES = int(os.getenv("FULL_BACKUP_SLOT_SIZE_GB", "5")) * 1024 ** 3  # default 5 GB
FULL_BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "full_backups")


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _load_json(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


# ─────────────────────────────────────────────────────────────
# Data extraction
# ─────────────────────────────────────────────────────────────

def _fetch_sessions_by_category() -> Dict[str, List[Dict]]:
    """Return {category: [{session_id, messages:[]}]} from the DB."""
    if not engine:
        return {}
    result: Dict[str, List[Dict]] = {}
    try:
        with engine.connect() as conn:
            # All session IDs + categories
            meta_rows = conn.execute(text(
                "SELECT session_id, COALESCE(category,'Uncategorized') as category "
                "FROM session_metadata"
            )).fetchall()
            cat_map: Dict[str, str] = {r[0]: r[1] for r in meta_rows}

            # All sessions in chat history
            session_rows = conn.execute(text(
                f"SELECT DISTINCT session_id FROM {CHAT_HISTORY_TABLE} WHERE session_id IS NOT NULL"
            )).fetchall()

            for (sid,) in session_rows:
                cat = cat_map.get(sid, "Uncategorized")
                msgs = conn.execute(text(
                    f"SELECT message FROM {CHAT_HISTORY_TABLE} "
                    "WHERE session_id=:s ORDER BY id ASC"
                ), {"s": sid}).fetchall()
                parsed = []
                for (raw,) in msgs:
                    try:
                        obj = json.loads(raw)
                        t = obj.get("type")
                        c = (obj.get("data") or {}).get("content", "")
                        if t in ("human", "ai"):
                            parsed.append({"type": t, "content": c})
                    except Exception:
                        pass
                result.setdefault(cat, []).append({"session_id": sid, "messages": parsed})
    except Exception as e:
        print(f"[full_backup] fetch sessions error: {e}")
    return result


def _fetch_memories_by_category() -> Dict[str, List[Dict]]:
    """Return {category: [memory_candidate_row]} grouped by session category."""
    if not engine:
        return {}
    result: Dict[str, List[Dict]] = {}
    try:
        with engine.connect() as conn:
            cat_map_rows = conn.execute(text(
                "SELECT session_id, COALESCE(category,'Uncategorized') FROM session_metadata"
            )).fetchall()
            cat_map: Dict[str, str] = {r[0]: r[1] for r in cat_map_rows}

            rows = conn.execute(text(
                "SELECT id, username, session_id, candidate_text, confidence, "
                "status, created_at FROM memory_candidates"
            )).fetchall()
            for r in rows:
                cat = cat_map.get(r[2] or "", "Uncategorized")
                result.setdefault(cat, []).append({
                    "id": r[0], "username": r[1], "session_id": r[2],
                    "candidate_text": r[3], "confidence": r[4],
                    "status": r[5], "created_at": str(r[6] or ""),
                })
    except Exception as e:
        print(f"[full_backup] fetch memories error: {e}")
    return result


def _fetch_core_memories() -> List[Dict]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, fact FROM core_memories")).fetchall()
            return [{"id": r[0], "fact": r[1]} for r in rows]
    except Exception:
        return []


def _fetch_users() -> List[Dict]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT username, role, password_hash, created_at FROM users"
            )).fetchall()
            return [{"username": r[0], "role": r[1],
                     "password_hash": r[2], "created_at": str(r[3] or "")} for r in rows]
    except Exception:
        return []


def _fetch_all_configs() -> Dict[str, str]:
    """Return all app_configs decrypted."""
    if not engine:
        return {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT config_key, config_value FROM app_configs")).fetchall()
            return {r[0]: decrypt_config_value(r[1]) for r in rows}
    except Exception:
        return {}


def _fetch_personas() -> List[Dict]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, username, name, system_prompt, tags, is_default, created_at FROM persona_presets"
            )).fetchall()
            return [{"id": r[0], "username": r[1], "name": r[2], "system_prompt": r[3],
                     "tags": r[4], "is_default": bool(r[5]), "created_at": str(r[6] or "")} for r in rows]
    except Exception:
        return []


def _fetch_tasks() -> List[Dict]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, title, description, status, priority, due_at, session_id, "
                "created_at, updated_at, username FROM tasks"
            )).fetchall()
            return [{"id": r[0], "title": r[1], "description": r[2], "status": r[3],
                     "priority": r[4], "due_at": r[5], "session_id": r[6],
                     "created_at": str(r[7] or ""), "updated_at": str(r[8] or ""),
                     "username": r[9] if len(r) > 9 else ""} for r in rows]
    except Exception:
        return []


def _fetch_network_targets() -> List[Dict]:
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name, ip_address FROM network_targets")).fetchall()
            return [{"id": r[0], "name": r[1], "ip_address": r[2]} for r in rows]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# Memory slot builder  (5 GB chunks per category)
# ─────────────────────────────────────────────────────────────

def build_memory_slots(
    sessions_by_cat: Dict[str, List[Dict]],
    memories_by_cat: Dict[str, List[Dict]],
    slot_size: int = SLOT_SIZE_BYTES,
) -> Tuple[List[Dict], Dict]:
    """
    Pack category data into slots of up to `slot_size` bytes.
    Returns (slots, summary):
      slots  = [{"slot": 1, "categories": [...], "bytes": N, "payload": {...}}, ...]
      summary = {category: slot_number, ...}
    """
    slots: List[Dict] = []
    cat_to_slot: Dict[str, int] = {}
    current_payload: Dict[str, Any] = {"categories": {}}
    current_bytes = 0
    slot_num = 1

    all_categories = sorted(set(list(sessions_by_cat.keys()) + list(memories_by_cat.keys())))

    for cat in all_categories:
        cat_data = {
            "sessions": sessions_by_cat.get(cat, []),
            "memories": memories_by_cat.get(cat, []),
        }
        cat_bytes = len(_dump(cat_data))

        # Flush slot if adding this category would exceed limit
        if current_bytes + cat_bytes > slot_size and current_bytes > 0:
            slots.append({
                "slot": slot_num,
                "categories": list(current_payload["categories"].keys()),
                "bytes": current_bytes,
                "payload": current_payload,
            })
            slot_num += 1
            current_payload = {"categories": {}}
            current_bytes = 0

        current_payload["categories"][cat] = cat_data
        current_bytes += cat_bytes
        cat_to_slot[cat] = slot_num

    # Final slot
    if current_payload["categories"]:
        slots.append({
            "slot": slot_num,
            "categories": list(current_payload["categories"].keys()),
            "bytes": current_bytes,
            "payload": current_payload,
        })

    return slots, cat_to_slot


# ─────────────────────────────────────────────────────────────
# Full backup builder
# ─────────────────────────────────────────────────────────────

def build_full_backup(actor: str) -> Dict[str, Any]:
    """
    Collect all data, split into memory slots, and return a bundle dict.
    {
        "manifest": {...},
        "memory_slots": [{"slot":1,"categories":[...],"bytes":N,"checksum":""}, ...],
        "full_data": {
            "sessions_by_category": {...},
            "memories_by_category": {...},
            "core_memories": [...],
            "users": [...],
            "configs": {...},
            "personas": [...],
            "tasks": [...],
            "network_targets": [...],
        }
    }
    """
    ts = _now()
    sessions_by_cat = _fetch_sessions_by_category()
    memories_by_cat = _fetch_memories_by_category()
    core_mems = _fetch_core_memories()
    users = _fetch_users()
    configs = _fetch_all_configs()
    personas = _fetch_personas()
    tasks = _fetch_tasks()
    network_targets = _fetch_network_targets()

    slots, cat_to_slot = build_memory_slots(sessions_by_cat, memories_by_cat)

    # Strip payload from slot summary (keep it separate for download)
    slot_summaries = []
    for s in slots:
        payload_bytes = _dump(s["payload"])
        checksum = _sha256(payload_bytes)
        slot_summaries.append({
            "slot": s["slot"],
            "categories": s["categories"],
            "bytes": s["bytes"],
            "checksum": checksum,
        })

    total_sessions = sum(len(v) for v in sessions_by_cat.values())
    total_memories = sum(len(v) for v in memories_by_cat.values())
    total_messages = sum(
        len(sess.get("messages", []))
        for slist in sessions_by_cat.values()
        for sess in slist
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": ts,
        "created_by": actor,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_memories": total_memories,
        "total_core_memories": len(core_mems),
        "total_users": len(users),
        "total_configs": len(configs),
        "total_personas": len(personas),
        "total_tasks": len(tasks),
        "slot_count": len(slots),
        "slot_size_bytes": SLOT_SIZE_BYTES,
        "category_slot_map": cat_to_slot,
        "slots": slot_summaries,
    }

    full_data = {
        "sessions_by_category": sessions_by_cat,
        "memories_by_category": memories_by_cat,
        "core_memories": core_mems,
        "users": users,
        "configs": configs,
        "personas": personas,
        "tasks": tasks,
        "network_targets": network_targets,
    }

    return {
        "manifest": manifest,
        "slots": slots,   # includes payload
        "full_data": full_data,
    }


# ─────────────────────────────────────────────────────────────
# Disk save  (zip with manifest + per-slot files)
# ─────────────────────────────────────────────────────────────

def save_full_backup_to_disk(bundle: Dict, output_dir: Optional[str] = None) -> str:
    """
    Writes a .zip archive:
      manifest.json
      slot_1.json.gz, slot_2.json.gz, ...
      full_data.json.gz  (complete non-slot data)
    Returns the path to the .zip file.
    """
    dest_dir = output_dir or FULL_BACKUP_DIR
    os.makedirs(dest_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = os.path.join(dest_dir, f"ampai_full_backup_{ts}.zip")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        zf.writestr("manifest.json", json.dumps(bundle["manifest"], indent=2))

        # Per-slot gzip files
        for s in bundle["slots"]:
            slot_bytes = gzip.compress(_dump(s["payload"]))
            zf.writestr(f"slot_{s['slot']}.json.gz", slot_bytes)

        # Full data (non-memory: configs, users, tasks, etc.)
        non_mem = {k: v for k, v in bundle["full_data"].items()
                   if k not in ("sessions_by_category", "memories_by_category")}
        zf.writestr("full_data.json.gz", gzip.compress(_dump(non_mem)))

    return zip_path


# ─────────────────────────────────────────────────────────────
# List saved backups
# ─────────────────────────────────────────────────────────────

def list_full_backups(backup_dir: Optional[str] = None) -> List[Dict]:
    dest_dir = backup_dir or FULL_BACKUP_DIR
    os.makedirs(dest_dir, exist_ok=True)
    result = []
    for fname in sorted(os.listdir(dest_dir), reverse=True):
        if not fname.endswith(".zip"):
            continue
        fpath = os.path.join(dest_dir, fname)
        size = os.path.getsize(fpath)
        # Try to read manifest from zip
        manifest = {}
        try:
            with zipfile.ZipFile(fpath) as zf:
                if "manifest.json" in zf.namelist():
                    manifest = json.loads(zf.read("manifest.json").decode())
        except Exception:
            pass
        result.append({
            "filename": fname,
            "path": fpath,
            "size_bytes": size,
            "created_at": manifest.get("created_at", ""),
            "slot_count": manifest.get("slot_count", 0),
            "total_sessions": manifest.get("total_sessions", 0),
            "total_messages": manifest.get("total_messages", 0),
            "total_memories": manifest.get("total_memories", 0),
            "total_users": manifest.get("total_users", 0),
            "schema_version": manifest.get("schema_version", ""),
        })
    return result


# ─────────────────────────────────────────────────────────────
# Restore
# ─────────────────────────────────────────────────────────────

def restore_full_backup(zip_path: str, options: Dict) -> Dict[str, Any]:
    """
    Restore from a full-backup zip.
    options keys (all bool, default True):
      restore_chats, restore_memories, restore_core_memories,
      restore_users, restore_configs, restore_personas, restore_tasks
    Returns {"ok": True/False, "summary": {...}, "errors": [...]}
    """
    if not engine:
        return {"ok": False, "errors": ["Database not available"]}

    errors: List[str] = []
    summary: Dict[str, int] = {}

    do = lambda k: options.get(k, True)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()

            # ── Full (non-slot) data ─────────────────────────────────
            non_mem: Dict = {}
            if "full_data.json.gz" in names:
                non_mem = _load_json(gzip.decompress(zf.read("full_data.json.gz")))

            # ── Slot data ────────────────────────────────────────────
            slot_files = sorted(n for n in names if n.startswith("slot_") and n.endswith(".json.gz"))
            sessions_by_cat: Dict[str, List] = {}
            memories_by_cat: Dict[str, List] = {}
            for sf in slot_files:
                payload = _load_json(gzip.decompress(zf.read(sf)))
                for cat, cat_data in (payload.get("categories") or {}).items():
                    sessions_by_cat.setdefault(cat, []).extend(cat_data.get("sessions", []))
                    memories_by_cat.setdefault(cat, []).extend(cat_data.get("memories", []))

        with engine.begin() as conn:

            # ── Chat sessions ────────────────────────────────────────
            if do("restore_chats"):
                n_sessions = n_messages = 0
                for cat, sessions in sessions_by_cat.items():
                    for sess in sessions:
                        sid = sess.get("session_id", "")
                        if not sid:
                            continue
                        # Upsert session metadata
                        conn.execute(text(
                            "INSERT INTO session_metadata (session_id, category, pinned, archived, updated_at) "
                            "VALUES (:s,:c,FALSE,FALSE,NOW()) "
                            "ON CONFLICT (session_id) DO UPDATE SET category=EXCLUDED.category"
                        ), {"s": sid, "c": cat})
                        for msg in sess.get("messages", []):
                            raw = json.dumps({"type": msg["type"],
                                              "data": {"content": msg.get("content", "")}})
                            conn.execute(text(
                                f"INSERT INTO {CHAT_HISTORY_TABLE} (session_id, message) "
                                "VALUES (:s,:m) ON CONFLICT DO NOTHING"
                            ), {"s": sid, "m": raw})
                            n_messages += 1
                        n_sessions += 1
                summary["restored_sessions"] = n_sessions
                summary["restored_messages"] = n_messages

            # ── Memory candidates ────────────────────────────────────
            if do("restore_memories"):
                n_mems = 0
                for cat, mems in memories_by_cat.items():
                    for m in mems:
                        try:
                            conn.execute(text(
                                "INSERT INTO memory_candidates "
                                "(username, session_id, candidate_text, confidence, status, created_at) "
                                "VALUES (:u,:s,:t,:c,:st,NOW()) ON CONFLICT DO NOTHING"
                            ), {
                                "u": m.get("username", "system"),
                                "s": m.get("session_id", ""),
                                "t": (m.get("candidate_text") or "")[:2000],
                                "c": str(m.get("confidence", "")),
                                "st": m.get("status", "approved"),
                            })
                            n_mems += 1
                        except Exception as ex:
                            errors.append(f"memory: {ex}")
                summary["restored_memories"] = n_mems

            # ── Core memories ─────────────────────────────────────────
            if do("restore_core_memories"):
                n_cm = 0
                for cm in (non_mem.get("core_memories") or []):
                    try:
                        conn.execute(text(
                            "INSERT INTO core_memories (fact) VALUES (:f) ON CONFLICT DO NOTHING"
                        ), {"f": cm.get("fact", "")})
                        n_cm += 1
                    except Exception as ex:
                        errors.append(f"core_memory: {ex}")
                summary["restored_core_memories"] = n_cm

            # ── Users ─────────────────────────────────────────────────
            if do("restore_users"):
                n_users = 0
                for u in (non_mem.get("users") or []):
                    try:
                        conn.execute(text(
                            "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                            "VALUES (:u,:r,:p,NOW(),NOW()) "
                            "ON CONFLICT (username) DO UPDATE SET role=EXCLUDED.role"
                        ), {"u": u["username"], "r": u.get("role", "user"),
                            "p": u.get("password_hash", "")})
                        n_users += 1
                    except Exception as ex:
                        errors.append(f"user: {ex}")
                summary["restored_users"] = n_users

            # ── Configs (AI keys + settings) ─────────────────────────
            if do("restore_configs"):
                n_cfg = 0
                for k, v in (non_mem.get("configs") or {}).items():
                    try:
                        conn.execute(text(
                            "INSERT INTO app_configs (config_key, config_value) "
                            "VALUES (:k,:v) ON CONFLICT (config_key) "
                            "DO UPDATE SET config_value=EXCLUDED.config_value"
                        ), {"k": k, "v": str(v)})
                        n_cfg += 1
                    except Exception as ex:
                        errors.append(f"config: {ex}")
                summary["restored_configs"] = n_cfg

            # ── Personas ──────────────────────────────────────────────
            if do("restore_personas"):
                n_p = 0
                for p in (non_mem.get("personas") or []):
                    try:
                        conn.execute(text(
                            "INSERT INTO persona_presets "
                            "(username, name, system_prompt, tags, is_default, created_at) "
                            "VALUES (:u,:n,:sp,:t,:d,NOW()) ON CONFLICT DO NOTHING"
                        ), {"u": p.get("username"), "n": p.get("name", ""),
                            "sp": p.get("system_prompt", ""), "t": p.get("tags", ""),
                            "d": bool(p.get("is_default"))})
                        n_p += 1
                    except Exception as ex:
                        errors.append(f"persona: {ex}")
                summary["restored_personas"] = n_p

            # ── Tasks ─────────────────────────────────────────────────
            if do("restore_tasks"):
                n_t = 0
                for t in (non_mem.get("tasks") or []):
                    try:
                        conn.execute(text(
                            "INSERT INTO tasks (title, description, status, priority, "
                            "due_at, session_id, created_at, updated_at) "
                            "VALUES (:ti,:de,:st,:pr,:du,:se,NOW(),NOW()) ON CONFLICT DO NOTHING"
                        ), {"ti": t.get("title", ""), "de": t.get("description", ""),
                            "st": t.get("status", "todo"), "pr": t.get("priority", "medium"),
                            "du": t.get("due_at"), "se": t.get("session_id")})
                        n_t += 1
                    except Exception as ex:
                        errors.append(f"task: {ex}")
                summary["restored_tasks"] = n_t

    except Exception as e:
        errors.append(f"Fatal: {e}")
        return {"ok": False, "errors": errors, "summary": summary}

    return {"ok": len(errors) == 0, "summary": summary, "errors": errors}
