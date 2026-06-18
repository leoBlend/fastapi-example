"""
POST /auth/token
Authenticate user and return JWT.  No authentication required.

The original FastAPI endpoint uses OAuth2PasswordRequestForm which expects
application/x-www-form-urlencoded body (username=...&password=...).
We parse that format here using urllib.parse — no extra dependency needed.
"""
import logging
import sys
import os
import uuid
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import create_access_token, verify_password
from shared.dynamo_client import get_table
from shared.response import ok, error

logger = logging.getLogger(__name__)
users_table = get_table("DYNAMO_TABLE_USERS")
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    body_raw = event.get("body") or ""
    content_type = (event.get("headers") or {}).get("Content-Type", "")

    if "application/x-www-form-urlencoded" in content_type or "=" in body_raw:
        parsed = urllib.parse.parse_qs(body_raw)
        username = (parsed.get("username") or [""])[0]
        password = (parsed.get("password") or [""])[0]
    else:
        # Also accept JSON for convenience during local testing
        import json
        try:
            data = json.loads(body_raw or "{}")
            username = data.get("username", "")
            password = data.get("password", "")
        except json.JSONDecodeError:
            return error(422, "Invalid request body")

    if not username or not password:
        return error(422, "username and password are required")

    result = users_table.get_item(Key={"username": username})
    user = result.get("Item")

    if not user or not verify_password(password, user["hashed_password"]):
        logger.warning("Failed login attempt for username: %s", username)
        return error(401, "Could not retrieve user.")

    if not user.get("is_active", True):
        return error(401, "Account is inactive")

    token = create_access_token(username, user["user_id"], user["role"])
    _write_audit(username, "user_login")
    logger.info("User logged in: %s", username)

    return ok({"access_token": token, "token_type": "bearer"})


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
