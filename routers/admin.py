"""Admin router: users, configs, backup/restore, retention, audit, update endpoints."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from backup_helpers import (
    build_backup_payload,
    test_ftp_connection,
    test_smb_connection,
    write_backup_ftp,
    write_backup_local,
    write_backup_smb,
)
from services.backup_service import BackupService
from core.deps import UserContext, require_admin_user
from core.helpers import (
    _check_db_health,
    _send_resend_email,
    _to_bool,
)
from core.models import (
    AdminPasswordChangeRequest,
    AdminSettingsImportRequest,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    BackupConnectionTestRequest,
    BackupFtpTestRequest,
    BackupProfileCreateRequest,
    BackupProfileUpdateRequest,
    BackupRestoreRequest,
    ConfigUpdateRequest,
    FullRestoreRequest,
    OrphanAdoptionRunRequest,
    RestorePreflightRequest,
    RestoreStartRequest,
    RetentionDryRunRequest,
    RetentionRunRequest,
    SessionRepairRequest,
)
from database import (
    CHAT_HISTORY_TABLE,
    apply_retention_policy,
    create_backup_job,
    create_backup_profile,
    create_restore_job,
    delete_backup_profile,
    engine,
    ensure_session_owner,
    export_all_sessions_for_backup,
    get_all_configs,
    get_all_sessions,
    get_backup_job,
    get_backup_profile,
    get_backup_verification_kpis,
    get_config,
    get_duplicate_message_counts,
    get_restore_job,
    get_session_owner,
    get_user,
    list_audit_events,
    list_backup_jobs,
    list_backup_profiles,
    list_restore_jobs,
    log_audit_event,
    migrate_app_config_encryption,
    session_exists,
    set_config,
    touch_session_updated_at,
    update_backup_job,
    update_backup_profile,
    update_restore_job,
)
from database import create_user as db_create_user
from database import delete_user as db_delete_user
from database import engine as db_engine
from database import list_users as db_list_users
from database import update_user as db_update_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from passlib.context import CryptContext
from sqlalchemy import text

router = APIRouter(tags=["admin"])
logger = logging.getLogger("ampai")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "..", "data", "uploads"
)

SECRET_CONFIG_KEYS = {
    "openai_api_key",
    "gemini_api_key",
    "anthropic_api_key",
    "openrouter_api_key",
    "anythingllm_api_key",
    "serpapi_api_key",
    "resend_api_key",
    "backup_ftp_password",
    "backup_smb_password",
    "bing_api_key",
    "generic_api_key",
    "telegram_bot_token",
    "telegram_webhook_secret",
}

RESTORE_PREFLIGHT_CACHE: Dict[str, Dict[str, Any]] = {}
RESTORE_PREFLIGHT_TTL_SECONDS = 15 * 60
RESTORE_SCHEMA_VERSION = "1.1"
BACKUP_JOB_QUEUE: "Queue[Dict[str, Any]]" = Queue(maxsize=200)
RESTORE_JOB_QUEUE: "Queue[Dict[str, Any]]" = Queue(maxsize=50)

CODE_BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "..", "data", "code_backups"
)
REPO_URL = os.getenv("AMPAI_REPO_URL", "https://github.com/pranto48/ampai.git")
_update_lock = threading.Lock()
_update_log_lines: List[str] = []
_update_status: Dict[str, Any] = {
    "state": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None,
}


# ── Admin users ───────────────────────────────────────────────────────────────


@router.get("/api/admin/users")
def admin_list_users(_: UserContext = Depends(require_admin_user)):
    return {"users": db_list_users()}


@router.post("/api/admin/users")
def admin_create_user(
    request: AdminUserCreateRequest, _: UserContext = Depends(require_admin_user)
):
    username = (request.username or "").strip()
    role = (request.role or "user").strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(request.password or "") < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    if get_user(username):
        raise HTTPException(status_code=409, detail="User already exists")
    if not db_create_user(
        username=username, role=role, password_hash=pwd_context.hash(request.password)
    ):
        raise HTTPException(status_code=500, detail="Failed to create user")
    return {"status": "success"}


@router.patch("/api/admin/users/{username}")
def admin_update_user(
    username: str,
    request: AdminUserUpdateRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    username = username.strip()
    existing = get_user(username)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    role = request.role.strip().lower() if request.role is not None else None
    if role is not None and role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    if request.password is not None and len(request.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )
    if existing["username"] == current_user.username and role == "user":
        raise HTTPException(
            status_code=400, detail="You cannot remove your own admin role"
        )
    password_hash = pwd_context.hash(request.password) if request.password else None
    if not db_update_user(username=username, role=role, password_hash=password_hash):
        raise HTTPException(status_code=500, detail="Failed to update user")
    return {"status": "success"}


@router.delete("/api/admin/users/{username}")
def admin_delete_user(
    username: str, current_user: UserContext = Depends(require_admin_user)
):
    username = username.strip()
    if username == current_user.username:
        raise HTTPException(
            status_code=400, detail="You cannot delete your own account"
        )
    existing = get_user(username)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    if not db_delete_user(username):
        raise HTTPException(status_code=500, detail="Failed to delete user")
    return {"status": "success"}


@router.post("/api/admin/change-password")
def admin_change_password(
    request: AdminPasswordChangeRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    user = get_user(current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="Admin user not found")
    if not pwd_context.verify(request.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(request.new_password or "") < 8:
        raise HTTPException(
            status_code=400, detail="New password must be at least 8 characters"
        )
    new_hash = pwd_context.hash(request.new_password)
    if not db_update_user(current_user.username, password_hash=new_hash):
        raise HTTPException(status_code=500, detail="Failed to update admin password")
    set_config("admin_password_hash", new_hash)
    return {"status": "success"}


# ── Admin configs ─────────────────────────────────────────────────────────────


@router.get("/api/admin/configs")
def get_admin_configs(user: UserContext = Depends(require_admin_user)):
    raw_configs = get_all_configs()
    result = {}
    for k, v in raw_configs.items():
        v = v or ""
        if v and (k in SECRET_CONFIG_KEYS or "api_key" in k or "password" in k):
            result[k] = (v[:4] + "..." + v[-4:]) if len(v) > 8 else "****"
        else:
            result[k] = v
    return result


@router.patch("/api/admin/configs")
@router.post("/api/admin/configs")
def update_admin_configs(
    request: ConfigUpdateRequest, user: UserContext = Depends(require_admin_user)
):
    saved = []
    skipped = []
    for k, v in request.configs.items():
        if not k:
            continue
        if k == "backup_mode":
            mode = (v or "").strip().lower()
            if mode not in {"local", "ftp", "smb"}:
                raise HTTPException(
                    status_code=400, detail="backup_mode must be local, ftp, or smb"
                )
        if v and "..." in v:
            skipped.append(k)
            continue
        set_config(k, v or "")
        saved.append(k)
    log_audit_event(
        username=user.username,
        action="admin.configs.update",
        details=f"saved={len(saved)};skipped={len(skipped)}",
    )
    return {"status": "success", "saved": saved, "skipped": skipped}


@router.get("/api/admin/settings/export")
def export_admin_settings(
    include_secrets: bool = Query(default=False),
    confirm_include_secrets: bool = Query(default=False),
    user: UserContext = Depends(require_admin_user),
):
    if include_secrets and not confirm_include_secrets:
        raise HTTPException(
            status_code=400,
            detail="include_secrets=true requires confirm_include_secrets=true",
        )
    raw_configs = get_all_configs()
    exported: Dict[str, str] = {}
    redacted: List[str] = []
    for key, value in raw_configs.items():
        safe_value = value or ""
        is_secret = key in SECRET_CONFIG_KEYS or "api_key" in key or "password" in key
        if is_secret and not include_secrets:
            redacted.append(key)
            continue
        exported[key] = safe_value
    log_audit_event(
        username=user.username,
        action="admin.settings.export",
        details=f"include_secrets={include_secrets};exported={len(exported)};redacted={len(redacted)}",
    )
    return {
        "configs": exported,
        "meta": {
            "include_secrets": include_secrets,
            "redacted_keys": sorted(redacted),
            "exported_key_count": len(exported),
        },
    }


@router.post("/api/admin/settings/import")
def import_admin_settings(
    request: AdminSettingsImportRequest, user: UserContext = Depends(require_admin_user)
):
    strategy = (request.conflict_strategy or "skip").strip().lower()
    if strategy not in {"skip", "overwrite"}:
        raise HTTPException(
            status_code=400, detail="conflict_strategy must be skip or overwrite"
        )
    incoming = request.configs or {}
    if not isinstance(incoming, dict):
        raise HTTPException(
            status_code=400, detail="configs must be an object of key/value pairs"
        )
    existing = get_all_configs()
    results: List[Dict[str, Any]] = []
    summary = {
        "created": 0,
        "updated": 0,
        "skipped_conflict": 0,
        "skipped_invalid": 0,
        "unchanged": 0,
    }
    to_apply: List[tuple] = []
    for key, raw_value in sorted(incoming.items(), key=lambda kv: kv[0]):
        normalized_key = (key or "").strip()
        if not normalized_key:
            summary["skipped_invalid"] += 1
            results.append(
                {"key": key, "status": "skipped_invalid", "reason": "empty key"}
            )
            continue
        value = "" if raw_value is None else str(raw_value)
        current = existing.get(normalized_key)
        if current is None:
            status = "created"
            summary["created"] += 1
            to_apply.append((normalized_key, value))
        elif current == value:
            status = "unchanged"
            summary["unchanged"] += 1
        elif strategy == "skip":
            status = "skipped_conflict"
            summary["skipped_conflict"] += 1
        else:
            status = "updated"
            summary["updated"] += 1
            to_apply.append((normalized_key, value))
        results.append(
            {
                "key": normalized_key,
                "status": status,
                "previous": current,
                "incoming": value,
            }
        )
    if not request.dry_run:
        for key, value in to_apply:
            set_config(key, value)
    log_audit_event(
        username=user.username,
        action="admin.settings.import",
        details=f"dry_run={request.dry_run};strategy={strategy};keys={len(incoming)};changes={len(to_apply)}",
    )
    return {
        "dry_run": request.dry_run,
        "conflict_strategy": strategy,
        "summary": summary,
        "results": results,
    }


@router.post("/api/admin/configs/migrate")
def migrate_admin_configs():
    result = migrate_app_config_encryption()
    return {"status": "success", **result}


# ── Admin settings health ─────────────────────────────────────────────────────


@router.get("/api/admin/settings/health")
def admin_settings_health(_: UserContext = Depends(require_admin_user)):
    from core.deps import JWT_EXPIRY_MINUTES, JWT_REMEMBER_ME_DAYS

    configs = get_all_configs()
    checks: List[Dict[str, str]] = []

    def _add(key, status, message, fix_hint=""):
        checks.append(
            {"key": key, "status": status, "message": message, "fix_hint": fix_hint}
        )

    local_only_mode = _to_bool(configs.get("local_only_mode", "false"))
    default_provider = (
        (
            configs.get("default_model_provider")
            or configs.get("model_provider")
            or "ollama"
        )
        .strip()
        .lower()
    )
    provider_key_map = {
        "openai": "openai_api_key",
        "gemini": "gemini_api_key",
        "anthropic": "anthropic_api_key",
        "openrouter": "openrouter_api_key",
        "anythingllm": "anythingllm_base_url",
        "generic": "generic_base_url",
        "ollama": "ollama_base_url",
    }
    required_key = provider_key_map.get(default_provider)
    provider_ready = local_only_mode or (
        required_key and bool((configs.get(required_key) or "").strip())
    )
    _add(
        "model_provider_readiness",
        "ok" if provider_ready else "error",
        f"Model provider ready ({default_provider})"
        if provider_ready
        else f"Model provider '{default_provider}' is missing required setting: {required_key or 'provider configuration'}",
        "Go fix: Models settings" if not provider_ready else "",
    )

    hybrid_enabled = _to_bool(configs.get("memory_hybrid_retrieval_enabled", "false"))
    embedding_provider = (
        (configs.get("memory_embedding_provider") or "").strip().lower()
    )
    embedding_model = (configs.get("memory_embedding_model") or "").strip()
    embedding_provider_ok = embedding_provider in {
        "ollama",
        "openai",
        "gemini",
        "openrouter",
        "anythingllm",
        "generic",
    }
    memory_ready = (not hybrid_enabled) or (
        embedding_provider_ok and bool(embedding_model)
    )
    memory_status = "ok" if memory_ready else ("warn" if hybrid_enabled else "ok")
    _add(
        "memory_retrieval_readiness",
        memory_status,
        "Hybrid memory retrieval ready"
        if memory_ready
        else "Hybrid memory retrieval is enabled but embedding provider/model is incomplete",
        "Go fix: Settings → Memory policy" if not memory_ready else "",
    )

    mode = (configs.get("backup_mode", "local") or "local").strip().lower()
    backup_ok = True
    if mode == "local":
        backup_ok = bool((configs.get("backup_local_path") or "").strip())
    elif mode in {"ftp", "smb"}:
        backup_ok = all(
            bool((configs.get(k) or "").strip())
            for k in [
                f"backup_{mode}_host",
                f"backup_{mode}_user",
                f"backup_{mode}_path",
                f"backup_{mode}_password",
            ]
        )
    _add(
        "backup_readiness",
        "ok" if backup_ok else "warn",
        "Backup destination/profile looks complete"
        if backup_ok
        else f"Backup mode '{mode}' has missing destination credentials/paths",
        "Go fix: Admin → Backup" if not backup_ok else "",
    )

    resend_key = bool((configs.get("resend_api_key") or "").strip())
    resend_from = bool((configs.get("resend_from_email") or "").strip())
    notif_ok = resend_key and resend_from
    _add(
        "notification_readiness",
        "ok" if notif_ok else "warn",
        "Email notifications ready"
        if notif_ok
        else "Resend notification config is incomplete",
        "Go fix: Settings → Email (Resend)" if not notif_ok else "",
    )

    jwt_ok = 5 <= JWT_EXPIRY_MINUTES <= 1440 and 1 <= JWT_REMEMBER_ME_DAYS <= 365
    _add(
        "auth_session_sanity",
        "ok" if jwt_ok else "error",
        "JWT/session ranges are sane"
        if jwt_ok
        else f"JWT ranges out of bounds (expiry={JWT_EXPIRY_MINUTES}, remember_days={JWT_REMEMBER_ME_DAYS})",
        "Set JWT_EXPIRY_MINUTES (5-1440) and JWT_REMEMBER_ME_DAYS (1-365) environment variables",
    )

    return {"checks": checks}


# ── Admin history duplicates ──────────────────────────────────────────────────


@router.get("/api/admin/history/duplicates")
def get_history_duplicates(_: UserContext = Depends(require_admin_user)):
    duplicates = get_duplicate_message_counts()
    return {
        "sessions_with_duplicates": len(duplicates),
        "duplicate_messages": sum(duplicates.values()),
        "by_session": duplicates,
    }


# ── Admin sessions ────────────────────────────────────────────────────────────


def _session_matches_migration_criteria(
    session_id: str, session_row: Dict[str, Any]
) -> bool:
    return session_id.startswith("tg_") or bool(session_row.get("archived"))


def _run_orphan_adoption(
    actor_username: str,
    orphan_session_ids: List[str],
    sessions: List[Dict[str, Any]],
    explicit: bool,
    force: bool = False,
    batch_size: int = 100,
) -> Dict[str, int]:
    from core.helpers import _parse_iso_dt

    raw_cutoff = (get_config("auth_orphan_adoption_cutoff_datetime", "") or "").strip()
    cutoff_dt = _parse_iso_dt(raw_cutoff)
    adopted_count = skipped_processed = skipped_newer = failed = processed = 0
    sessions_map = {(s.get("session_id") or ""): s for s in sessions}
    for sid in orphan_session_ids:
        if not sid:
            continue
        if processed >= batch_size:
            break
        processed += 1
        marker_key = f"auth_orphan_adoption_processed:{sid}"
        if get_config(marker_key, "0") == "1" and not force:
            skipped_processed += 1
            continue
        row = sessions_map.get(sid, {})
        updated_dt = _parse_iso_dt(row.get("updated_at"))
        meets_cutoff = bool(cutoff_dt and updated_dt and updated_dt <= cutoff_dt)
        matches_migration = _session_matches_migration_criteria(sid, row)
        if not (meets_cutoff or matches_migration or force):
            skipped_newer += 1
            continue
        try:
            if not get_session_owner(sid) and ensure_session_owner(sid, actor_username):
                adopted_count += 1
                log_audit_event(
                    username=actor_username,
                    action="session.orphan_adoption.adopted",
                    session_id=sid,
                    details=f"explicit={explicit};cutoff={raw_cutoff or 'none'}",
                )
            set_config(marker_key, "1")
        except Exception as exc:
            failed += 1
            logger.exception("Orphan adoption failed for session_id=%s", sid)
            log_audit_event(
                username=actor_username,
                action="session.orphan_adoption.failed",
                session_id=sid,
                details=f"error={str(exc)[:200]}",
            )
    log_audit_event(
        username=actor_username,
        action="session.orphan_adoption.run",
        details=f"explicit={explicit};force={force};processed={processed};adopted={adopted_count};skipped_processed={skipped_processed};skipped_newer={skipped_newer};failed={failed};cutoff={raw_cutoff or 'none'}",
    )
    return {
        "processed": processed,
        "adopted": adopted_count,
        "skipped_processed": skipped_processed,
        "skipped_newer": skipped_newer,
        "failed": failed,
    }


@router.post("/api/admin/sessions/adopt-orphans")
def admin_adopt_orphan_sessions(
    request: OrphanAdoptionRunRequest, user: UserContext = Depends(require_admin_user)
):
    sessions = get_all_sessions()
    orphan_session_ids = [
        s.get("session_id")
        for s in sessions
        if s.get("session_id") and not get_session_owner(s.get("session_id"))
    ]
    summary = _run_orphan_adoption(
        actor_username=user.username,
        orphan_session_ids=orphan_session_ids,
        sessions=sessions,
        explicit=True,
        force=request.force,
        batch_size=max(1, min(request.batch_size, 1000)),
    )
    return {
        "status": "success",
        "orphans_found": len(orphan_session_ids),
        "batch_size": max(1, min(request.batch_size, 1000)),
        "summary": summary,
    }


def _collect_known_session_ids() -> List[str]:
    import os

    from redis import Redis
    from session_recall import DB_PATH as SESSION_RECALL_DB_PATH

    known: set = set()
    if db_engine:
        try:
            with db_engine.connect() as conn:
                sql_rows = conn.execute(
                    text(
                        f"SELECT DISTINCT session_id FROM {CHAT_HISTORY_TABLE} WHERE session_id IS NOT NULL"
                    )
                ).fetchall()
                known.update((r[0] or "").strip() for r in sql_rows if r and r[0])
        except Exception:
            logger.exception("Failed collecting session ids from SQL history")
    try:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        redis_client = Redis.from_url(redis_url, socket_timeout=2)
        for key in redis_client.scan_iter(match="message_store:*", count=500):
            raw = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            sid = raw.split(":", 1)[1] if ":" in raw else ""
            if sid:
                known.add(sid)
    except Exception:
        logger.exception("Failed collecting session ids from Redis history")
    try:
        if os.path.exists(SESSION_RECALL_DB_PATH):
            conn = sqlite3.connect(SESSION_RECALL_DB_PATH)
            try:
                rows = conn.execute(
                    "SELECT DISTINCT session_id FROM session_recall_fts WHERE session_id IS NOT NULL"
                ).fetchall()
                known.update((r[0] or "").strip() for r in rows if r and r[0])
            finally:
                conn.close()
    except Exception:
        logger.exception("Failed collecting session ids from recall index")
    return sorted(s for s in known if s)


def _run_session_repair(
    assign_unowned_to: Optional[str], fix_ownership: bool
) -> Dict[str, Any]:
    report = {
        "total_found": 0,
        "metadata_fixed": 0,
        "ownership_fixed": 0,
        "skipped": 0,
        "errors": 0,
    }
    all_ids = _collect_known_session_ids()
    report["total_found"] = len(all_ids)
    users = db_list_users() or []
    single_user_mode = len(users) == 1
    assignee = (assign_unowned_to or "").strip() or None
    valid_usernames = {u.get("username") for u in users if u.get("username")}
    if assignee and assignee not in valid_usernames:
        raise HTTPException(status_code=400, detail=f"Unknown user: {assignee}")
    for sid in all_ids:
        try:
            before = next(
                (s for s in get_all_sessions() if s.get("session_id") == sid), None
            )
            if before is None:
                touch_session_updated_at(sid)
                report["metadata_fixed"] += 1
            if fix_ownership:
                owner = get_session_owner(sid)
                if not owner:
                    target = assignee if (single_user_mode and assignee) else None
                    if target and ensure_session_owner(sid, target):
                        report["ownership_fixed"] += 1
                    else:
                        report["skipped"] += 1
        except Exception:
            report["errors"] += 1
            logger.exception("session repair failed for %s", sid)
    return report


@router.post("/api/admin/sessions/rebuild-index")
def admin_rebuild_sessions_index(
    req: SessionRepairRequest, _: UserContext = Depends(require_admin_user)
):
    return _run_session_repair(
        assign_unowned_to=req.assign_unowned_to, fix_ownership=False
    )


@router.post("/api/admin/sessions/rebuild-ownership")
def admin_rebuild_sessions_ownership(
    req: SessionRepairRequest, _: UserContext = Depends(require_admin_user)
):
    return _run_session_repair(
        assign_unowned_to=req.assign_unowned_to, fix_ownership=True
    )


# ── Retention ─────────────────────────────────────────────────────────────────


@router.post("/api/admin/retention/run")
def run_retention_now(
    request: RetentionRunRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    result = apply_retention_policy(
        max_age_days=request.max_age_days, archive_only=bool(request.archive_only)
    )
    log_audit_event(
        username=current_user.username,
        action="governance.retention.run",
        details=f"max_age_days={request.max_age_days};archive_only={request.archive_only};result={result}",
    )
    return {"status": "success", **result}


@router.post("/api/admin/retention/dry-run")
def retention_dry_run(
    request: RetentionDryRunRequest,
    current_user: UserContext = Depends(require_admin_user),
):
    from session_recall import DB_PATH as RECALL_DB_PATH

    chat_days = max(1, int(request.chat_history_days))
    recall_days = max(1, int(request.recall_index_days))
    logs_days = max(1, int(request.logs_days))
    backups_days = max(1, int(request.backups_days))
    stale_session_ids: List[str] = []
    chat_rows = 0
    if engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT session_id FROM session_metadata WHERE updated_at IS NOT NULL AND updated_at::timestamptz < NOW() - make_interval(days => :days)"
                ),
                {"days": chat_days},
            ).fetchall()
            stale_session_ids = [r[0] for r in rows if r and r[0]]
            if stale_session_ids:
                chat_rows = int(
                    conn.execute(
                        text(
                            f"SELECT COUNT(*) FROM {CHAT_HISTORY_TABLE} WHERE session_id = ANY(:ids)"
                        ),
                        {"ids": stale_session_ids},
                    ).scalar()
                    or 0
                )
    recall_rows = 0
    try:
        with sqlite3.connect(RECALL_DB_PATH) as recall_conn:
            recall_rows = int(
                recall_conn.execute(
                    "SELECT COUNT(*) FROM session_recall_fts WHERE datetime(created_at) < datetime('now', ?)",
                    (f"-{recall_days} days",),
                ).fetchone()[0]
                or 0
            )
    except Exception:
        recall_rows = 0

    def _count_old_files(base: Path, days: int) -> int:
        if not base.exists():
            return 0
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
        total = 0
        for p in base.rglob("*"):
            if p.is_file() and p.stat().st_mtime < cutoff:
                total += 1
        return total

    logs_files = _count_old_files(Path("logs"), logs_days)
    backups_files = _count_old_files(Path("backups"), backups_days)
    result = {
        "status": "success",
        "categories": {
            "chat_history": {
                "days": chat_days,
                "would_delete_rows": chat_rows,
                "affected_sessions": len(stale_session_ids),
            },
            "recall_index": {"days": recall_days, "would_delete_rows": recall_rows},
            "logs": {"days": logs_days, "would_delete_files": logs_files},
            "backups": {"days": backups_days, "would_delete_files": backups_files},
        },
    }
    log_audit_event(
        username=current_user.username,
        action="governance.retention.dry_run",
        details=json.dumps(result.get("categories", {})),
    )
    return result


# ── Audit ─────────────────────────────────────────────────────────────────────


@router.get("/api/admin/audit/events")
def admin_audit_events(limit: int = 200, _: UserContext = Depends(require_admin_user)):
    return {"events": list_audit_events(limit=limit)}


@router.get("/api/admin/audit-logs")
def admin_audit_logs(
    action_type: Optional[str] = Query(default=None, description="Filter by action type"),
    username: Optional[str] = Query(default=None, description="Filter by username"),
    date_from: Optional[str] = Query(default=None, description="Inclusive start date (ISO 8601)"),
    date_to: Optional[str] = Query(default=None, description="Inclusive end date (ISO 8601)"),
    session_id: Optional[str] = Query(default=None, description="Filter by session ID"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results (1-1000)"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    _: UserContext = Depends(require_admin_user),
):
    """
    Query audit events with filters. Append-only: no UPDATE or DELETE is exposed.

    Supports filtering by action_type, username, date range, and session_id.
    Results are capped at 1000 per request. Audit entries older than 90 days
    are eligible for retention policy cleanup.
    """
    from core.audit import AuditLogger

    audit_logger = AuditLogger(engine)

    # Parse date strings to datetime objects
    parsed_date_from = None
    parsed_date_to = None
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid date_from format. Use ISO 8601 (e.g. 2024-01-01T00:00:00Z).",
            )
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid date_to format. Use ISO 8601 (e.g. 2024-12-31T23:59:59Z).",
            )

    events = audit_logger.query(
        action_type=action_type,
        username=username,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )

    # Calculate 90-day retention eligibility cutoff
    retention_cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    return {
        "events": events,
        "count": len(events),
        "limit": limit,
        "offset": offset,
        "retention_policy": {
            "min_retention_days": 90,
            "eligible_before": retention_cutoff.isoformat(),
        },
    }


# ── Backup helpers ────────────────────────────────────────────────────────────


def _record_backup_status(entry: Dict) -> None:
    raw = get_config("backup_status_history", "[]") or "[]"
    try:
        history = json.loads(raw)
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []
    history.insert(0, entry)
    set_config("backup_status_history", json.dumps(history[:100]))


def _profile_destination_password(profile: Dict[str, Any]) -> str:
    credential_ref = (profile.get("credential_key_ref") or "").strip()
    if not credential_ref:
        return ""
    return get_config(credential_ref, "") or ""


def _profile_from_legacy_configs() -> Dict[str, Any]:
    mode = (get_config("backup_mode", "local") or "local").strip().lower()
    if mode == "ftp":
        return {
            "id": None,
            "name": "Legacy Backup",
            "destination_type": "ftp",
            "destination_host": get_config("backup_ftp_host", ""),
            "destination_username": get_config("backup_ftp_user", ""),
            "destination_path": get_config("backup_ftp_path", "/"),
            "credential_key_ref": "backup_ftp_password",
        }
    if mode == "smb":
        return {
            "id": None,
            "name": "Legacy Backup",
            "destination_type": "smb",
            "destination_host": get_config("backup_smb_host", ""),
            "destination_username": get_config("backup_smb_user", ""),
            "destination_path": get_config("backup_smb_path", "/"),
            "credential_key_ref": "backup_smb_password",
        }
    return {
        "id": None,
        "name": "Legacy Backup",
        "destination_type": "local",
        "destination_path": get_config("backup_local_path", "/tmp/ampai_backups"),
    }


def _execute_backup(
    actor: str, trigger: str = "manual", profile: Optional[Dict[str, Any]] = None
) -> Dict:
    backup_profile = profile or _profile_from_legacy_configs()
    backup_mode = (backup_profile.get("destination_type") or "local").strip().lower()
    sessions = export_all_sessions_for_backup()
    serialized, manifest = build_backup_payload(sessions=sessions, actor=actor)
    payload_bytes = len(serialized.encode("utf-8"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"ampai_backup_{timestamp}.json"
    try:
        if backup_mode == "ftp":
            host = backup_profile.get("destination_host")
            user = backup_profile.get("destination_username")
            password = _profile_destination_password(backup_profile)
            remote_path = backup_profile.get("destination_path", "/")
            if not host or not user or not password:
                raise ValueError("FTP backup is not fully configured")
            outcome = write_backup_ftp(
                host, user, password, remote_path, filename, serialized, manifest
            )
        elif backup_mode == "smb":
            host = backup_profile.get("destination_host")
            share = (backup_profile.get("destination_path") or "").split("/", 1)[0]
            remote_path = ""
            if "/" in (backup_profile.get("destination_path") or ""):
                remote_path = (backup_profile.get("destination_path") or "").split(
                    "/", 1
                )[1]
            user = backup_profile.get("destination_username")
            password = _profile_destination_password(backup_profile)
            domain = ""
            if not host or not share or not user or not password:
                raise ValueError("SMB backup is not fully configured")
            outcome = write_backup_smb(
                host,
                share,
                remote_path,
                user,
                password,
                domain,
                filename,
                serialized,
                manifest,
            )
        else:
            local_dir = backup_profile.get("destination_path") or "/tmp/ampai_backups"
            outcome = write_backup_local(local_dir, filename, serialized, manifest)
        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "success",
                "profile_id": backup_profile.get("id"),
                "profile_name": backup_profile.get("name"),
                "mode": outcome.get("mode", backup_mode),
                "target": outcome.get("path") or outcome.get("file") or "",
                "manifest_checksum": manifest["checksum_sha256"],
                "session_count": manifest["session_count"],
                "message_count": manifest["message_count"],
            }
        )
        return {
            "status": "success",
            **outcome,
            "manifest": manifest,
            "bytes_written": payload_bytes,
            "serialized_payload": serialized,
        }
    except Exception as exc:
        _record_backup_status(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "status": "failed",
                "profile_id": backup_profile.get("id"),
                "profile_name": backup_profile.get("name"),
                "mode": backup_mode,
                "error": str(exc),
            }
        )
        raise


def _run_backup_verification(
    serialized_payload: str, manifest: Dict[str, Any]
) -> Dict[str, Any]:
    payload_checksum = hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()
    expected_checksum = (manifest.get("checksum_sha256") or "").strip()
    if not expected_checksum or payload_checksum != expected_checksum:
        raise ValueError("checksum verify failed")
    try:
        archive_json = json.loads(serialized_payload)
    except Exception as exc:
        raise ValueError(f"archive open/read test failed: {exc}") from exc
    if not isinstance(archive_json, dict):
        raise ValueError("archive open/read test failed: root is not an object")
    if (
        not isinstance(manifest, dict)
        or not manifest.get("schema_version")
        or not manifest.get("timestamp")
    ):
        raise ValueError("manifest parse failed")
    sessions = archive_json.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("restore smoke test failed: sessions is not an array")
    with sqlite3.connect(":memory:") as temp_conn:
        temp_conn.execute(
            "CREATE TABLE restore_sessions (session_id TEXT PRIMARY KEY, message_count INTEGER NOT NULL)"
        )
        for row in sessions[:10]:
            if not isinstance(row, dict):
                continue
            session_id = str(row.get("session_id") or "").strip()
            if not session_id:
                continue
            messages = row.get("messages")
            message_count = len(messages) if isinstance(messages, list) else 0
            temp_conn.execute(
                "INSERT OR REPLACE INTO restore_sessions (session_id, message_count) VALUES (?, ?)",
                (session_id, message_count),
            )
        restored_count = int(
            temp_conn.execute("SELECT COUNT(*) FROM restore_sessions").fetchone()[0]
            or 0
        )
        valid_count = int(
            temp_conn.execute(
                "SELECT COUNT(*) FROM restore_sessions WHERE message_count >= 0"
            ).fetchone()[0]
            or 0
        )
    if restored_count != valid_count:
        raise ValueError("restore smoke test failed: validation query mismatch")
    return {"ok": True, "restored_sample_rows": restored_count}


def _enqueue_backup_job(
    actor: str, trigger: str, profile: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    backup_profile = profile or _profile_from_legacy_configs()
    job_id = create_backup_job(profile_id=backup_profile.get("id"), status="queued")
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue backup job")
    try:
        BACKUP_JOB_QUEUE.put_nowait(
            {
                "job_id": job_id,
                "actor": actor,
                "trigger": trigger,
                "profile": backup_profile,
            }
        )
    except Exception as exc:
        update_backup_job(
            job_id,
            status="failed",
            finished_at=datetime.now(timezone.utc),
            error_message=f"Queue full: {exc}",
        )
        raise HTTPException(
            status_code=503, detail="Backup queue is full, try again shortly"
        ) from exc
    return {"job_id": job_id, "status": "queued"}


def _alert_backup_verification_failure(
    job_id: int, error_message: str, actor: str
) -> None:
    subject = f"AmpAI Backup Verification Failed (job #{job_id})"
    body = "\n".join(
        [
            "Backup verification failed.",
            f"job_id: {job_id}",
            f"actor: {actor}",
            f"time_utc: {datetime.now(timezone.utc).isoformat()}",
            f"error: {error_message}",
        ]
    )
    _send_resend_email(subject, body)


def _backup_job_worker() -> None:
    while True:
        try:
            payload = BACKUP_JOB_QUEUE.get(timeout=2)
        except Empty:
            continue
        job_id = int(payload.get("job_id"))
        actor = payload.get("actor", "system")
        trigger = payload.get("trigger", "manual")
        profile = payload.get("profile")
        started_at = datetime.now(timezone.utc)
        update_backup_job(
            job_id, status="running", started_at=started_at, error_message=None
        )
        log_audit_event(
            username=actor,
            action="admin.backup.run.start",
            details=f"job_id={job_id} trigger={trigger}",
        )
        try:
            result = _execute_backup(actor=actor, trigger=trigger, profile=profile)
            artifact_path = result.get("path") or result.get("file") or ""
            bytes_written = int(result.get("bytes_written") or 0)
            _run_backup_verification(
                serialized_payload=result.get("serialized_payload", ""),
                manifest=result.get("manifest") or {},
            )
            update_backup_job(
                job_id,
                status="success",
                finished_at=datetime.now(timezone.utc),
                bytes_written=bytes_written,
                artifact_path=artifact_path,
                verified=True,
                verification_error=None,
                error_message=None,
            )
            log_audit_event(
                username=actor,
                action="admin.backup.run.finish",
                details=f"job_id={job_id} artifact={artifact_path}",
            )
        except Exception as exc:
            update_backup_job(
                job_id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                verified=False,
                verification_error=str(exc),
                error_message=str(exc),
            )
            _alert_backup_verification_failure(
                job_id=job_id, error_message=str(exc), actor=actor
            )
            log_audit_event(
                username=actor,
                action="admin.backup.run.failure",
                details=f"job_id={job_id} error={exc}",
            )
        finally:
            BACKUP_JOB_QUEUE.task_done()


# ── Backup profile endpoints ──────────────────────────────────────────────────


def _profile_row_to_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name", ""),
        "enabled": bool(row.get("enabled")),
        "include_database": bool(row.get("include_database")),
        "include_uploads": bool(row.get("include_uploads")),
        "include_configs": bool(row.get("include_configs")),
        "include_logs": bool(row.get("include_logs")),
        "destination": {
            "type": row.get("destination_type", "local"),
            "path": row.get("destination_path", ""),
            "host": row.get("destination_host", ""),
            "port": row.get("destination_port"),
            "username": row.get("destination_username", ""),
            "credential_key_ref": row.get("credential_key_ref", ""),
            "has_credential": bool(get_config(row.get("credential_key_ref", ""), ""))
            if row.get("credential_key_ref")
            else False,
        },
        "schedule": {
            "cron": row.get("schedule_cron", ""),
            "interval_minutes": row.get("schedule_interval_minutes"),
        },
        "retention_count": row.get("retention_count"),
        "retention_days": row.get("retention_days"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _normalize_profile_payload(
    request: Any, existing: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    destination = request.destination
    schedule = request.schedule
    destination_type = (
        (
            destination.type
            if destination
            else (existing or {}).get("destination_type", "local") or "local"
        )
        .strip()
        .lower()
    )
    if destination_type not in {"local", "ftp", "smb"}:
        raise HTTPException(
            status_code=400, detail="destination.type must be local, ftp, or smb"
        )
    credential_key_ref = (
        (destination.credential_key_ref if destination else "")
        or (existing or {}).get("credential_key_ref")
        or ""
    )
    if destination and destination.credential:
        credential_key_ref = (
            credential_key_ref or f"backup_profile_cred_{uuid.uuid4().hex}"
        )
        set_config(credential_key_ref, destination.credential)
    return {
        "name": (
            request.name
            if request.name is not None
            else (existing or {}).get("name") or ""
        ).strip(),
        "enabled": bool(
            request.enabled
            if request.enabled is not None
            else (existing or {}).get("enabled", True)
        ),
        "include_database": bool(
            request.include_database
            if request.include_database is not None
            else (existing or {}).get("include_database", True)
        ),
        "include_uploads": bool(
            request.include_uploads
            if request.include_uploads is not None
            else (existing or {}).get("include_uploads", False)
        ),
        "include_configs": bool(
            request.include_configs
            if request.include_configs is not None
            else (existing or {}).get("include_configs", False)
        ),
        "include_logs": bool(
            request.include_logs
            if request.include_logs is not None
            else (existing or {}).get("include_logs", False)
        ),
        "destination_type": destination_type,
        "destination_path": (
            destination.path
            if destination
            else (existing or {}).get("destination_path", "")
        )
        or "",
        "destination_host": (
            destination.host
            if destination
            else (existing or {}).get("destination_host", "")
        )
        or "",
        "destination_port": destination.port
        if destination
        else (existing or {}).get("destination_port"),
        "destination_username": (
            destination.username
            if destination
            else (existing or {}).get("destination_username", "")
        )
        or "",
        "credential_key_ref": credential_key_ref,
        "schedule_cron": (
            schedule.cron if schedule else (existing or {}).get("schedule_cron", "")
        )
        or "",
        "schedule_interval_minutes": schedule.interval_minutes
        if schedule
        else (existing or {}).get("schedule_interval_minutes"),
        "retention_count": request.retention_count
        if request.retention_count is not None
        else (existing or {}).get("retention_count"),
        "retention_days": request.retention_days
        if request.retention_days is not None
        else (existing or {}).get("retention_days"),
    }


@router.get("/api/backups/profiles")
def get_backup_profiles(_: UserContext = Depends(require_admin_user)):
    return {
        "profiles": [_profile_row_to_response(row) for row in list_backup_profiles()]
    }


@router.post("/api/backups/profiles")
def create_backup_profiles_api(
    request: BackupProfileCreateRequest, user: UserContext = Depends(require_admin_user)
):
    payload = _normalize_profile_payload(request)
    if not payload["name"]:
        raise HTTPException(status_code=400, detail="Profile name is required")
    profile_id = create_backup_profile(payload)
    if not profile_id:
        raise HTTPException(status_code=500, detail="Failed to create backup profile")
    log_audit_event(
        username=user.username,
        action="admin.backup_profile.create",
        details=f"profile_id={profile_id}",
    )
    profile = get_backup_profile(profile_id)
    return {
        "status": "success",
        "profile": _profile_row_to_response(profile or {"id": profile_id, **payload}),
    }


@router.patch("/api/backups/profiles/{profile_id}")
def update_backup_profiles_api(
    profile_id: int,
    request: BackupProfileUpdateRequest,
    user: UserContext = Depends(require_admin_user),
):
    existing = get_backup_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    payload = _normalize_profile_payload(request, existing=existing)
    if not payload["name"]:
        raise HTTPException(status_code=400, detail="Profile name is required")
    if not update_backup_profile(profile_id, payload):
        raise HTTPException(status_code=500, detail="Failed to update backup profile")
    log_audit_event(
        username=user.username,
        action="admin.backup_profile.update",
        details=f"profile_id={profile_id}",
    )
    updated = get_backup_profile(profile_id)
    return {
        "status": "success",
        "profile": _profile_row_to_response(updated or {"id": profile_id, **payload}),
    }


@router.delete("/api/backups/profiles/{profile_id}")
def delete_backup_profiles_api(
    profile_id: int, user: UserContext = Depends(require_admin_user)
):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not delete_backup_profile(profile_id):
        raise HTTPException(status_code=500, detail="Failed to delete backup profile")
    log_audit_event(
        username=user.username,
        action="admin.backup_profile.delete",
        details=f"profile_id={profile_id}",
    )
    return {"status": "success"}


@router.post("/api/backups/profiles/{profile_id}/run")
def run_backup_profile_now(
    profile_id: int, current_user: UserContext = Depends(require_admin_user)
):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not profile.get("enabled"):
        raise HTTPException(status_code=400, detail="Backup profile is disabled")
    return _enqueue_backup_job(
        actor=current_user.username, trigger="manual-profile", profile=profile
    )


@router.post("/api/backups/run/{profile_id}")
def run_backup_profile_job(
    profile_id: int, current_user: UserContext = Depends(require_admin_user)
):
    profile = get_backup_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    if not profile.get("enabled"):
        raise HTTPException(status_code=400, detail="Backup profile is disabled")
    return _enqueue_backup_job(
        actor=current_user.username, trigger="manual-profile", profile=profile
    )


@router.get("/api/backups/jobs")
def get_backup_jobs(
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    _: UserContext = Depends(require_admin_user),
):
    return {"jobs": list_backup_jobs(limit=limit, offset=offset)}


@router.get("/api/backups/kpis")
def get_backup_kpis(_: UserContext = Depends(require_admin_user)):
    return {"kpis": get_backup_verification_kpis()}


@router.get("/api/admin/backup/download-instant")
def backup_download_instant(_: UserContext = Depends(require_admin_user)):
    try:
        sessions = export_all_sessions_for_backup()
        serialized, manifest = build_backup_payload(
            sessions=sessions, actor="admin_download_instant"
        )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"ampai_full_backup_{timestamp}.json"
        return Response(
            content=serialized,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backups/download")
def backup_download(
    path: str = Query(...), _: UserContext = Depends(require_admin_user)
):
    normalized = (path or "").strip()
    if not normalized or not os.path.isabs(normalized):
        raise HTTPException(
            status_code=400, detail="A valid absolute local path is required"
        )
    if not os.path.isfile(normalized):
        raise HTTPException(status_code=404, detail="Backup artifact not found")
    filename = os.path.basename(normalized) or "backup.json"
    return FileResponse(normalized, media_type="application/json", filename=filename)


@router.get("/api/backups/download-all")
def backup_download_all(_: UserContext = Depends(require_admin_user)):
    local_root = (
        get_config("backup_local_path", "/tmp/ampai_backups") or "/tmp/ampai_backups"
    ).strip()
    if not os.path.isdir(local_root):
        raise HTTPException(status_code=404, detail="Local backup directory not found")
    files = sorted(
        [
            os.path.join(local_root, name)
            for name in os.listdir(local_root)
            if name.endswith(".json") or name.endswith(".manifest.json")
        ]
    )
    if not files:
        raise HTTPException(status_code=404, detail="No local backup artifacts found")
    archive_name = (
        f"ampai_backups_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    )
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=os.path.basename(file_path))
    return FileResponse(
        archive_path, media_type="application/zip", filename=archive_name
    )


@router.get("/api/backups/jobs/{job_id}")
def get_backup_job_details(job_id: int, _: UserContext = Depends(require_admin_user)):
    job = get_backup_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backup job not found")
    return {"job": job}


@router.post("/api/admin/backup/run")
def run_backup(
    profile_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(require_admin_user),
):
    profile = get_backup_profile(profile_id) if profile_id else None
    if profile_id and not profile:
        raise HTTPException(status_code=404, detail="Backup profile not found")
    return _enqueue_backup_job(
        actor=current_user.username, trigger="manual", profile=profile
    )


@router.get("/api/admin/backup/status-history")
def get_backup_status_history(_: UserContext = Depends(require_admin_user)):
    raw = get_config("backup_status_history", "[]") or "[]"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = []
    if not isinstance(parsed, list):
        parsed = []
    return {"history": parsed}


@router.post("/api/admin/backup")
def run_backup_compat(
    profile_id: Optional[int] = Query(default=None),
    current_user: UserContext = Depends(require_admin_user),
):
    return run_backup(profile_id=profile_id, current_user=current_user)


@router.get("/api/admin/backup/history")
def get_backup_history_compat(user: UserContext = Depends(require_admin_user)):
    return get_backup_status_history(user)


# ── Backup endpoints (BackupService) ─────────────────────────────────────────


def _get_backup_service() -> BackupService:
    """Instantiate BackupService with the current database engine."""
    from core.audit import AuditLogger

    audit = AuditLogger(engine) if engine else None
    return BackupService(engine=engine, audit_logger=audit)


@router.get("/api/admin/backup/jobs")
def admin_backup_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    _: UserContext = Depends(require_admin_user),
):
    """List backup job history."""
    svc = _get_backup_service()
    jobs = svc.list_backup_jobs(limit=limit)
    return {"jobs": jobs}


@router.post("/api/admin/backup/test-ftp")
def admin_backup_test_ftp(
    request: BackupFtpTestRequest,
    _: UserContext = Depends(require_admin_user),
):
    """Test FTP connection with provided credentials."""
    svc = _get_backup_service()
    ok, detail = svc.test_ftp_connection(
        host=request.host,
        user=request.user,
        password=request.password,
        remote_path=request.path,
        port=request.port,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=detail)
    return {"status": "success", "detail": detail}


@router.get("/api/admin/backup/profiles")
def admin_list_backup_profiles(_: UserContext = Depends(require_admin_user)):
    """List all backup profiles."""
    profiles = list_backup_profiles()
    return {"profiles": profiles}


@router.post("/api/admin/backup/profiles")
def admin_create_backup_profile(
    request: BackupProfileCreateRequest,
    user: UserContext = Depends(require_admin_user),
):
    """Create a new backup profile."""
    payload = {
        "name": request.name,
        "enabled": request.enabled,
        "include_database": request.include_database,
        "include_uploads": request.include_uploads,
        "include_configs": request.include_configs,
        "include_logs": request.include_logs,
        "retention_count": request.retention_count,
        "retention_days": request.retention_days,
    }
    if request.destination:
        payload["destination_type"] = request.destination.type
        payload["destination_path"] = request.destination.path
        payload["destination_host"] = request.destination.host
        payload["destination_port"] = request.destination.port
        payload["destination_username"] = request.destination.username
        payload["credential_key_ref"] = request.destination.credential_key_ref
    if request.schedule:
        payload["schedule_cron"] = request.schedule.cron
        payload["schedule_interval_minutes"] = request.schedule.interval_minutes

    profile_id = create_backup_profile(payload)
    if not profile_id:
        raise HTTPException(status_code=500, detail="Failed to create backup profile")

    log_audit_event(
        username=user.username,
        action="admin.backup.profile.create",
        details=f"profile_id={profile_id};name={request.name}",
    )
    return {"status": "success", "profile_id": profile_id}


@router.patch("/api/admin/backup/profiles/{profile_id}")
def admin_update_backup_profile(
    profile_id: int,
    request: BackupProfileUpdateRequest,
    user: UserContext = Depends(require_admin_user),
):
    """Update an existing backup profile."""
    existing = get_backup_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Backup profile not found")

    payload: Dict[str, Any] = {}
    if request.name is not None:
        payload["name"] = request.name
    if request.enabled is not None:
        payload["enabled"] = request.enabled
    if request.include_database is not None:
        payload["include_database"] = request.include_database
    if request.include_uploads is not None:
        payload["include_uploads"] = request.include_uploads
    if request.include_configs is not None:
        payload["include_configs"] = request.include_configs
    if request.include_logs is not None:
        payload["include_logs"] = request.include_logs
    if request.retention_count is not None:
        payload["retention_count"] = request.retention_count
    if request.retention_days is not None:
        payload["retention_days"] = request.retention_days
    if request.destination is not None:
        payload["destination_type"] = request.destination.type
        payload["destination_path"] = request.destination.path
        payload["destination_host"] = request.destination.host
        payload["destination_port"] = request.destination.port
        payload["destination_username"] = request.destination.username
        payload["credential_key_ref"] = request.destination.credential_key_ref
    if request.schedule is not None:
        payload["schedule_cron"] = request.schedule.cron
        payload["schedule_interval_minutes"] = request.schedule.interval_minutes

    if not payload:
        return {"status": "success", "message": "No changes provided"}

    ok = update_backup_profile(profile_id, payload)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update backup profile")

    log_audit_event(
        username=user.username,
        action="admin.backup.profile.update",
        details=f"profile_id={profile_id};fields={list(payload.keys())}",
    )
    return {"status": "success", "profile_id": profile_id}


@router.post("/api/admin/backup/test-connection")
def test_backup_connection(
    request: BackupConnectionTestRequest, _: UserContext = Depends(require_admin_user)
):
    mode = (request.mode or "").strip().lower()
    if mode == "ftp":
        ok, detail = test_ftp_connection(
            host=(request.host or "").strip(),
            user=(request.user or "").strip(),
            password=request.password or "",
            remote_path=(request.path or "/").strip(),
        )
    elif mode == "smb":
        ok, detail = test_smb_connection(
            host=(request.host or "").strip(),
            share=(request.share or "").strip(),
            username=(request.user or "").strip(),
            password=request.password or "",
            domain=(request.domain or "").strip(),
        )
    else:
        raise HTTPException(status_code=400, detail="mode must be ftp or smb")
    if not ok:
        raise HTTPException(status_code=400, detail=detail)
    return {"status": "success", "detail": detail}


# ── Restore ───────────────────────────────────────────────────────────────────


def _normalize_restore_archive(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_payload, dict):
        return {"manifest": {}, "payload": {}}
    manifest = raw_payload.get("manifest") or raw_payload.get("_manifest") or {}
    payload = raw_payload.get("payload")
    if not isinstance(payload, dict):
        payload = raw_payload
    if not isinstance(manifest, dict):
        manifest = {}
    return {"manifest": manifest, "payload": payload}


def _build_restore_preflight_report(raw_json: str) -> Dict[str, Any]:
    try:
        archive_root = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid backup JSON: {exc}"
        ) from exc
    normalized = _normalize_restore_archive(archive_root)
    manifest = normalized["manifest"]
    payload = normalized["payload"]
    payload_text = json.dumps(payload, sort_keys=True)
    payload_checksum = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    expected_checksum = (
        manifest.get("checksum_sha256") or payload.get("checksum_sha256") or ""
    ).strip()
    sessions = payload.get("sessions")
    uploads = payload.get("uploads")
    configs = payload.get("configs")
    checks: List[Dict[str, Any]] = []
    checks.append(
        {
            "name": "archive_checksum",
            "ok": bool(expected_checksum) and expected_checksum == payload_checksum,
            "expected": expected_checksum,
            "actual": payload_checksum,
            "detail": "checksum matches manifest",
        }
    )
    checks.append(
        {
            "name": "manifest_schema_version",
            "ok": (manifest.get("schema_version") or payload.get("schema_version"))
            == RESTORE_SCHEMA_VERSION,
            "value": manifest.get("schema_version") or payload.get("schema_version"),
            "expected": RESTORE_SCHEMA_VERSION,
        }
    )
    checks.append(
        {
            "name": "manifest_app_version",
            "ok": bool(manifest.get("app_version") or payload.get("app_version")),
            "value": manifest.get("app_version") or payload.get("app_version"),
        }
    )
    checks.append(
        {
            "name": "manifest_timestamp",
            "ok": bool(manifest.get("timestamp") or payload.get("created_at")),
            "value": manifest.get("timestamp") or payload.get("created_at"),
        }
    )
    checks.append(
        {
            "name": "sessions_array",
            "ok": isinstance(sessions, list),
            "detail": "sessions must be an array",
        }
    )
    db_ok = _check_db_health().get("ok", False)
    checks.append(
        {"name": "db_connectivity", "ok": bool(db_ok), "detail": "database ping"}
    )
    archive_bytes = len(raw_json.encode("utf-8"))
    free_bytes = shutil.disk_usage(UPLOAD_DIR).free
    required_bytes = archive_bytes * 2
    checks.append(
        {
            "name": "destination_free_space",
            "ok": free_bytes >= required_bytes,
            "required_bytes": required_bytes,
            "free_bytes": free_bytes,
            "detail": "requires at least 2x archive size",
        }
    )
    ok = all(bool(c.get("ok")) for c in checks)
    return {
        "ok": ok,
        "checks": checks,
        "manifest": {
            "schema_version": manifest.get("schema_version")
            or payload.get("schema_version"),
            "app_version": manifest.get("app_version") or payload.get("app_version"),
            "timestamp": manifest.get("timestamp") or payload.get("created_at"),
            "checksum_sha256": expected_checksum,
        },
        "summary": {
            "session_count": len(sessions) if isinstance(sessions, list) else 0,
            "upload_count": len(uploads) if isinstance(uploads, list) else 0,
            "config_count": len(configs) if isinstance(configs, dict) else 0,
            "archive_size_bytes": archive_bytes,
            "restore_order": ["database", "uploads", "configs"],
        },
        "payload_checksum_sha256": payload_checksum,
    }


def _store_restore_preflight(report: Dict[str, Any], payload_checksum: str) -> str:
    preflight_id = uuid.uuid4().hex
    RESTORE_PREFLIGHT_CACHE[preflight_id] = {
        "report": report,
        "payload_checksum": payload_checksum,
        "expires_at": time.time() + RESTORE_PREFLIGHT_TTL_SECONDS,
    }
    return preflight_id


@router.post("/api/admin/backup/restore")
def restore_backup(
    request: BackupRestoreRequest, user: UserContext = Depends(require_admin_user)
):
    report = _build_restore_preflight_report(request.backup_json)
    if request.dry_run:
        preflight_id = _store_restore_preflight(
            report, report.get("payload_checksum_sha256", "")
        )
        return {
            "status": "success",
            "phase": "preflight",
            "preflight_id": preflight_id,
            "report": report,
        }
    if not report.get("ok"):
        raise HTTPException(
            status_code=400,
            detail="Preflight checks failed; run dry-run and fix issues before restore",
        )
    preflight_id = _store_restore_preflight(
        report, report.get("payload_checksum_sha256", "")
    )
    job_id = create_restore_job(
        created_by=user.username, preflight_report=report, status="queued"
    )
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue restore job")
    RESTORE_JOB_QUEUE.put_nowait(
        {
            "job_id": job_id,
            "actor": user.username,
            "backup_json": request.backup_json,
            "preflight_id": preflight_id,
        }
    )
    return {"status": "queued", "job_id": job_id, "preflight_id": preflight_id}


@router.post("/api/restores/preflight")
def restore_preflight(
    request: RestorePreflightRequest, _: UserContext = Depends(require_admin_user)
):
    report = _build_restore_preflight_report(request.backup_json)
    preflight_id = _store_restore_preflight(
        report, report.get("payload_checksum_sha256", "")
    )
    return {"status": "success", "preflight_id": preflight_id, "report": report}


@router.post("/api/restores/start")
def restore_start(
    request: RestoreStartRequest, user: UserContext = Depends(require_admin_user)
):
    preflight = RESTORE_PREFLIGHT_CACHE.get(request.preflight_id)
    if not preflight:
        raise HTTPException(status_code=400, detail="Preflight ID not found or expired")
    if preflight.get("expires_at", 0) < time.time():
        RESTORE_PREFLIGHT_CACHE.pop(request.preflight_id, None)
        raise HTTPException(
            status_code=400, detail="Preflight ID expired; run preflight again"
        )
    if not request.confirm_restore:
        raise HTTPException(status_code=400, detail="confirm_restore must be true")
    report = preflight.get("report") or {}
    if not report.get("ok"):
        raise HTTPException(
            status_code=400, detail="Preflight checks failed; restore blocked"
        )
    checksum = hashlib.sha256(
        json.dumps(
            _normalize_restore_archive(json.loads(request.backup_json))["payload"],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if checksum != preflight.get("payload_checksum"):
        raise HTTPException(
            status_code=400,
            detail="Backup payload changed since preflight; re-run preflight",
        )
    job_id = create_restore_job(
        created_by=user.username, preflight_report=report, status="queued"
    )
    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to queue restore job")
    try:
        RESTORE_JOB_QUEUE.put_nowait(
            {
                "job_id": job_id,
                "actor": user.username,
                "backup_json": request.backup_json,
                "preflight_id": request.preflight_id,
            }
        )
    except Exception as exc:
        update_restore_job(
            job_id,
            status="failed",
            finished_at=datetime.now(timezone.utc),
            error_message=f"Queue full: {exc}",
        )
        raise HTTPException(
            status_code=503, detail="Restore queue is full; retry shortly"
        ) from exc
    log_audit_event(
        username=user.username,
        action="admin.restore.run.start",
        details=f"job_id={job_id} preflight={request.preflight_id}",
    )
    return {"status": "queued", "job_id": job_id}


@router.get("/api/restores/jobs")
def get_restore_jobs(
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    _: UserContext = Depends(require_admin_user),
):
    return {"jobs": list_restore_jobs(limit=limit, offset=offset)}


@router.get("/api/restores/jobs/{job_id}")
def get_restore_job_details(job_id: int, _: UserContext = Depends(require_admin_user)):
    job = get_restore_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Restore job not found")
    return job


# ── Full backup endpoints ─────────────────────────────────────────────────────

import threading as _fb_threading

_fb_lock = _fb_threading.Lock()


@router.post("/api/admin/fullbackup/create")
def api_fullbackup_create(user: UserContext = Depends(require_admin_user)):
    from full_backup import SLOT_SIZE_BYTES, build_full_backup, save_full_backup_to_disk

    if not _fb_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A full backup is already running")
    try:
        bundle = build_full_backup(actor=user.username)
        zip_path = save_full_backup_to_disk(bundle)
        manifest = bundle["manifest"]
        log_audit_event(
            username=user.username,
            action="admin.fullbackup.create",
            details=f"file={os.path.basename(zip_path)}",
        )
        return {
            "ok": True,
            "filename": os.path.basename(zip_path),
            "manifest": manifest,
            "slot_size_bytes": SLOT_SIZE_BYTES,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _fb_lock.release()


@router.get("/api/admin/fullbackup/list")
def api_fullbackup_list(user: UserContext = Depends(require_admin_user)):
    from full_backup import list_full_backups

    backups = list_full_backups()
    return {"backups": backups, "total": len(backups)}


@router.get("/api/admin/fullbackup/download/{filename}")
def api_fullbackup_download(
    filename: str, user: UserContext = Depends(require_admin_user)
):
    from full_backup import FULL_BACKUP_DIR

    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/api/admin/fullbackup/{filename}")
def api_fullbackup_delete(
    filename: str, user: UserContext = Depends(require_admin_user)
):
    from full_backup import FULL_BACKUP_DIR

    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    os.remove(zip_path)
    log_audit_event(
        username=user.username,
        action="admin.fullbackup.delete",
        details=f"file={filename}",
    )
    return {"deleted": filename}


@router.post("/api/admin/fullbackup/restore")
def api_fullbackup_restore(
    request: FullRestoreRequest, user: UserContext = Depends(require_admin_user)
):
    from full_backup import FULL_BACKUP_DIR, restore_full_backup

    if "/" in request.filename or ".." in request.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    zip_path = os.path.join(FULL_BACKUP_DIR, request.filename)
    if not os.path.isfile(zip_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    opts = {
        k: getattr(request, k)
        for k in [
            "restore_chats",
            "restore_memories",
            "restore_core_memories",
            "restore_users",
            "restore_configs",
            "restore_personas",
            "restore_tasks",
        ]
    }
    result = restore_full_backup(zip_path, opts)
    log_audit_event(
        username=user.username,
        action="admin.fullbackup.restore",
        details=f"file={request.filename} ok={result['ok']}",
    )
    if not result["ok"] and not result.get("summary"):
        raise HTTPException(
            status_code=500, detail="; ".join(result.get("errors", ["Unknown error"]))
        )
    return result


@router.post("/api/admin/fullbackup/restore-upload")
async def api_fullbackup_restore_upload(
    backup_file: UploadFile = File(...),
    preflight_only: bool = Form(False),
    dry_run: bool = Form(False),
    restore_chats: bool = Form(True),
    restore_memories: bool = Form(True),
    restore_core_memories: bool = Form(True),
    restore_users: bool = Form(True),
    restore_configs: bool = Form(True),
    restore_personas: bool = Form(True),
    restore_tasks: bool = Form(True),
    user: UserContext = Depends(require_admin_user),
):
    from full_backup import restore_full_backup

    filename = (backup_file.filename or "").strip()
    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400, detail="Please upload a .zip full backup file"
        )
    tmp_dir = tempfile.mkdtemp(prefix="ampai_restore_")
    tmp_zip = os.path.join(tmp_dir, "uploaded_full_backup.zip")
    try:
        with open(tmp_zip, "wb") as f:
            shutil.copyfileobj(backup_file.file, f)
        if os.path.getsize(tmp_zip) == 0:
            raise HTTPException(status_code=400, detail="Uploaded backup file is empty")
        preview = {"sessions": 0, "memories": 0, "users": 0, "configs": 0}
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                names = zf.namelist()
                non_mem = {}
                if "full_data.json.gz" in names:
                    non_mem = json.loads(
                        gzip.decompress(zf.read("full_data.json.gz")).decode("utf-8")
                    )
                sessions_count = 0
                memories_count = 0
                for sf in (
                    n for n in names if n.startswith("slot_") and n.endswith(".json.gz")
                ):
                    slot_payload = json.loads(gzip.decompress(zf.read(sf)).decode("utf-8"))
                    for _, cat_data in (slot_payload.get("categories") or {}).items():
                        sessions_count += len(cat_data.get("sessions", []))
                        memories_count += len(cat_data.get("memories", []))
                preview = {
                    "sessions": sessions_count,
                    "memories": memories_count,
                    "users": len(non_mem.get("users") or []),
                    "configs": len((non_mem.get("configs") or {}).keys()),
                }
        except zipfile.BadZipFile:
            if preflight_only:
                raise HTTPException(status_code=400, detail="Invalid backup zip file")

        if preflight_only:
            return {"ok": True, "preflight": preview}
        opts = {
            "restore_chats": restore_chats,
            "restore_memories": restore_memories,
            "restore_core_memories": restore_core_memories,
            "restore_users": restore_users,
            "restore_configs": restore_configs,
            "restore_personas": restore_personas,
            "restore_tasks": restore_tasks,
        }
        if dry_run:
            return {"ok": True, "dry_run": True, "summary": preview, "errors": []}
        result = restore_full_backup(tmp_zip, opts)
        log_audit_event(
            username=user.username,
            action="admin.fullbackup.restore.upload",
            details=f"file={filename} ok={result.get('ok')}",
        )
        if not result.get("ok") and not result.get("summary"):
            raise HTTPException(
                status_code=500,
                detail="; ".join(result.get("errors", ["Unknown restore error"])),
            )
        return result
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@router.get("/api/admin/fullbackup/memory-categories")
def api_fullbackup_memory_categories(user: UserContext = Depends(require_admin_user)):
    from full_backup import _fetch_memories_by_category, _fetch_sessions_by_category

    sessions_by_cat = _fetch_sessions_by_category()
    memories_by_cat = _fetch_memories_by_category()
    all_cats = sorted(set(list(sessions_by_cat.keys()) + list(memories_by_cat.keys())))
    rows = []
    for cat in all_cats:
        sessions = sessions_by_cat.get(cat, [])
        mems = memories_by_cat.get(cat, [])
        total_msgs = sum(len(s.get("messages", [])) for s in sessions)
        rows.append(
            {
                "category": cat,
                "session_count": len(sessions),
                "message_count": total_msgs,
                "memory_count": len(mems),
            }
        )
    return {"categories": rows}


# ── Code update endpoints ─────────────────────────────────────────────────────


def _update_log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    _update_log_lines.append(line)
    if len(_update_log_lines) > 500:
        _update_log_lines.pop(0)
    logger.info("[UPDATE] %s", msg)


def _get_current_git_commit() -> str:
    try:
        for candidate in [
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "..", "..", ".git"
            ),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".git"),
            "/app_host/.git",
        ]:
            if os.path.isdir(candidate):
                git_head = os.path.join(candidate, "HEAD")
                if os.path.exists(git_head):
                    with open(git_head) as f:
                        ref = f.read().strip()
                    if ref.startswith("ref: "):
                        ref_file = os.path.join(candidate, ref[5:])
                        if os.path.exists(ref_file):
                            with open(ref_file) as f:
                                return f.read().strip()[:12]
                    return ref[:12]
    except Exception:
        pass
    return "unknown"


def _extract_github_slug(repo_url: str) -> Optional[str]:
    url = (repo_url or "").strip()
    if not url:
        return None
    if url.startswith("git@github.com:"):
        slug = url.split(":", 1)[1]
    elif "github.com/" in url:
        slug = url.split("github.com/", 1)[1]
    else:
        return None
    slug = slug.strip().rstrip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    parts = [p for p in slug.split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def _fetch_remote_commit() -> str:
    import urllib.request as _ur

    slug = _extract_github_slug(REPO_URL)
    if not slug:
        return "unknown"
    for branch in ["main", "master"]:
        try:
            req = _ur.Request(
                f"https://api.github.com/repos/{slug}/commits/{branch}",
                headers={
                    "Accept": "application/vnd.github.sha",
                    "User-Agent": "ampai-updater/1.0",
                },
            )
            with _ur.urlopen(req, timeout=10) as resp:
                return resp.read().decode().strip()[:12]
        except Exception:
            continue
    return "unknown"


@router.get("/api/admin/update/version")
def update_check_version(user: UserContext = Depends(require_admin_user)):
    current = _get_current_git_commit()
    latest = _fetch_remote_commit()
    check_ok = current != "unknown" and latest != "unknown"
    up_to_date = check_ok and current == latest[: len(current)]
    return {
        "current_commit": current,
        "latest_commit": latest,
        "up_to_date": up_to_date,
        "check_ok": check_ok,
        "repo_url": REPO_URL,
    }


@router.post("/api/admin/update/trigger")
def update_trigger(user: UserContext = Depends(require_admin_user)):
    if not _update_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An update is already in progress")
    try:

        def _do_update():
            global _update_status
            _update_status = {
                "state": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
                "error": None,
            }
            _update_log_lines.clear()
            try:
                import subprocess

                _update_log("Starting AmpAI code update…")
                _update_status["state"] = "success"
                _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
                log_audit_event(
                    username=user.username,
                    action="admin.docker.update.success",
                    details="",
                )
            except Exception as exc:
                _update_log(f"ERROR: {exc}")
                _update_status["state"] = "error"
                _update_status["finished_at"] = datetime.now(timezone.utc).isoformat()
                _update_status["error"] = str(exc)
                log_audit_event(
                    username=user.username,
                    action="admin.docker.update.failure",
                    details=str(exc),
                )
            finally:
                _update_lock.release()

        t = threading.Thread(target=_do_update, daemon=True)
        t.start()
    except Exception as e:
        _update_lock.release()
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "status": "started",
        "message": "Update started. Poll /api/admin/update/status for progress.",
    }


@router.get("/api/admin/update/status")
def update_status_endpoint(user: UserContext = Depends(require_admin_user)):
    return {**_update_status, "log_lines": list(_update_log_lines)}


@router.get("/api/admin/update/backups")
def update_list_backups(user: UserContext = Depends(require_admin_user)):
    os.makedirs(CODE_BACKUP_DIR, exist_ok=True)
    backups = []
    for name in sorted(os.listdir(CODE_BACKUP_DIR), reverse=True):
        full = os.path.join(CODE_BACKUP_DIR, name)
        if not os.path.isdir(full):
            continue
        size = 0
        for dirpath, _, filenames in os.walk(full):
            for fname in filenames:
                try:
                    size += os.path.getsize(os.path.join(dirpath, fname))
                except Exception:
                    pass
        commit_file = os.path.join(full, "git_commit.txt")
        commit = "unknown"
        if os.path.exists(commit_file):
            with open(commit_file) as f:
                commit = f.read().strip()[:12]
        backups.append(
            {
                "name": name,
                "path": full,
                "created_at": name,
                "size_bytes": size,
                "commit": commit,
            }
        )
    return {"backups": backups, "total": len(backups)}


@router.delete("/api/admin/update/backups/{backup_name}")
def update_delete_backup(
    backup_name: str, user: UserContext = Depends(require_admin_user)
):
    if "/" in backup_name or ".." in backup_name:
        raise HTTPException(status_code=400, detail="Invalid backup name")
    full_path = os.path.join(CODE_BACKUP_DIR, backup_name)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    shutil.rmtree(full_path)
    log_audit_event(
        username=user.username,
        action="admin.docker.backup.delete",
        details=f"backup={backup_name}",
    )
    return {"deleted": backup_name}


@router.post("/api/admin/update/backups/{backup_name}/restore")
def update_restore_backup(
    backup_name: str, user: UserContext = Depends(require_admin_user)
):
    if "/" in backup_name or ".." in backup_name:
        raise HTTPException(status_code=400, detail="Invalid backup name")
    full_path = os.path.join(CODE_BACKUP_DIR, backup_name)
    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="Backup not found")
    backend_backup = os.path.join(full_path, "backend")
    frontend_backup = os.path.join(full_path, "frontend")
    backend_dst = os.path.dirname(os.path.dirname(__file__))
    frontend_dst = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "frontend"
    )
    if not os.path.isdir(backend_backup) and not os.path.isdir(frontend_backup):
        raise HTTPException(
            status_code=400, detail="Backup does not contain backend/frontend folders"
        )
    if os.path.isdir(backend_backup):
        shutil.copytree(backend_backup, backend_dst, dirs_exist_ok=True)
    if os.path.isdir(frontend_backup):
        shutil.copytree(frontend_backup, frontend_dst, dirs_exist_ok=True)
    log_audit_event(
        username=user.username,
        action="admin.docker.backup.restore",
        details=f"backup={backup_name}",
    )

    def _restart_server():
        time.sleep(2)
        os.execv(
            "/usr/local/bin/uvicorn",
            ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        )

    threading.Thread(target=_restart_server, daemon=True).start()
    return {
        "restored": backup_name,
        "status": "restoring",
        "message": "Backup restored. Server restarting...",
    }
