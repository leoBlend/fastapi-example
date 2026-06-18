"""GET /todos/{todo_id} — get a single todo (must belong to current user)."""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import ok, error

logger = logging.getLogger(__name__)
todos_table = get_table("DYNAMO_TABLE_TODOS")


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

    if not todo:
        logger.warning("Todo %s not found for user %s", todo_id, user["username"])
        return error(404, "Todo not found.")

    # Ownership check — users can only read their own todos
    if todo.get("owner_id") != user["id"]:
        return error(404, "Todo not found.")

    return ok(todo)
