"""
Tests for UC-10 Escalation — save_escalation, Slack webhook, admin endpoint.
Uses moto to mock DynamoDB (same pattern as test_document_store.py).
"""
from __future__ import annotations

import os
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import jwt as pyjwt
from moto import mock_aws

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")

from app.config import settings
from app.models import Role
from app.agent import (
    _sessions,
    _is_fallback_response,
    _has_sources,
    MAX_AGENT_RETRIES,
)


def _make_token(role: str, username: str = "testuser", expired: bool = False) -> str:
    delta = timedelta(hours=-1) if expired else timedelta(hours=8)
    payload = {"sub": username, "role": role, "exp": datetime.utcnow() + delta}
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _make_step(observation: str):
    action = MagicMock()
    return (action, observation)


@pytest.fixture(autouse=True)
def dynamo_env():
    """Run every test inside moto mock with fresh escalation + feedback tables."""
    with mock_aws():
        import app.escalation_store as es
        import app.feedback_store as fs
        es._table = None
        fs._table = None
        es.init_escalation_table()
        fs.init_feedback_table()
        yield es
        es._table = None
        fs._table = None


# ═══════════════════════════════════════════════════════════════
# DynamoDB escalation store unit tests
# ═══════════════════════════════════════════════════════════════


class TestEscalationStore:
    def test_save_returns_uuid(self, dynamo_env):
        es = dynamo_env
        eid = es.save_escalation("s1", "query", "student", "no_answer_found")
        assert isinstance(eid, str)
        assert len(eid) == 36

    def test_saved_item_has_correct_fields(self, dynamo_env):
        es = dynamo_env
        eid = es.save_escalation("s1", "What is X?", "faculty", "agent_parse_failure")
        items = es.get_all_escalations()
        assert len(items) == 1
        item = items[0]
        assert item["id"] == eid
        assert item["session_id"] == "s1"
        assert item["query"] == "What is X?"
        assert item["user_role"] == "faculty"
        assert item["reason"] == "agent_parse_failure"
        assert item["notified"] is False
        assert "timestamp" in item

    def test_mark_notified(self, dynamo_env):
        es = dynamo_env
        eid = es.save_escalation("s1", "q", "admin", "no_answer_found")
        es.mark_escalation_notified(eid)
        items = es.get_all_escalations()
        assert items[0]["notified"] is True


# ═══════════════════════════════════════════════════════════════
# Escalation triggered by agent chat() logic
# ═══════════════════════════════════════════════════════════════


