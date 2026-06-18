# TodoApp — AWS Serverless Layer

Local Lambda-style handlers for the TodoApp. No real AWS credentials needed to run locally.

## Quick Start (local simulation)

```bash
# From the project root
export JWT_SECRET_KEY=local_dev_secret
export USE_LOCAL_DYNAMO=true
export LOCAL_DATA_DIR=./aws/local_data
export PYTHONPATH=./aws
```

Then invoke any handler directly:

```bash
python -c "
import json, sys
sys.path.insert(0, './aws')
from handlers.health import handler
print(json.dumps(handler({}, None), indent=2))
"
```

Or run the full demo walkthrough in `demo_checklist.md`.

## Environment Variables

| Variable | Default | Required |
|---|---|---|
| `JWT_SECRET_KEY` | — | **Yes** — no default |
| `JWT_ALGORITHM` | `HS256` | No |
| `JWT_EXPIRE_MINUTES` | `30` | No |
| `USE_LOCAL_DYNAMO` | `true` | No |
| `LOCAL_DATA_DIR` | `./aws/local_data` | No |
| `DYNAMO_TABLE_USERS` | `TodoApp-Users` | No |
| `DYNAMO_TABLE_TODOS` | `TodoApp-Todos` | No |
| `DYNAMO_TABLE_AUDIT` | `TodoApp-AuditLog` | No |
| `AWS_REGION` | `us-east-1` | Only when `USE_LOCAL_DYNAMO=false` |

## Files

```
aws/
├── AWS_SERVICES_NOTES.md   Short notes on IAM, Lambda, API Gateway, DynamoDB, CloudWatch
├── architecture.md         Endpoint→Lambda mapping, DynamoDB table schema, design decisions
├── demo_checklist.md       Step-by-step sample requests, error cases, logging expectations
├── PLAN.md                 Implementation plan preserved here for reference
├── requirements-lambda.txt Lambda dependencies (passlib, python-jose)
├── template.yaml           AWS SAM skeleton — ready to deploy when credentials are added
│
├── shared/
│   ├── response.py         ok(), created(), no_content(), error() HTTP helpers
│   ├── auth_utils.py       JWT encode/decode + bcrypt (env-driven, no hardcoded secret)
│   ├── local_dynamo.py     JSON-file DynamoDB simulator
│   ├── dynamo_client.py    Factory: local or real boto3 based on USE_LOCAL_DYNAMO
│   └── validation.py       Request body validators (mirrors Pydantic Field constraints)
│
├── handlers/               One handler per endpoint
│   ├── health.py           GET /healthy
│   ├── auth_register.py    POST /auth/
│   ├── auth_login.py       POST /auth/token
│   ├── todos_list.py       GET /
│   ├── todos_get.py        GET /todos/{todo_id}
│   ├── todos_create.py     POST /todo
│   ├── todos_update.py     PUT /todos/{todo_id}
│   ├── todos_delete.py     DELETE /todos/{todo_id}
│   ├── users_get.py        GET /users/
│   ├── users_password.py   PUT /users/password
│   ├── users_phone.py      PUT /users/change_phone_number/{phone_number}
│   ├── admin_todos.py      GET /admin/todo
│   ├── admin_delete.py     DELETE /admin/todo/{todo_id}
│   └── admin_audit.py      GET /admin/audit
│
└── local_data/             JSON files written by local_dynamo.py (gitignored except .gitkeep)
```

## Deploying to Real AWS

When you have credentials:

```bash
# 1. Configure AWS credentials
aws configure

# 2. Install SAM CLI (if not already installed)
brew install aws-sam-cli

# 3. Build
cd aws/
sam build

# 4. Deploy (first time — interactive)
sam deploy --guided
#    Stack name: TodoApp
#    AWS Region: us-east-1
#    JwtSecretKey: <your-strong-secret>
#    Confirm changes before deploy: Y

# 5. Get the API URL from the output
# It will look like: https://abc123.execute-api.us-east-1.amazonaws.com

# 6. Run demo_checklist.md against the real URL
```

## How the Local Simulator Works

`shared/local_dynamo.py` implements `get_item`, `put_item`, `update_item`, `delete_item`, `query`, and `scan` using JSON files in `local_data/`. Writes are atomic (write to `.tmp`, then rename) to prevent corruption.

The `dynamo_client.py` factory checks `USE_LOCAL_DYNAMO`:
- `true` → returns a `LocalDynamoTable` backed by a JSON file
- `false` → returns a real `boto3.resource('dynamodb').Table(...)` object

Every handler imports only `get_table` from `dynamo_client` — no boto3 anywhere in the handlers. Switching environments requires only changing the env var.

## Key Design Notes

See `architecture.md` for the full explanation. Short version:
- **One Lambda per endpoint** — makes the API Gateway mapping explicit, easy to learn from
- **Audit logs are synchronous** — Lambda has no `BackgroundTasks`; writes happen inside the handler
- **UUIDs replace auto-increment IDs** — DynamoDB has no sequences
- **JWT validated in each handler** — no API Gateway JWT authorizer dependency for local testing
- **JWT_SECRET_KEY is an env var** — replaces the hardcoded `"secret123_!"` from `routers/auth.py`
