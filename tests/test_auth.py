from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from routers.auth import (
    SECRET_KEY,
    ALGORITHM,
    authenticate_user,
    create_access_token,
    get_current_user,
)
from models import Users


# --- Unit tests ---

def test_create_access_token():
    token = create_access_token("alice", 42, timedelta(minutes=15), "user")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["id"] == 42
    assert payload["role"] == "user"


def test_authenticate_user_success(db, test_user):
    user = authenticate_user("testuser", "testpass123", db)
    assert user is not False
    assert user.username == "testuser"


def test_authenticate_user_wrong_password(db, test_user):
    result = authenticate_user("testuser", "wrongpass", db)
    assert result is False


def test_authenticate_user_nonexistent(db):
    result = authenticate_user("nobody", "pass", db)
    assert result is False


async def test_get_current_user_valid_token():
    encode = {'sub': 'testuser', 'id': 1, 'role': 'admin'}
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    user = await get_current_user(token=token)
    assert user == {'username': 'testuser', 'id': 1, 'user_role': 'admin'}


async def test_get_current_user_missing_payload():
    encode = {'role': 'user'}
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token=token)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == 'Could not validate user'


# --- Integration tests ---

def test_create_user_success(client, db):
    payload = {
        "username": "newuser",
        "email": "new@example.com",
        "first_name": "New",
        "last_name": "User",
        "password": "securepass",
        "role": "user",
        "phone_number": "555-123-4567",
    }
    response = client.post("/auth/", json=payload)
    assert response.status_code == 201
    user = db.query(Users).filter(Users.username == "newuser").first()
    assert user is not None
    assert user.email == "new@example.com"
    assert user.hashed_password != "securepass"


def test_create_user_duplicate_username(client, test_user):
    payload = {
        "username": "testuser",
        "email": "other@example.com",
        "first_name": "Other",
        "last_name": "User",
        "password": "pass",
        "role": "user",
        "phone_number": "555-999-9999",
    }
    response = client.post("/auth/", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "Username or email already registered"


def test_login_success(client, test_user):
    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    response = client.post(
        "/auth/token",
        data={"username": "testuser", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/token",
        data={"username": "nobody", "password": "pass"},
    )
    assert response.status_code == 401
