"""
Request body validators — mirrors the Pydantic Field constraints from the
FastAPI routers without any FastAPI/Pydantic dependency.

Each function accepts a raw dict (parsed from event["body"]) and returns the
validated + coerced dict, or raises ValueError with a human-readable message.
"""


def validate_todo_request(body: dict) -> dict:
    title = str(body.get("title", "")).strip()
    description = str(body.get("description", "")).strip()
    priority = body.get("priority")
    complete = body.get("complete", False)

    if len(title) < 3:
        raise ValueError("title must be at least 3 characters")
    if len(description) < 3:
        raise ValueError("description must be at least 3 characters")
    if len(description) > 100:
        raise ValueError("description must be at most 100 characters")
    try:
        priority = int(priority)
    except (TypeError, ValueError):
        raise ValueError("priority must be an integer")
    if not (1 <= priority <= 5):
        raise ValueError("priority must be between 1 and 5")
    if not isinstance(complete, bool):
        complete = str(complete).lower() == "true"

    return {"title": title, "description": description, "priority": priority, "complete": complete}


def validate_create_user_request(body: dict) -> dict:
    required = ["username", "email", "first_name", "last_name", "password", "role", "phone_number"]
    for field in required:
        if not body.get(field):
            raise ValueError(f"{field} is required")

    role = body["role"]
    if role not in ("user", "admin"):
        raise ValueError("role must be 'user' or 'admin'")

    return {
        "username": str(body["username"]).strip(),
        "email": str(body["email"]).strip(),
        "first_name": str(body["first_name"]).strip(),
        "last_name": str(body["last_name"]).strip(),
        "password": str(body["password"]),
        "role": role,
        "phone_number": str(body["phone_number"]).strip(),
    }


def validate_user_verification(body: dict) -> dict:
    password = body.get("password", "")
    new_password = body.get("new_password", "")

    if not password:
        raise ValueError("password is required")
    if len(new_password) < 6:
        raise ValueError("new_password must be at least 6 characters")

    return {"password": str(password), "new_password": str(new_password)}
