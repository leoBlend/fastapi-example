import sys
import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base
from main import app
from models import Users, Todos
from routers.auth import get_db as auth_get_db, bcrypt_context, create_access_token
from routers.todos import get_db as todos_get_db
from routers.admin import get_db as admin_get_db
from routers.users import get_db as users_get_db

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_todo.db"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[auth_get_db] = override_get_db
    app.dependency_overrides[todos_get_db] = override_get_db
    app.dependency_overrides[admin_get_db] = override_get_db
    app.dependency_overrides[users_get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    user = Users(
        username="testuser",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=bcrypt_context.hash("testpass123"),
        is_active=True,
        role="user",
        phone_number="555-555-5555",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    user = Users(
        username="adminuser",
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        hashed_password=bcrypt_context.hash("adminpass123"),
        is_active=True,
        role="admin",
        phone_number="555-000-0000",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user):
    return create_access_token(test_user.username, test_user.id, timedelta(minutes=30), "user")


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_auth_token(admin_user):
    return create_access_token(admin_user.username, admin_user.id, timedelta(minutes=30), "admin")


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}


@pytest.fixture
def test_todo(db, test_user):
    todo = Todos(
        title="Test Todo",
        description="A test description",
        priority=3,
        complete=False,
        owner_id=test_user.id,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo
