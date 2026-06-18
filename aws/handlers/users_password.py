"""
PUT /users/password — change the authenticated user's password. Returns 204.
Audit: writes password_changed synchronously.
"""
import json
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event, verify_password, hash_password
from shared.dynamo_client import get_table
from shared.response import no_content, error
from shared.validation import validate_user_verification

logger = logging.getLogger(__name__)
users_table = get_table("DYNAMO_TABLE_USERS")
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    try:
        body = json.loads(event.get("body") or "{}")
        data = validate_user_verification(body)
    except (json.JSONDecodeError, ValueError) as e:
        return error(422, str(e))

    # Fetch user record by username (main PK)
    result = users_table.get_item(Key={"username": user["username"]})
    user_item = result.get("Item")
    if not user_item:
        return error(404, "User not found")

    if not verify_password(data["password"], user_item["hashed_password"]):
        logger.warning("Password change failed for user %s — wrong current password", user["username"])
        return error(401, "Error on password change")

    users_table.update_item(
        Key={"username": user["username"]},
        UpdateExpression="SET #hp = :hp",
        ExpressionAttributeNames={"#hp": "hashed_password"},
        ExpressionAttributeValues={":hp": hash_password(data["new_password"])},
    )

    _write_audit(user["username"], "password_changed")
    logger.info("Password changed for user %s", user["username"])
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
