"""
DynamoDB-backed feedback store for UC-15 (User Feedback).
Table: hm-feedback (configurable via settings.feedback_table).
"""
import uuid
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.config import settings

log = logging.getLogger(__name__)

_table = None


def _get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)
        _table = dynamodb.Table(settings.feedback_table)
    return _table


def init_feedback_table() -> None:
    """Create the feedback DynamoDB table if it does not already exist."""
    global _table
    dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)
    try:
        dynamodb.meta.client.describe_table(TableName=settings.feedback_table)
        log.info("DynamoDB table '%s' already exists.", settings.feedback_table)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            table = dynamodb.create_table(
                TableName=settings.feedback_table,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            log.info("Created DynamoDB table '%s'.", settings.feedback_table)
        else:
            raise
    _table = dynamodb.Table(settings.feedback_table)


def save_feedback(
    session_id: str,
    message: str,
    response_preview: str,
    rating: str,
    comment: str,
    user_role: str,
) -> str:
    """Save a feedback record. Returns the generated UUID."""
    feedback_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    _get_table().put_item(Item={
        "id": feedback_id,
        "session_id": session_id,
        "message": message,
        "response_preview": response_preview[:200],
        "rating": rating,
        "comment": comment or "",
        "user_role": user_role,
        "timestamp": now,
        "created_at": now,
    })
    return feedback_id


def get_all_feedback() -> list[dict]:
    """Return all feedback records, most recent first."""
    resp = _get_table().scan()
    items = resp.get("Items", [])
    items.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
    return items


def get_feedback_by_session(session_id: str) -> list[dict]:
    """Return feedback records for a specific session."""
    all_items = get_all_feedback()
    return [i for i in all_items if i.get("session_id") == session_id]
