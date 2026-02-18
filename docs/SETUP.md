# Lexecon — Setup & Installation Guide

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.9 – 3.12 |
| pip | ≥ 23.0 |
| SQLite | ≥ 3.35 (bundled with Python) |
| PostgreSQL | ≥ 14 (production only) |
| Redis | ≥ 7.0 (optional caching) |
| Docker | ≥ 24.0 (optional) |

---

## Local Development Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd Lexecon

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install with all extras
pip install -e ".[dev,observability,performance]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Minimum required settings for local development:

```dotenv
LEXECON_ENV=development
LEXECON_NODE_ID=dev-node
PORT=8000
LEXECON_LOG_LEVEL=INFO
LEXECON_POLICY_MODE=strict
```

### 3. Initialize a node

```bash
lexecon init --node-id dev-node
```

This generates Ed25519 signing keys and creates `lexecon-config.json` with the node's public key fingerprint.

### 4. Start the development server

```bash
# From the Lexecon/ directory:
uvicorn lexecon.api.server:app --reload --port 8000
```

The API is now at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

---

## CLI Usage

After installation, the `lexecon` CLI is available:

```bash
# Initialize node (generates keys, config)
lexecon init --node-id my-node [--data-dir /path/to/data]

# Start API server
lexecon server [--node-id my-node] [--port 8000] [--host 0.0.0.0]

# Make a decision via CLI
lexecon decide \
  --actor "ai_agent:assistant" \
  --action "read:customer_data" \
  --tool "database_query" \
  --intent "answer customer question"

# Load a policy from file
lexecon load-policy --policy-file policy.json

# Verify ledger integrity
lexecon verify-ledger --ledger-file lexecon_ledger.db

# Check version
lexecon --version
```

---

## Running Tests

```bash
# Full test suite
python3 -m pytest tests/ -q --no-cov

# With coverage report
python3 -m pytest tests/ --cov=src/lexecon --cov-report=term-missing

# Single module
python3 -m pytest tests/test_decision_service.py -v

# Exclude integration tests
python3 -m pytest tests/ --ignore=tests/integration -q

# Security tests only
python3 -m pytest tests/test_security.py tests/test_security_headers.py -v
```

Expected: 1,053 tests passing, 81% coverage.

---

## Docker Setup

### Development (docker-compose)

```bash
# Start all services (API + optional Redis)
docker-compose up

# Rebuild after code changes
docker-compose up --build
```

### Build image manually

```bash
docker build -t lexecon:latest .
docker run -p 8000:8000 \
  -e LEXECON_ENV=production \
  -e LEXECON_NODE_ID=prod-node \
  -e LEXECON_POLICY_MODE=strict \
  lexecon:latest
```

---

## Production Setup (PostgreSQL)

### 1. Provision PostgreSQL

```bash
# Example using Railway, Heroku, Supabase, or self-hosted
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/lexecon
```

### 2. Required environment variables (production)

```dotenv
# Node
LEXECON_ENV=production
LEXECON_NODE_ID=prod-node-01
LEXECON_POLICY_MODE=strict

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/lexecon
LEXECON_DB_POOL_SIZE=20
LEXECON_DB_MAX_OVERFLOW=30

# Security — generate strong random values
LEXECON_MASTER_KEY=<64-char hex>
DB_ENCRYPTION_KEY=<base64-32-bytes>
SESSION_SECRET_KEY=<64-char hex>

# API
PORT=8000
LEXECON_CORS_ORIGINS=https://your-frontend-domain.com

# Logging
LEXECON_LOG_LEVEL=INFO
LEXECON_LOG_FORMAT=json
```

### 3. Generate secure keys

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # LEXECON_MASTER_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"  # SESSION_SECRET_KEY
python3 -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"  # DB_ENCRYPTION_KEY
```

### 4. Kubernetes deployment

```bash
# Apply manifests
kubectl apply -f deployment/kubernetes/

# Or use Helm
helm install lexecon deployment/helm/ \
  --set env.LEXECON_ENV=production \
  --set env.DATABASE_URL=<your-db-url>
