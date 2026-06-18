"""GET /users/ — return the authenticated user's profile."""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import ok, error

logger = logging.getLogger(__name__)
users_table = get_table("DYNAMO_TABLE_USERS")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    # JWT carries user_id; look up by UserIdIndex GSI
    result = users_table.query(
        IndexName="UserIdIndex",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user["id"]},
    )
    items = result.get("Items", [])
    if not items:
        return error(404, "User not found")

    profile = {k: v for k, v in items[0].items() if k != "hashed_password"}
    return ok(profile)
