# Lexecon

A cryptographic governance engine for AI safety and regulatory compliance.

> **Quick Demo:** `./scripts/demo-setup.sh && ./scripts/demo-run.sh` → http://localhost:8000

[![CI](https://github.com/Lexicoding-systems/Lexecon/actions/workflows/ci.yml/badge.svg)](https://github.com/Lexicoding-systems/Lexecon/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Lexicoding-systems/Lexecon/branch/main/graph/badge.svg)](https://codecov.io/gh/Lexicoding-systems/Lexecon)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```bash
pip install -e ".[dev]"
uvicorn lexecon.api.server:app --reload --port 8000
python3 -m pytest tests/ -q   # 1,053 tests, 81% coverage
```

**Status:** v0.1.0 | 1,053 tests passing | 81% coverage | 17,882 LOC

---

## What It Does

Lexecon sits between AI agents and the systems they interact with, evaluating every proposed action before it executes:

1. **Evaluates decisions in <10ms** using a graph-based policy engine — no LLM in the evaluation path
2. **Issues capability tokens** — time-limited, Ed25519-signed authorization for approved actions
3. **Records everything** in a tamper-evident SHA-256 hash-chained ledger
4. **Scores risk** across 6 dimensions (security, privacy, compliance, operational, reputational, financial)
5. **Maps governance records to framework controls** — SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, NIST CSF
6. **Implements record-keeping and oversight controls** for EU AI Act Articles 11 (technical docs), 12 (record retention), and 14 (human oversight logging)

> **On compliance claims:** Lexecon provides infrastructure — auditable records, structured policy enforcement, cryptographic attestations — that can serve as evidence when satisfying regulatory controls. It does not certify compliance. Regulatory conformity requires organisational processes, legal review, and additional controls beyond what any software library provides. See [docs/SECURITY_POSTURE.md](docs/SECURITY_POSTURE.md).

---

## Quick Start

### Install

```bash
git clone https://github.com/Lexicoding-systems/Lexecon.git
cd Lexecon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn lexecon.api.server:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

### Make a Governance Decision

```python
import requests

response = requests.post("http://localhost:8000/decide", json={
    "actor": "ai_agent:customer_service",
    "proposed_action": "read customer transaction history",
    "tool": "database_query",
    "user_intent": "answer customer support question",
    "data_classes": ["pii", "financial"],
    "risk_level": 2,
    "policy_mode": "strict"
})

result = response.json()
# {
#   "decision_id": "dec_01HQXYZ...",
#   "outcome": "approved",
#   "reasoning": "Policy permits support access to customer data",
#   "risk_level": "medium",
#   "risk_score": 42,
#   "capability_token": "cap_...",
#   "ledger_entry_id": "entry_5"
# }
```

### Verify the Audit Trail

```python
# Verify cryptographic chain integrity
response = requests.get("http://localhost:8000/ledger/verify")
print(response.json())
# {"valid": true, "entries_verified": 42, "chain_intact": true}
```

### CLI

> **Key generation:** `lexecon init` generates a fresh keypair locally.
> Keys are never committed to the repository — keep them outside the project root
> or use a KMS in production (see [SECURITY.md](SECURITY.md)).

```bash
lexecon init --node-id my-node          # generate keys, create config
lexecon server --port 8000              # start API server
lexecon decide --actor "ai_agent:bot" \
               --action "read:data" \
               --tool "db_query" \
               --intent "answer user question"
lexecon verify-ledger --ledger-file lexecon_ledger.db
```

---

## Architecture

```
AI Agents / Applications
        │
        ▼
┌───────────────────────────────────────────────────────┐
│                  REST API (FastAPI)                     │
│   Rate Limiting │ Security Headers │ Auth Middleware    │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│              SERVICE REGISTRY (DI)                     │
│                                                       │
│  DecisionService ──► PolicyEngine (<10ms)             │
│       │                                               │
│       ├──► RiskService (6 dimensions, auto-escalate)  │
│       ├──► LedgerChain (SHA-256 hash chain)           │
│       ├──► EvidenceService (immutable artifacts)      │
│       └──► CapabilityToken (Ed25519-signed)           │
│                                                       │
│  EscalationService │ OverrideService                  │
│  ComplianceMappingService │ ResponsibilityTracker      │
│  AuthService (MFA + RBAC + OIDC)                      │
└───────────────────────────────────────────────────────┘
        │
        ▼
SQLite (dev) / PostgreSQL (prod) │ Redis (optional cache)
```

### Component Summary

| Component | Purpose | Notes |
|-----------|---------|-------|
| **PolicyEngine** | Deterministic graph-based evaluation | <10ms, 3 modes |
| **DecisionService** | Request orchestration + token issuance | Async FastAPI |
| **LedgerChain** | SHA-256 hash-chained audit trail | Tamper-evident |
| **RiskService** | 6-dimension scoring (0–100) | Auto-escalate ≥80 |
| **EvidenceService** | Immutable artifact storage | 8 artifact types |
| **EscalationService** | High-risk safety valve | SLA-tracked |
| **OverrideService** | Human intervention | Role-gated, justification required |
| **ComplianceMappingService** | Framework alignment | 6 frameworks + EU AI Act |
| **ResponsibilityTracker** | WHO/WHY accountability | 4 responsibility levels |
| **AuthService** | RBAC + MFA + OIDC | 4 roles, TOTP, Google/Azure/Okta |

---

## Policy Engine

Graph-based, fully deterministic — no LLM dependency:

```python
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.terms import PolicyTerm, TermType
from lexecon.policy.relations import PolicyRelation, RelationType

engine = PolicyEngine(mode=PolicyMode.STRICT)

# Define terms
actor = PolicyTerm(term_id="t_ai", term_type=TermType.ACTOR, value="ai_agent:*")
action = PolicyTerm(term_id="t_read", term_type=TermType.ACTION, value="read:customer_data")

# Define relation
engine.add_term(actor)
engine.add_term(action)
engine.add_relation(PolicyRelation(
    relation_type=RelationType.PERMITS,
    source_term_id="t_ai",
    target_term_id="t_read",
))

result = engine.evaluate(actor="ai_agent:assistant", action="read:customer_data")
# result.outcome = "approved"
```

**Modes:**
- `strict` — deny by default, explicit permit required
- `permissive` — allow unless explicitly forbidden
- `paranoid` — deny high-risk without human confirmation

---

## EU AI Act Compliance

```bash
# Article 11 — Auto-generated technical documentation
GET /compliance/eu-ai-act/article-11

# Article 12 — 10-year record-keeping with legal hold
GET /compliance/eu-ai-act/article-12/status
POST /compliance/eu-ai-act/article-12/legal-hold

# Article 14 — Human oversight intervention logging
POST /compliance/eu-ai-act/article-14/intervention
```

---

## API Reference (Summary)

```
# Decisions & Ledger
POST  /decide                              evaluate a governance decision
POST  /decide/verify                       verify decision signature
GET   /ledger/entries                      query ledger
GET   /ledger/verify                       verify chain integrity

# Policies
GET   /policies                            list loaded policies
POST  /policies/load                       load a policy

# Auth
POST  /auth/login                          login
GET   /auth/me                             current user
POST  /auth/users                          create user (admin)
GET   /auth/oidc/providers                 list OIDC providers

# Risk, Escalation, Override
POST  /api/governance/risk/assess          6-dimension risk score
POST  /api/governance/escalation           create escalation
POST  /api/governance/override             execute override

# Evidence & Compliance
POST  /api/governance/evidence             register artifact
GET   /api/governance/compliance/{fw}/gaps gap analysis
GET   /api/governance/audit-export/list    list exports

# Observability
GET   /health
GET   /metrics                             Prometheus format
```

Full reference: [docs/API_REFERENCE.md](docs/API_REFERENCE.md) or http://localhost:8000/docs

---

## Configuration

Minimum for development (`.env`):

```dotenv
LEXECON_ENV=development
LEXECON_NODE_ID=dev-node
LEXECON_POLICY_MODE=strict
PORT=8000
```

Production additions:

```dotenv
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/lexecon
LEXECON_MASTER_KEY=<64-char hex>
SESSION_SECRET_KEY=<64-char hex>
DB_ENCRYPTION_KEY=<base64-32-bytes>
LEXECON_CORS_ORIGINS=https://your-domain.com
```

Full variable reference: [docs/SETUP.md](docs/SETUP.md)

---

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -q

# With coverage
python3 -m pytest tests/ --cov=src/lexecon --cov-report=term-missing

# Specific area
python3 -m pytest tests/test_decision_service.py tests/test_policy_engine.py -v
python3 -m pytest tests/test_security.py tests/test_compliance_mapping.py -v

# Security scan
bandit -r src/
```

**Test coverage by area:**

| Area | Tests | Coverage |
|------|-------|----------|
| Security / Auth | ~100 | 90%+ |
| Compliance mapping | ~60 | 100% |
| EU AI Act | ~50 | 95%+ |
| Policy engine | ~100 | 90%+ |
| Decision service | ~200 | 82%+ |
| API endpoints | ~150 | 85%+ |
| **Total** | **1,053** | **81%** |

---

## Deployment

```bash
# Docker
docker-compose up

# Kubernetes
kubectl apply -f deployment/kubernetes/

# Helm
helm install lexecon deployment/helm/ \
  --set env.LEXECON_ENV=production \
  --set env.DATABASE_URL=<your-db-url>
```

See [docs/SETUP.md](docs/SETUP.md) for full production guide.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/SETUP.md](docs/SETUP.md) | Installation, environment variables, Docker, production setup |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | All 40+ endpoints with request/response examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagrams, data flows, component architecture |
| [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) | Developer guide and module reference |
| [docs/market/](docs/market/) | Business strategy, investor, and market-positioning materials |

---

## Known Limitations

- No GraphQL — REST API only
- Frontend (React dashboard) not fully integrated with API
- Multi-tenancy uses logical separation, not database sharding
- Synchronous API only — no event streaming

---

## Contributing

1. Fork → feature branch → `pip install -e ".[dev]"` → `pre-commit install`
2. Write tests (coverage ≥80% required)
3. `python3 -m pytest tests/ -q` — all tests must pass
4. `ruff check src/ && mypy src/`
5. Submit PR

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

**Contact:** contact@lexicodinglabs.com | security@lexicodinglabs.com

**Version:** 0.1.0 | **Updated:** February 2026
