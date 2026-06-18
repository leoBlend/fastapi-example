import json

_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def ok(body: dict) -> dict:
    return {"statusCode": 200, "headers": _HEADERS, "body": json.dumps(body)}


def created(body: dict) -> dict:
    return {"statusCode": 201, "headers": _HEADERS, "body": json.dumps(body)}


def no_content() -> dict:
    return {"statusCode": 204, "headers": _HEADERS, "body": ""}


def error(status: int, detail: str) -> dict:
    return {"statusCode": status, "headers": _HEADERS, "body": json.dumps({"detail": detail})}
