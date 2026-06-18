"""
DELETE /todos/{todo_id} — delete a todo (must belong to current user). Returns 204.
Audit: writes todo_deleted synchronously.
"""
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import no_content, error

logger = logging.getLogger(__name__)
todos_table = get_table("DYNAMO_TABLE_TODOS")
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    todo_id = (event.get("pathParameters") or {}).get("todo_id")
    if not todo_id:
        return error(400, "todo_id path parameter is required")

    result = todos_table.get_item(Key={"todo_id": todo_id})
    todo = result.get("Item")

    if not todo or todo.get("owner_id") != user["id"]:
        logger.warning("Delete failed — todo %s not found for user %s", todo_id, user["username"])
        return error(404, "Todo not found.")

    todos_table.delete_item(Key={"todo_id": todo_id})
    _write_audit(user["username"], "todo_deleted", f"todo_id={todo_id}")
    logger.info("Todo %s deleted by user %s", todo_id, user["username"])
    return no_content()


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
