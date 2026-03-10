"""
Tests for UC-12 Workflow Execution Prevention (UIB-148 + UIB-152).

Covers: detect_workflow_attempt() pattern matching, WorkflowAttempt exception,
configurable patterns, HTTP endpoint integration, escalation logging.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.workflow_guard import (
    detect_workflow_attempt,
    WorkflowAttempt,
    _get_patterns,
    _DEFAULT_PATTERNS,
)
from app.models import Role


# ── Unit tests: detection patterns ───────────────────────────

class TestWorkflowDetection:
    """UIB-148: Detect workflow-execution attempts."""

    # AC: UIB-148-AC1 — submit form detected
    def test_submit_form_detected(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("submit my leave form now")

    # AC: UIB-148-AC1 — approve request detected
    def test_approve_request_detected(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("approve my registration")

    # AC: UIB-148-AC1 — apply now detected
    def test_apply_now_detected(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("I want to apply now for the scholarship")

    # AC: UIB-148-AC1 — process request detected
    def test_process_request_detected(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("process my leave request")

    # AC: UIB-148-AC1 — enroll me detected
    def test_enroll_me_detected(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("enroll me in the course")

    # AC: UIB-148-AC1 — case insensitive
    def test_case_insensitive_detection(self):
        with pytest.raises(WorkflowAttempt):
            detect_workflow_attempt("SUBMIT MY FORM please")

    # AC: UIB-148-AC3 — informational query NOT blocked
    def test_informational_query_passes(self):
        # Should not raise — asking about a form, not submitting
        detect_workflow_attempt("What is the leave form?")

    def test_general_question_passes(self):
        detect_workflow_attempt("How do I find the admission policy?")

    def test_form_guidance_not_blocked(self):
        detect_workflow_attempt("Where can I download the leave form?")

    # AC: UIB-148-AC5 — WorkflowAttempt stores matched pattern
    def test_exception_contains_pattern(self):
        with pytest.raises(WorkflowAttempt) as exc_info:
            detect_workflow_attempt("submit my leave form")
        assert exc_info.value.matched_pattern  # non-empty pattern string


class TestWorkflowConfig:
    """UIB-150: Configurable workflow patterns."""

    # AC: UIB-150 — custom patterns via env override
    def test_custom_patterns_override(self):
        custom = r"\bexecute\b.*\btask\b"
        with patch("app.workflow_guard.settings") as mock_settings:
            mock_settings.workflow_patterns = custom
            patterns = _get_patterns()
            assert len(patterns) == 1
            assert patterns[0].search("execute this task")

    # AC: UIB-150 — empty config uses defaults
    def test_empty_config_uses_defaults(self):
        with patch("app.workflow_guard.settings") as mock_settings:
            mock_settings.workflow_patterns = ""
            patterns = _get_patterns()
            assert len(patterns) == len(_DEFAULT_PATTERNS)

    # AC: UIB-150 — pipe-separated multiple custom patterns
    def test_pipe_separated_patterns(self):
        custom = r"\brun\b|\bexecute\b"
        with patch("app.workflow_guard.settings") as mock_settings:
            mock_settings.workflow_patterns = custom
            patterns = _get_patterns()
            assert len(patterns) == 2


# ── HTTP endpoint integration ────────────────────────────────

class TestWorkflowEndpointIntegration:
    """UIB-152 + UIB-153: Endpoint returns refusal, does not run agent."""

    @pytest.fixture(autouse=True)
    def _client(self):
        """Create a TestClient with mocked auth."""
        import jwt as pyjwt
        from datetime import datetime, timedelta
        from fastapi.testclient import TestClient
        from app.main import app
        from app.config import settings

        payload = {
            "sub": "student1",
            "role": "student",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        self.token = pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        self.client = TestClient(app)

    # AC: UIB-152-AC1 — workflow attempt returns refusal message
    @patch("app.routers.chat_router.agent_chat")
    @patch("app.routers.chat_router.save_escalation")
    def test_workflow_returns_refusal(self, mock_esc, mock_agent):
        resp = self.client.post(
            "/chat",
            json={"message": "submit my leave form now", "session_id": "wf-1"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "can't submit" in data["answer"].lower() or "cannot submit" in data["answer"].lower() or "can\u2019t submit" in data["answer"].lower()
        assert data["sources"] == []
        # Agent must NOT have been called
        mock_agent.assert_not_called()

    # AC: UIB-152-AC5 — consistent across roles (student shown here, admin below)
    @patch("app.routers.chat_router.agent_chat")
    @patch("app.routers.chat_router.save_escalation")
    def test_workflow_blocked_for_admin_too(self, mock_esc, mock_agent):
        import jwt as pyjwt
        from datetime import datetime, timedelta
        from app.config import settings
        admin_payload = {
            "sub": "admin1", "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        admin_token = pyjwt.encode(admin_payload, settings.jwt_secret, algorithm="HS256")
        resp = self.client.post(
            "/chat",
            json={"message": "approve my registration", "session_id": "wf-2"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["sources"] == []
        mock_agent.assert_not_called()

    # AC: UIB-152-AC4 — informational query still reaches agent
    @patch("app.routers.chat_router.agent_chat", return_value={
        "answer": "The leave form is used for...",
        "session_id": "wf-3", "role": "student",
        "sources": [], "reasoning_steps": 2,
    })
    @patch("app.routers.chat_router.save_escalation")
    def test_informational_reaches_agent(self, mock_esc, mock_agent):
        resp = self.client.post(
            "/chat",
            json={"message": "What is the leave form?", "session_id": "wf-3"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200
        mock_agent.assert_called_once()

    # AC: UIB-148-AC5 / UIB-152-AC6 — escalation logged on workflow block
    @patch("app.routers.chat_router.agent_chat")
    @patch("app.routers.chat_router.save_escalation")
    def test_workflow_logged_as_escalation(self, mock_esc, mock_agent):
        self.client.post(
            "/chat",
            json={"message": "submit my leave form", "session_id": "wf-4"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        mock_esc.assert_called_once()
        args = mock_esc.call_args
        assert args[0][3] == "workflow_attempt_blocked"  # reason

    # AC: UIB-148-PROD1 — workflow intercepted before agent runs
    @patch("app.routers.chat_router.agent_chat")
    @patch("app.routers.chat_router.save_escalation")
    def test_workflow_intercepted_before_agent(self, mock_esc, mock_agent):
        """Production regression: 'submit my leave form now' must block before agent."""
        resp = self.client.post(
            "/chat",
            json={"message": "submit my leave form now", "session_id": "wf-prod1"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200
        # Agent must NEVER be called — workflow guard fires first
        mock_agent.assert_not_called()
        # Response must be the refusal, not "could not find"
        assert "could not find" not in resp.json()["answer"].lower()

    # AC: UIB-148-PROD2 — workflow patterns loaded from config
    def test_workflow_patterns_loaded_from_config(self):
        """Default patterns are non-empty and contain expected keywords."""
        patterns = _get_patterns()
        assert len(patterns) > 0
        # Verify key action verbs are covered by at least one pattern
        pattern_text = " ".join(p.pattern for p in patterns)
        for keyword in ["submit", "approve", "enroll"]:
            assert keyword in pattern_text.lower(), f"Missing keyword: {keyword}"
