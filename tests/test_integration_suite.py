"""
Unified Integration Test Suite — Subsystem Isolation Tests.

Ensures at least one nominal-path and one error-path test for each subsystem:
- Docker environment validation (config_validator)
- Memory system operations
- Chat history CRUD
- Task CRUD
- Web search integration
- Browser automation security constraints
- Terminal command blocking
- Telegram message handling
- Backup and restore
- local_only_mode enforcement
- Desktop chat payload structure

Uses mocks/stubs for database, Redis, network, and third-party APIs.
Each subsystem is isolated so failure in one does not prevent others from running.
Exit with non-zero code on any test failure (pytest default behavior).

Requirements: 16.1, 16.2, 16.3, 16.4
"""

import gzip
import hashlib
import json
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# =============================================================================
# SUBSYSTEM 1: Docker Environment Validation (config_validator)
# =============================================================================


class TestConfigValidatorSubsystem:
    """Config validator: nominal and error paths."""

    def test_nominal_safe_production_config(self):
        """Nominal: safe values in production mode pass validation."""
        from config_validator import validate_config

        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "super-secure-random-key-2024",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "Str0ng!Pr0duction#Pass",
            "POSTGRES_PASSWORD": "pg-production-secret-42",
        }
        with patch.dict(os.environ, env, clear=True):
            validate_config()  # Should not raise

    def test_error_unsafe_defaults_in_production(self):
        """Error: unsafe defaults in production terminate with exit code 1."""
        from config_validator import validate_config

        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "change-me",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "P@ssw0rd",
            "POSTGRES_PASSWORD": "ampai",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()
            assert exc_info.value.code == 1


# =============================================================================
# SUBSYSTEM 2: Memory System Operations
# =============================================================================


class TestMemorySubsystem:
    """Memory system: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self):
        """Mock heavy dependencies for memory service."""
        for mod in [
            "cryptography", "cryptography.fernet",
            "langchain_community", "langchain_community.chat_message_histories",
            "langchain_community.embeddings", "langchain_core",
            "langchain_core.documents", "langchain_postgres",
            "langchain_openai", "langchain_google_genai",
            "logging_utils", "ampai_identity",
        ]:
            sys.modules.setdefault(mod, MagicMock())

        mock_db = MagicMock()
        mock_db.engine = MagicMock()
        mock_db.DATABASE_URL = "postgresql://test:test@localhost/test"
        mock_db.get_config = MagicMock(return_value=None)
        mock_db.add_core_memory = MagicMock(return_value=True)
        mock_db.list_chat_messages = MagicMock(return_value=[])
        sys.modules.setdefault("database", mock_db)

        mock_persistence = MagicMock()
        mock_persistence.memory_persistence_manager = MagicMock()
        mock_persistence.memory_persistence_manager._analyze_text_importance = (
            MagicMock(return_value=0.5)
        )
        sys.modules.setdefault("memory_persistence", mock_persistence)
        sys.modules.setdefault("memory_indexer", MagicMock())
        sys.modules.setdefault("memory_curator", MagicMock())
        yield

    def test_nominal_save_explicit_memory(self):
        """Nominal: saving an explicit memory returns the stored record."""
        from services.memory_service import MemoryService

        # Fake DB connection that returns an inserted row
        class FakeConn:
            def execute(self, stmt, params=None):
                class R:
                    def fetchone(self):
                        return (1, "2024-01-01T00:00:00")
                return R()
            def __enter__(self): return self
            def __exit__(self, *a): pass

        class FakeEngine:
            def begin(self): return FakeConn()
            def connect(self): return FakeConn()

        indexer = MagicMock()
        indexer.enabled = True
        indexer.add_fact = MagicMock()

        svc = MemoryService(db_engine=FakeEngine(), indexer=indexer)
        result = svc.save_explicit_memory("user1", "sess1", "I like Python")
        assert result is not None
        assert result["fact"] == "I like Python"
        indexer.add_fact.assert_called_once_with("I like Python", "user1")

    def test_error_empty_memory_text_returns_none(self):
        """Error: empty text returns None without DB interaction."""
        from services.memory_service import MemoryService

        indexer = MagicMock()
        indexer.enabled = True
        engine = MagicMock()
        engine.__bool__ = lambda s: True

        svc = MemoryService(db_engine=engine, indexer=indexer)
        result = svc.save_explicit_memory("user1", "sess1", "")
        assert result is None


# =============================================================================
# SUBSYSTEM 3: Chat History CRUD
# =============================================================================


class TestChatHistoryCRUDSubsystem:
    """Chat history CRUD: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self):
        """Mock dependencies for sessions router."""
        for mod in [
            "cryptography", "cryptography.fernet",
            "langchain_community", "langchain_community.chat_message_histories",
            "langchain_community.embeddings", "langchain_core",
            "langchain_core.prompts", "langchain_core.messages",
            "langchain_core.output_parsers", "redis",
            "jose", "jose.jwt", "passlib", "passlib.context",
            "memory_indexer", "memory_persistence", "memory_curator",
            "session_recall", "scheduler", "logging_utils",
            "agent", "integrations", "integrations.github",
            "integrations.gmail_api", "integrations.telegram_api",
            "backup_helpers", "auth",
        ]:
            sys.modules.setdefault(mod, MagicMock())
        mock_db = MagicMock()
        mock_db.CHAT_HISTORY_TABLE = "chat_message_store"
        mock_db.engine = MagicMock()
        sys.modules.setdefault("database", mock_db)
        yield

    def test_nominal_create_session(self):
        """Nominal: POST /api/sessions creates a new session."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.deps import UserContext, require_authenticated_user
        import routers.sessions as sessions_module

        app = FastAPI()
        app.include_router(sessions_module.router)
        app.dependency_overrides[require_authenticated_user] = (
            lambda: UserContext(username="testuser", role="user")
        )
        client = TestClient(app)

        with patch("routers.sessions.ensure_session_owner", return_value=True), \
             patch("routers.sessions.log_audit_event"), \
             patch("routers.sessions.create_session_metadata", return_value=True):
            resp = client.post("/api/sessions", json={"title": "Test"})
        assert resp.status_code == 201
        assert "session_id" in resp.json()
        app.dependency_overrides.clear()

    def test_error_patch_nonexistent_session(self):
        """Error: PATCH on non-existent session returns 404."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.deps import UserContext, require_authenticated_user
        import routers.sessions as sessions_module

        app = FastAPI()
        app.include_router(sessions_module.router)
        app.dependency_overrides[require_authenticated_user] = (
            lambda: UserContext(username="testuser", role="user")
        )
        client = TestClient(app)

        with patch("routers.sessions.get_session_metadata", return_value=None), \
             patch("routers.sessions._can_access_session", return_value=True):
            resp = client.patch("/api/sessions/nonexistent", json={"title": "X"})
        assert resp.status_code == 404
        app.dependency_overrides.clear()


