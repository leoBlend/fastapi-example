"""
DynamoDB client factory.

USE_LOCAL_DYNAMO=true  → returns a LocalDynamoTable (JSON-file simulator)
USE_LOCAL_DYNAMO=false → returns a real boto3 DynamoDB Table resource

Every handler does:
    from shared.dynamo_client import get_table
    users_table = get_table("DYNAMO_TABLE_USERS")

To switch to real AWS, set:
    export USE_LOCAL_DYNAMO=false
    export AWS_REGION=us-east-1
    # and configure AWS credentials via ~/.aws/credentials or IAM role
"""
import os

from shared.local_dynamo import LocalDynamoTable

_USE_LOCAL = os.environ.get("USE_LOCAL_DYNAMO", "true").lower() == "true"

# Env var name  →  default table name
_TABLE_ENV_DEFAULTS = {
    "DYNAMO_TABLE_USERS": "TodoApp-Users",
    "DYNAMO_TABLE_TODOS": "TodoApp-Todos",
    "DYNAMO_TABLE_AUDIT": "TodoApp-AuditLog",
}


def get_table(env_var: str):
    """
    Returns a DynamoDB Table object (local or real boto3) for the table
    whose name is stored in the given environment variable.
    """
    table_name = os.environ.get(env_var, _TABLE_ENV_DEFAULTS.get(env_var, env_var))

    if _USE_LOCAL:
        return LocalDynamoTable(table_name)

    # Real AWS — only imported when needed so Lambda packages don't require boto3 in local mode
    import boto3
    region = os.environ.get("AWS_REGION", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)
