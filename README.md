# Lexecon

A governance runtime for AI agents. Evaluates proposed actions against a deterministic policy graph, issues Ed25519-signed capability tokens for approved actions, and records every decision in a SHA-256 hash-chained audit ledger.

[![CI](https://github.com/Lexicoding-systems/Lexecon/actions/workflows/ci.yml/badge.svg)](https://github.com/Lexicoding-systems/Lexecon/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Lexicoding-systems/Lexecon/branch/main/graph/badge.svg)](https://codecov.io/gh/Lexicoding-systems/Lexecon)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**v0.1.0** | 1,053 tests | 81% coverage | 17,882 LOC

---

## How It Works

```
AI Agent / Application
        │  proposed action
        ▼
┌───────────────────────────────────────────────────┐
│               REST API  (FastAPI)                  │
└───────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│             Governance Runtime                     │
│                                                   │
│  PolicyEngine  ──  deterministic graph, <10ms     │
│       │                                           │
│       ├── RiskService      6-dimension scoring    │
│       ├── LedgerChain      SHA-256 hash chain     │
│       ├── EvidenceService  immutable artifacts    │
│       └── CapabilityToken  Ed25519-signed auth    │
└───────────────────────────────────────────────────┘
        │
        ▼
SQLite (dev) / PostgreSQL (prod)  ·  Redis (optional)
```

An agent submits a proposed action. The policy engine evaluates it deterministically — no LLM in the path. Approved actions receive a time-limited signed token. Every decision, approved or denied, is appended to a hash-chained ledger that can be independently verified.

---

## Quick Start

```bash
git clone https://github.com/Lexicoding-systems/Lexecon.git
cd Lexecon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn lexecon.api.server:app --reload --port 8000
```

Open http://localhost:8000/docs, or send a decision directly:

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

# {
#   "decision_id": "dec_01HQXYZ...",
#   "outcome": "approved",
#   "capability_token": "cap_...",
#   "risk_score": 42,
#   "ledger_entry_id": "entry_5"
# }
```

Verify the audit chain:

```python
requests.get("http://localhost:8000/ledger/verify").json()
# {"valid": true, "entries_verified": 42, "chain_intact": true}
```

Run the tests:

```bash
python3 -m pytest tests/ -q   # 1,053 tests, 81% coverage
```

---

## Policy Engine

Policies are expressed as graphs of typed terms and relations — not prompts. Evaluation is fully deterministic.

```python
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.terms import PolicyTerm, TermType
from lexecon.policy.relations import PolicyRelation, RelationType

engine = PolicyEngine(mode=PolicyMode.STRICT)

actor  = PolicyTerm(term_id="t_ai",   term_type=TermType.ACTOR,  value="ai_agent:*")
action = PolicyTerm(term_id="t_read", term_type=TermType.ACTION, value="read:customer_data")

engine.add_term(actor)
engine.add_term(action)
engine.add_relation(PolicyRelation(
    relation_type=RelationType.PERMITS,
    source_term_id="t_ai",
    target_term_id="t_read",
))

result = engine.evaluate(actor="ai_agent:assistant", action="read:customer_data")
# result.outcome == "approved"
```

**Modes:** `strict` (deny by default) · `permissive` (allow unless forbidden) · `paranoid` (deny high-risk without human confirmation)

---

## Components

| Component | Purpose | Notes |
|-----------|---------|-------|
| **PolicyEngine** | Deterministic graph-based evaluation | <10ms, 3 modes |
| **LedgerChain** | SHA-256 hash-chained audit trail | Tamper-evident, independently verifiable |
| **RiskService** | 6-dimension scoring (0–100) | Auto-escalate ≥80 |
| **CapabilityToken** | Ed25519-signed authorization | Time-limited |
| **EvidenceService** | Immutable artifact storage | 8 artifact types |
| **EscalationService** | High-risk safety valve | SLA-tracked |
| **OverrideService** | Human intervention | Role-gated, justification required |
| **ComplianceMappingService** | Audit record → framework mapping | SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, NIST CSF |
| **AuthService** | RBAC + MFA + OIDC | 4 roles, TOTP, Google/Azure/Okta |

---

## CLI

```bash
lexecon init --node-id my-node          # generate keypair, create config
lexecon server --port 8000
lexecon decide --actor "ai_agent:bot" \
               --action "read:data" \
               --tool "db_query" \
               --intent "answer user question"
lexecon verify-ledger --ledger-file lexecon_ledger.db
```

> Keys are generated locally and never committed to the repository. Use a KMS in production — see [SECURITY.md](SECURITY.md).

---

## API Reference

```
POST  /decide                              evaluate a governance decision
POST  /decide/verify                       verify decision signature
GET   /ledger/entries                      query ledger
GET   /ledger/verify                       verify chain integrity

GET   /policies                            list loaded policies
POST  /policies/load                       load a policy

POST  /auth/login
GET   /auth/me
POST  /auth/users                          create user (admin)
GET   /auth/oidc/providers

POST  /api/governance/risk/assess          6-dimension risk score
POST  /api/governance/escalation
POST  /api/governance/override
POST  /api/governance/evidence             register artifact
GET   /api/governance/compliance/{fw}/gaps gap analysis

GET   /health
GET   /metrics                             Prometheus format
```

Full reference: [docs/API_REFERENCE.md](docs/API_REFERENCE.md) or http://localhost:8000/docs

---

## Configuration

Development (`.env`):

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

Full reference: [docs/SETUP.md](docs/SETUP.md)

---

## Testing

```bash
python3 -m pytest tests/ -q
python3 -m pytest tests/ --cov=src/lexecon --cov-report=term-missing
python3 -m pytest tests/test_decision_service.py tests/test_policy_engine.py -v
bandit -r src/
```

| Area | Tests | Coverage |
|------|-------|----------|
| Security / Auth | ~100 | 90%+ |
| Compliance mapping | ~60 | 100% |
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

See [docs/SETUP.md](docs/SETUP.md) for the full production guide.

---

## Use Cases

Governance records and policy enforcement can support requirements in a range of contexts:

- **AI agent safety** — intercept and evaluate agent actions before execution
- **Regulated industries** — auditable records for healthcare, finance, and legal workflows
- **Framework alignment** — governance records mapped to SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, NIST CSF, and EU AI Act Articles 11, 12, and 14
- **Internal compliance programs** — structured evidence collection and gap analysis

Lexecon provides infrastructure: auditable records, structured policy enforcement, cryptographic attestations. It does not certify compliance. Regulatory conformity requires organisational processes, legal review, and additional controls beyond what any software library provides. See [docs/SECURITY_POSTURE.md](docs/SECURITY_POSTURE.md).

---

## Known Limitations

- REST API only — no GraphQL or event streaming
- Frontend dashboard not fully integrated with API
- Multi-tenancy uses logical separation, not database sharding

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/SETUP.md](docs/SETUP.md) | Installation, environment variables, Docker, production setup |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | All 40+ endpoints with request/response examples |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagrams, data flows, component architecture |
| [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) | Developer guide and module reference |

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

**Version:** 0.1.0 | **Updated:** March 2026