# =============================================================================
# SUBSYSTEM 4: Task CRUD
# =============================================================================


class TestTaskCRUDSubsystem:
    """Task CRUD: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self):
        for mod in [
            "cryptography", "cryptography.fernet",
            "langchain_community", "langchain_community.chat_message_histories",
            "logging_utils",
        ]:
            sys.modules.setdefault(mod, MagicMock())
        mock_db = MagicMock()
        mock_db.create_task = MagicMock(return_value=1)
        mock_db.list_tasks = MagicMock(return_value=([], 0))
        mock_db.get_task_by_id = MagicMock(return_value=None)
        mock_db.log_audit_event = MagicMock()
        sys.modules.setdefault("database", mock_db)
        mock_jose = MagicMock()
        mock_jose.JWTError = Exception
        sys.modules.setdefault("jose", mock_jose)
        sys.modules.setdefault("core.helpers", MagicMock())
        yield

    def test_nominal_create_task(self):
        """Nominal: POST /api/tasks creates a task successfully."""
        import importlib.util
        _tasks_path = os.path.join(_project_root, "routers", "tasks.py")
        _spec = importlib.util.spec_from_file_location("routers.tasks", _tasks_path)
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["routers.tasks"] = _mod
        _spec.loader.exec_module(_mod)

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.deps import UserContext, require_authenticated_user

        app = FastAPI()
        app.include_router(_mod.router)
        app.dependency_overrides[require_authenticated_user] = (
            lambda: UserContext(username="testuser", role="user")
        )
        client = TestClient(app)

        with patch.object(_mod, "create_task", return_value=42), \
             patch.object(_mod, "log_audit_event"):
            resp = client.post("/api/tasks", json={"title": "Buy milk"})
        assert resp.status_code == 201
        assert resp.json()["id"] == 42
        app.dependency_overrides.clear()

    def test_error_task_title_too_long(self):
        """Error: title > 150 chars returns 400."""
        import importlib.util
        _tasks_path = os.path.join(_project_root, "routers", "tasks.py")
        _spec = importlib.util.spec_from_file_location("routers.tasks", _tasks_path)
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["routers.tasks"] = _mod
        _spec.loader.exec_module(_mod)

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.deps import UserContext, require_authenticated_user

        app = FastAPI()
        app.include_router(_mod.router)
        app.dependency_overrides[require_authenticated_user] = (
            lambda: UserContext(username="testuser", role="user")
        )
        client = TestClient(app)

        resp = client.post("/api/tasks", json={"title": "x" * 151})
        assert resp.status_code == 400
        app.dependency_overrides.clear()


# =============================================================================
# SUBSYSTEM 5: Web Search Integration
# =============================================================================


class TestWebSearchSubsystem:
    """Web search: nominal and error paths."""

    def test_nominal_search_returns_results(self):
        """Nominal: WebSearchService returns hits from first provider."""
        from services.web_search_service import WebSearchService, SearchHit

        svc = WebSearchService(configs={})
        # Mock the internal provider method
        hit = SearchHit(
            title="Result", url="https://example.com",
            snippet="A snippet", provider="duckduckgo",
            timestamp="2024-01-01T00:00:00Z",
        )
        with patch.object(svc, "_search_duckduckgo", return_value=[hit]):
            result = svc.search("test query")
        assert result.status == "ok"
        assert len(result.hits) == 1
        assert result.hits[0].title == "Result"

    def test_error_all_providers_fail(self):
        """Error: all providers fail returns error status."""
        from services.web_search_service import WebSearchService

        svc = WebSearchService(configs={})
        with patch.object(svc, "_search_duckduckgo", side_effect=Exception("timeout")), \
             patch.object(svc, "_search_tavily", side_effect=Exception("no key")), \
             patch.object(svc, "_search_serpapi", side_effect=Exception("no key")), \
             patch.object(svc, "_search_brave", side_effect=Exception("no key")):
            result = svc.search("failing query")
        assert result.status == "failed"
        assert len(result.hits) == 0


# =============================================================================
# SUBSYSTEM 6: Browser Automation Security Constraints
# =============================================================================


class TestBrowserAutomationSubsystem:
    """Browser automation security: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Import browser service directly."""
        import importlib.util
        _svc_path = os.path.join(_project_root, "services", "browser_automation_service.py")
        spec = importlib.util.spec_from_file_location(
            "services.browser_automation_service", _svc_path
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["services.browser_automation_service"] = mod
        spec.loader.exec_module(mod)
        self.mod = mod
        yield

    def test_nominal_allowed_domain_passes(self):
        """Nominal: navigation to allowed domain succeeds check."""
        from policy.browser_policy import BrowserPolicy

        policy = BrowserPolicy(domain_allowlist=["example.com"])
        svc = self.mod.BrowserAutomationService(
            config=self.mod.BrowserConfig(enabled=True, domain_allowlist=["example.com"]),
            audit_logger=MagicMock(),
            browser_policy=policy,
        )
        # Should not raise
        svc.check_domain("https://example.com/page")

    def test_error_disabled_raises(self):
        """Error: browser disabled raises BrowserDisabledError."""
        svc = self.mod.BrowserAutomationService(
            config=self.mod.BrowserConfig(enabled=False),
            audit_logger=MagicMock(),
        )
        with pytest.raises(self.mod.BrowserDisabledError):
            svc.check_enabled()


# =============================================================================
# SUBSYSTEM 7: Terminal Command Blocking
# =============================================================================


class TestTerminalBlockingSubsystem:
    """Terminal command blocking: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Import terminal service directly."""
        import importlib.util
        _svc_path = os.path.join(_project_root, "services", "terminal_service.py")
        spec = importlib.util.spec_from_file_location(
            "services.terminal_service", _svc_path
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["services.terminal_service"] = mod
        spec.loader.exec_module(mod)
        self.mod = mod
        yield

    def test_nominal_safe_command_executes(self):
        """Nominal: safe command executes successfully."""
        config = self.mod.TerminalConfig(enabled=True, require_confirmation=False)
        svc = self.mod.TerminalService(config)
        result = svc.execute("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.blocked is False

    def test_error_dangerous_command_blocked(self):
        """Error: dangerous command (rm -rf /) is blocked."""
        config = self.mod.TerminalConfig(enabled=True, require_confirmation=False)
        svc = self.mod.TerminalService(config)
        with pytest.raises(self.mod.CommandBlockedError):
            svc.execute("rm -rf /")


# =============================================================================
# SUBSYSTEM 8: Telegram Message Handling
# =============================================================================


class TestTelegramSubsystem:
    """Telegram message handling: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Ensure real telegram module is loaded."""
        import importlib
        # Purge any mocked versions
        keys_to_purge = [k for k in sys.modules if k.startswith("integrations")
                         and hasattr(sys.modules[k], "_mock_name")]
        for k in keys_to_purge:
            del sys.modules[k]
        import integrations.telegram_api
        importlib.reload(integrations.telegram_api)
        self.tg = integrations.telegram_api
        yield

    def _make_service(self, allowed_ids=None, chat_response="Hi!"):
        config = self.tg.TelegramBotConfig(
            bot_token="test-token",
            enabled=True,
            allowed_telegram_user_ids=allowed_ids or [],
            telegram_tool_access_enabled=False,
        )
        chat_handler = MagicMock(return_value={"response": chat_response})
        audit_logger = MagicMock()
        user_resolver = MagicMock(return_value="testuser")
        session_manager = MagicMock()
        svc = self.tg.TelegramBotService(
            config=config,
            chat_handler=chat_handler,
            audit_logger=audit_logger,
            user_resolver=user_resolver,
            session_manager=session_manager,
        )
        return svc, chat_handler, audit_logger

    def test_nominal_allowed_user_processed(self):
        """Nominal: message from allowed user is processed."""
        svc, chat_handler, _ = self._make_service(allowed_ids=[123])
        update = {
            "update_id": 1,
            "message": {"from": {"id": 123}, "chat": {"id": 456}, "text": "hi"},
        }
        with patch.object(svc, "_send_reply"):
            result = svc.process_webhook_update(update)
        assert result["status"] == "ok"
        chat_handler.assert_called_once()

    def test_error_disallowed_user_discarded(self):
        """Error: message from disallowed user is silently discarded."""
        svc, chat_handler, audit_logger = self._make_service(allowed_ids=[999])
        update = {
            "update_id": 1,
            "message": {"from": {"id": 123}, "chat": {"id": 456}, "text": "hi"},
        }
        result = svc.process_webhook_update(update)
        assert result["status"] == "ok"
        chat_handler.assert_not_called()
        # Audit event logged for unauthorized user
        audit_logger.assert_called()


# =============================================================================
# SUBSYSTEM 9: Backup and Restore
# =============================================================================


class TestBackupRestoreSubsystem:
    """Backup and restore: nominal and error paths."""

    def _create_valid_archive(self, tmp_path, schema_version="2.0"):
        """Create a valid backup archive with manifest."""
        archive_path = str(tmp_path / "backup.zip")
        data = {"users": [], "configs": {}, "sessions": []}
        serialized = json.dumps(data).encode("utf-8")
        compressed = gzip.compress(serialized)
        checksum = hashlib.sha256(compressed).hexdigest()

        manifest = {
            "schema_version": schema_version,
            "timestamp": "2024-06-15T12:00:00Z",
            "session_count": 0,
            "message_count": 0,
            "checksum_sha256": checksum,
            "created_by": "test",
            "job_id": "test-job-1",
        }

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("full_data.json.gz", compressed)

        return archive_path

    def test_nominal_preflight_valid_archive(self, tmp_path):
        """Nominal: preflight passes with a valid archive."""
        sys.modules.setdefault("logging_utils", MagicMock())
        from services.backup_service import BackupService

        archive_path = self._create_valid_archive(tmp_path)
        engine = MagicMock()
        # Mock DB connectivity check
        conn = MagicMock()
        conn.execute = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        engine.connect = MagicMock(return_value=conn)

        svc = BackupService(engine=engine, audit_logger=MagicMock())

        # Mock checksum verification to match the stored checksum
        with patch.object(svc, "_check_db_connectivity", return_value=True), \
             patch.object(svc, "_check_disk_space", return_value=(True, 999999999)), \
             patch.object(svc, "_verify_archive_checksum") as mock_checksum:
            # Make checksum match what's in the manifest
            data = json.dumps({"users": [], "configs": {}, "sessions": []}).encode("utf-8")
            compressed = gzip.compress(data)
            mock_checksum.return_value = hashlib.sha256(compressed).hexdigest()
            result = svc.preflight_restore(archive_path)

        assert result.passed is True
        assert all(c.passed for c in result.checks)

    def test_error_preflight_missing_file(self, tmp_path):
        """Error: preflight fails when archive file does not exist."""
        sys.modules.setdefault("logging_utils", MagicMock())
        from services.backup_service import BackupService

        engine = MagicMock()
        svc = BackupService(engine=engine, audit_logger=MagicMock())
        result = svc.preflight_restore(str(tmp_path / "nonexistent.zip"))

        assert result.passed is False
        assert any(c.name == "archive_exists" and not c.passed for c in result.checks)

    def test_error_preflight_schema_mismatch(self, tmp_path):
        """Error: preflight fails with incompatible schema version."""
        sys.modules.setdefault("logging_utils", MagicMock())
        from services.backup_service import BackupService

        archive_path = self._create_valid_archive(tmp_path, schema_version="99.0")
        engine = MagicMock()
        svc = BackupService(engine=engine, audit_logger=MagicMock())

        with patch.object(svc, "_check_db_connectivity", return_value=True), \
             patch.object(svc, "_check_disk_space", return_value=(True, 999999999)):
            result = svc.preflight_restore(archive_path)

        assert result.passed is False
        schema_check = next(c for c in result.checks if c.name == "schema_version")
        assert schema_check.passed is False

    def test_error_preflight_db_unreachable(self, tmp_path):
        """Error: preflight fails when database is unreachable."""
        sys.modules.setdefault("logging_utils", MagicMock())
        from services.backup_service import BackupService

        archive_path = self._create_valid_archive(tmp_path)
        engine = MagicMock()
        svc = BackupService(engine=engine, audit_logger=MagicMock())

        with patch.object(svc, "_check_db_connectivity", return_value=False), \
             patch.object(svc, "_check_disk_space", return_value=(True, 999999999)):
            result = svc.preflight_restore(archive_path)

        assert result.passed is False
        db_check = next(c for c in result.checks if c.name == "database_connectivity")
        assert db_check.passed is False


# =============================================================================
# SUBSYSTEM 10: local_only_mode Enforcement
# =============================================================================


class TestLocalOnlyModeSubsystem:
    """local_only_mode enforcement: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Load models_router directly via importlib to avoid __init__.py chain."""
        import importlib.util
        _router_path = os.path.join(_project_root, "routers", "models_router.py")
        spec = importlib.util.spec_from_file_location(
            "routers.models_router_direct", _router_path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.models_mod = mod
        yield

    def test_nominal_local_only_filters_cloud_providers(self):
        """Nominal: local_only_mode=true filters out cloud providers."""
        from core.deps import UserContext

        configs = {"local_only_mode": "true"}
        with patch.object(self.models_mod, "get_all_configs", return_value=configs):
            user = UserContext(username="testuser", role="user")
            result = self.models_mod.get_model_options(user)

        provider_values = [p["value"] for p in result["providers"]]
        assert "ollama" in provider_values
        assert "openai" not in provider_values
        assert "anthropic" not in provider_values

    def test_error_local_only_ollama_unreachable_falls_to_default(self):
        """Error: in local_only_mode, unreachable Ollama falls to ampai_default."""
        configs = {
            "local_only_mode": "true",
            "ollama_base_url": "http://localhost:11434",
        }
        with patch.object(self.models_mod, "_timed_probe") as mock_probe:
            mock_probe.side_effect = Exception("Connection refused")
            result = self.models_mod.resolve_fallback_provider(configs)
        assert result == "ampai_default"


# =============================================================================
# SUBSYSTEM 11: Desktop Chat Payload Structure
# =============================================================================


class TestDesktopChatPayloadSubsystem:
    """Desktop chat payload structure: nominal and error paths."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        for mod in [
            "cryptography", "cryptography.fernet",
            "langchain_community", "langchain_community.chat_message_histories",
            "langchain_community.embeddings", "langchain_core",
            "langchain_core.documents", "langchain_postgres",
            "langchain_openai", "langchain_google_genai",
            "logging_utils",
        ]:
            sys.modules.setdefault(mod, MagicMock())
        yield

    def test_nominal_full_chat_request_payload(self):
        """Nominal: ChatRequest accepts all extended payload fields."""
        from core.models import ChatRequest, Attachment

        req = ChatRequest(
            session_id="sess-1",
            message="Hello",
            model_type="ollama",
            model_name="llama3",
            memory_mode="indexed",
            memory_top_k=5,
            memory_recency_bias=0.3,
            memory_category_filter="work",
            use_web_search=True,
            enable_browser_tools=True,
            enable_terminal_tools=True,
            chat_output_mode="compact",
            attachments=[
                Attachment(filename="f.pdf", url="/u/f.pdf", type="application/pdf")
            ],
        )
        assert req.session_id == "sess-1"
        assert req.enable_browser_tools is True
        assert req.enable_terminal_tools is True
        assert req.use_web_search is True
        assert len(req.attachments) == 1

    def test_error_missing_required_fields(self):
        """Error: ChatRequest without session_id or message raises ValidationError."""
        from core.models import ChatRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatRequest()  # Missing session_id and message
