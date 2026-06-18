"""
JWT and bcrypt utilities — ported from routers/auth.py.

JWT_SECRET_KEY must be set in the environment. In Lambda, set it as a
function environment variable. For local runs:
    export JWT_SECRET_KEY=local_dev_secret
"""
import logging
import os
from datetime import timedelta, datetime, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(username: str, user_id: str, role: str) -> str:
    expires = datetime.now(tz=timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    payload = {"sub": username, "id": user_id, "exp": expires, "role": role}
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Returns {username, id, user_role} or raises ValueError."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("id")
        role: str = payload.get("role")
        if not username or not user_id:
            raise ValueError("Invalid token payload")
        return {"username": username, "id": user_id, "user_role": role}
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc


def get_current_user_from_event(event: dict) -> dict:
    """
    Extracts the Bearer token from the Lambda event Authorization header,
    decodes it, and returns the user dict.  Raises ValueError on any failure.
    """
    headers = event.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        raise ValueError("Missing or malformed Authorization header")
    token = auth.removeprefix("Bearer ").strip()
    return decode_token(token)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return bcrypt_context.hash(plain)


def _secret() -> str:
    if not _SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    return _SECRET_KEY
