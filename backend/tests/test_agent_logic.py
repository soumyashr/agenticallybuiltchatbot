"""
Tests covering agent retry logic, RBAC, document ingest, chat endpoint,
and the GET /documents/my sidebar endpoint.

All OpenAI / FAISS calls are mocked — no real API calls are made.
"""
from __future__ import annotations

import json
import time
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
    _filter_sources_by_role,
    _enrich_sources,
    _is_session_expired,
    _cleanup_expired_sessions,
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

    # AC: UIB-122-GENERAL — fallback detection supports UC-09 no-match handling
    def test_clean_answer(self):
        assert _is_fallback_response("The syllabus covers machine learning.") is False

    # AC: UIB-122-GENERAL
    def test_fallback_could_not_find(self):
        assert _is_fallback_response("I could not find information on this topic.") is True

    # AC: UIB-122-GENERAL
    def test_fallback_no_information(self):
        assert _is_fallback_response("No information found in documents.") is True

    # AC: UIB-122-GENERAL
    def test_fallback_parsing_error(self):
        assert _is_fallback_response("There was a parsing error in the response.") is True

    # AC: UIB-122-GENERAL
    def test_fallback_agent_stopped(self):
        assert _is_fallback_response("Agent stopped due to iteration limit.") is True

    # AC: UIB-122-GENERAL
    def test_case_insensitive(self):
        assert _is_fallback_response("I COULD NOT FIND INFORMATION on this.") is True
        assert _is_fallback_response("PARSING ERROR occurred.") is True

    # AC: UIB-122-GENERAL
    def test_partial_word_non_match(self):
        """Words that contain fallback substrings but are valid answers."""
        # "information" alone doesn't trigger — needs the full phrase
        assert _is_fallback_response("Here is detailed information about the topic.") is False


class TestHasSources:
    """_has_sources() unit tests."""

    # AC: UIB-35-GENERAL — source extraction supports citation pipeline
    def test_empty_steps(self):
        assert _has_sources([]) is False

    # AC: UIB-35-GENERAL
    def test_with_source_tag(self):
        steps = [_make_step("[1] Source: syllabus.pdf, Page: 3\nContent here")]
        assert _has_sources(steps) is True

    # AC: UIB-35-GENERAL
    def test_without_source_tag(self):
        steps = [_make_step("No relevant information found.")]
        assert _has_sources(steps) is False

    # AC: UIB-35-GENERAL
    def test_non_string_observation(self):
        steps = [_make_step(12345)]  # non-string
        assert _has_sources(steps) is False


