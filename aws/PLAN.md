# AWS Serverless Implementation Plan — TodoApp

## Context

The existing FastAPI + SQLite todo app needs AWS serverless equivalents as a learning exercise. The goal is to understand IAM / Lambda / API Gateway / DynamoDB / CloudWatch conceptually AND have working local handlers (no real AWS credentials needed yet) that mirror the exact Lambda + API Gateway contract, so the user can drop in credentials later and deploy with minimal changes.

---

## Output Files

```
aws/
├── AWS_SERVICES_NOTES.md          # Short notes: IAM, Lambda, API Gateway, DynamoDB, CloudWatch
├── architecture.md                # Endpoint→Lambda mapping, DynamoDB table schema, design decisions
├── demo_checklist.md              # Sample requests, error cases, logging expectations
├── README.md                      # How to run locally, env var reference, real AWS checklist
├── requirements-lambda.txt        # passlib[bcrypt], python-jose[cryptography] (no FastAPI/SQLAlchemy)
├── template.yaml                  # AWS SAM skeleton — ready to deploy when credentials are added
│
├── shared/
│   ├── __init__.py
│   ├── response.py                # ok(), created(), no_content(), error() helpers
│   ├── auth_utils.py              # JWT encode/decode + bcrypt (ported from routers/auth.py)
│   ├── local_dynamo.py            # JSON-file DynamoDB simulator (get_item, put_item, query, scan, …)
│   ├── dynamo_client.py           # Factory: USE_LOCAL_DYNAMO=true → LocalClient, false → boto3
│   └── validation.py             # Field validators mirroring Pydantic constraints (no FastAPI dep)
│
├── handlers/                      # One handler per endpoint
│   ├── health.py                  # GET /healthy
│   ├── auth_register.py           # POST /auth/
│   ├── auth_login.py              # POST /auth/token  (parses x-www-form-urlencoded)
│   ├── todos_list.py              # GET /
│   ├── todos_get.py               # GET /todos/{todo_id}
│   ├── todos_create.py            # POST /todo
│   ├── todos_update.py            # PUT /todos/{todo_id}
│   ├── todos_delete.py            # DELETE /todos/{todo_id}
│   ├── users_get.py               # GET /users/
│   ├── users_password.py          # PUT /users/password
│   ├── users_phone.py             # PUT /users/change_phone_number/{phone_number}
│   ├── admin_todos.py             # GET /admin/todo
│   ├── admin_delete.py            # DELETE /admin/todo/{todo_id}
│   └── admin_audit.py             # GET /admin/audit
│
└── local_data/                    # Runtime JSON files (gitignored except .gitkeep)
    └── .gitkeep
```

---

## DynamoDB Table Schema

Three separate tables (one per SQL entity). Access patterns drive the design.

### `TodoApp-Users`
- **PK:** `username` (String) — login flow does `GetItem` by username
- **Attributes:** `user_id` (UUID String), `email`, `first_name`, `last_name`, `hashed_password`, `is_active` (Bool), `role`, `phone_number`
- **GSI EmailIndex:** PK = `email` — duplicate-email check at registration (O(1) instead of Scan)
- **GSI UserIdIndex:** PK = `user_id` — look up profile by UUID from JWT `id` claim

### `TodoApp-Todos`
- **PK:** `todo_id` (UUID String) — direct lookup for GET/PUT/DELETE by ID
- **Attributes:** `owner_id` (user UUID), `title`, `description`, `priority` (Number), `complete` (Bool), `created_at` (ISO-8601)
- **GSI OwnerIndex:** PK = `owner_id`, SK = `created_at` — list user's todos sorted by time (GET /)

### `TodoApp-AuditLog`
- **PK:** `audit_id` (UUID String) — immutable write-once records
- **Attributes:** `username`, `action`, `detail`, `timestamp` (ISO-8601), `entity_type` (constant `"AUDIT"`)
- **GSI TimestampIndex:** PK = `entity_type`, SK = `timestamp` — GET /admin/audit ordered by time desc

---

