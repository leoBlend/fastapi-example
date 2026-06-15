---
name: python-fastapi-pytest
description: "Use this skill when building, extending, or testing a FastAPI application with pytest. Triggers: any mention of FastAPI routes, routers, dependencies, Pydantic models, async endpoints, or pytest test files for a FastAPI app. Covers project structure, dependency injection patterns, async testing with httpx, fixtures, and common gotchas. Use for both greenfield APIs and adding tests to existing ones."
---

# Python · FastAPI · pytest

## Project Structure

```
project/
├── app/
│   ├── main.py          # FastAPI() app, mounts routers
│   ├── routers/         # One file per domain (users.py, items.py …)
│   ├── models.py        # SQLAlchemy / ODM models
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── deps.py          # Shared dependencies (get_db, get_current_user …)
│   └── config.py        # Settings via pydantic-settings
└── tests/
    ├── conftest.py      # Fixtures: app, client, db session
    └── test_*.py        # One file per router/domain
```

---

## Core Patterns

### App + Router

```python
# app/main.py
from fastapi import FastAPI
from app.routers import users, items

app = FastAPI()
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(items.router, prefix="/items", tags=["items"])
```

```python
# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from app import schemas, deps

router = APIRouter()

@router.get("/{user_id}", response_model=schemas.UserOut)
async def get_user(user_id: int, db=Depends(deps.get_db)):
    user = await db.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### Dependency Injection

```python
# app/deps.py
from app.database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Override deps in tests — never patch internals directly.

---

## Testing with pytest + httpx

### conftest.py

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.deps import get_db
from tests.db import override_get_db   # test DB session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

### Test file

```python
import pytest

@pytest.mark.asyncio
async def test_get_user(client):
    resp = await client.get("/users/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1

@pytest.mark.asyncio
async def test_not_found(client):
    resp = await client.get("/users/9999")
    assert resp.status_code == 404
```

---

## Key Rules

| Rule | Why |
|---|---|
| Use `response_model=` on every route | Prevents leaking internal fields |
| Raise `HTTPException`, never return raw dicts for errors | Consistent error shape |
| Override deps, don't monkeypatch | Keeps tests isolated and fast |
| Use `AsyncClient` + `ASGITransport` | No real HTTP server needed |
| One `conftest.py` per test directory max | Avoids fixture shadowing surprises |
| Mark async tests with `@pytest.mark.asyncio` | Required by `pytest-asyncio` |

---

## Required packages

```
fastapi
uvicorn[standard]
pydantic-settings
httpx
pytest
pytest-asyncio
anyio[trio]   # optional but stabilises async test runner
```

Set in `pytest.ini` or `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # removes need to mark every test manually
```

---

## Common Gotchas

- **`422 Unprocessable Entity`** — request body doesn't match the Pydantic schema; check field names and types.
- **`dependency_overrides` not taking effect** — make sure you're importing and mutating the same `app` object used in tests.
- **Async fixture scope** — use `scope="session"` carefully; DB state bleeds between tests.
- **Lifespan events** (`startup`/`shutdown`) don't fire with `ASGITransport` by default — use `app.router.lifespan_context` or `asgi_lifespan` if you need them.