class TestEscalationLogic:
    @pytest.fixture(autouse=True)
    def cleanup_sessions(self):
        _sessions.clear()
        yield
        _sessions.clear()

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.save_escalation")
    @patch("app.agent._notify_slack", new_callable=AsyncMock)
    def test_escalation_saved_on_no_answer(
        self, mock_slack, mock_save_esc, mock_tools, mock_llm
    ):
        """Fallback phrase + no sources → escalation saved with reason no_answer_found."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_save_esc.return_value = "esc-123"

        call_count = 0

        def fake_invoke(inputs):
            nonlocal call_count
            call_count += 1
            return {
                "output": "I could not find information on this topic.",
                "intermediate_steps": [],
            }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = fake_invoke
            mock_create.return_value = executor
            with patch("app.agent._direct_faiss_search", new_callable=AsyncMock) as mock_fallback:
                mock_fallback.return_value = {
                    "answer": "Fallback answer",
                    "sources": [], "reasoning_steps": 1,
                    "fallback_used": True, "error_type": None,
                }
                asyncio.get_event_loop().run_until_complete(
                    __import__("app.agent", fromlist=["chat"]).chat(
                        "What is quantum?", "esc-session-1", Role.student
                    )
                )

        # Escalation saved at least once (on parse failure path + on exhausted retries)
        assert mock_save_esc.call_count >= 1

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.save_escalation")
    @patch("app.agent._notify_slack", new_callable=AsyncMock)
    @patch("app.agent._direct_faiss_search", new_callable=AsyncMock)
    def test_escalation_saved_on_parse_failure(
        self, mock_fallback, mock_slack, mock_save_esc, mock_tools, mock_llm
    ):
        """Exhaust all retries → escalation saved with reason agent_parse_failure."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_save_esc.return_value = "esc-456"
        mock_fallback.return_value = {
            "answer": "Fallback", "sources": [], "reasoning_steps": 0,
            "fallback_used": True, "error_type": None,
        }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = MagicMock(side_effect=TimeoutError("timed out"))
            mock_create.return_value = executor
            asyncio.get_event_loop().run_until_complete(
                __import__("app.agent", fromlist=["chat"]).chat(
                    "test", "esc-parse-session", Role.student
                )
            )

        # Should be called with reason "agent_parse_failure" on final exhaustion
        reasons = [call.args[3] if len(call.args) > 3 else call.kwargs.get("reason", "")
                   for call in mock_save_esc.call_args_list]
        assert "agent_parse_failure" in reasons

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.save_escalation")
    @patch("app.agent._notify_slack", new_callable=AsyncMock)
    def test_slack_notification_sent_when_webhook_configured(
        self, mock_slack, mock_save_esc, mock_tools, mock_llm
    ):
        """When slack_webhook_url is set, _notify_slack is called."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_save_esc.return_value = "esc-789"

        with patch("app.agent._create_executor") as mock_create, \
             patch("app.agent.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.escalation_enabled = True
            mock_settings.ai_provider = "openai"
            mock_settings.llm_model = "gpt-4o"
            mock_settings.llm_temperature = 0.1
            mock_settings.openai_api_key = "sk-test"
            mock_settings.agent_system_prompt = "test"
            mock_settings.agent_max_iterations = 5
            mock_settings.clarify_ambiguous_prompt = ""
            mock_settings.irrelevant_query_response = ""
            mock_settings.max_history_turns = 10

            executor = MagicMock()
            executor.invoke = MagicMock(return_value={
                "output": "I could not find information.",
                "intermediate_steps": [],
            })
            mock_create.return_value = executor

            with patch("app.agent._direct_faiss_search", new_callable=AsyncMock) as mock_fb:
                mock_fb.return_value = {
                    "answer": "Fallback", "sources": [], "reasoning_steps": 0,
                    "fallback_used": True, "error_type": None,
                }
                asyncio.get_event_loop().run_until_complete(
                    __import__("app.agent", fromlist=["chat"]).chat(
                        "question", "slack-session", Role.student
                    )
                )

        assert mock_slack.call_count >= 1

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.save_escalation")
    @patch("app.agent._notify_slack", new_callable=AsyncMock)
    @patch("app.agent._direct_faiss_search", new_callable=AsyncMock)
    def test_slack_failure_does_not_break_chat(
        self, mock_fallback, mock_slack, mock_save_esc, mock_tools, mock_llm
    ):
        """If _notify_slack raises, chat() still returns a valid response."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_save_esc.return_value = "esc-fail"
        mock_slack.side_effect = Exception("Slack is down")
        mock_fallback.return_value = {
            "answer": "Fallback answer", "sources": [],
            "reasoning_steps": 0, "fallback_used": True, "error_type": None,
        }

        with patch("app.agent._create_executor") as mock_create:
            executor = MagicMock()
            executor.invoke = MagicMock(return_value={
                "output": "I could not find information.",
                "intermediate_steps": [],
            })
            mock_create.return_value = executor
            result = asyncio.get_event_loop().run_until_complete(
                __import__("app.agent", fromlist=["chat"]).chat(
                    "test", "slack-fail-session", Role.student
                )
            )

        assert "answer" in result  # Chat still returned a valid result

    @patch("app.agent._build_llm")
    @patch("app.agent.make_search_tools")
    @patch("app.agent.save_escalation")
    @patch("app.agent._notify_slack", new_callable=AsyncMock)
    def test_no_slack_when_webhook_not_configured(
        self, mock_slack, mock_save_esc, mock_tools, mock_llm
    ):
        """Empty SLACK_WEBHOOK_URL → no Slack call made."""
        mock_llm.return_value = MagicMock()
        mock_tools.return_value = [MagicMock(name="semantic_search")]
        mock_save_esc.return_value = "esc-no-slack"

        with patch("app.agent._create_executor") as mock_create, \
             patch("app.agent.settings") as mock_settings:
            mock_settings.slack_webhook_url = ""
            mock_settings.escalation_enabled = True
            mock_settings.ai_provider = "openai"
            mock_settings.llm_model = "gpt-4o"
            mock_settings.llm_temperature = 0.1
            mock_settings.openai_api_key = "sk-test"
            mock_settings.agent_system_prompt = "test"
            mock_settings.agent_max_iterations = 5
            mock_settings.clarify_ambiguous_prompt = ""
            mock_settings.irrelevant_query_response = ""
            mock_settings.max_history_turns = 10

            executor = MagicMock()
            executor.invoke = MagicMock(return_value={
                "output": "The syllabus covers ML topics.",
                "intermediate_steps": [
                    _make_step("[1] Source: doc.pdf, Page: 1\nContent")
                ],
            })
            mock_create.return_value = executor

            result = asyncio.get_event_loop().run_until_complete(
                __import__("app.agent", fromlist=["chat"]).chat(
                    "What is ML?", "no-slack-session", Role.student
                )
            )

        mock_slack.assert_not_called()
        assert "ML topics" in result["answer"]


# ═══════════════════════════════════════════════════════════════
# Admin endpoint tests
# ═══════════════════════════════════════════════════════════════


class TestEscalationEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_admin_can_view_escalations(self, client, dynamo_env):
        es = dynamo_env
        es.save_escalation("s1", "query", "student", "no_answer_found")
        token = _make_token("admin", "admin")
        resp = client.get("/admin/escalations",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["query"] == "query"

    def test_student_cannot_view_escalations(self, client, dynamo_env):
        token = _make_token("student")
        resp = client.get("/admin/escalations",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