## Env Var Convention

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET_KEY` | *(required)* | Replaces hardcoded `"secret123_!"` in `routers/auth.py` |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_MINUTES` | `30` | Token lifetime |
| `USE_LOCAL_DYNAMO` | `true` | `true` = JSON-file sim; `false` = real boto3 |
| `LOCAL_DATA_DIR` | `./aws/local_data` | Where `.json` files live |
| `DYNAMO_TABLE_USERS` | `TodoApp-Users` | Overridable per environment |
| `DYNAMO_TABLE_TODOS` | `TodoApp-Todos` | |
| `DYNAMO_TABLE_AUDIT` | `TodoApp-AuditLog` | |
| `AWS_REGION` | `us-east-1` | Used only when `USE_LOCAL_DYNAMO=false` |

For local runs: `export JWT_SECRET_KEY=local_dev_secret USE_LOCAL_DYNAMO=true` before running tests or the handler directly.

---

## Key Design Decisions

**One Lambda per endpoint** (not a monolith). Makes the API Gateway → Lambda mapping explicit and teaches IAM scoping per function. A Mangum adapter (which runs FastAPI on Lambda unchanged) is explicitly avoided — the learning value is in writing real handlers.

**Audit logs written synchronously** inside the handler. Lambda has no after-response hook equivalent to FastAPI's `BackgroundTasks`. The 5–10ms extra write cost is negligible. A code comment in each affected handler explains this translation.

**UUIDs replace auto-increment IDs.** DynamoDB has no sequences. `uuid.uuid4()` is generated in the handler before the `put_item` call — normal DynamoDB practice.

**`urllib.parse.parse_qs`** parses the `x-www-form-urlencoded` body for `POST /auth/token` (the `OAuth2PasswordRequestForm` contract) — no extra dependency.

---

## Pre-Implementation Setup (first steps)

1. **Create branch:** `git checkout -b feature/aws-serverless`
2. **Save plan inside project:** copy this plan to `aws/PLAN.md` so it lives with the code
3. **Create/update memory:** write a `project` memory entry to `~/.claude/projects/.../memory/project_aws_serverless.md` summarising what this feature is and why
4. **Initial commit:** `aws/PLAN.md` + `.gitkeep` for `aws/local_data/` as the feature's first commit

---

## Implementation Order

1. `shared/response.py` — pure stdlib, no deps
2. `shared/auth_utils.py` — port JWT/bcrypt from `routers/auth.py:21–55`
3. `shared/local_dynamo.py` — file-backed get/put/query/scan, stdlib only
4. `shared/dynamo_client.py` — factory returning local or boto3
5. `shared/validation.py` — mirrors Pydantic Field constraints
6. `handlers/health.py` — smoke test, no auth/DB
7. `handlers/auth_register.py` + `auth_login.py` — no JWT required to call
8. `handlers/todos_*.py` — full CRUD, tests JWT infrastructure
9. `handlers/users_*.py`
10. `handlers/admin_*.py`
11. `aws/AWS_SERVICES_NOTES.md` + `architecture.md` + `demo_checklist.md`
12. `template.yaml` — SAM skeleton, last because handler signatures are stable

---

## Key Source Files to Port From

- `routers/auth.py` — `bcrypt_context`, `create_access_token`, `get_current_user` → `shared/auth_utils.py`
- `tasks.py` — `write_audit_log` pattern → inline DynamoDB `put_item` inside each handler
- `routers/todos.py` — owner-scoped CRUD; `owner_id` filter maps to `OwnerIndex` GSI Query
- `routers/admin.py` — role check pattern + all-todos Scan + audit log query

---

## Verification

**Local (no AWS):**
```bash
export JWT_SECRET_KEY=local_dev_secret USE_LOCAL_DYNAMO=true LOCAL_DATA_DIR=./aws/local_data
pytest aws/tests/ -v           # All handlers tested via fixture events
```

**Manual curl walkthrough** (sequence in `aws/demo_checklist.md`):
1. Register user → check `local_data/TodoApp-Users.json`
2. Duplicate register → expect 409
3. Login → copy token
4. Login with wrong password → expect 401
5. Create todo → check `local_data/TodoApp-Todos.json` + audit log
6. Bad todo (short title, priority=6, description >100) → expect 422 each
7. List todos, GET by ID, PUT update, DELETE → check 404 after delete
8. Admin flow (register admin, login, GET /admin/todo, GET /admin/audit)
9. Admin endpoint with user token → expect 401
10. Health check → `{"status": "Healthy"}`

**When real AWS credentials are available:**
- Set `USE_LOCAL_DYNAMO=false`, `AWS_REGION=us-east-1`
- `sam build && sam deploy --guided` using `template.yaml`
- Re-run the same curl sequence against the API Gateway URL