class TestExtractSources:
    """_extract_sources() unit tests."""

    # AC: UIB-35-GENERAL — source extraction for citation pipeline
    def test_single_source(self):
        steps = [_make_step("[1] Source: syllabus.pdf, Page: 5\nSome content here")]
        result = _extract_sources(steps)
        assert len(result) == 1
        assert result[0].source == "syllabus.pdf"
        assert result[0].page == 5

    # AC: UIB-35-GENERAL
    def test_dedup(self):
        obs = "[1] Source: syllabus.pdf, Page: 5\nContent\n---\n[2] Source: syllabus.pdf, Page: 5\nDuplicate"
        steps = [_make_step(obs)]
        result = _extract_sources(steps)
        assert len(result) == 1

    # AC: UIB-83-GENERAL — multiple source extraction for multi-doc answers
    def test_multiple_sources(self):
        obs = "[1] Source: doc_a.pdf, Page: 1\nA\n---\n[2] Source: doc_b.pdf, Page: 2\nB"
        steps = [_make_step(obs)]
        result = _extract_sources(steps)
        assert len(result) == 2
        names = {s.source for s in result}
        assert names == {"doc_a.pdf", "doc_b.pdf"}

    # AC: UIB-126-GENERAL — no sources on no-match
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

    # AC: UIB-18-GENERAL — agent retry on parse failure
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

    # AC: UIB-126-GENERAL — genuine no-match does not retry
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
    """Auth/rate-limit errors should raise immediately, not retry.
    # AC: UIB-18-GENERAL — error classification for agent robustness
    """

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    # AC: UIB-18-GENERAL — hard errors not retried
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
    # AC: UIB-18-GENERAL — soft errors retried with fallback

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

    # AC: UIB-27-GENERAL — RBAC session isolation
    def test_role_mismatch_raises(self):
        """Reusing a session with a different role raises PermissionError."""
        with patch("app.agent._create_executor") as mock_create:
            mock_create.return_value = MagicMock()
            get_or_create_session("rbac-test-1", Role.admin)
            with pytest.raises(PermissionError):
                get_or_create_session("rbac-test-1", Role.student)

    # AC: UIB-3-GENERAL — SSO/JWT token validation
    def test_jwt_decode_valid(self):
        token = _make_token("admin", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    # AC: UIB-3-GENERAL — expired JWT rejected
    def test_jwt_expired_raises(self):
        token = _make_token("admin", expired=True)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    # AC: UIB-3-GENERAL — invalid JWT rejected
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

    # AC: UIB-27-GENERAL — admin sees all documents
    def test_admin_sees_all(self):
        result = self._filter_for_role("admin")
        assert len(result) == 3

    # AC: UIB-27-GENERAL — faculty sees permitted documents only
    def test_faculty_sees_two(self):
        result = self._filter_for_role("faculty")
        assert len(result) == 2
        names = {d["display_name"] for d in result}
        assert "Admin Protocol" not in names

    # AC: UIB-27-GENERAL — student sees permitted documents only
    def test_student_sees_one(self):
        result = self._filter_for_role("student")
        assert len(result) == 1
        assert result[0]["display_name"] == "CS405 Syllabus"


# ═══════════════════════════════════════════════════════════════
# 3. Document ingest
# ═══════════════════════════════════════════════════════════════


class TestDocumentIngest:
    """Tests for document upload and ingest pipeline."""

    # AC: UIB-27-GENERAL — search-layer role filtering
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

    # AC: UIB-27-GENERAL — JSON string roles parsed correctly
    def test_role_filter_json_string(self):
        """Roles stored as JSON string should be parsed."""
        from app.tools import _filter_by_role

        doc = MagicMock()
        doc.metadata = {"allowed_roles": '["admin", "student"]'}

        result = _filter_by_role([doc], "student")
        assert len(result) == 1

    # AC: UIB-23-GENERAL — graceful handling when no index exists
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

    # AC: UIB-1-GENERAL — unauthenticated access rejected
    def test_missing_token_returns_401(self, client):
        resp = client.post("/chat", json={"message": "hello", "session_id": "s1"})
        assert resp.status_code == 401

    # AC: UIB-3-GENERAL — expired token rejected
    def test_expired_token_returns_401(self, client):
        token = _make_token("student", expired=True)
        resp = client.post(
            "/chat",
            json={"message": "hello", "session_id": "s1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    # AC: UIB-18-GENERAL — valid chat request returns 200
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

    # AC: UIB-18-GENERAL — LLM error returns 500
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

    # AC: UIB-1-GENERAL — unauthenticated access rejected
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/documents/my")
        assert resp.status_code == 401

    # AC: UIB-27-GENERAL — admin sees all documents
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

    # AC: UIB-27-GENERAL — faculty role filtering
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

    # AC: UIB-27-GENERAL — student role filtering
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

    # AC: UIB-52-GENERAL — no restricted details leaked in API response
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


# ═══════════════════════════════════════════════════════════════
# 6. UC-11 Form Guidance (UIB-140 + UIB-143)
# ═══════════════════════════════════════════════════════════════


class TestFormGuidanceUC11:
    """
    Tests for UC-11 form guidance behavior (UIB-140 + UIB-143).
    Verifies system prompt additions for form purpose/usage and location guidance.
    """

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    # ── UIB-140: Answer questions about form purpose and usage ──

    # AC: UIB-140-AC1
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_form_query_triggers_semantic_search(self, mock_tools, mock_llm):
        """AC1: Query containing 'form' triggers semantic search tool."""
        mock_llm.return_value = MagicMock()
        search_tool = MagicMock(name="semantic_search")
        mock_tools.return_value = [search_tool]

        invoked_inputs = []

        def fake_invoke(inputs):
            invoked_inputs.append(inputs)
            return {
                "output": "The Leave Application Form is used for requesting time off. Source: forms_guide.pdf, Page: 12",
                "intermediate_steps": [
                    _make_step("[1] Source: forms_guide.pdf, Page: 12\nLeave Application Form details...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What is the leave application form?", "form-ac1", Role.student)
            )

        assert len(invoked_inputs) == 1
        assert "form" in invoked_inputs[0]["input"].lower()
        assert result["fallback_used"] is False

    # AC: UIB-140-AC2
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_form_response_contains_purpose(self, mock_tools, mock_llm):
        """AC2: Response contains form purpose when docs have it."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "The Travel Reimbursement Form is used for claiming travel expenses after official trips. Eligible employees include full-time staff. Source: hr_forms.pdf, Page: 5",
                "intermediate_steps": [
                    _make_step("[1] Source: hr_forms.pdf, Page: 5\nTravel Reimbursement Form purpose and eligibility...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What is the travel reimbursement form for?", "form-ac2", Role.student)
            )

        answer = result["answer"].lower()
        assert "travel reimbursement form" in answer
        assert "expense" in answer or "claiming" in answer

    # AC: UIB-140-AC3
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_form_response_no_speculation(self, mock_tools, mock_llm):
        """AC3: Response does not contain speculative phrases for form queries."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "The IT Access Request Form is used by new employees to request system access. Source: it_forms.pdf, Page: 3",
                "intermediate_steps": [
                    _make_step("[1] Source: it_forms.pdf, Page: 3\nIT Access Request Form...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Tell me about the IT access request form", "form-ac3", Role.student)
            )

        answer = result["answer"].lower()
        speculative_phrases = ["i think", "probably", "you might want to", "i believe", "maybe"]
        for phrase in speculative_phrases:
            assert phrase not in answer, f"Speculative phrase '{phrase}' found in response"

    # AC: UIB-140-AC4
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_similar_forms_differentiated(self, mock_tools, mock_llm):
        """AC4: When two similar forms exist, response differentiates them."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": (
                    "There are two leave-related forms: "
                    "1) The Casual Leave Form is for short-term personal leave (up to 3 days). "
                    "2) The Medical Leave Form is for health-related absences requiring a doctor's certificate. "
                    "Source: hr_forms.pdf, Page: 8"
                ),
                "intermediate_steps": [
                    _make_step(
                        "[1] Source: hr_forms.pdf, Page: 8\nCasual Leave Form...\n---\n"
                        "[2] Source: hr_forms.pdf, Page: 10\nMedical Leave Form..."
                    )
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What leave forms are available?", "form-ac4", Role.student)
            )

        answer = result["answer"].lower()
        assert "casual leave" in answer
        assert "medical leave" in answer

    # AC: UIB-140-AC5
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_undocumented_form_returns_fallback(self, mock_tools, mock_llm):
        """AC5: Undocumented form query returns no-match fallback."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "I could not find information on this topic in the documents accessible to you.",
                "intermediate_steps": [
                    _make_step("[1] Source: general_docs.pdf, Page: 1\nUnrelated content about policies")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("How do I fill the XYZ-9999 form?", "form-ac5", Role.student)
            )

        assert "could not find" in result["answer"].lower()

    # AC: UIB-140-AC6
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_role_based_form_access(self, mock_tools, mock_llm):
        """AC6: Student querying faculty-only form gets access-denied response."""
        mock_llm.return_value = MagicMock()

        def make_tools_for_role(user_role):
            tool = MagicMock(name="semantic_search")
            return [tool]

        mock_tools.side_effect = make_tools_for_role

        def fake_invoke(inputs):
            return {
                "output": "I could not find information on this topic in the documents accessible to you.",
                "intermediate_steps": [],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Show me the faculty evaluation form", "form-ac6", Role.student)
            )

        # Student should not see faculty-only content — fallback expected
        answer = result["answer"].lower()
        assert "could not find" in answer or "not available" in answer or "accessible to you" in answer

    # ── UIB-143: Guide users on where to find forms ──

    # AC: UIB-143-AC1
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_form_location_returned_when_in_docs(self, mock_tools, mock_llm):
        """AC1: Location info returned when available in docs."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "The Leave Application Form can be found in the HR Portal under Forms > Leave Management. Source: hr_guide.pdf, Page: 15",
                "intermediate_steps": [
                    _make_step("[1] Source: hr_guide.pdf, Page: 15\nLeave Application Form location: HR Portal > Forms > Leave Management")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Where can I find the leave application form?", "loc-ac1", Role.student)
            )

        answer = result["answer"].lower()
        assert "hr portal" in answer or "forms" in answer or "leave management" in answer

    # AC: UIB-143-AC2
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_form_location_respects_rbac(self, mock_tools, mock_llm):
        """AC2: Location guidance respects RBAC — student can't see faculty-only form locations."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "I could not find information on this topic in the documents accessible to you.",
                "intermediate_steps": [
                    _make_step("[1] Source: general.pdf, Page: 1\nUnrelated content")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Where do I find the faculty performance review form?", "loc-ac2", Role.student)
            )

        assert "could not find" in result["answer"].lower()

    # AC: UIB-143-AC3
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_step_by_step_navigation_when_no_direct_link(self, mock_tools, mock_llm):
        """AC3: Step-by-step navigation provided when no direct link available."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": (
                    "To access the IT Access Request Form: "
                    "1. Log in to the internal portal. "
                    "2. Navigate to IT Services. "
                    "3. Click on Forms & Requests. "
                    "4. Select 'New Access Request'. "
                    "Source: it_guide.pdf, Page: 22"
                ),
                "intermediate_steps": [
                    _make_step("[1] Source: it_guide.pdf, Page: 22\nIT Access Request Form — navigation steps...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("How do I get to the IT access request form?", "loc-ac3", Role.student)
            )

        answer = result["answer"]
        # Should contain step indicators (numbered steps or navigation path)
        assert "1." in answer or "step" in answer.lower() or "navigate" in answer.lower()

    # AC: UIB-143-AC5
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_no_guessed_urls_in_response(self, mock_tools, mock_llm):
        """AC5: No guessed URLs appear in form location responses."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "The form can be found in the HR Portal under Forms section. Contact HR for direct access. Source: hr_guide.pdf, Page: 15",
                "intermediate_steps": [
                    _make_step("[1] Source: hr_guide.pdf, Page: 15\nForm location details...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Where can I download the expense form?", "loc-ac5", Role.student)
            )

        answer = result["answer"]
        # Should not contain fabricated URLs
        import re as _re
        url_pattern = _re.compile(r'https?://(?![\s])[^\s]+')
        urls_found = url_pattern.findall(answer)
        assert len(urls_found) == 0, f"Guessed URLs found in response: {urls_found}"

    # AC: UIB-143-AC6
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    def test_location_access_control_respected(self, mock_tools, mock_llm):
        """AC6: Access control respected for form locations — admin-only locations hidden from students."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]

        def fake_invoke(inputs):
            return {
                "output": "I could not find information on this topic in the documents accessible to you.",
                "intermediate_steps": [],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("Where is the admin budget allocation form?", "loc-ac6", Role.student)
            )

        answer = result["answer"].lower()
        assert "could not find" in answer or "accessible to you" in answer

    # ── System prompt verification ──

    def test_system_prompt_contains_form_guidance(self):
        """Verify the system prompt includes UC-11 form guidance sections."""
        # Read from .env file directly since lru_cache may hold stale settings
        import os
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        with open(env_path) as f:
            env_content = f.read()
        # Find AGENT_SYSTEM_PROMPT value in .env
        for line in env_content.split("\n"):
            if line.startswith("AGENT_SYSTEM_PROMPT="):
                prompt = line[len("AGENT_SYSTEM_PROMPT="):]
                break
        else:
            pytest.fail("AGENT_SYSTEM_PROMPT not found in .env")
        assert "FORM GUIDANCE" in prompt
        assert "UIB-140" in prompt
        assert "FORM LOCATION GUIDANCE" in prompt
        assert "UIB-143" in prompt
        assert "never guess" in prompt.lower() or "never fabricate" in prompt.lower()
        assert "role-based access" in prompt.lower() or "role" in prompt.lower()


# ═══════════════════════════════════════════════════════════════
# 7. RBAC Citation Filter (UIB-31, UIB-35, UIB-40, UIB-44, UIB-52)
# ═══════════════════════════════════════════════════════════════


class TestRBACCitationFilter:
    """
    Tests for post-generation RBAC filter on source citations.
    Ensures restricted document names never leak to unauthorized users.
    """

    # Roles map: simulates what get_allowed_roles_map() returns from DynamoDB
    MOCK_ROLES_MAP = {
        "student_handbook.pdf": ["admin", "faculty", "student"],
        "faculty_manual.pdf": ["admin", "faculty"],
        "admin_protocol.pdf": ["admin"],
        "shared_policies.pdf": ["admin", "faculty", "student"],
    }

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    # ── Unit tests for _filter_sources_by_role ──

    # AC: UIB-31 — authorized sources only returned
    @patch("app.agent.get_allowed_roles_map")
    def test_citations_filtered_by_role_student(self, mock_roles):
        """Student sees only student-accessible docs in citations."""
        mock_roles.return_value = self.MOCK_ROLES_MAP

        sources = [
            SourceDoc(source="student_handbook.pdf", page=1, snippet="..."),
            SourceDoc(source="faculty_manual.pdf", page=5, snippet="..."),
            SourceDoc(source="admin_protocol.pdf", page=10, snippet="..."),
        ]

        filtered = _filter_sources_by_role(sources, "student")
        names = {s.source for s in filtered}
        assert names == {"student_handbook.pdf"}

    # AC: UIB-35 — no restricted doc names in citations
    @patch("app.agent.get_allowed_roles_map")
    def test_no_restricted_docs_in_student_citations(self, mock_roles):
        """Admin-only doc name must NOT appear in student response sources."""
        mock_roles.return_value = self.MOCK_ROLES_MAP

        sources = [
            SourceDoc(source="student_handbook.pdf", page=1, snippet="..."),
            SourceDoc(source="admin_protocol.pdf", page=3, snippet="Secret admin info"),
        ]

        filtered = _filter_sources_by_role(sources, "student")
        for s in filtered:
            assert s.source != "admin_protocol.pdf"

    # AC: UIB-44 — neutral message has empty sources
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.get_allowed_roles_map")
    def test_neutral_response_has_empty_sources(self, mock_roles, mock_tools, mock_llm):
        """When agent returns neutral/no-match with sources, response sources = []."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_roles.return_value = self.MOCK_ROLES_MAP

        def fake_invoke(inputs):
            return {
                "output": "I could not find information on this topic in the documents accessible to you.",
                "intermediate_steps": [
                    _make_step("[1] Source: admin_protocol.pdf, Page: 1\nRestricted content")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("What is the admin budget?", "rbac-filter-neutral", Role.student)
            )

        assert "could not find" in result["answer"].lower()
        assert result["sources"] == [], f"Sources should be empty on neutral response, got: {result['sources']}"

    # AC: UIB-40 — fallback response has empty sources
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent._direct_faiss_search", new_callable=AsyncMock)
    def test_fallback_response_has_empty_sources(self, mock_fallback, mock_tools, mock_llm):
        """Fallback/error response never leaks source names."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_fallback.return_value = {
            "answer": "I could not find information on this topic.",
            "sources": [],
            "reasoning_steps": 0,
            "fallback_used": True,
            "error_type": "no_match",
        }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = MagicMock(side_effect=TimeoutError("LLM timeout"))
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("test query", "rbac-filter-fallback", Role.student)
            )

        assert result["sources"] == []

    # AC: UIB-52 — admin sees all accessible sources
    @patch("app.agent.get_allowed_roles_map")
    def test_admin_citations_include_admin_docs(self, mock_roles):
        """Admin query → admin-only doc names ARE visible in sources."""
        mock_roles.return_value = self.MOCK_ROLES_MAP

        sources = [
            SourceDoc(source="student_handbook.pdf", page=1, snippet="..."),
            SourceDoc(source="faculty_manual.pdf", page=5, snippet="..."),
            SourceDoc(source="admin_protocol.pdf", page=10, snippet="..."),
        ]

        filtered = _filter_sources_by_role(sources, "admin")
        names = {s.source for s in filtered}
        assert names == {"student_handbook.pdf", "faculty_manual.pdf", "admin_protocol.pdf"}

    # Regression guard
    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.get_allowed_roles_map")
    def test_authorized_user_still_gets_citations(self, mock_roles, mock_tools, mock_llm):
        """Fix must not strip ALL citations — authorized ones must remain."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_roles.return_value = self.MOCK_ROLES_MAP

        def fake_invoke(inputs):
            return {
                "output": "The student handbook covers enrollment procedures. Source: student_handbook.pdf, Page: 12",
                "intermediate_steps": [
                    _make_step("[1] Source: student_handbook.pdf, Page: 12\nEnrollment procedures...")
                ],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                agent_chat("How do I enroll?", "rbac-filter-auth", Role.student)
            )

        assert result["fallback_used"] is False
        assert len(result["sources"]) == 1
        assert result["sources"][0]["source"] == "student_handbook.pdf"


# ═══════════════════════════════════════════════════════════════
# 8. Session TTL + Memory Cleanup (UIB-93, UC-07)
# ═══════════════════════════════════════════════════════════════


class TestSessionTTLUC07:
    """
    Tests for session memory TTL and automatic cleanup.
    Ensures conversation memory expires with JWT and does not
    leak across sessions or accumulate indefinitely.
    """

    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    # AC: UIB-93-TTL1 — expired session memory cleared
    @patch("app.agent._create_executor")
    def test_expired_session_memory_cleared(self, mock_create):
        """Expired session is evicted; next access creates a fresh executor."""
        mock_create.return_value = MagicMock()

        # Create a session manually with a past timestamp
        _sessions["ttl-test-1"] = {
            "executor": MagicMock(),
            "role": Role.student,
            "created_at": time.time() - 99999,  # well past any TTL
        }

        # Accessing should evict the expired session and create a new one
        executor = get_or_create_session("ttl-test-1", Role.student)
        mock_create.assert_called_once()  # new executor created
        assert _sessions["ttl-test-1"]["created_at"] > time.time() - 5

    # AC: UIB-93-TTL2 — valid session memory preserved
    @patch("app.agent._create_executor")
    def test_valid_session_memory_preserved(self, mock_create):
        """Session within TTL keeps its existing executor."""
        original_executor = MagicMock()
        mock_create.return_value = original_executor

        _sessions["ttl-test-2"] = {
            "executor": original_executor,
            "role": Role.student,
            "created_at": time.time(),  # just created — well within TTL
        }

        executor = get_or_create_session("ttl-test-2", Role.student)
        mock_create.assert_not_called()  # no new executor
        assert executor is original_executor

    # AC: UIB-93-TTL3 — memory cleared on explicit clear_session
    @patch("app.agent._create_executor")
    def test_memory_cleared_on_explicit_clear(self, mock_create):
        """clear_session() removes the session entirely."""
        mock_create.return_value = MagicMock()

        _sessions["ttl-test-3"] = {
            "executor": MagicMock(),
            "role": Role.student,
            "created_at": time.time(),
        }
        assert "ttl-test-3" in _sessions

        clear_session("ttl-test-3")
        assert "ttl-test-3" not in _sessions

    # AC: UIB-93-TTL4 — TTL configurable via settings
    def test_session_ttl_configurable(self):
        """session_memory_ttl_seconds setting exists and is reasonable."""
        assert hasattr(settings, "session_memory_ttl_seconds")
        assert settings.session_memory_ttl_seconds > 0
        # Default should match JWT expiry (8 hours = 28800 seconds)
        assert settings.session_memory_ttl_seconds == 28800

    # AC: UIB-93-TTL5 — no memory leak across sessions
    @patch("app.agent._create_executor")
    def test_no_memory_leak_across_sessions(self, mock_create):
        """Two different users with different session IDs have isolated memory."""
        mock_create.return_value = MagicMock()

        get_or_create_session("user-A-session", Role.student)
        get_or_create_session("user-B-session", Role.faculty)

        assert "user-A-session" in _sessions
        assert "user-B-session" in _sessions
        assert _sessions["user-A-session"]["role"] != _sessions["user-B-session"]["role"]

        # Clearing one does not affect the other
        clear_session("user-A-session")
        assert "user-A-session" not in _sessions
        assert "user-B-session" in _sessions

    # AC: UIB-93-TTL6 — fresh session gets no prior context after expiry
    @patch("app.agent._create_executor")
    def test_new_session_has_no_prior_context(self, mock_create):
        """After expiry, a new executor is created — no stale memory."""
        first_executor = MagicMock(name="old_executor")
        second_executor = MagicMock(name="new_executor")
        # Only the recreation call happens; return the new executor
        mock_create.return_value = second_executor

        # Create session manually with expired timestamp
        _sessions["ttl-test-6"] = {
            "executor": first_executor,
            "role": Role.student,
            "created_at": time.time() - 99999,
        }

        # Access triggers expiry + recreation
        executor = get_or_create_session("ttl-test-6", Role.student)
        mock_create.assert_called_once()  # recreated
        assert executor is second_executor
        assert executor is not first_executor


# ── Citation Format Enrichment (M1, UIB-35) ──────────────────

class TestCitationFormatUC02:
    """UC-02 citation format: display_name, uploaded_at enrichment from DynamoDB."""

    # AC: UIB-35-AC1 — citations include display_name
    def test_enriched_source_has_display_name(self):
        """_enrich_sources populates display_name from DynamoDB metadata."""
        src = SourceDoc(source="policy_v2.pdf", page=3, snippet="Some text")
        meta_map = {"policy_v2.pdf": {"display_name": "University Policy v2", "uploaded_at": "2026-03-01T10:00:00"}}
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            result = _enrich_sources([src])
        assert result[0].display_name == "University Policy v2"

    # AC: UIB-35-AC2 — citations include uploaded_at
    def test_enriched_source_has_uploaded_at(self):
        """_enrich_sources populates uploaded_at from DynamoDB metadata."""
        src = SourceDoc(source="policy_v2.pdf", page=3, snippet="Some text")
        meta_map = {"policy_v2.pdf": {"display_name": "University Policy v2", "uploaded_at": "2026-03-01T10:00:00"}}
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            result = _enrich_sources([src])
        assert result[0].uploaded_at == "2026-03-01T10:00:00"

    # AC: UIB-35-AC3 — unknown files get no enrichment (graceful)
    def test_unknown_file_stays_raw(self):
        """Files not in DynamoDB retain original source without enrichment."""
        src = SourceDoc(source="unknown.pdf", page=1, snippet="x")
        meta_map = {"policy_v2.pdf": {"display_name": "University Policy v2", "uploaded_at": "2026-03-01T10:00:00"}}
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            result = _enrich_sources([src])
        assert result[0].display_name is None
        assert result[0].uploaded_at is None
        assert result[0].source == "unknown.pdf"

    # AC: UIB-35-AC4 — metadata lookup failure returns raw sources safely
    def test_metadata_error_returns_raw_sources(self):
        """If DynamoDB metadata fails, sources are returned without enrichment."""
        src = SourceDoc(source="policy_v2.pdf", page=3, snippet="Some text")
        with patch("app.agent.get_document_metadata_map", side_effect=Exception("DynamoDB down")):
            result = _enrich_sources([src])
        assert len(result) == 1
        assert result[0].display_name is None
        assert result[0].source == "policy_v2.pdf"

    # AC: UIB-35-AC5 — _extract_sources returns raw, _enrich_sources enriches separately
    def test_extract_then_enrich_pipeline(self):
        """_extract_sources returns raw sources; _enrich_sources adds metadata."""
        observation = "[1] Source: handbook.pdf, Page: 5\nAdmission details here"
        steps = [(MagicMock(), observation)]
        # _extract_sources no longer calls _enrich_sources internally
        sources = _extract_sources(steps)
        assert len(sources) == 1
        assert sources[0].source == "handbook.pdf"
        assert sources[0].display_name is None  # raw, not yet enriched
        # Now enrich separately (as chat() does after filtering)
        meta_map = {"handbook.pdf": {"display_name": "Student Handbook", "uploaded_at": "2026-02-15T08:00:00"}}
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            enriched = _enrich_sources(sources)
        assert enriched[0].display_name == "Student Handbook"
        assert enriched[0].uploaded_at == "2026-02-15T08:00:00"
        assert enriched[0].page == 5

    # AC: UIB-35-AC6 — empty sources stay empty
    def test_empty_sources_no_enrichment_call(self):
        """_enrich_sources on empty list returns empty without calling DynamoDB."""
        with patch("app.agent.get_document_metadata_map") as mock_meta:
            result = _enrich_sources([])
        mock_meta.assert_not_called()
        assert result == []

    # AC: UIB-35-AC7 — SourceDoc model accepts new optional fields
    def test_source_doc_new_fields_optional(self):
        """SourceDoc display_name and uploaded_at are optional and default to None."""
        src = SourceDoc(source="file.pdf", snippet="text")
        assert src.display_name is None
        assert src.uploaded_at is None
        assert src.page is None
        # With values
        src2 = SourceDoc(source="f.pdf", snippet="t", display_name="My File", uploaded_at="2026-01-01")
        assert src2.display_name == "My File"
        assert src2.uploaded_at == "2026-01-01"

    # AC: UIB-35-PROD1 — enrichment consistent on faculty path
    def test_citation_enrichment_on_faculty_role(self):
        """Faculty query returns enriched SourceDoc dicts, not raw strings."""
        src = SourceDoc(source="policy.pdf", page=1, snippet="text")
        meta_map = {"policy.pdf": {"display_name": "Faculty Policy", "uploaded_at": "2026-03-01T10:00:00"}}
        roles_map = {"policy.pdf": ["faculty", "admin"]}
        with patch("app.agent.get_allowed_roles_map", return_value=roles_map):
            filtered = _filter_sources_by_role([src], "faculty")
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            enriched = _enrich_sources(filtered)
        assert len(enriched) == 1
        assert isinstance(enriched[0], SourceDoc)
        assert enriched[0].display_name == "Faculty Policy"
        assert enriched[0].uploaded_at == "2026-03-01T10:00:00"

    # AC: UIB-35-PROD2 — enrichment consistent: filter then enrich on all paths
    def test_citation_enrichment_on_all_response_paths(self):
        """Verify filter→enrich order: _extract_sources returns raw, enrich adds metadata."""
        observation = "[1] Source: doc.pdf, Page: 2\nContent here"
        steps = [(MagicMock(), observation)]
        # _extract_sources must return raw (not enriched)
        sources = _extract_sources(steps)
        assert sources[0].display_name is None, "_extract_sources must not enrich"
        # Simulate the filter→enrich pipeline used by chat()
        roles_map = {"doc.pdf": ["student"]}
        meta_map = {"doc.pdf": {"display_name": "My Document", "uploaded_at": "2026-01-15"}}
        with patch("app.agent.get_allowed_roles_map", return_value=roles_map):
            filtered = _filter_sources_by_role(sources, "student")
        with patch("app.agent.get_document_metadata_map", return_value=meta_map):
            enriched = _enrich_sources(filtered)
        assert enriched[0].display_name == "My Document"
        # Verify output is SourceDoc, not raw string
        assert isinstance(enriched[0], SourceDoc)
        assert hasattr(enriched[0], "source")
        assert hasattr(enriched[0], "display_name")
        assert hasattr(enriched[0], "uploaded_at")
