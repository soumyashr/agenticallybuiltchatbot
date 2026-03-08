"""
Tests covering agent retry logic, RBAC, document ingest, chat endpoint,
and the GET /documents/my sidebar endpoint.

All OpenAI / FAISS calls are mocked — no real API calls are made.
"""
from __future__ import annotations

import json
import asyncio
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import jwt as pyjwt

# ── Ensure settings are importable without a real .env ──────
# We patch config.settings at module level where needed.

from app.config import settings
from app.models import Role, SourceDoc
from app.agent import (
    _is_fallback_response,
    _has_sources,
    _extract_sources,
    _direct_faiss_search,
    chat as agent_chat,
    get_or_create_session,
    clear_session,
    _sessions,
    MAX_AGENT_RETRIES,
    AgentAccessError,
    AgentParseError,
    AgentRetrievalError,
)
from app.auth import create_token, decode_token


# ── Helpers ──────────────────────────────────────────────────

def _make_token(role: str, username: str = "testuser", expired: bool = False) -> str:
    """Create a valid or expired JWT for testing."""
    delta = timedelta(hours=-1) if expired else timedelta(hours=8)
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + delta,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _make_step(observation: str):
    """Create a fake intermediate_step tuple (action, observation)."""
    action = MagicMock()
    return (action, observation)


# ═══════════════════════════════════════════════════════════════
# 1. Agent retry logic (agent.py)
# ═══════════════════════════════════════════════════════════════


class TestIsFallbackResponse:
    """_is_fallback_response() unit tests."""

    def test_clean_answer(self):
        assert _is_fallback_response("The syllabus covers machine learning.") is False

    def test_fallback_could_not_find(self):
        assert _is_fallback_response("I could not find information on this topic.") is True

    def test_fallback_no_information(self):
        assert _is_fallback_response("No information found in documents.") is True

    def test_fallback_parsing_error(self):
        assert _is_fallback_response("There was a parsing error in the response.") is True

    def test_fallback_agent_stopped(self):
        assert _is_fallback_response("Agent stopped due to iteration limit.") is True

    def test_case_insensitive(self):
        assert _is_fallback_response("I COULD NOT FIND INFORMATION on this.") is True
        assert _is_fallback_response("PARSING ERROR occurred.") is True

    def test_partial_word_non_match(self):
        """Words that contain fallback substrings but are valid answers."""
        # "information" alone doesn't trigger — needs the full phrase
        assert _is_fallback_response("Here is detailed information about the topic.") is False


class TestHasSources:
    """_has_sources() unit tests."""

    def test_empty_steps(self):
        assert _has_sources([]) is False

    def test_with_source_tag(self):
        steps = [_make_step("[1] Source: syllabus.pdf, Page: 3\nContent here")]
        assert _has_sources(steps) is True

    def test_without_source_tag(self):
        steps = [_make_step("No relevant information found.")]
        assert _has_sources(steps) is False

    def test_non_string_observation(self):
        steps = [_make_step(12345)]  # non-string
        assert _has_sources(steps) is False


class TestExtractSources:
    """_extract_sources() unit tests."""

    def test_single_source(self):
        steps = [_make_step("[1] Source: syllabus.pdf, Page: 5\nSome content here")]
        result = _extract_sources(steps)
        assert len(result) == 1
        assert result[0].source == "syllabus.pdf"
        assert result[0].page == 5

    def test_dedup(self):
        obs = "[1] Source: syllabus.pdf, Page: 5\nContent\n---\n[2] Source: syllabus.pdf, Page: 5\nDuplicate"
        steps = [_make_step(obs)]
        result = _extract_sources(steps)
        assert len(result) == 1

    def test_multiple_sources(self):
        obs = "[1] Source: doc_a.pdf, Page: 1\nA\n---\n[2] Source: doc_b.pdf, Page: 2\nB"
        steps = [_make_step(obs)]
        result = _extract_sources(steps)
        assert len(result) == 2
        names = {s.source for s in result}
        assert names == {"doc_a.pdf", "doc_b.pdf"}

    def test_no_source_tag(self):
        steps = [_make_step("No relevant information found.")]
        result = _extract_sources(steps)
        assert result == []


