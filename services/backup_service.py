"""
Backup Service — Refactored from backup_helpers.py.

Implements daily automated backup of database (chat history, memories, core memories,
users, configs, personas, tasks), manifest generation, local/FTP destinations with
configurable profiles, restore with preflight validation, and audit logging.

Requirements: 13.1, 13.2, 13.4, 13.5, 13.6, 13.7
"""

from __future__ import annotations

import ftplib
import gzip
import hashlib
import json
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from logging_utils import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = "2.0"
DEFAULT_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BackupProfile:
    """Configurable backup destination profile."""
    id: Optional[int] = None
    name: str = "default"
    destination_type: str = "local"  # "local" or "ftp"
    destination_host: Optional[str] = None
    destination_port: int = 21
    destination_path: Optional[str] = None
    destination_username: Optional[str] = None
    credential_key_ref: Optional[str] = None
    retention_count: int = 7
    enabled: bool = True


@dataclass
class BackupManifest:
    """Manifest generated with each backup."""
    schema_version: str = SCHEMA_VERSION
    timestamp: str = ""
    session_count: int = 0
    message_count: int = 0
    checksum_sha256: str = ""
    created_by: str = ""
    job_id: str = ""


@dataclass
class PreflightCheck:
    """Result of a single preflight validation check."""
    name: str
    passed: bool
    expected: str = ""
    actual: str = ""


@dataclass
class PreflightResult:
    """Aggregate preflight validation result."""
    passed: bool
    checks: List[PreflightCheck] = field(default_factory=list)

    @property
    def failed_checks(self) -> List[PreflightCheck]:
        return [c for c in self.checks if not c.passed]


@dataclass
class BackupResult:
    """Result of a backup operation."""
    ok: bool
    job_id: str = ""
    manifest: Optional[BackupManifest] = None
    artifact_path: Optional[str] = None
    error: Optional[str] = None
    item_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class RestoreResult:
    """Result of a restore operation."""
    ok: bool
    job_id: str = ""
    summary: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BackupService
# ---------------------------------------------------------------------------


