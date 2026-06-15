# TodoApp

A REST API for managing to-do items, built with FastAPI, SQLAlchemy, and JWT authentication.

---

## Running the app

```bash
# Install dependencies (Python 3.10+)
pip install fastapi uvicorn[standard] sqlalchemy passlib python-jose python-multipart bcrypt

# Apply database migrations
alembic upgrade head

# Start the dev server (auto-reloads on file changes)
uvicorn main:app --reload
```

Interactive docs are available at `http://127.0.0.1:8000/docs` once the server is running.

## Running tests

```bash
pip install pytest pytest-asyncio httpx

# All tests
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/ -v

# Single file
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/test_todos.py -v

# Single test
/Users/leonardoferreyra/Library/Python/3.14/bin/pytest tests/test_todos.py::test_create_todo_success -v
```

---

## Endpoints

### Auth  (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/` | No | Create a new user account |
| POST | `/auth/token` | No | Log in — returns a JWT bearer token |

**Create user**
```bash
curl -X POST http://localhost:8000/auth/ \
  -H "Content-Type: application/json" \
  -d '{"username":"leo","email":"leo@example.com","first_name":"Leo","last_name":"F","password":"secret","role":"user","phone_number":"555-1234"}'
```

**Login**
```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=leo" -F "password=secret"
# → {"access_token": "<jwt>", "token_type": "bearer"}
```

---

### Todos (no prefix)

All routes except health check require a bearer token: `-H "Authorization: Bearer <token>"`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List your todos |
| GET | `/todos/{id}` | Yes | Get a single todo |
| POST | `/todo` | Yes | Create a todo |
| PUT | `/todos/{id}` | Yes | Update a todo |
| DELETE | `/todos/{id}` | Yes | Delete a todo |

**Create a todo**
```bash
curl -X POST http://localhost:8000/todo \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy milk","description":"From the store","priority":2,"complete":false}'
```

**List todos**
```bash
curl http://localhost:8000/ -H "Authorization: Bearer <token>"
```

---

### Users (`/users`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/` | Yes | Get your profile |
| PUT | `/users/password` | Yes | Change password |
| PUT | `/users/change_phone_number/{number}` | Yes | Update phone number |

---

### Admin (`/admin`)

Requires a token with `role: admin`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/todo` | List all todos (every user) |
| DELETE | `/admin/todo/{id}` | Delete any todo |

---

### Health

```bash
curl http://localhost:8000/healthy
# → {"status": "Healthy"}
```

---

## For .NET developers

If you're coming from ASP.NET Core, here's how the concepts map across:

| ASP.NET Core | FastAPI equivalent |
|---|---|
| `WebApplication.CreateBuilder` + `app.Run()` | `FastAPI()` instance in `main.py` + `uvicorn` |
| `[ApiController]` + `[Route("prefix")]` | `APIRouter(prefix="/prefix")` in each router file |
| `IActionResult` / `ActionResult<T>` | Return type is inferred; use `response_model=` on the decorator |
| `[HttpGet]`, `[HttpPost]`, … | `@router.get(...)`, `@router.post(...)`, … |
| Dependency Injection container (`services.AddScoped`) | `Depends(get_db)` in the function signature — no registration step needed |
| `DbContext` (EF Core) | `Session` (SQLAlchemy) — yielded by `get_db()` |
| Data annotations (`[Required]`, `[MaxLength]`) | Pydantic `Field(min_length=3, max_length=100)` on the schema class |
| `ModelState.IsValid` + 400 | Pydantic validates automatically; invalid bodies return **422** |
| `[Authorize]` attribute | `Depends(get_current_user)` in the route parameters |
| `appsettings.json` | `pydantic-settings` `BaseSettings` class (`config.py`) |
| Middleware (`app.UseAuthentication()`) | FastAPI middleware or dependencies on the router |
| `dotnet ef migrations add` | `alembic revision --autogenerate -m "description"` |
| `dotnet ef database update` | `alembic upgrade head` |

Key mindset shift: FastAPI leans on **function parameters** for everything (auth, DB, validation). There is no service container — if a route needs the database, it declares `db: Session = Depends(get_db)` directly. This makes dependencies explicit and trivially overridable in tests.
