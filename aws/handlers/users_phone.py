"""PUT /users/change_phone_number/{phone_number} — update phone number. Returns 204."""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import no_content, error

logger = logging.getLogger(__name__)
users_table = get_table("DYNAMO_TABLE_USERS")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    phone_number = (event.get("pathParameters") or {}).get("phone_number")
    if not phone_number:
        return error(400, "phone_number path parameter is required")

    result = users_table.get_item(Key={"username": user["username"]})
    if not result.get("Item"):
        return error(404, "User not found")

    users_table.update_item(
        Key={"username": user["username"]},
        UpdateExpression="SET #pn = :pn",
        ExpressionAttributeNames={"#pn": "phone_number"},
        ExpressionAttributeValues={":pn": phone_number},
    )
    logger.info("Phone number updated for user %s", user["username"])
    return no_content()
