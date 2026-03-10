import json
import uuid
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.config import settings

log = logging.getLogger(__name__)

_table = None


def _get_table():
    """Return the cached DynamoDB Table resource."""
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)
        _table = dynamodb.Table(settings.dynamo_table)
    return _table


def init_db() -> None:
    """Create the DynamoDB table if it does not already exist."""
    global _table
    dynamodb = boto3.resource("dynamodb", region_name=settings.dynamo_region)

    try:
        dynamodb.meta.client.describe_table(TableName=settings.dynamo_table)
        log.info("DynamoDB table '%s' already exists.", settings.dynamo_table)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            table = dynamodb.create_table(
                TableName=settings.dynamo_table,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
            log.info("Created DynamoDB table '%s'.", settings.dynamo_table)
        else:
            raise

    _table = dynamodb.Table(settings.dynamo_table)
    log.info("Documents DB initialised (DynamoDB).")


def _item_to_dict(item: dict) -> dict:
    """Convert a DynamoDB item to a plain dict with correct types."""
    d = {
        "id": item["id"],
        "filename": item.get("filename", ""),
        "display_name": item.get("display_name", ""),
        "allowed_roles": item.get("allowed_roles", []),
        "status": item.get("status", "UPLOADED"),
        "chunk_count": int(item.get("chunk_count", 0)),
        "file_size": int(item.get("file_size", 0)),
        "uploaded_at": item.get("uploaded_at", ""),
        "ingested_at": item.get("ingested_at"),
        "error_msg": item.get("error_msg"),
    }
    # allowed_roles may be stored as JSON string (legacy) or list
    if isinstance(d["allowed_roles"], str):
        d["allowed_roles"] = json.loads(d["allowed_roles"])
    return d


def register_document(
    filename: str,
    display_name: str,
    allowed_roles: list[str],
    file_size: int,
) -> str:
    doc_id = str(uuid.uuid4())
    _get_table().put_item(Item={
        "id": doc_id,
        "filename": filename,
        "display_name": display_name,
        "allowed_roles": allowed_roles,
        "status": "UPLOADED",
        "chunk_count": 0,
        "file_size": file_size,
        "uploaded_at": datetime.utcnow().isoformat(),
        "ingested_at": None,
        "error_msg": None,
    })
    return doc_id


def get_all_documents() -> list[dict]:
    resp = _get_table().scan()
    items = resp.get("Items", [])
    docs = [_item_to_dict(i) for i in items]
    docs.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)
    return docs


def get_pending_documents() -> list[dict]:
    return [d for d in get_all_documents() if d["status"] == "UPLOADED"]


def get_ingested_documents() -> list[dict]:
    return [d for d in get_all_documents() if d["status"] == "INGESTED"]


def get_allowed_roles_map() -> dict[str, list[str]]:
    """Returns { filename: [roles] } for all INGESTED documents."""
    return {
        d["filename"]: d["allowed_roles"]
        for d in get_all_documents()
        if d["status"] == "INGESTED"
    }


def set_status_ingesting(doc_id: str) -> None:
    _update_status(doc_id, "INGESTING")


def set_status_ingested(doc_id: str, chunk_count: int) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s, chunk_count = :c, ingested_at = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "INGESTED",
            ":c": chunk_count,
            ":t": datetime.utcnow().isoformat(),
        },
    )


def set_status_failed(doc_id: str, error: str) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s, error_msg = :e",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "FAILED", ":e": error},
    )


def delete_document(doc_id: str) -> None:
    _get_table().delete_item(Key={"id": doc_id})


def _update_status(doc_id: str, status: str) -> None:
    _get_table().update_item(
        Key={"id": doc_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )
