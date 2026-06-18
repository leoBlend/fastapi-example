"""
GET /admin/audit — list all audit log entries ordered by timestamp desc. Admin only.

Queries TimestampIndex GSI on TodoApp-AuditLog:
    PK = entity_type = "AUDIT", sorted by SK = timestamp descending.
"""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.auth_utils import get_current_user_from_event
from shared.dynamo_client import get_table
from shared.response import ok, error

logger = logging.getLogger(__name__)
audit_table = get_table("DYNAMO_TABLE_AUDIT")


def handler(event, context):
    try:
        user = get_current_user_from_event(event)
    except ValueError as e:
        return error(401, str(e))

    if user.get("user_role") != "admin":
        return error(401, "Admins only")

    result = audit_table.query(
        IndexName="TimestampIndex",
        KeyConditionExpression="entity_type = :et",
        ExpressionAttributeValues={":et": "AUDIT"},
        ScanIndexForward=False,
    )
    entries = result.get("Items", [])
    logger.info("Admin %s fetched audit log (%d entries)", user["username"], len(entries))
    return ok(entries)
