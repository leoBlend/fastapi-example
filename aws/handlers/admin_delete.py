"""DELETE /admin/todo/{todo_id} — admin delete any todo. Returns 204."""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import no_content, error

logger = logging.getLogger(__name__)
todos_table = get_table("DYNAMO_TABLE_TODOS")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    if user.get("user_role") != "admin":
        return error(401, "Admins only")

    todo_id = (event.get("pathParameters") or {}).get("todo_id")
    if not todo_id:
        return error(400, "todo_id path parameter is required")

    result = todos_table.get_item(Key={"todo_id": todo_id})
    if not result.get("Item"):
        logger.warning("Admin %s tried to delete non-existent todo %s", user["username"], todo_id)
        return error(404, "Todo not found.")

    todos_table.delete_item(Key={"todo_id": todo_id})
    logger.info("Admin %s deleted todo %s", user["username"], todo_id)
    return no_content()
