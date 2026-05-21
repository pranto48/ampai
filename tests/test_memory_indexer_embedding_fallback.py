"""Tests for local embedding fallback in memory_indexer.

Validates Requirements 6.7 and 6.8:
- 6.7: If no cloud embedding API key configured and Ollama reachable, use nomic-embed-text via Ollama
- 6.8: If no cloud embedding API key and Ollama unreachable, report error and disable vector retrieval
"""

import importlib
import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level setup: load memory_indexer from the real source file with
# properly mocked dependencies, regardless of test execution order.
# ---------------------------------------------------------------------------

def _load_memory_indexer_module():
    """Load memory_indexer from source with controlled mocks.
    Returns the module object which we use for all function calls.
    """
    # Mock heavy dependencies
    modules_to_mock = [
        "langchain_core", "langchain_core.documents",
        "langchain_postgres", "langchain_openai", "langchain_google_genai",
        "langchain_community", "langchain_community.embeddings",
        "cryptography", "cryptography.fernet",
    ]
    for mod in modules_to_mock:
        sys.modules[mod] = MagicMock()

    # Set up database mock
    mock_database = MagicMock()
    mock_database.DATABASE_URL = "postgresql://test:test@localhost/test"
    mock_database.engine = MagicMock()
    mock_database.get_config = MagicMock(return_value=None)
    sys.modules["database"] = mock_database

    # Set up memory_persistence mock
    mock_persistence = MagicMock()
    mock_persistence.memory_persistence_manager = MagicMock()
    sys.modules["memory_persistence"] = mock_persistence

    # Remove cached memory_indexer to force fresh import
    sys.modules.pop("memory_indexer", None)

    # Load from the actual file
    module_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "memory_indexer.py",
    )
    spec = importlib.util.spec_from_file_location("memory_indexer", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_indexer"] = module
    spec.loader.exec_module(module)
    return module


# Load the module once at import time
_mi = _load_memory_indexer_module()


class TestHasCloudEmbeddingKey:
    """Tests for _has_cloud_embedding_key helper."""

    def test_no_keys_configured(self):
        with patch.object(_mi, "get_config", return_value=None):
            with patch.dict("os.environ", {}, clear=True):
                assert _mi._has_cloud_embedding_key() is False

    def test_openai_key_from_config(self):
        def mock_get_config(key, *args, **kwargs):
            if key == "openai_api_key":
                return "sk-test-key"
            return None

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                assert _mi._has_cloud_embedding_key() is True

    def test_gemini_key_from_env(self):
        with patch.object(_mi, "get_config", return_value=None):
            with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-gemini-key"}, clear=True):
                assert _mi._has_cloud_embedding_key() is True

    def test_openai_key_from_env(self):
        with patch.object(_mi, "get_config", return_value=None):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}, clear=True):
                assert _mi._has_cloud_embedding_key() is True


class TestIsOllamaReachable:
    """Tests for _is_ollama_reachable helper."""

    def test_ollama_reachable(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            assert _mi._is_ollama_reachable("http://localhost:11434") is True

    def test_ollama_unreachable(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")
            assert _mi._is_ollama_reachable("http://localhost:11434") is False

    def test_ollama_timeout(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Timed out")
            assert _mi._is_ollama_reachable("http://localhost:11434") is False


class TestFallbackToLocalEmbedding:
    """Tests for _fallback_to_local_embedding function."""

    def test_ollama_reachable_returns_ollama_embeddings(self):
        """Requirement 6.7: Use nomic-embed-text via Ollama when reachable."""
        mock_ollama_cls = MagicMock()
        mock_ollama_instance = MagicMock()
        mock_ollama_cls.return_value = mock_ollama_instance

        mock_lc_embeddings = MagicMock()
        mock_lc_embeddings.OllamaEmbeddings = mock_ollama_cls

        with patch.object(_mi, "_get_ollama_base_url", return_value="http://localhost:11434"):
            with patch.object(_mi, "_is_ollama_reachable", return_value=True):
                with patch.dict(sys.modules, {"langchain_community.embeddings": mock_lc_embeddings}):
                    result = _mi._fallback_to_local_embedding()
                    mock_ollama_cls.assert_called_once_with(
                        model="nomic-embed-text",
                        base_url="http://localhost:11434",
                    )
                    assert result == mock_ollama_instance

    def test_ollama_unreachable_raises_error(self):
        """Requirement 6.8: Raise error when no provider available."""
        with patch.object(_mi, "_get_ollama_base_url", return_value="http://localhost:11434"):
            with patch.object(_mi, "_is_ollama_reachable", return_value=False):
                with pytest.raises(_mi.EmbeddingUnavailableError) as exc_info:
                    _mi._fallback_to_local_embedding()
                assert "No embedding provider available" in str(exc_info.value)
                assert "Ollama is unreachable" in str(exc_info.value)
                assert "Vector-based memory retrieval is disabled" in str(exc_info.value)


class TestGetEmbeddingModelFallback:
    """Tests for get_embedding_model with local embedding fallback."""

    def test_openai_provider_no_key_falls_back_to_ollama(self):
        """Requirement 6.7: OpenAI provider without key falls back to Ollama."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "openai",
                "memory_embedding_model": "",
                "openai_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        mock_ollama_cls = MagicMock(return_value=MagicMock())
        mock_lc_embeddings = MagicMock()
        mock_lc_embeddings.OllamaEmbeddings = mock_ollama_cls

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=True):
                    with patch.dict(sys.modules, {"langchain_community.embeddings": mock_lc_embeddings}):
                        result = _mi.get_embedding_model("openai")
                        mock_ollama_cls.assert_called_once_with(
                            model="nomic-embed-text",
                            base_url="http://localhost:11434",
                        )

    def test_openai_provider_no_key_ollama_unreachable_raises(self):
        """Requirement 6.8: OpenAI provider without key and Ollama unreachable raises error."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "openai",
                "memory_embedding_model": "",
                "openai_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=False):
                    with pytest.raises(_mi.EmbeddingUnavailableError):
                        _mi.get_embedding_model("openai")

    def test_gemini_provider_no_key_falls_back_to_ollama(self):
        """Requirement 6.7: Gemini provider without key falls back to Ollama."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "gemini",
                "memory_embedding_model": "",
                "gemini_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        mock_ollama_cls = MagicMock(return_value=MagicMock())
        mock_lc_embeddings = MagicMock()
        mock_lc_embeddings.OllamaEmbeddings = mock_ollama_cls

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=True):
                    with patch.dict(sys.modules, {"langchain_community.embeddings": mock_lc_embeddings}):
                        result = _mi.get_embedding_model("gemini")
                        mock_ollama_cls.assert_called_once_with(
                            model="nomic-embed-text",
                            base_url="http://localhost:11434",
                        )

    def test_gemini_provider_no_key_ollama_unreachable_raises(self):
        """Requirement 6.8: Gemini provider without key and Ollama unreachable raises error."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "gemini",
                "memory_embedding_model": "",
                "gemini_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=False):
                    with pytest.raises(_mi.EmbeddingUnavailableError):
                        _mi.get_embedding_model("gemini")

    def test_openrouter_provider_no_cloud_keys_falls_back_to_ollama(self):
        """Requirement 6.7: OpenRouter provider without any cloud key falls back to Ollama."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "openrouter",
                "memory_embedding_model": "",
                "openai_api_key": None,
                "gemini_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        mock_ollama_cls = MagicMock(return_value=MagicMock())
        mock_lc_embeddings = MagicMock()
        mock_lc_embeddings.OllamaEmbeddings = mock_ollama_cls

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=True):
                    with patch.dict(sys.modules, {"langchain_community.embeddings": mock_lc_embeddings}):
                        result = _mi.get_embedding_model("openrouter")
                        mock_ollama_cls.assert_called_once_with(
                            model="nomic-embed-text",
                            base_url="http://localhost:11434",
                        )

    def test_openrouter_provider_no_cloud_keys_ollama_unreachable_raises(self):
        """Requirement 6.8: OpenRouter without cloud keys and Ollama unreachable raises error."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "openrouter",
                "memory_embedding_model": "",
                "openai_api_key": None,
                "gemini_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=False):
                    with pytest.raises(_mi.EmbeddingUnavailableError):
                        _mi.get_embedding_model("openrouter")

    def test_ollama_provider_unreachable_no_cloud_key_raises(self):
        """Requirement 6.8: Ollama provider unreachable with no cloud key raises error."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "",
                "memory_embedding_model": "",
                "openai_api_key": None,
                "gemini_api_key": None,
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=False):
                    with patch.object(_mi, "_has_cloud_embedding_key", return_value=False):
                        with pytest.raises(_mi.EmbeddingUnavailableError):
                            _mi.get_embedding_model("ollama")

    def test_ollama_provider_reachable_uses_nomic_embed_text(self):
        """Requirement 6.7: Default Ollama provider uses nomic-embed-text."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "",
                "memory_embedding_model": "",
                "ollama_base_url": "http://localhost:11434",
            }
            return config_map.get(key)

        mock_ollama_cls = MagicMock(return_value=MagicMock())
        mock_lc_embeddings = MagicMock()
        mock_lc_embeddings.OllamaEmbeddings = mock_ollama_cls

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.object(_mi, "_is_ollama_reachable", return_value=True):
                    with patch.object(_mi, "_has_cloud_embedding_key", return_value=False):
                        with patch.dict(sys.modules, {"langchain_community.embeddings": mock_lc_embeddings}):
                            result = _mi.get_embedding_model("ollama")
                            mock_ollama_cls.assert_called_once_with(
                                model="nomic-embed-text",
                                base_url="http://localhost:11434",
                            )

    def test_openai_provider_with_key_uses_openai(self):
        """When OpenAI key is available, use OpenAI embeddings (no fallback needed)."""
        def mock_get_config(key, *args, **kwargs):
            config_map = {
                "memory_embedding_provider": "openai",
                "memory_embedding_model": "",
                "openai_api_key": "sk-real-key",
            }
            return config_map.get(key)

        mock_openai_cls = MagicMock(return_value=MagicMock())
        mock_lc_openai = MagicMock()
        mock_lc_openai.OpenAIEmbeddings = mock_openai_cls

        with patch.object(_mi, "get_config", side_effect=mock_get_config):
            with patch.dict("os.environ", {}, clear=True):
                with patch.dict(sys.modules, {"langchain_openai": mock_lc_openai}):
                    result = _mi.get_embedding_model("openai")
                    mock_openai_cls.assert_called_once_with(
                        model="text-embedding-3-small",
                        api_key="sk-real-key",
                    )


class TestMemoryIndexerDisabledState:
    """Tests for MemoryIndexer handling of EmbeddingUnavailableError."""

    def test_indexer_disabled_when_no_provider_available(self):
        """Requirement 6.8: MemoryIndexer disables vector retrieval when no provider available."""
        with patch.object(_mi, "get_embedding_model") as mock_get_model:
            mock_get_model.side_effect = _mi.EmbeddingUnavailableError(
                "No embedding provider available. Vector-based memory retrieval is disabled."
            )
            indexer = _mi.MemoryIndexer(model_type="ollama")
            assert indexer.enabled is False
            assert indexer.disabled_reason is not None
            assert "Vector-based memory retrieval is disabled" in indexer.disabled_reason

    def test_indexer_search_returns_empty_when_disabled(self):
        """Requirement 6.8: Disabled indexer returns empty results for search."""
        with patch.object(_mi, "get_embedding_model") as mock_get_model:
            mock_get_model.side_effect = _mi.EmbeddingUnavailableError(
                "No embedding provider available"
            )
            indexer = _mi.MemoryIndexer(model_type="ollama")
            results = indexer.search_facts("test query")
            assert results == []

    def test_indexer_add_fact_noop_when_disabled(self):
        """Requirement 6.8: Disabled indexer does nothing on add_fact."""
        with patch.object(_mi, "get_embedding_model") as mock_get_model:
            mock_get_model.side_effect = _mi.EmbeddingUnavailableError(
                "No embedding provider available"
            )
            indexer = _mi.MemoryIndexer(model_type="ollama")
            # Should not raise
            indexer.add_fact("some fact")

    def test_indexer_enabled_when_embedding_model_available(self):
        """Requirement 6.7: MemoryIndexer is enabled when embedding model is available."""
        mock_embedding = MagicMock()
        mock_pgvector = MagicMock()

        with patch.object(_mi, "get_embedding_model", return_value=mock_embedding):
            with patch.object(_mi, "PGVector", return_value=mock_pgvector):
                indexer = _mi.MemoryIndexer(model_type="ollama")
                assert indexer.enabled is True
                assert indexer.disabled_reason is None

    def test_indexer_disabled_reason_set_on_general_error(self):
        """MemoryIndexer sets disabled_reason on general initialization errors."""
        mock_embedding = MagicMock()

        with patch.object(_mi, "get_embedding_model", return_value=mock_embedding):
            with patch.object(_mi, "PGVector") as MockPGVector:
                MockPGVector.side_effect = RuntimeError("DB connection failed")
                indexer = _mi.MemoryIndexer(model_type="ollama")
                assert indexer.enabled is False
                assert "PGVector initialization failed" in indexer.disabled_reason