```

---

## Environment Variables Reference

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `LEXECON_ENV` | `development` | `development` or `production` |
| `LEXECON_NODE_ID` | `railway-node` | Unique node identifier |
| `PORT` | `8000` | API server port |
| `LEXECON_POLICY_MODE` | `strict` | `strict`, `permissive`, or `paranoid` |
| `LEXECON_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LEXECON_LOG_FORMAT` | `json` | `json` or `text` |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | SQLite | Full database URL |
| `LEXECON_DATABASE_URL` | — | Alternative to `DATABASE_URL` |
| `LEXECON_USE_POSTGRESQL` | `false` | Force PostgreSQL even if SQLite URL |
| `LEXECON_DATA_DIR` | `.` | Directory for SQLite files |
| `LEXECON_DB_POOL_SIZE` | `20` | Connection pool size |
| `LEXECON_DB_MAX_OVERFLOW` | `30` | Max overflow connections |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `LEXECON_MASTER_KEY` | — | Master encryption key (required in prod) |
| `DB_ENCRYPTION_KEY` | — | Field-level DB encryption key |
| `SESSION_SECRET_KEY` | — | Session token signing key |
| `MFA_ENCRYPTION_KEY` | — | TOTP secret encryption key |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `LEXECON_RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `LEXECON_RATE_LIMIT_GLOBAL_PER_IP` | `100/60` | Global per-IP limit |
| `LEXECON_RATE_LIMIT_AUTH_LOGIN` | `5/300` | Login endpoint limit |
| `LEXECON_RATE_LIMIT_API_PER_USER` | `1000/3600` | Per-user API limit |

### OIDC (Optional)

| Variable | Description |
|----------|-------------|
| `OIDC_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `OIDC_GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `OIDC_AZURE_CLIENT_ID` | Azure AD client ID |
| `OIDC_AZURE_CLIENT_SECRET` | Azure AD client secret |
| `OIDC_AZURE_TENANT_ID` | Azure AD tenant (default: `common`) |
| `OIDC_CUSTOM_DISCOVERY_URL` | Any OIDC provider discovery URL |
| `OIDC_CUSTOM_CLIENT_ID` | Custom OIDC client ID |
| `OIDC_CUSTOM_CLIENT_SECRET` | Custom OIDC client secret |

### Observability (Optional)

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry error tracking DSN |
| `LEXECON_ENABLE_METRICS` | Enable Prometheus metrics (`true`/`false`) |
| `LEXECON_REDIS_URL` | Redis URL for caching |

---

## First API Request

### Health check

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "version": "0.1.0", "node_id": "dev-node"}
```

### Make a governance decision

```bash
curl -X POST http://localhost:8000/decide \
  -H "Content-Type: application/json" \
  -d '{
    "actor": "ai_agent:assistant",
    "proposed_action": "read customer transaction history",
    "tool": "database_query",
    "user_intent": "answer customer support question",
    "data_classes": ["pii", "financial"],
    "risk_level": 2,
    "policy_mode": "strict"
  }'
```

```json
{
  "decision_id": "dec_01HQXYZ...",
  "outcome": "approved",
  "reasoning": "Action permitted: policy allows ai_agent actors read access to customer data for support purposes",
  "risk_level": "medium",
  "risk_score": 42,
  "capability_token": "cap_...",
  "ledger_entry_id": "entry_1",
  "timestamp": "2024-02-18T12:00:00Z"
}
```

---

## Makefile Shortcuts

```bash
make install      # Install all dependencies
make test         # Run test suite
make coverage     # Run tests with coverage report
make lint         # Run ruff + mypy
make format       # Run black + isort
make security     # Run bandit security scan
make docker-build # Build Docker image
make docker-run   # Run Docker container
```

---

## Programmatic Usage

```python
from lexecon.decision.service import DecisionService, DecisionRequest
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.ledger.chain import LedgerChain
from lexecon.risk.service import RiskService

# Initialize services
policy_engine = PolicyEngine(mode=PolicyMode.STRICT)
ledger = LedgerChain()
risk_service = RiskService()
decision_service = DecisionService(
    policy_engine=policy_engine,
    ledger=ledger,
    risk_service=risk_service,
)

# Make a decision
request = DecisionRequest(
    actor="ai_agent:customer_service",
    proposed_action="read:customer_profile",
    tool="database_query",
    user_intent="answer customer question about their account",
    risk_level=2,
)

response = decision_service.evaluate_request(request)
print(response.decision)   # "allowed" | "denied" | "escalated"
print(response.reasoning)  # Human-readable explanation
```

---

## Troubleshooting

### `No such table: ...` errors during tests

Stale SQLite database files. Clean up:

```bash
find . -name "lexecon_*.db" -delete
find . -name "lexecon_*.db-wal" -delete
find . -name "lexecon_*.db-shm" -delete
```

### `ModuleNotFoundError: No module named 'cryptography'`

Install the cryptography extra:

```bash
pip install cryptography>=42.0.0
```

### `LibreSSL` warnings on macOS

Expected on macOS (uses LibreSSL instead of OpenSSL). Does not affect functionality. Suppress with:

```bash
export PYTHONWARNINGS="ignore::urllib3.exceptions.NotOpenSSLWarning"
```

### Tests timeout when run all at once

Run in smaller batches:

```bash
python3 -m pytest tests/test_decision_service.py tests/test_policy_engine.py -q
python3 -m pytest tests/test_ledger.py tests/test_security.py -q
```

### Port already in use

```bash
lsof -ti :8000 | xargs kill -9
```
