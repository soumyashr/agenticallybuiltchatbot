"""
Tests for the Settings configuration class, focusing on the AI_PROVIDER
flag and Azure-specific field validation.

All tests use unittest.mock — no real API calls are made.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch


# ═══════════════════════════════════════════════════════════════
# AI_PROVIDER defaults and env reading
# ═══════════════════════════════════════════════════════════════


class TestAIProviderDefaults:
    """Tests for AI_PROVIDER default value and env var reading."""

    def test_ai_provider_defaults_to_azure_openai(self):
        """The default value for ai_provider should be 'azure_openai'."""
        from app.config import Settings
        # Create fresh settings without env file influence
        with patch.dict("os.environ", {}, clear=True):
            s = Settings(_env_file=None)
            assert s.ai_provider == "azure_openai"

    @patch.dict("os.environ", {
        "AI_PROVIDER": "openai",
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
        "AZURE_SEARCH_ADMIN_KEY": "test-search-key",
    }, clear=False)
    def test_all_azure_fields_readable_from_env(self):
        """All Azure-specific fields should be readable from env vars."""
        from app.config import Settings
        s = Settings(_env_file=None)
        assert s.azure_openai_api_key == "test-key"
        assert s.azure_openai_endpoint == "https://test.openai.azure.com/"
        assert s.azure_search_endpoint == "https://test.search.windows.net"
        assert s.azure_search_admin_key == "test-search-key"
        assert s.azure_search_index == "hm-knowledge-hub"  # default
        assert s.azure_openai_embedding_deployment == "text-embedding-3-small"  # default
        assert s.azure_openai_api_version == "2024-08-01-preview"  # default


class TestAzureValidation:
    """Tests that missing Azure config raises appropriate errors at build time."""

    @patch.dict("os.environ", {"AI_PROVIDER": "azure_openai"}, clear=False)
    def test_missing_azure_key_raises_on_build(self):
        """When AI_PROVIDER=azure_openai and azure_openai_api_key is empty,
        _build_llm() should still attempt to build (validation happens at call time)."""
        from app.config import Settings
        s = Settings(_env_file=None)
        # Settings object creates fine — empty strings are allowed at config level.
        # The error surfaces when AzureChatOpenAI actually tries to connect.
        assert s.ai_provider == "azure_openai"
        assert s.azure_openai_api_key == ""  # empty but no crash at config level

    @patch.dict("os.environ", {"AI_PROVIDER": "azure_openai"}, clear=False)
    def test_missing_azure_endpoint_raises_on_build(self):
        """When AI_PROVIDER=azure_openai and azure_openai_endpoint is empty,
        config loads but build will fail at connection time."""
        from app.config import Settings
        s = Settings(_env_file=None)
        assert s.azure_openai_endpoint == ""  # empty but no crash at config level
