"""
Tests for DynamoDB-backed document_store.

Uses moto to mock AWS DynamoDB — no real AWS calls are made.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from moto import mock_aws

# Patch settings before importing document_store
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")


@pytest.fixture(autouse=True)
def dynamo_env():
    """Run every test inside a moto mock with a fresh DynamoDB table."""
    with mock_aws():
        import app.document_store as ds
        # Reset cached table so each test gets a fresh one
        ds._table = None
        ds.init_db()
        yield ds
        ds._table = None


# ═══════════════════════════════════════════════════════════════
# init_db
# ═══════════════════════════════════════════════════════════════

class TestInitDB:
    def test_init_creates_table(self, dynamo_env):
        ds = dynamo_env
        import boto3
        client = boto3.client("dynamodb", region_name="ap-south-1")
        tables = client.list_tables()["TableNames"]
        assert "hm-documents" in tables

    def test_init_idempotent(self, dynamo_env):
        ds = dynamo_env
        # calling init_db again should not raise
        ds.init_db()


# ═══════════════════════════════════════════════════════════════
# register_document
# ═══════════════════════════════════════════════════════════════

class TestRegisterDocument:
    def test_returns_string_id(self, dynamo_env):
        ds = dynamo_env
        doc_id = ds.register_document("a.pdf", "Doc A", ["admin"], 100)
        assert isinstance(doc_id, str)
        assert len(doc_id) == 36  # UUID format

    def test_document_retrievable_after_register(self, dynamo_env):
        ds = dynamo_env
        doc_id = ds.register_document("b.pdf", "Doc B", ["admin", "student"], 200)
        docs = ds.get_all_documents()
        assert any(d["id"] == doc_id for d in docs)
        doc = next(d for d in docs if d["id"] == doc_id)
        assert doc["filename"] == "b.pdf"
        assert doc["display_name"] == "Doc B"
        assert doc["allowed_roles"] == ["admin", "student"]
        assert doc["status"] == "UPLOADED"
        assert doc["file_size"] == 200
        assert doc["chunk_count"] == 0

    def test_multiple_registers(self, dynamo_env):
        ds = dynamo_env
        ds.register_document("x.pdf", "X", ["admin"], 10)
        ds.register_document("y.pdf", "Y", ["admin"], 20)
        ds.register_document("z.pdf", "Z", ["admin"], 30)
        assert len(ds.get_all_documents()) == 3


# ═══════════════════════════════════════════════════════════════
# get helpers
# ═══════════════════════════════════════════════════════════════

class TestGetHelpers:
    def test_get_pending_documents(self, dynamo_env):
        ds = dynamo_env
        ds.register_document("a.pdf", "A", ["admin"], 10)
        d2 = ds.register_document("b.pdf", "B", ["admin"], 20)
        ds.set_status_ingested(d2, 5)
        pending = ds.get_pending_documents()
        assert len(pending) == 1
        assert pending[0]["filename"] == "a.pdf"

    def test_get_ingested_documents(self, dynamo_env):
        ds = dynamo_env
        d1 = ds.register_document("a.pdf", "A", ["admin"], 10)
        ds.set_status_ingested(d1, 5)
        ingested = ds.get_ingested_documents()
        assert len(ingested) == 1
        assert ingested[0]["chunk_count"] == 5

    def test_get_allowed_roles_map(self, dynamo_env):
        ds = dynamo_env
        d1 = ds.register_document("a.pdf", "A", ["admin", "faculty"], 10)
        ds.set_status_ingested(d1, 5)
        ds.register_document("b.pdf", "B", ["student"], 20)  # still UPLOADED
        roles_map = ds.get_allowed_roles_map()
        assert "a.pdf" in roles_map
        assert roles_map["a.pdf"] == ["admin", "faculty"]
        assert "b.pdf" not in roles_map

    def test_get_all_sorted_by_uploaded_at(self, dynamo_env):
        ds = dynamo_env
        ds.register_document("first.pdf", "First", ["admin"], 10)
        ds.register_document("second.pdf", "Second", ["admin"], 20)
        docs = ds.get_all_documents()
        assert len(docs) == 2
        # Most recent first
        assert docs[0]["filename"] == "second.pdf"


# ═══════════════════════════════════════════════════════════════
# Status transitions
# ═══════════════════════════════════════════════════════════════

class TestStatusTransitions:
    def test_set_status_ingesting(self, dynamo_env):
        ds = dynamo_env
        d = ds.register_document("a.pdf", "A", ["admin"], 10)
        ds.set_status_ingesting(d)
        doc = next(x for x in ds.get_all_documents() if x["id"] == d)
        assert doc["status"] == "INGESTING"

    def test_set_status_ingested(self, dynamo_env):
        ds = dynamo_env
        d = ds.register_document("a.pdf", "A", ["admin"], 10)
        ds.set_status_ingested(d, 42)
        doc = next(x for x in ds.get_all_documents() if x["id"] == d)
        assert doc["status"] == "INGESTED"
        assert doc["chunk_count"] == 42
        assert doc["ingested_at"] is not None

    def test_set_status_failed(self, dynamo_env):
        ds = dynamo_env
        d = ds.register_document("a.pdf", "A", ["admin"], 10)
        ds.set_status_failed(d, "bad pdf")
        doc = next(x for x in ds.get_all_documents() if x["id"] == d)
        assert doc["status"] == "FAILED"
        assert doc["error_msg"] == "bad pdf"

    def test_full_lifecycle(self, dynamo_env):
        ds = dynamo_env
        d = ds.register_document("a.pdf", "A", ["admin"], 10)
        assert ds.get_all_documents()[0]["status"] == "UPLOADED"
        ds.set_status_ingesting(d)
        assert ds.get_all_documents()[0]["status"] == "INGESTING"
        ds.set_status_ingested(d, 10)
        assert ds.get_all_documents()[0]["status"] == "INGESTED"


# ═══════════════════════════════════════════════════════════════
# delete
# ═══════════════════════════════════════════════════════════════

class TestDeleteDocument:
    def test_delete_removes_item(self, dynamo_env):
        ds = dynamo_env
        d = ds.register_document("a.pdf", "A", ["admin"], 10)
        assert len(ds.get_all_documents()) == 1
        ds.delete_document(d)
        assert len(ds.get_all_documents()) == 0

    def test_delete_nonexistent_is_noop(self, dynamo_env):
        ds = dynamo_env
        ds.delete_document("nonexistent-id")  # should not raise
