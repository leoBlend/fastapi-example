"""
POST /todo — create a new todo.
Audit: writes todo_created to TodoApp-AuditLog synchronously.
"""
import json
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import created, error
from shared.validation import validate_todo_request

logger = logging.getLogger(__name__)
todos_table = get_table("DYNAMO_TABLE_TODOS")
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    try:
        body = json.loads(event.get("body") or "{}")
        data = validate_todo_request(body)
    except (json.JSONDecodeError, ValueError) as e:
        return error(422, str(e))

    todo_id = str(uuid.uuid4())
    item = {
        "todo_id": todo_id,
        "owner_id": user["id"],
        "title": data["title"],
        "description": data["description"],
        "priority": data["priority"],
        "complete": data["complete"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    todos_table.put_item(Item=item)

    _write_audit(user["username"], "todo_created", f"title={data['title']}, priority={data['priority']}")
    logger.info("Todo created by user %s: '%s'", user["username"], data["title"])

    return created(item)


def _write_audit(username: str, action: str, detail: str = "") -> None:
    try:
        audit_table.put_item(Item={
            "audit_id": str(uuid.uuid4()),
            "entity_type": "AUDIT",
            "username": username,
            "action": action,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("Failed to write audit log for action '%s' by '%s'", action, username)