class TestRetryDecisions:
    """Tests that the retry logic in chat() makes correct decisions."""

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_fallback_no_faiss_triggers_retry(self, mock_tools, mock_llm):
        """Fallback phrase + no sources → should retry (agent parse failure)."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        call_count = 0

        def fake_invoke(inputs):
            nonlocal call_count
            call_count += 1
            if call_count < MAX_AGENT_RETRIES:
                return {
                    "output": "Invalid or incomplete response",
                    "intermediate_steps": [],
                }
            return {
                "output": "The syllabus covers ML topics.",
                "intermediate_steps": [],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What is ML?", "test-session-1", Role.student)
            )

        assert call_count == MAX_AGENT_RETRIES
        assert result["fallback_used"] is False
        assert "ML topics" in result["answer"]

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_fallback_with_faiss_no_retry(self, mock_tools, mock_llm):
        """Fallback phrase + sources present → genuine not-found, no retry."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        call_count = 0

        def fake_invoke(inputs):
            nonlocal call_count
            call_count += 1
            return {
                "output": "I could not find information on this topic.",
                "intermediate_steps": [
                    _make_step("[1] Source: doc.pdf, Page: 1\nUnrelated content")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What is quantum computing?", "test-session-2", Role.student)
            )

        assert call_count == 1  # No retry
        assert "could not find" in result["answer"].lower()


class TestHardErrorNoRetry:
    """Auth/rate-limit errors should raise immediately, not retry."""

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    @pytest.mark.parametrize("error_msg", [
        "401 Unauthorized",
        "invalid_api_key provided",
        "AuthenticationError: bad key",
        "insufficient_quota: plan exceeded",
        "429 Too Many Requests",
        "rate_limit exceeded",
    ])
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_auth_errors_not_retried(self, mock_tools, mock_llm, error_msg):
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = MagicMock(side_effect=Exception(error_msg))
            mock_create.return_value = executor

            with pytest.raises(AgentAccessError):
                asyncio.get_event_loop().run_until_complete(
                    agent_chat("test", f"hard-err-{error_msg[:10]}", Role.student)
                )

        executor.invoke.assert_called_once()  # Only 1 call, no retry


class TestSoftErrorRetried:
    """Timeout / generic errors should be retried."""

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent._direct_faiss_search", new_callable=AsyncMock)
    def test_timeout_retried_then_fallback(self, mock_fallback, mock_tools, mock_llm):
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_fallback.return_value = {
            "answer": "Fallback answer",
            "sources": [],
            "reasoning_steps": 1,
            "fallback_used": True,
            "error_type": None,
        }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = MagicMock(side_effect=TimeoutError("LLM timed out"))
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("test", "soft-err-session", Role.student)
            )

        assert executor.invoke.call_count == MAX_AGENT_RETRIES
        assert result["fallback_used"] is True
        mock_fallback.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# 2. RBAC / access control
# ═══════════════════════════════════════════════════════════════


class TestRBAC:
    """Role-based access control tests."""

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    def test_role_mismatch_raises(self):
        """Reusing a session with a different role raises PermissionError."""
        with patch("app.agent._create_executor") as mock_create:
            mock_create.return_value = MagicMock()
            get_or_create_session("rbac-test-1", Role.admin)
            with pytest.raises(PermissionError):
                get_or_create_session("rbac-test-1", Role.student)

    def test_jwt_decode_valid(self):
        token = _make_token("admin", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    def test_jwt_expired_raises(self):
        token = _make_token("admin", expired=True)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_jwt_invalid_raises(self):
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token("not.a.valid.token")


class TestRBACDocumentFiltering:
    """Tests that document filtering by role works correctly."""

    MOCK_DOCS = [
        {
            "id": 1, "filename": "student_syllabus.pdf",
            "display_name": "CS405 Syllabus",
            "allowed_roles": ["admin", "faculty", "student"],
            "status": "INGESTED", "chunk_count": 10,
            "file_size": 1000, "uploaded_at": "2024-01-01",
            "ingested_at": "2024-01-01", "error_msg": None,
        },
        {
            "id": 2, "filename": "feature_6_document.pdf",
            "display_name": "Faculty Manual",
            "allowed_roles": ["admin", "faculty"],
            "status": "INGESTED", "chunk_count": 20,
            "file_size": 2000, "uploaded_at": "2024-01-01",
            "ingested_at": "2024-01-01", "error_msg": None,
        },
        {
            "id": 3, "filename": "feature_7_document.pdf",
            "display_name": "Admin Protocol",
            "allowed_roles": ["admin"],
            "status": "INGESTED", "chunk_count": 15,
            "file_size": 1500, "uploaded_at": "2024-01-01",
            "ingested_at": "2024-01-01", "error_msg": None,
        },
    ]

    def _filter_for_role(self, role: str) -> list[dict]:
        """Simulate what GET /documents/my does."""
        return [
            {
                "id": d["id"],
                "display_name": d["display_name"],
                "allowed_roles": d["allowed_roles"],
                "chunk_count": d["chunk_count"],
            }
            for d in self.MOCK_DOCS
            if d["status"] == "INGESTED" and role in d.get("allowed_roles", [])
        ]

    def test_admin_sees_all(self):
        result = self._filter_for_role("admin")
        assert len(result) == 3

    def test_faculty_sees_two(self):
        result = self._filter_for_role("faculty")
        assert len(result) == 2
        names = {d["display_name"] for d in result}
        assert "Admin Protocol" not in names

    def test_student_sees_one(self):
        result = self._filter_for_role("student")
        assert len(result) == 1
        assert result[0]["display_name"] == "CS405 Syllabus"


# ═══════════════════════════════════════════════════════════════
# 3. Document ingest
# ═══════════════════════════════════════════════════════════════


class TestDocumentIngest:
    """Tests for document upload and ingest pipeline."""

    def test_role_filter_keeps_allowed(self):
        """Verify the role filter logic (unit test of _filter_by_role)."""
        from app.tools import _filter_by_role

        doc1 = MagicMock()
        doc1.metadata = {"allowed_roles": ["admin", "faculty", "student"]}
        doc2 = MagicMock()
        doc2.metadata = {"allowed_roles": ["admin", "faculty"]}
        doc3 = MagicMock()
        doc3.metadata = {"allowed_roles": ["admin"]}

        # Student should only see doc1
        result = _filter_by_role([doc1, doc2, doc3], "student")
        assert len(result) == 1
        assert result[0] is doc1

        # Faculty should see doc1 and doc2
        result = _filter_by_role([doc1, doc2, doc3], "faculty")
        assert len(result) == 2

        # Admin should see all
        result = _filter_by_role([doc1, doc2, doc3], "admin")
        assert len(result) == 3

    def test_role_filter_json_string(self):
        """Roles stored as JSON string should be parsed."""
        from app.tools import _filter_by_role

        doc = MagicMock()
        doc.metadata = {"allowed_roles": '["admin", "student"]'}

        result = _filter_by_role([doc], "student")
        assert len(result) == 1

    @patch("app.tools.get_vector_store")
    def test_search_tool_no_index(self, mock_vs):
        """When no FAISS index exists, search tool returns helpful message."""
        mock_vs.return_value = None
        from app.tools import make_search_tools
        tools = make_search_tools("student")
        result = tools[0].func("test query")
        assert "No documents have been ingested" in result


# ═══════════════════════════════════════════════════════════════
# 4. Chat endpoint (via FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════


class TestChatEndpoint:
    """Tests for POST /chat endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_missing_token_returns_401(self, client):
        resp = client.post("/chat", json={"message": "hello", "session_id": "s1"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client):
        token = _make_token("student", expired=True)
        resp = client.post(
            "/chat",
            json={"message": "hello", "session_id": "s1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    @patch("app.routers.chat_router.agent_chat", new_callable=AsyncMock)
    def test_valid_token_returns_200(self, mock_chat, client):
        mock_chat.return_value = {
            "answer": "The answer is 42.",
            "session_id": "s1",
            "role": "student",
            "sources": [],
            "reasoning_steps": 1,
            "fallback_used": False,
            "error_type": None,
        }
        token = _make_token("student")
        resp = client.post(
            "/chat",
            json={"message": "What is 42?", "session_id": "s1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "The answer is 42."
        assert data["session_id"] == "s1"

    @patch("app.routers.chat_router.agent_chat", new_callable=AsyncMock)
    def test_llm_error_returns_500(self, mock_chat, client):
        mock_chat.side_effect = RuntimeError("LLM crashed")
        token = _make_token("student")
        resp = client.post(
            "/chat",
            json={"message": "hello", "session_id": "s1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════
# 5. GET /documents/my endpoint
# ═══════════════════════════════════════════════════════════════


class TestDocumentsMyEndpoint:
    """Tests for GET /documents/my sidebar endpoint."""

    MOCK_DOCS = TestRBACDocumentFiltering.MOCK_DOCS

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/documents/my")
        assert resp.status_code == 401

    @patch("app.routers.documents_router.get_all_documents")
    def test_admin_gets_all(self, mock_docs, client):
        mock_docs.return_value = self.MOCK_DOCS
        token = _make_token("admin", "admin")
        resp = client.get(
            "/documents/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    @patch("app.routers.documents_router.get_all_documents")
    def test_faculty_gets_two(self, mock_docs, client):
        mock_docs.return_value = self.MOCK_DOCS
        token = _make_token("faculty", "faculty1")
        resp = client.get(
            "/documents/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {d["display_name"] for d in data}
        assert "Admin Protocol" not in names

    @patch("app.routers.documents_router.get_all_documents")
    def test_student_gets_one(self, mock_docs, client):
        mock_docs.return_value = self.MOCK_DOCS
        token = _make_token("student", "student1")
        resp = client.get(
            "/documents/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["display_name"] == "CS405 Syllabus"

    @patch("app.routers.documents_router.get_all_documents")
    def test_no_file_paths_exposed(self, mock_docs, client):
        """Ensure no filename/filepath fields leak through."""
        mock_docs.return_value = self.MOCK_DOCS
        token = _make_token("admin", "admin")
        resp = client.get(
            "/documents/my",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        for doc in data:
            assert "filename" not in doc
            assert "filepath" not in doc
            assert "file_size" not in doc
            assert set(doc.keys()) == {"id", "display_name", "allowed_roles", "chunk_count"}
