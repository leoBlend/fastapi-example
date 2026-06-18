"""
GET /admin/todo — list ALL todos across all users. Admin role required.

Uses a DynamoDB Scan — acceptable for a learning/low-volume app.
At scale this should use a GSI with a constant partition key (entity_type="TODO").
"""
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

    if user.get("user_role") != "admin":
        return error(401, "Admins only")

    result = todos_table.scan()
    todos = result.get("Items", [])
    logger.info("Admin %s fetched all todos (%d)", user["username"], len(todos))
    return ok(todos)
