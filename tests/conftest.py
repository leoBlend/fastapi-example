import sys
import os
import hashlib
import struct
from datetime import timedelta

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from database import Base
from main import app
from models import Users, Todos
from routers.auth import get_db as auth_get_db, bcrypt_context, create_access_token
from routers.todos import get_db as todos_get_db
from routers.admin import get_db as admin_get_db
from routers.users import get_db as users_get_db
from routers.rag import get_db as rag_get_db

# Tests run against a SEPARATE Postgres database (todoapp_test) so they never
# touch your real data. The container must be up (`docker compose up -d`).
SQLALCHEMY_TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

test_engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    # The todos table has a pgvector column, so the extension must exist in the
    # test database before we create the schema.
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


# --- RAG test doubles -------------------------------------------------------
# Real embeddings load an ~80MB model; real /rag/ask calls Claude over the
# network. Tests stub both so the suite stays fast and offline.

EMBEDDING_DIM = 384


def fake_embed(text_value: str) -> list[float]:
    """Deterministic fake embedding: same text -> same vector, different text ->
    different vector. Seeded from a hash so cosine_distance is stable and an
    exact-text query ranks its own todo first (distance ~0)."""
    digest = hashlib.sha256((text_value or "").encode("utf-8")).digest()
    # Stretch the 32-byte digest into 384 floats deterministically.
    raw = (digest * (EMBEDDING_DIM // len(digest) + 1))[:EMBEDDING_DIM]
    return [b / 255.0 for b in raw]


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch):
    """Replace embed_text everywhere it's used so no model is loaded in tests."""
    monkeypatch.setattr("embeddings.embed_text", fake_embed)
    monkeypatch.setattr("routers.todos.embed_text", fake_embed)
    monkeypatch.setattr("routers.rag.embed_text", fake_embed)


@pytest.fixture
def mock_claude(monkeypatch):
    """Stub the Claude generation step; records what it was asked."""
    calls = {}

    def fake_answer(question, todos):
        calls["question"] = question
        calls["todos"] = [t.title for t in todos]
        return f"STUB ANSWER for: {question}"

    monkeypatch.setattr("rag_service.answer_question", fake_answer)
    return calls


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[auth_get_db] = override_get_db
    app.dependency_overrides[todos_get_db] = override_get_db
    app.dependency_overrides[admin_get_db] = override_get_db
    app.dependency_overrides[users_get_db] = override_get_db
    app.dependency_overrides[rag_get_db] = override_get_db

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
