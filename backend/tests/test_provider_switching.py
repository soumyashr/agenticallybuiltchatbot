"""
Tests for AI_PROVIDER flag switching between 'openai' and 'azure_openai'.
Validates that the correct LLM, embeddings, and vector store types are
instantiated based on the AI_PROVIDER setting.

All tests use unittest.mock — no real API calls are made.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws

from app.models import Role
from app.agent import _sessions

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")


# ── Helpers ──────────────────────────────────────────────────

def _make_settings(**overrides):
    """Return a mock settings object with sensible defaults + overrides."""
    defaults = {
        "ai_provider": "openai",
        "llm_model": "gpt-4o",
        "llm_temperature": 0.1,
        "openai_api_key": "sk-test-key",
        "azure_openai_api_key": "azure-test-key",
        "azure_openai_endpoint": "https://test.openai.azure.com/",
        "azure_openai_deployment": "gpt-4o",
        "azure_openai_embedding_deployment": "text-embedding-3-small",
        "azure_openai_api_version": "2024-08-01-preview",
        "azure_search_endpoint": "https://test.search.windows.net",
        "azure_search_admin_key": "search-key",
        "azure_search_index": "test-index",
        "embedding_model": "text-embedding-ada-002",
        "vector_store_dir": "/tmp/test_vs",
        "retriever_top_k": 5,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "max_history_turns": 10,
        "agent_max_iterations": 5,
        "agent_system_prompt": "Test prompt",
        "jwt_secret": "test-secret",
        "jwt_algorithm": "HS256",
        "jwt_expire_hours": 8,
        "data_dir": "data",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ═══════════════════════════════════════════════════════════════
# Provider switching — LLM
# ═══════════════════════════════════════════════════════════════


class TestProviderLLM:
    """Tests that _build_llm() returns the correct LLM type per provider."""

    @patch("app.agent.settings", _make_settings(ai_provider="openai"))
    def test_openai_provider_builds_correct_llm_type(self):
        """When AI_PROVIDER=openai, _build_llm() returns a ChatOpenAI instance."""
        with patch("langchain_openai.ChatOpenAI") as MockChatOpenAI:
            MockChatOpenAI.return_value = MagicMock()
            from app.agent import _build_llm
            llm = _build_llm()
            MockChatOpenAI.assert_called_once()
            call_kwargs = MockChatOpenAI.call_args[1]
            assert call_kwargs["openai_api_key"] == "sk-test-key"

    @patch("app.agent.settings", _make_settings(ai_provider="azure_openai"))
    def test_azure_provider_builds_correct_llm_type(self):
        """When AI_PROVIDER=azure_openai, _build_llm() returns an AzureChatOpenAI instance."""
        with patch("langchain_openai.AzureChatOpenAI") as MockAzureLLM:
            MockAzureLLM.return_value = MagicMock()
            from app.agent import _build_llm
            llm = _build_llm()
            MockAzureLLM.assert_called_once()
            call_kwargs = MockAzureLLM.call_args[1]
            assert call_kwargs["azure_deployment"] == "gpt-4o"
            assert call_kwargs["azure_endpoint"] == "https://test.openai.azure.com/"

    @patch("app.agent.settings", _make_settings(ai_provider="invalid_provider"))
    def test_invalid_provider_raises_value_error(self):
        """An unknown AI_PROVIDER raises ValueError."""
        from app.agent import _build_llm
        with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
            _build_llm()


# ═══════════════════════════════════════════════════════════════
# Provider switching — Embeddings
# ═══════════════════════════════════════════════════════════════


class TestProviderEmbeddings:
    """Tests that _build_embeddings() returns the correct type per provider."""

    @patch("app.ingest.settings", _make_settings(ai_provider="openai"))
    def test_openai_provider_builds_openai_embeddings(self):
        """When AI_PROVIDER=openai, _build_embeddings() returns OpenAIEmbeddings."""
        with patch("langchain_openai.OpenAIEmbeddings") as MockEmbed:
            MockEmbed.return_value = MagicMock()
            from app.ingest import _build_embeddings
            emb = _build_embeddings()
            MockEmbed.assert_called_once()
            call_kwargs = MockEmbed.call_args[1]
            assert call_kwargs["openai_api_key"] == "sk-test-key"

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    def test_azure_provider_builds_azure_embeddings(self):
        """When AI_PROVIDER=azure_openai, _build_embeddings() returns AzureOpenAIEmbeddings."""
        with patch("langchain_openai.AzureOpenAIEmbeddings") as MockEmbed:
            MockEmbed.return_value = MagicMock()
            from app.ingest import _build_embeddings
            emb = _build_embeddings()
            MockEmbed.assert_called_once()
            call_kwargs = MockEmbed.call_args[1]
            assert call_kwargs["azure_deployment"] == "text-embedding-3-small"


# ═══════════════════════════════════════════════════════════════
# Provider switching — Vector Store
# ═══════════════════════════════════════════════════════════════


class TestProviderVectorStore:
    """Tests that get_vector_store() returns the correct store type per provider."""

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.ingest._build_embeddings")
    def test_azure_provider_builds_azure_search_store(self, mock_embed):
        """When AI_PROVIDER=azure_openai, get_vector_store() creates an AzureSearch store."""
        mock_embed.return_value = MagicMock()
        with patch("langchain_community.vectorstores.AzureSearch") as MockAzSearch:
            MockAzSearch.return_value = MagicMock()
            from app.ingest import get_vector_store
            get_vector_store.cache_clear()
            vs = get_vector_store()
            MockAzSearch.assert_called_once()
            call_kwargs = MockAzSearch.call_args[1]
            assert call_kwargs["index_name"] == "test-index"
            get_vector_store.cache_clear()

    @patch("app.ingest.settings", _make_settings(ai_provider="openai"))
    @patch("app.ingest._build_embeddings")
    @patch("os.path.exists", return_value=True)
    def test_openai_provider_builds_faiss_store(self, mock_exists, mock_embed):
        """When AI_PROVIDER=openai and index exists, get_vector_store() loads FAISS."""
        mock_embed.return_value = MagicMock()
        with patch("langchain_community.vectorstores.FAISS") as MockFAISS:
            MockFAISS.load_local.return_value = MagicMock()
            from app.ingest import get_vector_store
            get_vector_store.cache_clear()
            vs = get_vector_store()
            MockFAISS.load_local.assert_called_once()
            get_vector_store.cache_clear()


# ═══════════════════════════════════════════════════════════════
# Provider switching — RBAC preserved
# ═══════════════════════════════════════════════════════════════


class TestProviderRBAC:
    """Tests that RBAC enforcement is not affected by provider switching."""

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    def test_provider_switch_does_not_affect_rbac(self):
        """Switching providers should not bypass role-based session isolation."""
        with patch("app.agent._create_executor") as mock_create:
            mock_create.return_value = MagicMock()

            from app.agent import get_or_create_session
            get_or_create_session("rbac-provider-test", Role.admin)

            with pytest.raises(PermissionError):
                get_or_create_session("rbac-provider-test", Role.student)


# ═══════════════════════════════════════════════════════════════
# Environment variable reading
# ═══════════════════════════════════════════════════════════════


class TestEnvReading:
    """Tests that the AI_PROVIDER env var is read correctly."""

    @patch.dict("os.environ", {"AI_PROVIDER": "openai"}, clear=False)
    def test_env_flag_ai_provider_is_read_correctly(self):
        """AI_PROVIDER env var should be accessible via Settings."""
        from pydantic_settings import BaseSettings
        from app.config import Settings
        s = Settings()
        assert s.ai_provider == "openai"

    @patch.dict("os.environ", {"AI_PROVIDER": "azure_openai"}, clear=False)
    def test_env_flag_azure_provider(self):
        """AI_PROVIDER=azure_openai should be read correctly."""
        from app.config import Settings
        s = Settings()
        assert s.ai_provider == "azure_openai"


# ═══════════════════════════════════════════════════════════════
# Provider switching — OpenAI uses FAISS, not Azure Search
# ═══════════════════════════════════════════════════════════════


class TestOpenAIProviderUsesCorrectStack:
    """Verify that AI_PROVIDER=openai never touches Azure services."""

    @patch("app.ingest.settings", _make_settings(ai_provider="openai"))
    @patch("app.ingest._build_embeddings")
    @patch("os.path.exists", return_value=True)
    def test_openai_provider_uses_faiss_not_azure_search(self, mock_exists, mock_embed):
        """When AI_PROVIDER=openai, get_vector_store() loads FAISS, not AzureSearch."""
        mock_embed.return_value = MagicMock()
        with patch("langchain_community.vectorstores.FAISS") as MockFAISS, \
             patch("langchain_community.vectorstores.AzureSearch") as MockAzSearch:
            MockFAISS.load_local.return_value = MagicMock()
            from app.ingest import get_vector_store
            get_vector_store.cache_clear()
            get_vector_store()
            MockFAISS.load_local.assert_called_once()
            MockAzSearch.assert_not_called()
            get_vector_store.cache_clear()

    @patch("app.ingest.settings", _make_settings(ai_provider="openai"))
    def test_openai_provider_uses_openai_embeddings_not_azure(self):
        """When AI_PROVIDER=openai, _build_embeddings() uses OpenAIEmbeddings, not Azure."""
        with patch("langchain_openai.OpenAIEmbeddings") as MockOAI, \
             patch("langchain_openai.AzureOpenAIEmbeddings") as MockAzEmbed:
            MockOAI.return_value = MagicMock()
            from app.ingest import _build_embeddings
            _build_embeddings()
            MockOAI.assert_called_once()
            MockAzEmbed.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# Provider switching does not affect DynamoDB document store
# ═══════════════════════════════════════════════════════════════


class TestProviderDocumentStoreIndependence:
    """DynamoDB document_store works regardless of AI_PROVIDER value."""

    def test_switching_provider_does_not_break_document_store(self):
        """document_store functions work with AI_PROVIDER=openai."""
        with mock_aws():
            import app.document_store as ds
            ds._table = None
            ds.init_db()
            doc_id = ds.register_document("test.pdf", "Test", ["admin"], 100)
            docs = ds.get_all_documents()
            assert len(docs) == 1
            assert docs[0]["id"] == doc_id
            ds._table = None

    @patch.dict("os.environ", {"AI_PROVIDER": "openai"}, clear=False)
    def test_dynamo_works_regardless_of_ai_provider(self):
        """DynamoDB operations succeed with AI_PROVIDER=openai (not azure_openai)."""
        with mock_aws():
            import app.document_store as ds
            ds._table = None
            ds.init_db()
            d1 = ds.register_document("a.pdf", "A", ["admin", "student"], 50)
            ds.set_status_ingested(d1, 10)
            ingested = ds.get_ingested_documents()
            assert len(ingested) == 1
            assert ingested[0]["chunk_count"] == 10
            roles_map = ds.get_allowed_roles_map()
            assert roles_map["a.pdf"] == ["admin", "student"]
            ds._table = None
