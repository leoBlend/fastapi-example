"""GET / — list all todos for the authenticated user."""
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

    result = todos_table.query(
        IndexName="OwnerIndex",
        KeyConditionExpression="owner_id = :owner_id",
        ExpressionAttributeValues={":owner_id": user["id"]},
        ScanIndexForward=False,
    )
    todos = result.get("Items", [])
    logger.info("User %s fetched %d todos", user["username"], len(todos))
    return ok(todos)
