"""
Tests for Azure-specific integration: AzureChatOpenAI config, AzureOpenAIEmbeddings
config, Azure AI Search config, RBAC filtering, and ingest pipeline.

All tests use unittest.mock — no real API calls are made.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, call


# ── Helpers ──────────────────────────────────────────────────

def _make_settings(**overrides):
    """Return a mock settings object with Azure defaults + overrides."""
    defaults = {
        "ai_provider": "azure_openai",
        "llm_model": "gpt-4o",
        "llm_temperature": 0.1,
        "openai_api_key": "sk-test-key",
        "azure_openai_api_key": "azure-test-key",
        "azure_openai_endpoint": "https://test.openai.azure.com/",
        "azure_openai_deployment": "gpt-4o",
        "azure_openai_embedding_deployment": "text-embedding-3-small",
        "azure_openai_api_version": "2024-08-01-preview",
        "azure_search_endpoint": "https://test.search.windows.net",
        "azure_search_admin_key": "search-admin-key",
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
# Azure LLM Configuration
# ═══════════════════════════════════════════════════════════════


class TestAzureLLMConfig:
    """Tests that Azure LLM configuration contains required fields."""

    @patch("app.agent.settings", _make_settings(ai_provider="azure_openai"))
    def test_azure_llm_config_has_required_fields(self):
        """AzureChatOpenAI should receive deployment, endpoint, api_key, api_version."""
        with patch("langchain_openai.AzureChatOpenAI") as MockLLM:
            MockLLM.return_value = MagicMock()
            from app.agent import _build_llm
            _build_llm()
            call_kwargs = MockLLM.call_args[1]
            assert "azure_deployment" in call_kwargs
            assert "azure_endpoint" in call_kwargs
            assert "api_key" in call_kwargs
            assert "api_version" in call_kwargs
            assert call_kwargs["azure_deployment"] == "gpt-4o"
            assert call_kwargs["api_version"] == "2024-08-01-preview"


# ═══════════════════════════════════════════════════════════════
# Azure Embeddings Configuration
# ═══════════════════════════════════════════════════════════════


class TestAzureEmbeddingsConfig:
    """Tests that Azure Embeddings configuration contains required fields."""

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    def test_azure_embeddings_config_has_required_fields(self):
        """AzureOpenAIEmbeddings should receive deployment, endpoint, api_key, api_version."""
        with patch("langchain_openai.AzureOpenAIEmbeddings") as MockEmbed:
            MockEmbed.return_value = MagicMock()
            from app.ingest import _build_embeddings
            _build_embeddings()
            call_kwargs = MockEmbed.call_args[1]
            assert "azure_deployment" in call_kwargs
            assert "azure_endpoint" in call_kwargs
            assert "api_key" in call_kwargs
            assert "api_version" in call_kwargs
            assert call_kwargs["azure_deployment"] == "text-embedding-3-small"


# ═══════════════════════════════════════════════════════════════
# Azure AI Search Configuration
# ═══════════════════════════════════════════════════════════════


class TestAzureSearchConfig:
    """Tests that Azure AI Search configuration contains required fields."""

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.ingest._build_embeddings")
    def test_azure_search_config_has_required_fields(self, mock_embed):
        """AzureSearch should receive endpoint, key, and index_name."""
        mock_embed_instance = MagicMock()
        mock_embed.return_value = mock_embed_instance
        with patch("langchain_community.vectorstores.AzureSearch") as MockSearch:
            MockSearch.return_value = MagicMock()
            from app.ingest import get_vector_store
            get_vector_store.cache_clear()
            get_vector_store()
            call_kwargs = MockSearch.call_args[1]
            assert "azure_search_endpoint" in call_kwargs
            assert "azure_search_key" in call_kwargs
            assert "index_name" in call_kwargs
            assert call_kwargs["index_name"] == "test-index"
            get_vector_store.cache_clear()


# ═══════════════════════════════════════════════════════════════
# Azure Search RBAC Filtering
# ═══════════════════════════════════════════════════════════════


class TestAzureSearchRBAC:
    """Tests that Azure AI Search applies RBAC filters correctly."""

    @patch("app.tools.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.tools.get_vector_store")
    def test_azure_search_rbac_filter_applied_correctly(self, mock_vs):
        """Azure Search should use OData filter for role-based access."""
        mock_store = MagicMock()
        mock_doc = MagicMock()
        mock_doc.metadata = {"source": "test.pdf", "page": 1, "allowed_roles": ["student"]}
        mock_doc.page_content = "Test content"
        mock_store.similarity_search.return_value = [mock_doc]
        mock_vs.return_value = mock_store

        from app.tools import make_search_tools
        tools = make_search_tools("student")
        result = tools[0].func("test query")

        # Verify the OData filter was passed
        mock_store.similarity_search.assert_called_once()
        call_kwargs = mock_store.similarity_search.call_args[1]
        assert "filters" in call_kwargs
        assert "student" in call_kwargs["filters"]
        assert "allowed_roles" in call_kwargs["filters"]

    @patch("app.tools.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.tools.get_vector_store")
    def test_azure_search_returns_role_filtered_results(self, mock_vs):
        """Azure Search results should be returned directly (filtering is server-side)."""
        mock_store = MagicMock()
        mock_doc = MagicMock()
        mock_doc.metadata = {"source": "admin_doc.pdf", "page": 5, "allowed_roles": ["admin"]}
        mock_doc.page_content = "Admin-only content"
        mock_store.similarity_search.return_value = [mock_doc]
        mock_vs.return_value = mock_store

        from app.tools import make_search_tools
        tools = make_search_tools("admin")
        result = tools[0].func("admin query")

        assert "admin_doc.pdf" in result
        assert "Admin-only content" in result


# ═══════════════════════════════════════════════════════════════
# Azure Ingest Pipeline
# ═══════════════════════════════════════════════════════════════


class TestAzureIngest:
    """Tests for the Azure AI Search ingest pipeline."""

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.ingest._build_embeddings")
    def test_azure_ingest_creates_index_if_not_exists(self, mock_embed):
        """_push_to_azure_search should create the index via create_or_update_index."""
        mock_embed_instance = MagicMock()
        mock_embed_instance.embed_query.return_value = [0.1] * 1536
        mock_embed.return_value = mock_embed_instance

        mock_chunk = MagicMock()
        mock_chunk.page_content = "Test content"
        mock_chunk.metadata = {"source": "test.pdf", "page": 1, "allowed_roles": ["admin"]}

        mock_index_client = MagicMock()
        mock_search_client = MagicMock()

        with patch("azure.search.documents.indexes.SearchIndexClient", return_value=mock_index_client), \
             patch("azure.search.documents.SearchClient", return_value=mock_search_client), \
             patch("azure.core.credentials.AzureKeyCredential"):

            from app.ingest import _push_to_azure_search
            _push_to_azure_search([mock_chunk], mock_embed_instance)

            mock_index_client.create_or_update_index.assert_called_once()

    @patch("app.ingest.settings", _make_settings(ai_provider="azure_openai"))
    @patch("app.ingest._build_embeddings")
    def test_azure_ingest_upserts_documents(self, mock_embed):
        """_push_to_azure_search should call upload_documents with chunk data."""
        mock_embed_instance = MagicMock()
        mock_embed_instance.embed_query.return_value = [0.1] * 1536
        mock_embed.return_value = mock_embed_instance

        chunks = []
        for i in range(3):
            mock_chunk = MagicMock()
            mock_chunk.page_content = f"Content {i}"
            mock_chunk.metadata = {"source": "test.pdf", "page": i, "allowed_roles": ["admin", "faculty"]}
            chunks.append(mock_chunk)

        mock_index_client = MagicMock()
        mock_search_client = MagicMock()

        with patch("azure.search.documents.indexes.SearchIndexClient", return_value=mock_index_client), \
             patch("azure.search.documents.SearchClient", return_value=mock_search_client), \
             patch("azure.core.credentials.AzureKeyCredential"):

            from app.ingest import _push_to_azure_search
            _push_to_azure_search(chunks, mock_embed_instance)

            mock_search_client.upload_documents.assert_called_once()
            uploaded_docs = mock_search_client.upload_documents.call_args[1]["documents"]
            assert len(uploaded_docs) == 3
            assert uploaded_docs[0]["source"] == "test.pdf"
            assert uploaded_docs[0]["allowed_roles"] == ["admin", "faculty"]
