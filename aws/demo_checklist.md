# Demo Checklist — Sample Requests, Error Cases & Logging

Run these in order against the local simulation. Each step notes what to verify in the JSON files and stdout.

## Setup

```bash
# From project root
export JWT_SECRET_KEY=local_dev_secret
export USE_LOCAL_DYNAMO=true
export LOCAL_DATA_DIR=./aws/local_data
export PYTHONPATH=./aws
```

---

## Step 1 — Health check (no auth)

```bash
python -c "
from handlers.health import handler
import json
print(json.dumps(handler({}, None), indent=2))
"
```

**Expected:** `200 {"status": "Healthy"}`

---

## Step 2 — Register a user

```bash
python -c "
import json, sys, os
sys.path.insert(0, './aws')
from handlers.auth_register import handler
event = {
    'body': json.dumps({
        'username': 'alice',
        'email': 'alice@example.com',
        'first_name': 'Alice',
        'last_name': 'Smith',
        'password': 'secret123',
        'role': 'user',
        'phone_number': '555-1234'
    }),
    'headers': {}
}
print(json.dumps(handler(event, None), indent=2))
"
```

**Expected:** `201`, body has user fields (no `hashed_password`).
**Verify:** `cat aws/local_data/TodoApp-Users.json` — one item.
**Verify:** `cat aws/local_data/TodoApp-AuditLog.json` — action=`user_registered`.
**Verify stdout:** `INFO ... New user registered: alice`

---

## Step 3 — Register duplicate (error case)

Same payload as Step 2.

**Expected:** `409 {"detail": "Username or email already registered"}`

---

## Step 4 — Register an admin user

```bash
# Change username, email, and role="admin"
```

---

## Step 5 — Login

```bash
python -c "
import json, sys
sys.path.insert(0, './aws')
from handlers.auth_login import handler
event = {
    'body': 'username=alice&password=secret123',
    'headers': {'Content-Type': 'application/x-www-form-urlencoded'}
}
print(json.dumps(handler(event, None), indent=2))
"
```

**Expected:** `200 {"access_token": "eyJ...", "token_type": "bearer"}`
**Verify:** `cat aws/local_data/TodoApp-AuditLog.json` — action=`user_login` entry added.
**Save the token:** `TOKEN=$(python -c "..." | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")`

---

## Step 6 — Login with wrong password (error case)

```bash
# body: username=alice&password=wrongpassword
```

**Expected:** `401 {"detail": "Could not retrieve user."}`
**Verify stdout:** `WARNING ... Failed login attempt for username: alice`

---

## Step 7 — Create todo

```bash
python -c "
import json, sys, os
sys.path.insert(0, './aws')
os.environ['JWT_SECRET_KEY'] = 'local_dev_secret'
from handlers.todos_create import handler
event = {
    'headers': {'Authorization': 'Bearer TOKEN_HERE'},
    'body': json.dumps({
        'title': 'Buy milk',
        'description': 'From the store near work',
        'priority': 2,
        'complete': False
    })
}
print(json.dumps(handler(event, None), indent=2))
"
```

**Expected:** `201`, body has `todo_id` (UUID), `owner_id`, all fields.
**Verify:** `cat aws/local_data/TodoApp-Todos.json` — one item.
**Verify:** Audit log has `action=todo_created`.

---

## Step 8 — Invalid todo data (error cases)

```bash
# title too short (< 3 chars) → 422 "title must be at least 3 characters"
# priority = 6 → 422 "priority must be between 1 and 5"
# description > 100 chars → 422 "description must be at most 100 characters"
# no body → 422 "title must be at least 3 characters"
```

---

## Step 9 — List todos

```bash
# GET / with Authorization header
# Expected: 200, array containing the todo from Step 7
```

---

## Step 10 — No auth on protected route (error case)

```bash
# GET / without Authorization header
# Expected: 401 {"detail": "Missing or malformed Authorization header"}
```

---

## Step 11 — Get single todo

```bash
# GET /todos/{todo_id} — use todo_id from Step 7
# Expected: 200, the todo item
```

---

## Step 12 — Get wrong user's todo (error case)

```bash
# Login as a different user, try to GET the first user's todo_id
# Expected: 404 {"detail": "Todo not found."}
```

---

## Step 13 — Update todo

```bash
# PUT /todos/{todo_id} with complete=true
# Expected: 204 (no body)
# Verify: GET /todos/{todo_id} → complete is now true
```

---

## Step 14 — Delete todo

```bash
# DELETE /todos/{todo_id}
# Expected: 204
# Verify audit log: action=todo_deleted
# Verify: GET /todos/{todo_id} → 404
```

---

## Step 15 — Admin flow

```bash
# Login as admin user (registered in Step 4)
# GET /admin/todo → 200, all todos across all users
# GET /admin/audit → 200, all audit entries sorted newest first
# DELETE /admin/todo/{any_todo_id} → 204
```

---

## Step 16 — Admin endpoint with user token (error case)

```bash
# Use alice's token (role=user) to call GET /admin/todo
# Expected: 401 {"detail": "Admins only"}
```

---

## Step 17 — Change password

```bash
# PUT /users/password with {"password": "secret123", "new_password": "newpassword123"}
# Expected: 204
# Verify audit: action=password_changed
# Verify: login with old password → 401; login with new password → 200
```

---

## Step 18 — Wrong current password (error case)

```bash
# PUT /users/password with wrong "password" value
# Expected: 401 {"detail": "Error on password change"}
```

---

## Step 19 — Change phone number

```bash
# PUT /users/change_phone_number/555-9999
# Expected: 204
# Verify: GET /users/ → phone_number is 555-9999
```

---

## Logging Expectations

All handlers use Python's `logging` module. In Lambda, stdout automatically goes to CloudWatch Logs under `/aws/lambda/{function-name}`.

| Event | Level | Example message |
|---|---|---|
| User registered | INFO | `New user registered: alice` |
| Duplicate registration | WARNING | `Registration failed — duplicate username: alice` |
| Failed login | WARNING | `Failed login attempt for username: alice` |
| Successful login | INFO | `User logged in: alice` |
| Todo created | INFO | `Todo created by user alice: 'Buy milk'` |
| Todo update failed (not found) | WARNING | `Update failed — todo abc-123 not found for user alice` |
| Todo deleted | INFO | `Todo abc-123 deleted by user alice` |
| Password change wrong pw | WARNING | `Password change failed for user alice — wrong current password` |
| Password changed | INFO | `Password changed for user alice` |
| Phone updated | INFO | `Phone number updated for user alice` |
| Admin list todos | INFO | `Admin adminuser fetched all todos (3)` |
| Admin audit log | INFO | `Admin adminuser fetched audit log (7 entries)` |
| Audit write failure | ERROR | `Failed to write audit log for action 'todo_created' by 'alice'` |

---

## Real AWS — Switching Checklist

When you have credentials and want to test against real AWS:

- [ ] Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (or use `~/.aws/credentials`)
- [ ] Set `USE_LOCAL_DYNAMO=false`
- [ ] Create DynamoDB tables manually (console or `sam deploy`) with the schemas in `architecture.md`
- [ ] Run `sam build` from `aws/` directory
- [ ] Run `sam deploy --guided` — follow prompts, set `JWT_SECRET_KEY` as a parameter
- [ ] Copy the API Gateway URL from the deploy output
- [ ] Re-run this checklist using the real URL instead of the Python invocations
- [ ] Check CloudWatch Logs: `/aws/lambda/TodoApp-*` for each function's output
