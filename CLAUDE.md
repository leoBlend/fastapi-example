# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/ -v

# Run a single test file
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/test_todos.py -v

# Run a single test by name
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/test_todos.py::test_create_todo_success -v

# Start the dev server
uvicorn main:app --reload

# Run a database migration
alembic upgrade head

# Generate a new migration from model changes
alembic revision --autogenerate -m "description"
```

## Architecture

This is a FastAPI + SQLAlchemy todo app backed by SQLite (`todoapp.db`). The four routers cover auth, todos, admin, and users — all registered in `main.py` with no shared prefix except `/auth`, `/admin`, and `/users`. The todos router has no prefix, so todo routes live at the root (`/`, `/todo`, `/todos/{id}`).

**Auth flow:** `routers/auth.py` issues JWT tokens (`SECRET_KEY`, `ALGORITHM` are hardcoded there). `get_current_user` is an async dependency that decodes the token and returns `{'username', 'id', 'user_role'}`. All protected routes declare `user: Annotated[dict, Depends(get_current_user)]` and check `if user is None`. Note: a JWTError in `get_current_user` currently returns (not raises) an HTTPException — callers rely on the `is None` check to catch it.

**Database:** Each router defines its own `get_db()` yielding a `SessionLocal`. Tests override all four via `app.dependency_overrides`. Alembic handles schema migrations; `models.Base.metadata` is the single source of truth.

**Testing:** `tests/conftest.py` creates an in-memory-equivalent SQLite test DB (`StaticPool`), overrides all four routers' `get_db`, and provides fixtures: `db`, `client`, `test_user`, `admin_user`, `auth_headers`, `admin_auth_headers`, `test_todo`. Tests requiring authentication must receive `auth_headers` or `admin_auth_headers` as a fixture parameter. `pytest.ini` sets `asyncio_mode = auto` so async test functions run without explicit `@pytest.mark.asyncio`.

**`create_access_token` signature:** `(username, user_id, expires_delta, role)` — `role` is the 4th positional argument.
