"""Tests for routers/models_router.py.

Validates the GET /api/models/options, GET /api/models/health endpoints,
and the resolve_fallback_provider logic.
"""

from unittest.mock import patch, MagicMock
import urllib.error

import pytest

from routers.models_router import (
    FALLBACK_CHAIN,
    _PROVIDER_KEY_MAP,
    _LOCAL_PROBE_TIMEOUT,
    _check_provider_health,
    resolve_fallback_provider,
    get_model_options,
    get_model_health,
)


class TestFallbackChain:
    """Tests for the fallback chain constant and ordering."""

    def test_fallback_chain_order(self):
        assert FALLBACK_CHAIN == [
            "ollama", "openrouter", "openai", "gemini", "anthropic", "generic", "ampai_default"
        ]

    def test_provider_key_map_contains_cloud_providers(self):
        assert "openrouter" in _PROVIDER_KEY_MAP
        assert "openai" in _PROVIDER_KEY_MAP
        assert "gemini" in _PROVIDER_KEY_MAP
        assert "anthropic" in _PROVIDER_KEY_MAP

    def test_local_probe_timeout_is_8_seconds(self):
        assert _LOCAL_PROBE_TIMEOUT == 8


class TestCheckProviderHealth:
    """Tests for _check_provider_health function."""

    def test_ollama_reachable(self):
        configs = {"ollama_base_url": "http://localhost:11434"}
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.return_value = {"ok": True, "latency_ms": 42.5, "status_code": 200}
            result = _check_provider_health("ollama", configs)
        assert result["name"] == "ollama"
        assert result["ok"] is True
        assert result["latency_ms"] == 42.5

    def test_ollama_unreachable(self):
        configs = {"ollama_base_url": "http://localhost:11434"}
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.side_effect = Exception("Connection refused")
            result = _check_provider_health("ollama", configs)
        assert result["name"] == "ollama"
        assert result["ok"] is False

    def test_openrouter_reachable(self):
        configs = {"openrouter_api_key": "test-key-123"}
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.return_value = {"ok": True, "latency_ms": 150.0, "status_code": 200}
            result = _check_provider_health("openrouter", configs)
        assert result["name"] == "openrouter"
        assert result["ok"] is True

    def test_generic_without_base_url(self):
        configs = {}
        result = _check_provider_health("generic", configs)
        assert result["name"] == "generic"
        assert result["ok"] is False
        assert result["reason"] == "base_url_not_configured"

    def test_ampai_default_always_ok(self):
        result = _check_provider_health("ampai_default", {})
        assert result["name"] == "ampai_default"
        assert result["ok"] is True
        assert result["latency_ms"] == 0

    def test_unknown_provider(self):
        result = _check_provider_health("unknown_provider", {})
        assert result["name"] == "unknown_provider"
        assert result["ok"] is False


class TestResolveFallbackProvider:
    """Tests for resolve_fallback_provider function."""

    def test_local_only_mode_ollama_reachable(self):
        configs = {"local_only_mode": "true", "ollama_base_url": "http://localhost:11434"}
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.return_value = {"ok": True, "latency_ms": 50.0, "status_code": 200}
            result = resolve_fallback_provider(configs)
        assert result == "ollama"

    def test_local_only_mode_ollama_unreachable_falls_to_ampai_default(self):
        configs = {"local_only_mode": "true", "ollama_base_url": "http://localhost:11434"}
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.side_effect = Exception("Connection refused")
            result = resolve_fallback_provider(configs)
        assert result == "ampai_default"

    def test_cloud_mode_skips_providers_without_keys(self):
        configs = {
            "local_only_mode": "false",
            "ollama_base_url": "http://localhost:11434",
            # No API keys configured for cloud providers
        }
        with patch("routers.models_router._timed_probe") as mock_probe:
            # Ollama unreachable
            mock_probe.side_effect = Exception("Connection refused")
            result = resolve_fallback_provider(configs)
        # Should fall through to ampai_default since no cloud keys are set
        assert result == "ampai_default"

    def test_cloud_mode_uses_first_reachable_provider(self):
        configs = {
            "local_only_mode": "false",
            "ollama_base_url": "http://localhost:11434",
            "openrouter_api_key": "test-key",
        }
        with patch("routers.models_router._timed_probe") as mock_probe:
            def side_effect(url, **kwargs):
                if "ollama" in url or "11434" in url:
                    raise Exception("Connection refused")
                return {"ok": True, "latency_ms": 100.0, "status_code": 200}
            mock_probe.side_effect = side_effect
            result = resolve_fallback_provider(configs)
        assert result == "openrouter"

    def test_cloud_mode_ollama_reachable_returns_ollama(self):
        configs = {
            "local_only_mode": "false",
            "ollama_base_url": "http://localhost:11434",
            "openai_api_key": "sk-test",
        }
        with patch("routers.models_router._timed_probe") as mock_probe:
            mock_probe.return_value = {"ok": True, "latency_ms": 30.0, "status_code": 200}
            result = resolve_fallback_provider(configs)
        assert result == "ollama"


class TestGetModelHealth:
    """Tests for the GET /api/models/health endpoint logic."""

    def test_local_only_mode_returns_only_ollama_and_ampai_default(self):
        configs = {"local_only_mode": "true", "ollama_base_url": "http://localhost:11434"}
        with patch("routers.models_router.get_all_configs", return_value=configs):
            with patch("routers.models_router._timed_probe") as mock_probe:
                mock_probe.return_value = {"ok": True, "latency_ms": 25.0, "status_code": 200}
                from core.deps import UserContext
                user = UserContext(username="testuser", role="user")
                result = get_model_health(user)
        provider_names = [p["name"] for p in result["providers"]]
        assert "ollama" in provider_names
        assert "ampai_default" in provider_names
        # Cloud providers should not be present
        assert "openrouter" not in provider_names
        assert "openai" not in provider_names

    def test_cloud_mode_includes_all_providers(self):
        configs = {
            "local_only_mode": "false",
            "ollama_base_url": "http://localhost:11434",
            "openrouter_api_key": "key1",
            "openai_api_key": "key2",
            "gemini_api_key": "key3",
            "anthropic_api_key": "key4",
            "generic_base_url": "http://localhost:1234",
        }
        with patch("routers.models_router.get_all_configs", return_value=configs):
            with patch("routers.models_router._check_provider_health") as mock_health:
                mock_health.return_value = {"name": "test", "ok": True, "latency_ms": 50.0}
                from core.deps import UserContext
                user = UserContext(username="testuser", role="user")
                result = get_model_health(user)
        # All providers in the chain should be checked
        assert len(result["providers"]) == len(FALLBACK_CHAIN)

    def test_cloud_providers_without_keys_show_not_configured(self):
        configs = {
            "local_only_mode": "false",
            "ollama_base_url": "http://localhost:11434",
            # No API keys
        }
        with patch("routers.models_router.get_all_configs", return_value=configs):
            with patch("routers.models_router._timed_probe") as mock_probe:
                mock_probe.return_value = {"ok": True, "latency_ms": 25.0, "status_code": 200}
                from core.deps import UserContext
                user = UserContext(username="testuser", role="user")
                result = get_model_health(user)
        # Cloud providers without keys should show reason
        for p in result["providers"]:
            if p["name"] in _PROVIDER_KEY_MAP:
                assert p["ok"] is False
                assert p.get("reason") == "api_key_not_configured"


class TestGetModelOptions:
    """Tests for the GET /api/models/options endpoint logic."""

    def test_local_only_mode_filters_cloud_providers(self):
        configs = {"local_only_mode": "true"}
        with patch("routers.models_router.get_all_configs", return_value=configs):
            from core.deps import UserContext
            user = UserContext(username="testuser", role="user")
            result = get_model_options(user)
        provider_values = [p["value"] for p in result["providers"]]
        assert "ollama" in provider_values
        assert "generic" in provider_values
        assert "anythingllm" in provider_values
        assert "openai" not in provider_values
        assert "anthropic" not in provider_values

    def test_cloud_mode_includes_all_providers(self):
        configs = {"local_only_mode": "false"}
        with patch("routers.models_router.get_all_configs", return_value=configs):
            from core.deps import UserContext
            user = UserContext(username="testuser", role="user")
            result = get_model_options(user)
        provider_values = [p["value"] for p in result["providers"]]
        assert "ollama" in provider_values
        assert "openai" in provider_values
        assert "anthropic" in provider_values
        assert "openrouter" in provider_values
