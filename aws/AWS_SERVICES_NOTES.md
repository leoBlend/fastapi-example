# AWS Services — Short Reference Notes

---

## 1. IAM (Identity and Access Management)

**What it is:** The permission system for everything in AWS. Nothing can do anything without IAM allowing it.

**Key concepts:**
- **Principal** — who is acting (a Lambda function, a user, another service).
- **Policy** — a JSON document listing what actions are allowed/denied on which resources.
- **Role** — an identity that a service *assumes* temporarily. Lambda functions run as a role.
- **Least privilege** — only grant what is actually needed.

**For this app the Lambda role needs:**
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:Scan"
  ],
  "Resource": [
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-Users",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-Users/index/*",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-Todos",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-Todos/index/*",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-AuditLog",
    "arn:aws:dynamodb:REGION:ACCOUNT:table/TodoApp-AuditLog/index/*"
  ]
}
```
No `dynamodb:CreateTable`, no `s3:*`, no wildcards. If a Lambda doesn't need it, it doesn't get it.

Lambda also needs `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` to write to CloudWatch (SAM adds this automatically via `AWSLambdaBasicExecutionRole`).

---

## 2. Lambda

**What it is:** Run code without managing servers. You upload a function (a zip or container), and AWS runs it when triggered.

**Execution model:**
1. A trigger fires (API Gateway request, S3 event, cron, etc.).
2. AWS starts a container ("cold start" if no warm instance exists — ~200–500ms overhead).
3. Your `handler(event, context)` runs.
4. The function returns → container is frozen (not terminated — can be reused for the next invocation).
5. **Billing:** rounded to 1ms, charged for execution time + memory allocated.

**Key settings:**
- **Runtime:** Python 3.12 (latest stable Lambda Python runtime as of mid-2025).
- **Memory:** 128–10240 MB; more memory = more CPU too.
- **Timeout:** max 15 minutes; most HTTP handlers should be under 10 seconds.
- **Environment variables:** injected at deploy time; read with `os.environ` at runtime.

**Cold start mitigation:** provisioned concurrency (keeps warm instances), or just accept it for low-traffic apps.

**Lambda Layers:** zip of shared code/packages mounted at `/opt/python`. Use for libraries like `passlib` and `python-jose` that every function needs — avoids duplicating them in every function zip.

**One function per endpoint vs. monolith:**
- One per endpoint: clear IAM scoping, independent deploys, explicit API Gateway mapping.
- Monolith (one Lambda that routes internally): faster cold starts (one container serves many routes), simpler packaging. What the Mangum library does for FastAPI.
- This project uses one per endpoint for learning clarity.

---

## 3. API Gateway

**What it is:** The HTTP front door. Receives requests from the internet, routes them to Lambda functions, returns their responses.

**HTTP API vs REST API:**
| Feature | HTTP API | REST API |
|---|---|---|
| Price | ~$1/million requests | ~$3.50/million |
| Latency | ~6ms overhead | ~12ms overhead |
| Features | Lambda proxy, JWT auth, CORS | + Usage plans, WAF, API keys, request validation |

**Use HTTP API** for most new projects. REST API is worth it only when you need WAF or usage plans.

**Lambda Proxy Integration:** API Gateway passes the full HTTP request as a JSON `event` dict to Lambda. Lambda returns a JSON dict with `statusCode`, `headers`, `body`. API Gateway forwards that as the HTTP response. No transformation needed.

**Event structure (HTTP API v2.0):**
```json
{
  "version": "2.0",
  "routeKey": "POST /todo",
  "rawPath": "/todo",
  "headers": { "authorization": "Bearer eyJ..." },
  "pathParameters": { "todo_id": "abc-123" },
  "body": "{\"title\":\"Buy milk\"}",
  "requestContext": {
    "http": { "method": "POST", "path": "/todo", "sourceIp": "1.2.3.4" }
  }
}
```

**Route definition:** `METHOD /path` e.g. `POST /auth/`, `GET /todos/{todo_id}`. Path parameters become `event["pathParameters"]`.

**Authorization:**
- HTTP API supports JWT authorizers (validates tokens against a JWKS endpoint — e.g. Cognito).
- For this project, JWT is validated **inside each Lambda handler** — simpler and no Cognito dependency.
- Public routes (`/auth/`, `/auth/token`, `/healthy`) need no auth; protected routes check the token themselves.

---

## 4. DynamoDB

**What it is:** AWS's serverless key-value + document database. Fully managed, scales automatically, millisecond latency at any scale.

**Core mental model (vs SQL):**
| SQL | DynamoDB |
|---|---|
| Table with columns | Table with items (each item is a free-form map) |
| Primary key | Partition key (PK) — required; sort key (SK) — optional |
| `SELECT * WHERE id = ?` | `GetItem(Key={"PK": "..."})` — O(1), cheapest |
| `SELECT * WHERE fk = ?` | `Query` on a GSI — O(result size) |
| `SELECT *` | `Scan` — reads every item, expensive, avoid at scale |
| Foreign key join | Denormalize or use separate Query per entity |
| Auto-increment ID | UUID generated client-side before `PutItem` |

**Access pattern discipline:** Design the table around how you'll query it. Add a GSI for every query pattern that isn't the main PK. Never design schema first and query later (that's the SQL mindset).

**Billing modes:**
- **On-demand:** pay per request, no capacity planning. Best for variable/unknown traffic.
- **Provisioned:** you declare RCU/WCU; cheaper if traffic is predictable and steady.

**GSI (Global Secondary Index):** Project a different set of attributes as PK+SK, backed by a separate hidden table updated asynchronously. Adds cost. Use when you have a second common query pattern.

**This project's tables:**
- `TodoApp-Users` — PK=username; GSI EmailIndex (PK=email), GSI UserIdIndex (PK=user_id)
- `TodoApp-Todos` — PK=todo_id; GSI OwnerIndex (PK=owner_id, SK=created_at)
- `TodoApp-AuditLog` — PK=audit_id; GSI TimestampIndex (PK=entity_type, SK=timestamp)

**IDs:** integers from SQLite → `uuid.uuid4()` strings. DynamoDB has no sequences.

---

## 5. CloudWatch

**What it is:** AWS's observability service — logs, metrics, alarms, dashboards.

**Logs:**
- Every Lambda function automatically streams stdout/stderr to a CloudWatch Log Group named `/aws/lambda/{function-name}`.
- Python's `logging` module writes to stdout, so `logger.info(...)` in a Lambda handler appears in CloudWatch automatically.
- Set a **retention policy** (e.g. 30 days) in your SAM template — default is "never expires" which accumulates cost.

**Metrics (emitted automatically per Lambda):**
| Metric | What it means |
|---|---|
| `Invocations` | Total calls |
| `Errors` | Unhandled exceptions (not HTTP 4xx/5xx — those are "successful" invocations) |
| `Duration` | Execution time in ms |
| `Throttles` | Invocations rejected because concurrency limit was reached |
| `ConcurrentExecutions` | How many are running simultaneously |

**Alarms:** Set on a metric to notify (SNS, email) when a threshold is crossed — e.g. `Errors > 5 in 5 minutes`.

**Structured logging tip:** Log JSON in Lambda handlers so CloudWatch Insights can query fields:
```python
logger.info(json.dumps({"event": "todo_created", "user": username, "todo_id": todo_id}))
```

**X-Ray:** Distributed tracing — traces a request across Lambda + DynamoDB calls. Enable with `Tracing: Active` in SAM. Beyond this project's scope, but worth knowing.
