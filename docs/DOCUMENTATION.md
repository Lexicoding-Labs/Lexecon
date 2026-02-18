# Lexecon — Comprehensive Documentation

**Version:** 0.1.0
**License:** MIT
**Python:** 3.9 – 3.12

---

## What is Lexecon?

Lexecon is a **cryptographic governance engine** for AI safety and regulatory compliance. It provides:

- **Deterministic policy evaluation** — decisions made by a graph-based policy engine, not an LLM
- **Tamper-evident audit ledger** — SHA-256 hash-chained record of every decision
- **6-dimension risk assessment** — security, privacy, compliance, operational, reputational, financial
- **Capability tokens** — time-limited, cryptographically signed authorization tokens
- **EU AI Act automation** — Articles 11, 12, and 14 compliance out of the box
- **6 framework mappings** — SOC 2, ISO 27001, GDPR, HIPAA, PCI-DSS, NIST CSF
- **Human oversight layer** — escalation, override, and intervention tracking
- **RBAC + MFA + OIDC** — enterprise authentication built in

---

## Quick Navigation

| Document | Contents |
|----------|----------|
| [SETUP.md](SETUP.md) | Installation, configuration, Docker, production deployment |
| [API_REFERENCE.md](API_REFERENCE.md) | All endpoints with request/response examples |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams, data flows, component overview |
| [DOCUMENTATION.md](DOCUMENTATION.md) | This file — developer guide and module reference |

---

## Core Concepts

### Decision

A decision is the central unit of governance. When an AI agent wants to perform an action, it sends a `POST /decide` request. Lexecon evaluates it against loaded policies and returns an outcome.

```
actor + proposed_action + tool + intent → PolicyEngine → outcome
                                        ↓
                                  LedgerChain (immutable record)
                                        ↓
                                  RiskService (6-dimension score)
                                        ↓
                                  CapabilityToken (if approved)
```

Decision IDs use ULID format: `dec_01HQXYZ...` (26-char ULID suffix).

**Outcomes:**
- `approved` — action permitted
- `denied` — action forbidden
- `escalated` — requires human review (high risk)
- `conditional` — permitted with constraints

---

### Policy

Policies are graphs of terms and relations:

```
TERMS                   RELATIONS
─────                   ─────────
actor:    ai_agent:*    permits(ai_agent, read_customer)
action:   read_customer forbids(ai_agent, delete_records)
resource: customer_db   requires(bulk_export, human_approval)
```

Three evaluation modes:
- `strict` — deny by default, explicit permit required
- `permissive` — allow unless explicitly forbidden
- `paranoid` — deny high-risk without human confirmation

Load policies via `POST /policies/load` or the CLI: `lexecon load-policy --policy-file policy.json`

---

### Ledger

Every event (decision, risk, escalation, override) is appended to a hash-chained ledger:

```python
entry_hash = SHA-256(
    entry_id + event_type + timestamp +
    json.dumps(data, sort_keys=True) +
    previous_hash
)
```

This makes any retrospective tampering detectable. Verify at any time: `GET /ledger/verify`

---

### Capability Token

When a decision is `approved`, Lexecon issues a time-limited capability token:

```
cap_<base64_payload>_<ed25519_signature>
```

The token encodes the permitted actor, action, and expiry. Recipients can verify the token without calling back to Lexecon.

---

### Risk Assessment

Six independent dimensions, each scored 0–100:

| Dimension | What it measures |
|-----------|-----------------|
| Security | Attack surface, threat vectors |
| Privacy | PII exposure, data minimization |
| Compliance | Regulatory rule adherence |
| Operational | System stability impact |
| Reputational | Brand and trust risk |
| Financial | Cost, liability exposure |

Overall score ≥ 80 → automatic escalation.

---

### Escalation

When risk is critical or policy requires human review:

1. Escalation created (`POST /api/governance/escalation`)
2. Assigned to responsible humans
3. SLA deadline tracked
4. Resolved with outcome: `approved`, `denied`, `deferred`, `escalated_further`

---

### Override

Authorized executives can override governance decisions:

1. Override posted with `justification` (min 20 chars) and `authorized_by`
2. Records `original_outcome` → `new_outcome`
3. Optional `expires_at` for time-limited exceptions
4. Full audit trail in ledger

---

## Module Reference

### `lexecon.decision.service`

Central orchestration. Accepts a request, runs policy evaluation, risk assessment, issues token, records to ledger.

```python
from lexecon.decision.service import DecisionService, DecisionRequest

service = DecisionService(policy_engine=engine, ledger=ledger)
request = DecisionRequest(
    actor="ai_agent:assistant",
    proposed_action="read:customer_profile",
    tool="database_query",
    user_intent="answer customer question",
    risk_level=2,
)
response = service.evaluate_request(request)
# response.decision: "allowed" | "denied" | "escalated"
# response.to_dict(): full response dict
```

