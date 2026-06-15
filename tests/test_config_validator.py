"""Tests for config_validator module.

Validates unsafe default detection, production vs non-production behavior,
and case-insensitive environment detection.
"""

import logging
import os
from unittest.mock import patch

import pytest

from config_validator import UNSAFE_DEFAULTS, _is_production, validate_config


class TestIsProduction:
    """Tests for production mode detection from AMPAI_ENV."""

    def test_production_lowercase(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "production"}):
            assert _is_production() is True

    def test_prod_lowercase(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "prod"}):
            assert _is_production() is True

    def test_production_uppercase(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "PRODUCTION"}):
            assert _is_production() is True

    def test_prod_uppercase(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "PROD"}):
            assert _is_production() is True

    def test_production_mixed_case(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "Production"}):
            assert _is_production() is True

    def test_prod_mixed_case(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "Prod"}):
            assert _is_production() is True

    def test_development_is_not_production(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "development"}):
            assert _is_production() is False

    def test_staging_is_not_production(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "staging"}):
            assert _is_production() is False

    def test_empty_string_is_not_production(self):
        with patch.dict(os.environ, {"AMPAI_ENV": ""}):
            assert _is_production() is False

    def test_unset_is_not_production(self):
        env = os.environ.copy()
        env.pop("AMPAI_ENV", None)
        with patch.dict(os.environ, env, clear=True):
            assert _is_production() is False

    def test_whitespace_trimmed(self):
        with patch.dict(os.environ, {"AMPAI_ENV": "  production  "}):
            assert _is_production() is True


class TestValidateConfigProduction:
    """Tests for validate_config in production mode."""

    def test_exits_with_unsafe_jwt_secret(self):
        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "change-me",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "safe-password-123",
            "POSTGRES_PASSWORD": "safe-pg-pass",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()
            assert exc_info.value.code == 1

    def test_exits_with_unsafe_admin_password(self):
        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "a-real-secret-key-here",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "P@ssw0rd",
            "POSTGRES_PASSWORD": "safe-pg-pass",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()
            assert exc_info.value.code == 1

    def test_exits_with_unsafe_postgres_password(self):
        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "a-real-secret-key-here",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "safe-password-123",
            "POSTGRES_PASSWORD": "ampai",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()
            assert exc_info.value.code == 1

    def test_exits_with_multiple_unsafe_defaults(self):
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

    def test_logs_errors_for_each_unsafe_default(self, caplog):
        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "change-me",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "P@ssw0rd",
            "POSTGRES_PASSWORD": "safe-pg-pass",
        }
        with patch.dict(os.environ, env, clear=True):
            with caplog.at_level(logging.ERROR, logger="ampai.config_validator"):
                with pytest.raises(SystemExit):
                    validate_config()
            assert "JWT_SECRET" in caplog.text
            assert "AMPAI_DEFAULT_ADMIN_PASSWORD" in caplog.text
            assert "STARTUP BLOCKED" in caplog.text

    def test_passes_with_safe_values(self):
        env = {
            "AMPAI_ENV": "production",
            "JWT_SECRET": "my-super-secret-production-key-2024",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "Str0ng!Pr0duction#Pass",
            "POSTGRES_PASSWORD": "pg-production-secret-42",
        }
        with patch.dict(os.environ, env, clear=True):
            # Should not raise
            validate_config()

    def test_passes_when_vars_unset_in_production(self):
        """Unset variables have empty string value, which is not in unsafe defaults."""
        env = {"AMPAI_ENV": "production"}
        with patch.dict(os.environ, env, clear=True):
            # Should not raise - empty string is not in UNSAFE_DEFAULTS
            validate_config()


class TestValidateConfigNonProduction:
    """Tests for validate_config in non-production mode."""

    def test_allows_startup_with_unsafe_defaults(self):
        env = {
            "AMPAI_ENV": "development",
            "JWT_SECRET": "change-me",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "P@ssw0rd",
            "POSTGRES_PASSWORD": "ampai",
        }
        with patch.dict(os.environ, env, clear=True):
            # Should not raise
            validate_config()

    def test_logs_warnings_for_unsafe_defaults(self, caplog):
        env = {
            "AMPAI_ENV": "development",
            "JWT_SECRET": "change-me",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "P@ssw0rd",
            "POSTGRES_PASSWORD": "ampai",
        }
        with patch.dict(os.environ, env, clear=True):
            with caplog.at_level(logging.WARNING, logger="ampai.config_validator"):
                validate_config()
            assert "JWT_SECRET" in caplog.text
            assert "AMPAI_DEFAULT_ADMIN_PASSWORD" in caplog.text
            assert "POSTGRES_PASSWORD" in caplog.text
            assert "ok for dev" in caplog.text

    def test_no_warnings_with_safe_values(self, caplog):
        env = {
            "AMPAI_ENV": "development",
            "JWT_SECRET": "my-dev-secret",
            "AMPAI_DEFAULT_ADMIN_PASSWORD": "my-dev-password",
            "POSTGRES_PASSWORD": "my-dev-pg-pass",
        }
        with patch.dict(os.environ, env, clear=True):
            with caplog.at_level(logging.WARNING, logger="ampai.config_validator"):
                validate_config()
            assert caplog.text == ""


class TestUnsafeDefaultsDict:
    """Tests for the UNSAFE_DEFAULTS constant."""

    def test_contains_jwt_secret(self):
        assert "JWT_SECRET" in UNSAFE_DEFAULTS
        assert "change-me" in UNSAFE_DEFAULTS["JWT_SECRET"]
        assert "change-me-for-production" in UNSAFE_DEFAULTS["JWT_SECRET"]

    def test_contains_admin_password(self):
        assert "AMPAI_DEFAULT_ADMIN_PASSWORD" in UNSAFE_DEFAULTS
        assert "P@ssw0rd" in UNSAFE_DEFAULTS["AMPAI_DEFAULT_ADMIN_PASSWORD"]
        assert "change-this" in UNSAFE_DEFAULTS["AMPAI_DEFAULT_ADMIN_PASSWORD"]

    def test_contains_postgres_password(self):
        assert "POSTGRES_PASSWORD" in UNSAFE_DEFAULTS
        assert "change-this" in UNSAFE_DEFAULTS["POSTGRES_PASSWORD"]
        assert "ampai" in UNSAFE_DEFAULTS["POSTGRES_PASSWORD"]


class TestValidateConfigIntegration:
    """Tests that validate_config is integrated into main.py startup sequence."""

    def test_validate_config_called_before_app_creation_in_main(self):
        """Verify that main.py calls validate_config() before creating the FastAPI app.

        This ensures no requests are served while configuration is unsafe (Req 2.6).
        """
        from pathlib import Path

        main_py = Path(__file__).resolve().parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")

        # Find positions of validate_config() call and app = FastAPI()
        validate_pos = source.find("validate_config()")
        app_pos = source.find("app = FastAPI()")

        assert validate_pos != -1, "validate_config() call not found in main.py"
        assert app_pos != -1, "app = FastAPI() not found in main.py"
        assert validate_pos < app_pos, (
            "validate_config() must be called before app = FastAPI() "
            "to ensure no requests are served while configuration is unsafe"
        )

    def test_validate_config_import_present_in_main(self):
        """Verify that main.py imports validate_config from config_validator."""
        from pathlib import Path

        main_py = Path(__file__).resolve().parent.parent / "main.py"
        source = main_py.read_text(encoding="utf-8")

        assert "from config_validator import validate_config" in source, (
            "main.py must import validate_config from config_validator"
        )

