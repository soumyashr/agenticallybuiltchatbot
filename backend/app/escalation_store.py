"""
DynamoDB-backed escalation store for UC-10 (Escalate Unanswered Queries).
Table: hm-escalations (configurable via settings.escalation_table).
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
        _table = dynamodb.Table(settings.escalation_table)
    return _table


def init_escalation_table() -> None:
    """Create the escalation DynamoDB table if it does not already exist."""
    global _table
    dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)
    try:
        dynamodb.meta.client.describe_table(TableName=settings.escalation_table)
        log.info("DynamoDB table '%s' already exists.", settings.escalation_table)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            table = dynamodb.create_table(
                TableName=settings.escalation_table,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            log.info("Created DynamoDB table '%s'.", settings.escalation_table)
        else:
            raise
    _table = dynamodb.Table(settings.escalation_table)


def save_escalation(
    session_id: str,
    query: str,
    user_role: str,
    reason: str,
) -> str:
    """Save an escalation record. Returns the generated UUID."""
    esc_id = str(uuid.uuid4())
    _get_table().put_item(Item={
        "id": esc_id,
        "session_id": session_id,
        "query": query,
        "user_role": user_role,
        "timestamp": datetime.utcnow().isoformat(),
        "reason": reason,
        "notified": False,
    })
    return esc_id


def get_all_escalations() -> list[dict]:
    """Return all escalation records, most recent first."""
    resp = _get_table().scan()
    items = resp.get("Items", [])
    items.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
    return items


def mark_escalation_notified(esc_id: str) -> None:
    """Mark an escalation as notified (Slack sent)."""
    _get_table().update_item(
        Key={"id": esc_id},
        UpdateExpression="SET notified = :n",
        ExpressionAttributeValues={":n": True},
    )