---

### `lexecon.policy.engine`

Graph-based, deterministic policy evaluator.

```python
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.policy.terms import PolicyTerm, TermType
from lexecon.policy.relations import PolicyRelation, RelationType

engine = PolicyEngine(mode=PolicyMode.STRICT)

# Add terms
actor_term = PolicyTerm(term_id="t1", term_type=TermType.ACTOR, value="ai_agent:*")
action_term = PolicyTerm(term_id="t2", term_type=TermType.ACTION, value="read:data")

# Add relation
engine.add_term(actor_term)
engine.add_term(action_term)
engine.add_relation(PolicyRelation(
    relation_type=RelationType.PERMITS,
    source_term_id="t1",
    target_term_id="t2",
))

result = engine.evaluate(actor="ai_agent:assistant", action="read:data")
# result.outcome: "approved" | "denied" | "escalated" | "conditional"
```

---

### `lexecon.ledger.chain`

Tamper-evident append-only ledger.

```python
from lexecon.ledger.chain import LedgerChain

ledger = LedgerChain()
entry_id = ledger.append(event_type="decision", data={"decision_id": "dec_..."})
is_valid = ledger.verify()  # True if chain intact
entries = ledger.get_entries(event_type="decision", limit=10)
```

---

### `lexecon.security.auth_service`

User management, RBAC, session handling.

```python
from lexecon.security.auth_service import AuthService, Role

auth = AuthService(db_path="auth.db")

user = auth.create_user(
    username="alice",
    email="alice@example.com",
    password="Str0ng!Pass#2024",
    role=Role.AUDITOR,
    full_name="Alice Smith",
)

user, error = auth.authenticate("alice", "Str0ng!Pass#2024")
session = auth.create_session(user=user, ip_address="192.168.1.1")
validated, error = auth.validate_session(session.session_id)
```

---

### `lexecon.risk.service`

6-dimension risk scoring.

```python
from lexecon.risk.service import RiskService

risk_service = RiskService()
assessment = risk_service.assess(
    actor="ai_agent:assistant",
    action="bulk_export_pii",
    data_classes=["pii", "financial"],
    context={},
)
# assessment.overall_score: 0-100
# assessment.risk_level: "low" | "medium" | "high" | "critical"
# assessment.requires_escalation: bool
```

---

### `lexecon.identity.signing`

Ed25519 and RSA-4096 signing.

```python
from lexecon.identity.signing import KeyManager

km = KeyManager(keys_dir="/path/to/keys")
km.generate_keys()  # Generates Ed25519 + RSA-4096 key pairs

signature = km.sign(data=b"message")
valid = km.verify(data=b"message", signature=signature)
public_key_pem = km.get_public_key_pem()
fingerprint = km.get_fingerprint()
```

---

### `lexecon.capability.tokens`

Time-limited capability tokens.

```python
from lexecon.capability.tokens import CapabilityToken

token = CapabilityToken.issue(
    actor="ai_agent:assistant",
    action="read:customer_profile",
    ttl_seconds=3600,
)
# token.token_string: "cap_eyJ...._sig..."

is_valid = CapabilityToken.verify(token.token_string)
```

---

### `lexecon.observability.metrics`

Prometheus metrics.

```python
from lexecon.observability.metrics import metrics

metrics.record_request("POST", "/decide", 200, 0.015)
metrics.record_decision(allowed=True, actor="ai_agent", risk_level=2, duration=0.010)
metrics.record_ledger_entry()
output = metrics.export_metrics()  # Prometheus text format bytes
```

---

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -q

# Run with coverage
python3 -m pytest tests/ --cov=src/lexecon --cov-report=term-missing

# Run specific area
python3 -m pytest tests/test_decision_service.py tests/test_policy_engine.py -v
python3 -m pytest tests/test_security.py -v
python3 -m pytest tests/test_compliance_mapping.py -v

# Exclude integration tests (faster)
python3 -m pytest tests/ --ignore=tests/integration -q
```

### Test coverage by area

| Area | Tests | Coverage |
|------|-------|----------|
| Decision service | ~200 | 82% |
| Policy engine | ~100 | 90% |
| Security / Auth | ~100 | 90% |
| Compliance mapping | ~60 | 100% |
| EU AI Act | ~50 | 95% |
| Ledger / Evidence | ~80 | 88% |
| Risk / Escalation | ~100 | 85% |
| API endpoints | ~150 | 85% |
| **Total** | **1,053** | **81%** |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Run pre-commit hooks: `pre-commit install`
5. Write tests for new functionality
6. Run tests: `python3 -m pytest tests/ -q`
7. Run linting: `ruff check src/ && mypy src/`
8. Submit a pull request

Code style: black formatting, isort imports, ruff linting, mypy type checking.

---

## License

MIT — see [LICENSE](../LICENSE).
