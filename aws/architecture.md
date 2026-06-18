# Architecture Notes — FastAPI → Lambda + API Gateway + DynamoDB

---

## Endpoint → Lambda Mapping

| HTTP Method | Path | Lambda Handler | Auth | Notes |
|---|---|---|---|---|
| GET | `/healthy` | `handlers/health.handler` | None | No DB, smoke test |
| POST | `/auth/` | `handlers/auth_register.handler` | None | Checks duplicate username/email |
| POST | `/auth/token` | `handlers/auth_login.handler` | None | Body is `x-www-form-urlencoded` |
| GET | `/` | `handlers/todos_list.handler` | JWT | Queries OwnerIndex GSI |
| GET | `/todos/{todo_id}` | `handlers/todos_get.handler` | JWT | GetItem + ownership check |
| POST | `/todo` | `handlers/todos_create.handler` | JWT | Generates UUID, writes audit |
| PUT | `/todos/{todo_id}` | `handlers/todos_update.handler` | JWT | 204 on success |
| DELETE | `/todos/{todo_id}` | `handlers/todos_delete.handler` | JWT | 204 + writes audit |
| GET | `/users/` | `handlers/users_get.handler` | JWT | Queries UserIdIndex GSI |
| PUT | `/users/password` | `handlers/users_password.handler` | JWT | Verifies old pw, writes audit |
| PUT | `/users/change_phone_number/{phone_number}` | `handlers/users_phone.handler` | JWT | 204 on success |
| GET | `/admin/todo` | `handlers/admin_todos.handler` | JWT + admin | Full table Scan |
| DELETE | `/admin/todo/{todo_id}` | `handlers/admin_delete.handler` | JWT + admin | No ownership filter |
| GET | `/admin/audit` | `handlers/admin_audit.handler` | JWT + admin | Queries TimestampIndex GSI |

---

## DynamoDB Table Schema

### `TodoApp-Users`

```
PK (partition key): username (String)
Attributes:
  user_id       String  — UUID, referenced in JWT "id" claim and other tables
  email         String
  first_name    String
  last_name     String
  hashed_password String  — bcrypt hash, never returned in responses
  is_active     Bool
  role          String  — "user" | "admin"
  phone_number  String

GSI EmailIndex:    PK = email
GSI UserIdIndex:   PK = user_id
```

**Why this PK:** Login (`POST /auth/token`) looks up by username — `GetItem` is O(1).
`EmailIndex` gives O(1) duplicate-email detection at registration.
`UserIdIndex` allows `GET /users/` to look up by the UUID stored in the JWT.

---

### `TodoApp-Todos`

```
PK (partition key): todo_id (String, UUID)
Attributes:
  owner_id      String  — user_id from TodoApp-Users
  title         String
  description   String
  priority      Number  — 1 to 5
  complete      Bool
  created_at    String  — ISO-8601 UTC

GSI OwnerIndex:    PK = owner_id, SK = created_at
```

**Why this PK:** `GET /todos/{todo_id}`, `PUT /todos/{todo_id}`, `DELETE /todos/{todo_id}` all need O(1) lookup by ID.
`OwnerIndex` powers `GET /` — query by `owner_id`, sorted by `created_at`.

**Note on admin Scan:** `GET /admin/todo` uses a full table `Scan`. For a learning/low-volume app this is fine. At scale, add a GSI with a constant partition key (`entity_type = "TODO"`) so admin list is also a Query.

---

### `TodoApp-AuditLog`

```
PK (partition key): audit_id (String, UUID)
Attributes:
  entity_type   String  — constant "AUDIT" (used as GSI PK for ordered queries)
  username      String
  action        String  — user_registered | user_login | todo_created | todo_deleted | password_changed
  detail        String  — free-form context string
  timestamp     String  — ISO-8601 UTC

GSI TimestampIndex: PK = entity_type, SK = timestamp
```

**Why this design:** Audit records are immutable — write-once, never updated. Making `audit_id` the PK ensures every write is unique. `TimestampIndex` with the constant `entity_type = "AUDIT"` lets `GET /admin/audit` return all records ordered by time descending (`ScanIndexForward=False`) without a Scan.

---

## FastAPI → Lambda Translation Notes

### BackgroundTasks → Synchronous writes

FastAPI's `BackgroundTasks.add_task(write_audit_log, ...)` runs after the HTTP response is sent — it's still in the same process, just deferred. Lambda has no equivalent: once `handler()` returns, the execution context is frozen. **Audit log writes are synchronous inside each handler.** This adds ~5–10ms per call but is correct.

For truly async audit logging in production you would invoke a second Lambda with `InvocationType='Event'` (fire and forget), or use DynamoDB Streams to trigger an audit Lambda on every write.

### IDs: auto-increment → UUID

SQLite uses integer primary keys via auto-increment. DynamoDB has no sequences. `uuid.uuid4()` is called inside the handler before `put_item` — the ID is known before the write, not after.

### Password form body

The original `POST /auth/token` uses FastAPI's `OAuth2PasswordRequestForm`, which requires `Content-Type: application/x-www-form-urlencoded` and `username=...&password=...` encoding. The Lambda handler parses this with `urllib.parse.parse_qs`. For local testing, JSON body is also accepted as a convenience.

### JWT validation

The original app validates JWTs inside a FastAPI dependency (`get_current_user`). In Lambda, `shared/auth_utils.get_current_user_from_event(event)` does the same — extracts the `Authorization: Bearer` header, decodes the JWT, returns `{username, id, user_role}`. All protected handlers call this first.

---

## IAM Role for Lambda

The Lambda execution role needs these DynamoDB permissions scoped to the three tables and their GSI ARNs:

```
dynamodb:GetItem
dynamodb:PutItem
dynamodb:UpdateItem
dynamodb:DeleteItem
dynamodb:Query
dynamodb:Scan
```

Plus CloudWatch Logs permissions (added automatically by SAM's `AWSLambdaBasicExecutionRole`).

No `dynamodb:CreateTable`, no `dynamodb:DeleteTable`, no cross-account permissions.

---

## Local vs Real AWS

| Setting | Local simulation | Real AWS |
|---|---|---|
| `USE_LOCAL_DYNAMO` | `true` | `false` |
| Storage | JSON files in `aws/local_data/` | DynamoDB tables in your region |
| Auth | Same JWT logic | Same JWT logic |
| IAM | N/A | Lambda execution role required |
| Deploy | `python` direct or `pytest` | `sam build && sam deploy` |
