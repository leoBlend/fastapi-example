"""
POST /auth/
Register a new user.  No authentication required.
Audit: writes user_registered to TodoApp-AuditLog synchronously.
       (FastAPI used BackgroundTasks; Lambda has no after-response hook.)
"""
import json
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import hash_password
from shared.dynamo_client import get_table
from shared.response import created, error
from shared.validation import validate_create_user_request

logger = logging.getLogger(__name__)
users_table = get_table("DYNAMO_TABLE_USERS")
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        data = validate_create_user_request(body)
    except (json.JSONDecodeError, ValueError) as e:
        return error(422, str(e))

    # Check duplicate username
    existing = users_table.get_item(Key={"username": data["username"]})
    if existing.get("Item"):
        logger.warning("Registration failed — duplicate username: %s", data["username"])
        return error(409, "Username or email already registered")

    # Check duplicate email via GSI
    email_results = users_table.query(
        IndexName="EmailIndex",
        KeyConditionExpression="email = :email",
        ExpressionAttributeValues={":email": data["email"]},
    )
    if email_results.get("Items"):
        logger.warning("Registration failed — duplicate email: %s", data["email"])
        return error(409, "Username or email already registered")

    user_id = str(uuid.uuid4())
    item = {
        "username": data["username"],
        "user_id": user_id,
        "email": data["email"],
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "hashed_password": hash_password(data["password"]),
        "is_active": True,
        "role": data["role"],
        "phone_number": data["phone_number"],
    }
    users_table.put_item(Item=item)

    _write_audit(data["username"], "user_registered", f"email={data['email']}")
    logger.info("New user registered: %s", data["username"])

    item_out = {k: v for k, v in item.items() if k != "hashed_password"}
    return created(item_out)


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