class BackupService:
    """
    Manages backup and restore operations for the AmpAI database.

    Supports:
    - Daily automated backup of all database tables
    - Manifest generation with schema version, timestamp, counts, SHA-256 checksum
    - Local filesystem and FTP destinations with configurable profiles
    - Restore with preflight validation (schema version, checksum, DB, disk space)
    - Audit logging of all backup/restore operations
    """

    def __init__(self, engine, audit_logger=None):
        self.engine = engine
        self.audit_logger = audit_logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_backup(self, actor: str, profile: Optional[BackupProfile] = None) -> BackupResult:
        """
        Execute a full backup operation.

        Collects all database data, generates a manifest with SHA-256 checksum,
        and writes to the configured destination (local or FTP).
        """
        job_id = str(uuid.uuid4())
        profile = profile or BackupProfile(destination_path=DEFAULT_BACKUP_DIR)

        try:
            # Collect data from database
            data = self._collect_backup_data()
            serialized = json.dumps(data, indent=2, default=str)
            checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

            # Build manifest
            session_count = len(data.get("sessions", []))
            message_count = sum(
                len(s.get("messages", [])) for s in data.get("sessions", [])
            )
            manifest = BackupManifest(
                schema_version=SCHEMA_VERSION,
                timestamp=datetime.now(timezone.utc).isoformat(),
                session_count=session_count,
                message_count=message_count,
                checksum_sha256=checksum,
                created_by=actor,
                job_id=job_id,
            )

            item_counts = {
                "sessions": session_count,
                "messages": message_count,
                "core_memories": len(data.get("core_memories", [])),
                "users": len(data.get("users", [])),
                "configs": len(data.get("configs", {})),
                "personas": len(data.get("personas", [])),
                "tasks": len(data.get("tasks", [])),
            }

            # Write to destination
            artifact_path = self._write_backup(
                profile, serialized, manifest, job_id
            )

            # Record job in backup_jobs table
            self._record_backup_job(job_id, profile, "success", artifact_path, len(serialized.encode("utf-8")))

            # Apply retention policy
            if profile.retention_count and profile.destination_type == "local":
                self._apply_retention(profile)

            # Audit log
            self._audit_log(actor, "backup_run", "success", job_id, item_counts)

            return BackupResult(
                ok=True,
                job_id=job_id,
                manifest=manifest,
                artifact_path=artifact_path,
                item_counts=item_counts,
            )

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Backup failed: {error_msg}", exc_info=exc)
            # Record failure in backup status history (Req 13.7)
            self._record_backup_job(job_id, profile, "failed", error_message=error_msg)
            self._audit_log(actor, "backup_run", "failed", job_id, error=error_msg)
            return BackupResult(ok=False, job_id=job_id, error=error_msg)

    def preflight_restore(self, archive_path: str) -> PreflightResult:
        """
        Perform preflight validation before restore.

        Checks:
        - Schema version compatibility
        - Archive checksum integrity
        - Database connectivity
        - Available disk space

        Returns PreflightResult with pass/fail and details for each check.
        Requirement 13.4, 13.5
        """
        checks: List[PreflightCheck] = []

        # 1. Check archive exists and is readable
        if not os.path.isfile(archive_path):
            checks.append(PreflightCheck(
                name="archive_exists",
                passed=False,
                expected="file exists",
                actual="file not found",
            ))
            return PreflightResult(passed=False, checks=checks)

        # 2. Read and validate manifest from archive
        manifest_data = None
        stored_checksum = None
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                if "manifest.json" not in zf.namelist():
                    checks.append(PreflightCheck(
                        name="manifest_present",
                        passed=False,
                        expected="manifest.json in archive",
                        actual="manifest.json not found",
                    ))
                    return PreflightResult(passed=False, checks=checks)
                manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        except (zipfile.BadZipFile, json.JSONDecodeError) as exc:
            checks.append(PreflightCheck(
                name="archive_readable",
                passed=False,
                expected="valid zip with JSON manifest",
                actual=str(exc),
            ))
            return PreflightResult(passed=False, checks=checks)

        checks.append(PreflightCheck(name="archive_readable", passed=True,
                                     expected="valid zip", actual="valid zip"))

        # 3. Schema version compatibility
        archive_schema = manifest_data.get("schema_version", "unknown")
        compatible = self._is_schema_compatible(archive_schema)
        checks.append(PreflightCheck(
            name="schema_version",
            passed=compatible,
            expected=f"compatible with {SCHEMA_VERSION}",
            actual=archive_schema,
        ))

        # 4. Checksum integrity
        stored_checksum = manifest_data.get("checksum_sha256", "")
        if stored_checksum:
            actual_checksum = self._verify_archive_checksum(archive_path)
            checksum_ok = (stored_checksum == actual_checksum)
            checks.append(PreflightCheck(
                name="checksum_integrity",
                passed=checksum_ok,
                expected=stored_checksum,
                actual=actual_checksum or "could not compute",
            ))
        else:
            checks.append(PreflightCheck(
                name="checksum_integrity",
                passed=True,
                expected="no checksum in manifest",
                actual="skipped",
            ))

        # 5. Database connectivity
        db_ok = self._check_db_connectivity()
        checks.append(PreflightCheck(
            name="database_connectivity",
            passed=db_ok,
            expected="database reachable",
            actual="connected" if db_ok else "unreachable",
        ))

        # 6. Disk space check
        archive_size = os.path.getsize(archive_path)
        # Estimate needed space: 3x archive size for extraction + restore overhead
        needed_bytes = archive_size * 3
        disk_ok, available = self._check_disk_space(needed_bytes)
        checks.append(PreflightCheck(
            name="disk_space",
            passed=disk_ok,
            expected=f">= {needed_bytes} bytes needed",
            actual=f"{available} bytes available",
        ))

        all_passed = all(c.passed for c in checks)
        return PreflightResult(passed=all_passed, checks=checks)

    def restore(self, archive_path: str, actor: str, options: Optional[Dict] = None) -> RestoreResult:
        """
        Restore from a backup archive after preflight validation.

        Rejects restore on preflight failure with list of failed checks.
        Logs operation to AuditLogger.
        Requirements: 13.4, 13.5, 13.6
        """
        job_id = str(uuid.uuid4())
        options = options or {}

        # Run preflight validation
        preflight = self.preflight_restore(archive_path)
        if not preflight.passed:
            # Reject restore with failed checks (Req 13.5)
            failed_details = [
                {"check": c.name, "expected": c.expected, "actual": c.actual}
                for c in preflight.failed_checks
            ]
            self._audit_log(actor, "backup_restore", "failed", job_id,
                            error=f"Preflight failed: {failed_details}")
            return RestoreResult(
                ok=False,
                job_id=job_id,
                errors=[
                    f"{c.name}: expected={c.expected}, actual={c.actual}"
                    for c in preflight.failed_checks
                ],
            )

        # Perform restore
        try:
            result = self._execute_restore(archive_path, options)
            result.job_id = job_id

            # Audit log
            status = "success" if result.ok else "failed"
            self._audit_log(actor, "backup_restore", status, job_id, result.summary)

            return result

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"Restore failed: {error_msg}", exc_info=exc)
            self._audit_log(actor, "backup_restore", "failed", job_id, error=error_msg)
            return RestoreResult(ok=False, job_id=job_id, errors=[error_msg])

    def test_ftp_connection(self, host: str, user: str, password: str,
                           remote_path: Optional[str] = "/", port: int = 21) -> Tuple[bool, str]:
        """Test FTP connection with given credentials."""
        try:
            with ftplib.FTP() as ftp:
                ftp.connect(host, port, timeout=10)
                ftp.login(user=user, passwd=password)
                if remote_path:
                    ftp.cwd(remote_path)
            return True, "FTP connection successful"
        except Exception as exc:
            return False, str(exc)

    def list_backup_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List backup job history from the database."""
        if not self.engine:
            return []
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT id, profile_id, status, started_at, finished_at, "
                    "bytes_written, artifact_path, error_message, created_at "
                    "FROM backup_jobs ORDER BY created_at DESC LIMIT :limit"
                ), {"limit": limit}).mappings().all()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Failed to list backup jobs: {exc}")
            return []

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def _collect_backup_data(self) -> Dict[str, Any]:
        """Collect all database tables for backup (Req 13.1)."""
        if not self.engine:
            raise RuntimeError("Database engine not available")

        data: Dict[str, Any] = {}
        with self.engine.connect() as conn:
            # Chat history (sessions + messages)
            data["sessions"] = self._fetch_sessions(conn)

            # Core memories
            data["core_memories"] = self._fetch_table_rows(
                conn, "SELECT id, username, fact, category, created_at FROM core_memories"
            )

            # Memory candidates
            data["memories"] = self._fetch_table_rows(
                conn,
                "SELECT id, username, session_id, candidate_text, confidence, "
                "status, created_at FROM memory_candidates"
            )

            # Users
            data["users"] = self._fetch_table_rows(
                conn, "SELECT username, role, password_hash, created_at FROM users"
            )

            # App configs
            configs_rows = conn.execute(text(
                "SELECT config_key, config_value FROM app_configs"
            )).mappings().all()
            data["configs"] = {r["config_key"]: r["config_value"] for r in configs_rows}

            # Personas
            data["personas"] = self._fetch_table_rows(
                conn,
                "SELECT id, username, name, system_prompt, tags, is_default, created_at "
                "FROM persona_presets"
            )

            # Tasks
            data["tasks"] = self._fetch_table_rows(
                conn,
                "SELECT id, username, title, description, status, priority, "
                "due_at, session_id, created_at, updated_at FROM tasks"
            )

        return data

    def _fetch_sessions(self, conn) -> List[Dict]:
        """Fetch all chat sessions with their messages."""
        sessions = []
        session_rows = conn.execute(text(
            "SELECT DISTINCT session_id FROM chat_message_store "
            "WHERE session_id IS NOT NULL"
        )).fetchall()

        # Get session metadata
        meta_rows = conn.execute(text(
            "SELECT session_id, title, category, pinned, archived, owner_username "
            "FROM session_metadata"
        )).mappings().all()
        meta_map = {r["session_id"]: dict(r) for r in meta_rows}

        for (sid,) in session_rows:
            msg_rows = conn.execute(text(
                "SELECT message, created_at FROM chat_message_store "
                "WHERE session_id = :s ORDER BY id ASC"
            ), {"s": sid}).mappings().all()

            messages = []
            for row in msg_rows:
                messages.append({
                    "message": row["message"],
                    "created_at": str(row["created_at"] or ""),
                })

            meta = meta_map.get(sid, {})
            sessions.append({
                "session_id": sid,
                "title": meta.get("title"),
                "category": meta.get("category", "Uncategorized"),
                "pinned": bool(meta.get("pinned", False)),
                "archived": bool(meta.get("archived", False)),
                "owner_username": meta.get("owner_username"),
                "messages": messages,
            })

        return sessions

    def _fetch_table_rows(self, conn, sql: str) -> List[Dict]:
        """Generic helper to fetch rows as list of dicts."""
        rows = conn.execute(text(sql)).mappings().all()
        return [
            {k: (str(v) if isinstance(v, datetime) else v) for k, v in dict(r).items()}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Write backup to destination
    # ------------------------------------------------------------------

    def _write_backup(self, profile: BackupProfile, serialized: str,
                      manifest: BackupManifest, job_id: str) -> Optional[str]:
        """Write backup to the configured destination."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"ampai_backup_{ts}_{job_id[:8]}.zip"

        if profile.destination_type == "local":
            return self._write_local(profile, serialized, manifest, filename)
        elif profile.destination_type == "ftp":
            return self._write_ftp(profile, serialized, manifest, filename)
        else:
            raise ValueError(f"Unsupported destination type: {profile.destination_type}")

    def _write_local(self, profile: BackupProfile, serialized: str,
                     manifest: BackupManifest, filename: str) -> str:
        """Write backup archive to local filesystem."""
        dest_dir = profile.destination_path or DEFAULT_BACKUP_DIR
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, filename)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            manifest_dict = {
                "schema_version": manifest.schema_version,
                "timestamp": manifest.timestamp,
                "session_count": manifest.session_count,
                "message_count": manifest.message_count,
                "checksum_sha256": manifest.checksum_sha256,
                "created_by": manifest.created_by,
                "job_id": manifest.job_id,
            }
            zf.writestr("manifest.json", json.dumps(manifest_dict, indent=2))

            # Write payload (gzipped for efficiency)
            compressed = gzip.compress(serialized.encode("utf-8"))
            zf.writestr("payload.json.gz", compressed)

        return zip_path

    def _write_ftp(self, profile: BackupProfile, serialized: str,
                   manifest: BackupManifest, filename: str) -> str:
        """Write backup archive to FTP destination."""
        if not profile.destination_host:
            raise ValueError("FTP destination host not configured")

        # Build zip in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest_dict = {
                "schema_version": manifest.schema_version,
                "timestamp": manifest.timestamp,
                "session_count": manifest.session_count,
                "message_count": manifest.message_count,
                "checksum_sha256": manifest.checksum_sha256,
                "created_by": manifest.created_by,
                "job_id": manifest.job_id,
            }
            zf.writestr("manifest.json", json.dumps(manifest_dict, indent=2))
            compressed = gzip.compress(serialized.encode("utf-8"))
            zf.writestr("payload.json.gz", compressed)

        zip_buffer.seek(0)

        # Upload via FTP
        password = self._resolve_credential(profile.credential_key_ref) or ""
        port = profile.destination_port or 21
        with ftplib.FTP() as ftp:
            ftp.connect(profile.destination_host, port, timeout=30)
            ftp.login(user=profile.destination_username or "", passwd=password)
            if profile.destination_path:
                ftp.cwd(profile.destination_path)
            ftp.storbinary(f"STOR {filename}", zip_buffer)

        return f"ftp://{profile.destination_host}/{profile.destination_path or ''}/{filename}"

    # ------------------------------------------------------------------
    # Restore execution
    # ------------------------------------------------------------------

    def _execute_restore(self, archive_path: str, options: Dict) -> RestoreResult:
        """Execute the actual restore from a validated archive."""
        if not self.engine:
            return RestoreResult(ok=False, errors=["Database engine not available"])

        errors: List[str] = []
        summary: Dict[str, int] = {}
        do = lambda k: options.get(k, True)
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # Read payload
                if "payload.json.gz" in zf.namelist():
                    data = json.loads(
                        gzip.decompress(zf.read("payload.json.gz")).decode("utf-8")
                    )
                else:
                    return RestoreResult(ok=False, errors=["No payload found in archive"])

            with self.engine.begin() as conn:
                # Restore chat sessions
                if do("restore_chats"):
                    n_sessions = 0
                    n_messages = 0
                    for sess in data.get("sessions", []):
                        sid = sess.get("session_id", "")
                        if not sid:
                            continue
                        # Upsert session metadata
                        conn.execute(text(
                            "INSERT INTO session_metadata (session_id, title, category, "
                            "pinned, archived, updated_at) "
                            "VALUES (:s, :t, :c, :p, :a, :ts) "
                            "ON CONFLICT (session_id) DO UPDATE SET "
                            "category=EXCLUDED.category, updated_at=EXCLUDED.updated_at"
                        ), {
                            "s": sid,
                            "t": sess.get("title"),
                            "c": sess.get("category", "Uncategorized"),
                            "p": sess.get("pinned", False),
                            "a": sess.get("archived", False),
                            "ts": now_iso,
                        })
                        for msg in sess.get("messages", []):
                            conn.execute(text(
                                "INSERT INTO chat_message_store (session_id, message) "
                                "VALUES (:s, :m)"
                            ), {"s": sid, "m": msg.get("message", "")})
                            n_messages += 1
                        n_sessions += 1
                    summary["restored_sessions"] = n_sessions
                    summary["restored_messages"] = n_messages

                # Restore core memories
                if do("restore_core_memories"):
                    n_cm = 0
                    for cm in data.get("core_memories", []):
                        try:
                            conn.execute(text(
                                "INSERT INTO core_memories (username, fact, category, created_at) "
                                "VALUES (:u, :f, :c, :ts) ON CONFLICT DO NOTHING"
                            ), {
                                "u": cm.get("username", "system"),
                                "f": cm.get("fact", ""),
                                "c": cm.get("category", "general"),
                                "ts": now_iso,
                            })
                            n_cm += 1
                        except Exception as ex:
                            errors.append(f"core_memory: {ex}")
                    summary["restored_core_memories"] = n_cm

                # Restore memory candidates
                if do("restore_memories"):
                    n_mems = 0
                    for m in data.get("memories", []):
                        try:
                            conn.execute(text(
                                "INSERT INTO memory_candidates "
                                "(username, session_id, candidate_text, confidence, status, created_at) "
                                "VALUES (:u, :s, :t, :c, :st, :ts) ON CONFLICT DO NOTHING"
                            ), {
                                "u": m.get("username", "system"),
                                "s": m.get("session_id", ""),
                                "t": (m.get("candidate_text") or "")[:2000],
                                "c": str(m.get("confidence", 0.5)),
                                "st": m.get("status", "approved"),
                                "ts": now_iso,
                            })
                            n_mems += 1
                        except Exception as ex:
                            errors.append(f"memory: {ex}")
                    summary["restored_memories"] = n_mems

                # Restore users
                if do("restore_users"):
                    n_users = 0
                    for u in data.get("users", []):
                        try:
                            conn.execute(text(
                                "INSERT INTO users (username, role, password_hash, created_at, updated_at) "
                                "VALUES (:u, :r, :p, :ts, :ts) "
                                "ON CONFLICT (username) DO UPDATE SET role=EXCLUDED.role"
                            ), {
                                "u": u.get("username", ""),
                                "r": u.get("role", "user"),
                                "p": u.get("password_hash", ""),
                                "ts": now_iso,
                            })
                            n_users += 1
                        except Exception as ex:
                            errors.append(f"user: {ex}")
                    summary["restored_users"] = n_users

                # Restore configs
                if do("restore_configs"):
                    n_cfg = 0
                    for k, v in data.get("configs", {}).items():
                        try:
                            conn.execute(text(
                                "INSERT INTO app_configs (config_key, config_value) "
                                "VALUES (:k, :v) ON CONFLICT (config_key) "
                                "DO UPDATE SET config_value=EXCLUDED.config_value"
                            ), {"k": k, "v": str(v)})
                            n_cfg += 1
                        except Exception as ex:
                            errors.append(f"config: {ex}")
                    summary["restored_configs"] = n_cfg

                # Restore personas
                if do("restore_personas"):
                    n_p = 0
                    for p in data.get("personas", []):
                        try:
                            conn.execute(text(
                                "INSERT INTO persona_presets "
                                "(username, name, system_prompt, tags, is_default, created_at) "
                                "VALUES (:u, :n, :sp, :t, :d, :ts) ON CONFLICT DO NOTHING"
                            ), {
                                "u": p.get("username"),
                                "n": p.get("name", ""),
                                "sp": p.get("system_prompt", ""),
                                "t": p.get("tags", ""),
                                "d": bool(p.get("is_default")),
                                "ts": now_iso,
                            })
                            n_p += 1
                        except Exception as ex:
                            errors.append(f"persona: {ex}")
                    summary["restored_personas"] = n_p

                # Restore tasks
                if do("restore_tasks"):
                    n_t = 0
                    for t in data.get("tasks", []):
                        try:
                            conn.execute(text(
                                "INSERT INTO tasks (username, title, description, status, "
                                "priority, due_at, session_id, created_at, updated_at) "
                                "VALUES (:u, :ti, :de, :st, :pr, :du, :se, :ts, :ts) "
                                "ON CONFLICT DO NOTHING"
                            ), {
                                "u": t.get("username", "system"),
                                "ti": t.get("title", ""),
                                "de": t.get("description", ""),
                                "st": t.get("status", "todo"),
                                "pr": t.get("priority", "medium"),
                                "du": t.get("due_at"),
                                "se": t.get("session_id"),
                                "ts": now_iso,
                            })
                            n_t += 1
                        except Exception as ex:
                            errors.append(f"task: {ex}")
                    summary["restored_tasks"] = n_t

        except Exception as exc:
            errors.append(f"Fatal: {exc}")
            return RestoreResult(ok=False, summary=summary, errors=errors)

        return RestoreResult(ok=len(errors) == 0, summary=summary, errors=errors)

    # ------------------------------------------------------------------
    # Preflight helpers
    # ------------------------------------------------------------------

    def _is_schema_compatible(self, archive_schema: str) -> bool:
        """Check if the archive schema version is compatible with current."""
        # Major version must match; minor can differ
        try:
            archive_major = int(archive_schema.split(".")[0])
            current_major = int(SCHEMA_VERSION.split(".")[0])
            return archive_major == current_major
        except (ValueError, IndexError):
            return False

    def _verify_archive_checksum(self, archive_path: str) -> Optional[str]:
        """Compute SHA-256 of the payload inside the archive."""
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                if "payload.json.gz" in zf.namelist():
                    payload_bytes = gzip.decompress(zf.read("payload.json.gz"))
                    # The checksum is of the JSON string (uncompressed)
                    return hashlib.sha256(payload_bytes).hexdigest()
        except Exception:
            pass
        return None

    def _check_db_connectivity(self) -> bool:
        """Verify database is reachable."""
        if not self.engine:
            return False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _check_disk_space(self, needed_bytes: int) -> Tuple[bool, int]:
        """Check if sufficient disk space is available."""
        try:
            stat = shutil.disk_usage("/")
            available = stat.free
            return available >= needed_bytes, available
        except Exception:
            # If we can't check, assume it's fine
            return True, 0

    # ------------------------------------------------------------------
    # Retention policy
    # ------------------------------------------------------------------

    def _apply_retention(self, profile: BackupProfile) -> None:
        """Remove old backups beyond retention count for local destinations."""
        dest_dir = profile.destination_path or DEFAULT_BACKUP_DIR
        if not os.path.isdir(dest_dir):
            return

        # List zip files sorted by modification time (newest first)
        zip_files = sorted(
            [f for f in os.listdir(dest_dir) if f.endswith(".zip")],
            key=lambda f: os.path.getmtime(os.path.join(dest_dir, f)),
            reverse=True,
        )

        # Remove files beyond retention count
        retention = profile.retention_count or 7
        for old_file in zip_files[retention:]:
            try:
                os.remove(os.path.join(dest_dir, old_file))
                logger.info(f"Retention cleanup: removed {old_file}")
            except Exception as exc:
                logger.warning(f"Failed to remove old backup {old_file}: {exc}")

    # ------------------------------------------------------------------
    # Credential resolution
    # ------------------------------------------------------------------

    def _resolve_credential(self, key_ref: Optional[str]) -> Optional[str]:
        """Resolve a credential from app_configs or environment."""
        if not key_ref:
            return None
        # Try environment variable first
        env_val = os.getenv(key_ref)
        if env_val:
            return env_val
        # Try app_configs table
        if self.engine:
            try:
                with self.engine.connect() as conn:
                    row = conn.execute(text(
                        "SELECT config_value FROM app_configs WHERE config_key = :k"
                    ), {"k": key_ref}).first()
                    if row:
                        return row[0]
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Job recording
    # ------------------------------------------------------------------

    def _record_backup_job(self, job_id: str, profile: Optional[BackupProfile],
                           status: str, artifact_path: Optional[str] = None,
                           bytes_written: int = 0, error_message: Optional[str] = None) -> None:
        """Record backup job status in the backup_jobs table (Req 13.7)."""
        if not self.engine:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            profile_id = profile.id if profile else None
            with self.engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO backup_jobs "
                    "(profile_id, status, started_at, finished_at, bytes_written, "
                    "artifact_path, error_message, created_at) "
                    "VALUES (:pid, :status, :started, :finished, :bytes, :path, :err, :created)"
                ), {
                    "pid": profile_id,
                    "status": status,
                    "started": now,
                    "finished": now,
                    "bytes": bytes_written,
                    "path": artifact_path,
                    "err": error_message,
                    "created": now,
                })
        except Exception as exc:
            logger.error(f"Failed to record backup job: {exc}")

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _audit_log(self, actor: str, operation: str, status: str,
                   job_id: str, item_counts: Optional[Dict] = None,
                   error: Optional[str] = None) -> None:
        """Log backup/restore operation to AuditLogger (Req 13.6)."""
        if not self.audit_logger:
            return
        details = {
            "operation": operation,
            "status": status,
            "job_id": job_id,
        }
        if item_counts:
            details["item_counts"] = item_counts
        if error:
            details["error"] = error

        action_type = "backup_run" if "backup" in operation else "backup_restore"
        self.audit_logger.log(
            username=actor,
            action_type=action_type,
            details=details,
        )
