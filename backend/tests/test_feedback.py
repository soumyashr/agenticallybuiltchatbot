"""
Tests for UC-15 Feedback — POST /feedback + GET /admin/feedback + DynamoDB store.
Uses moto to mock DynamoDB (same pattern as test_document_store.py).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import jwt as pyjwt
from moto import mock_aws

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")

from app.config import settings


def _make_token(role: str, username: str = "testuser", expired: bool = False) -> str:
    delta = timedelta(hours=-1) if expired else timedelta(hours=8)
    payload = {"sub": username, "role": role, "exp": datetime.utcnow() + delta}
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture(autouse=True)
def dynamo_env():
    """Run every test inside moto mock with fresh feedback + escalation tables."""
    with mock_aws():
        import app.feedback_store as fs
        import app.escalation_store as es
        fs._table = None
        es._table = None
        fs.init_feedback_table()
        es.init_escalation_table()
        yield fs
        fs._table = None
        es._table = None


# ═══════════════════════════════════════════════════════════════
# DynamoDB store unit tests
# ═══════════════════════════════════════════════════════════════


class TestFeedbackStore:
    def test_save_returns_uuid(self, dynamo_env):
        fs = dynamo_env
        fid = fs.save_feedback("s1", "query", "response text", "positive", "", "student")
        assert isinstance(fid, str)
        assert len(fid) == 36

    def test_saved_item_has_correct_fields(self, dynamo_env):
        fs = dynamo_env
        fid = fs.save_feedback("s1", "hello?", "The answer is...", "negative", "not helpful", "faculty")
        items = fs.get_all_feedback()
        assert len(items) == 1
        item = items[0]
        assert item["id"] == fid
        assert item["session_id"] == "s1"
        assert item["message"] == "hello?"
        assert item["response_preview"] == "The answer is..."
        assert item["rating"] == "negative"
        assert item["comment"] == "not helpful"
        assert item["user_role"] == "faculty"
        assert "timestamp" in item
        assert "created_at" in item

    def test_get_feedback_by_session(self, dynamo_env):
        fs = dynamo_env
        fs.save_feedback("s1", "q1", "r1", "positive", "", "admin")
        fs.save_feedback("s2", "q2", "r2", "negative", "", "admin")
        fs.save_feedback("s1", "q3", "r3", "positive", "", "admin")
        result = fs.get_feedback_by_session("s1")
        assert len(result) == 2

    def test_response_preview_truncated(self, dynamo_env):
        fs = dynamo_env
        long_response = "x" * 500
        fs.save_feedback("s1", "q", long_response, "positive", "", "admin")
        items = fs.get_all_feedback()
        assert len(items[0]["response_preview"]) == 200

    def test_comment_default_empty(self, dynamo_env):
        fs = dynamo_env
        fs.save_feedback("s1", "q", "r", "positive", "", "student")
        items = fs.get_all_feedback()
        assert items[0]["comment"] == ""


# ═══════════════════════════════════════════════════════════════
# API endpoint tests (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════


class TestFeedbackEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_save_positive_feedback(self, client, dynamo_env):
        token = _make_token("student")
        resp = client.post("/feedback", json={
            "session_id": "s1", "message": "What is ML?",
            "response_preview": "ML is...", "rating": "positive",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["status"] == "saved"

    def test_save_negative_feedback(self, client, dynamo_env):
        token = _make_token("faculty")
        resp = client.post("/feedback", json={
            "session_id": "s1", "message": "q",
            "response_preview": "r", "rating": "negative",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_feedback_requires_auth(self, client):
        resp = client.post("/feedback", json={
            "session_id": "s1", "message": "q",
            "response_preview": "r", "rating": "positive",
        })
        assert resp.status_code == 401

    def test_invalid_rating_rejected(self, client, dynamo_env):
        token = _make_token("student")
        resp = client.post("/feedback", json={
            "session_id": "s1", "message": "q",
            "response_preview": "r", "rating": "maybe",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422

    def test_admin_can_view_feedback(self, client, dynamo_env):
        fs = dynamo_env
        fs.save_feedback("s1", "q", "r", "positive", "", "admin")
        token = _make_token("admin", "admin")
        resp = client.get("/admin/feedback",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_student_cannot_view_feedback(self, client, dynamo_env):
        token = _make_token("student")
        resp = client.get("/admin/feedback",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_comment_is_optional(self, client, dynamo_env):
        token = _make_token("student")
        resp = client.post("/feedback", json={
            "session_id": "s1", "message": "q",
            "response_preview": "r", "rating": "positive",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
