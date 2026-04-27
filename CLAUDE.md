# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lexecon is a **cryptographic governance engine** for AI safety and regulatory compliance. It provides deterministic (no-LLM) policy evaluation, tamper-evident audit logging, and multi-framework compliance automation (SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, NIST CSF, EU AI Act).

## Commands

### Backend

```bash
pip install -e ".[dev]"          # Install with dev dependencies

make test                        # Run pytest
make lint                        # flake8 + mypy
make format                      # black + isort
make clean                       # Clean build artifacts

python3 -m pytest tests/ -q                              # All tests (quiet)
python3 -m pytest tests/test_decision_service.py -v      # Single test file
python3 -m pytest tests/ --cov=lexecon --cov-report=term-missing  # With coverage

pre-commit install                # Install git hooks
pre-commit run --all-files        # Run all hooks manually
```

### Frontend (React)

```bash
cd frontend
npm start     # Dev server
npm run build # Production build
npm test      # Run tests
```

### Run API Server

```bash
lexecon server          # via CLI entry point
# or
uvicorn src.lexecon.api.server:app --reload
```

## Architecture

### Service Registry (Dependency Injection)

All services are instantiated once in `src/lexecon/api/dependencies.py` via a `ServiceRegistry` singleton. FastAPI route handlers receive services through `Depends()`. Never instantiate services directly in routes — always go through the registry.

### Decision Workflow

Every governance decision follows this pipeline:

```
HTTP Request → Validation → Rate Limit → PolicyEngine → RiskService → LedgerChain → CapabilityToken → Response
```

1. **PolicyEngine** (`src/lexecon/policy/`) — evaluates policies using terms (actor/action/resource) and relations (permits/forbids/requires). Three modes: `strict` (deny by default), `permissive` (allow unless forbidden), `paranoid` (require human approval for high risk). Deterministic, <10ms.

2. **RiskService** (`src/lexecon/risk/`) — scores 6 dimensions (Security, Privacy, Compliance, Operational, Reputational, Financial) 0–100. Auto-escalates if composite score ≥ 80.

3. **LedgerChain** (`src/lexecon/ledger/`) — SHA-256 hash-chained tamper-evident log. Every decision is appended; genesis entry anchors the chain. Do not mutate ledger entries.

4. **CapabilityToken** (`src/lexecon/capability/`) — time-limited Ed25519-signed authorization token issued after a permit decision.

5. **EvidenceService** (`src/lexecon/evidence/`) — registers immutable artifacts (8 types) associated with decisions.

### Security Layer

- **AuthService** (`src/lexecon/security/auth_service.py`) — RBAC with 4 roles: `viewer`, `operator`, `admin`, `executive`.
- **AsyncAuthService** — async variant; prefer this in async FastAPI routes.
- **OIDCService** (`src/lexecon/security/oidc_service.py`) — Google, Azure, Okta OAuth flows.
- **SignatureService** (`src/lexecon/security/signature_service.py`) — Ed25519 (default) and RSA-4096 signing.
- **Rate limiting** — configured per-IP, per-user, per-endpoint via `src/lexecon/security/rate_limit_middleware.py`; Redis-backed in production, in-memory fallback.

### API Structure

Routes live in `src/lexecon/api/routers/`. Each router maps to a domain:

| Router file | Prefix |
|---|---|
| `decisions.py` | `/decide` |
| `policy.py` | `/policies` |
| `auth.py` | `/auth/*` |
| `compliance.py` | `/compliance/*` |
| `eu_compliance.py` | `/eu-ai-act/*` |
| `compliance_mapping.py` | `/compliance/mapping/*` |
| `responsibility.py` | `/responsibility/*` |
| `audit.py` | `/audit-export/*` |
| `governance.py` | `/api/governance/*` |

### Database

`src/lexecon/db/async_database.py` manages async SQLAlchemy sessions. Database URL resolution order:
1. `LEXECON_DATABASE_URL`
2. `DATABASE_URL` (Railway/Heroku)
3. PostgreSQL default (`postgresql+asyncpg://lexecon:lexecon@localhost/lexecon`)
4. SQLite fallback (`sqlite+aiosqlite:///lexecon.db`)

Tables are created automatically at startup via `Base.metadata.create_all()`. Migration scripts are in `migrations/` (no Alembic; manual approach).

### Frontend

React 18 SPA in `frontend/src/`. The FastAPI server serves the built SPA from `/static` when `LEXECON_ENV=production`. Key frontend directories:

- `api/` — Axios-based API client
- `contexts/` — React context providers (auth, tenant)
- `pages/` — Route-level page components
- `design-system/` — Shared UI primitives

## Key Conventions

### Policy Mode

Set via `LEXECON_POLICY_MODE` env var (`strict` | `permissive` | `paranoid`). `strict` is the default and denies any action not explicitly permitted.

### Cryptographic Keys

`LEXECON_MASTER_KEY` (64-char hex) is the root secret. Never hardcode keys. `KeyManager` in `src/lexecon/identity/` manages derived Ed25519 key pairs.

### Compliance Frameworks

`ComplianceMappingService` (`src/lexecon/compliance/`) maps governance decisions to framework controls automatically. When adding new policy types, check whether they need a mapping entry.

### EU AI Act

`src/lexecon/compliance/eu_ai_act/` handles Articles 11 (technical documentation), 12 (logging), and 14 (human oversight) automation separately from the general compliance module.

### Test Coverage

CI enforces an **82% coverage threshold**. Run `python3 -m pytest tests/ --cov=lexecon --cov-report=term-missing` to check locally before pushing. Shared fixtures are in `tests/conftest.py`. Integration tests are under `tests/integration/`; load tests under `tests/load/` and `tests/k6/`.

### Observability

`src/lexecon/observability/` wraps Prometheus metrics, OpenTelemetry tracing, health checks, and Sentry. Feature flags (`FEATURE_FLAG_TRACING_ENABLED`, `FEATURE_FLAG_METRICS_DETAILED`) control which signals are active. Local Docker Compose (`docker-compose.yml`) starts Prometheus and Grafana alongside the API.

### Linting Rules

- **Line length:** 120 chars (ruff/flake8), 100 chars (black/isort)
- **mypy:** strict mode, Python 3.9 target, all untyped defs disallowed
- **docstrings:** interrogate enforces 80% coverage threshold
- **Commits:** conventional commit format enforced by pre-commit hook
