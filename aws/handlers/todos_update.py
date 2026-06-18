"""PUT /todos/{todo_id} — update a todo (must belong to current user). Returns 204."""
import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import no_content, error
from shared.validation import validate_todo_request

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

    try:
        body = json.loads(event.get("body") or "{}")
        data = validate_todo_request(body)
    except (json.JSONDecodeError, ValueError) as e:
        return error(422, str(e))

    result = todos_table.get_item(Key={"todo_id": todo_id})
    todo = result.get("Item")

    if not todo or todo.get("owner_id") != user["id"]:
        logger.warning("Update failed — todo %s not found for user %s", todo_id, user["username"])
        return error(404, "Todo not found.")

    todos_table.update_item(
        Key={"todo_id": todo_id},
        UpdateExpression="SET #t = :t, #d = :d, #p = :p, #c = :c",
        ExpressionAttributeNames={"#t": "title", "#d": "description", "#p": "priority", "#c": "complete"},
        ExpressionAttributeValues={":t": data["title"], ":d": data["description"], ":p": data["priority"], ":c": data["complete"]},
    )
    logger.info("Todo %s updated by user %s", todo_id, user["username"])
    return no_content()
