# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start Postgres+pgvector (required before running the app or tests)
docker compose up -d

# Install dependencies
/Users/leonardoferreyra/Library/Python/3.14/bin/pip install --user -r requirements.txt

# Run all tests (needs the Docker DB running)
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

# Backfill embeddings for todos missing one
python3 scripts/backfill_embeddings.py
```

## Architecture

This is a FastAPI + SQLAlchemy todo app backed by **Postgres + pgvector**, run via Docker (`docker-compose.yml`, image `pgvector/pgvector:pg16`). The connection string comes from `DATABASE_URL` in `.env` (see `.env.example`). The five routers cover auth, todos, admin, users, and rag — all registered in `main.py` with no shared prefix except `/auth`, `/admin`, `/users`, and `/rag`. The todos router has no prefix, so todo routes live at the root (`/`, `/todo`, `/todos/{id}`).

**RAG layer:** `routers/rag.py` adds `GET /rag/search` (semantic search over the user's todos via pgvector cosine distance — local, no API key) and `POST /rag/ask` (retrieve relevant todos, then have Claude answer grounded in them). Embeddings are produced locally by `embeddings.py` (`sentence-transformers`, `all-MiniLM-L6-v2`, 384-dim) and stored on `Todos.embedding` (`pgvector.sqlalchemy.Vector`). Todos are embedded synchronously on create/update in `routers/todos.py`. Generation lives in `rag_service.py` (Claude `claude-opus-4-8` via the `anthropic` SDK; needs `ANTHROPIC_API_KEY`).

**Auth flow:** `routers/auth.py` issues JWT tokens (`SECRET_KEY`, `ALGORITHM` are hardcoded there). `get_current_user` is an async dependency that decodes the token and returns `{'username', 'id', 'user_role'}`. All protected routes declare `user: Annotated[dict, Depends(get_current_user)]` and check `if user is None`. Note: a JWTError in `get_current_user` currently returns (not raises) an HTTPException — callers rely on the `is None` check to catch it.

**Database:** Each router defines its own `get_db()` yielding a `SessionLocal`. Tests override **all five** via `app.dependency_overrides` (auth, todos, admin, users, rag) — adding a router means adding its `get_db` override in `conftest.py`. Alembic handles schema migrations; `models.Base.metadata` is the single source of truth. The migration chain starts with `a0000000init` (base users+todos), then phone_number, audit_logs, and `b1111111vec` (enables the `vector` extension + adds `todos.embedding`).

**Testing:** `tests/conftest.py` uses a separate Postgres test database (`TEST_DATABASE_URL` → `todoapp_test`, created by `scripts/init-test-db.sql`), overrides all five routers' `get_db`, and provides fixtures: `db`, `client`, `test_user`, `admin_user`, `auth_headers`, `admin_auth_headers`, `test_todo`. The RAG layer is stubbed for speed/offline: `mock_embeddings` (autouse) replaces `embed_text` with a deterministic fake vector so no model loads; `mock_claude` (opt-in) stubs the Claude call. Tests requiring authentication must receive `auth_headers` or `admin_auth_headers` as a fixture parameter. `pytest.ini` sets `asyncio_mode = auto` so async test functions run without explicit `@pytest.mark.asyncio`.

**`create_access_token` signature:** `(username, user_id, expires_delta, role)` — `role` is the 4th positional argument.
