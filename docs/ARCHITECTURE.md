# Lexecon — Architecture Guide

## System Overview

Lexecon is a **cryptographic governance engine** for AI safety and regulatory compliance. It evaluates governance decisions deterministically (no LLM), issues capability tokens, maintains a tamper-evident audit ledger, and automates compliance with 6 regulatory frameworks including the EU AI Act.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LEXECON GOVERNANCE PLATFORM                         │
│                                                                               │
│   AI Agents / Applications / Human Operators                                  │
│          │                                                                    │
│          ▼                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          REST API (FastAPI)                            │  │
│  │   /decide  /ledger  /policies  /auth  /compliance  /api/governance   │  │
│  │   Rate Limiting │ Security Headers │ CORS │ Auth Middleware           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                    │
│          ▼                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        SERVICE REGISTRY (DI)                           │  │
│  │  DecisionService  │  RiskService  │  EscalationService               │  │
│  │  PolicyEngine     │  AuthService  │  OverrideService                  │  │
│  │  LedgerChain      │  EvidenceService  │  ComplianceMappingService    │  │
│  │  AuditExportService  │  ResponsibilityTracker  │  FeatureFlagService │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                    │
│          ▼                                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          DATA LAYER                                    │  │
│  │  SQLite (dev) / PostgreSQL (prod)  │  Redis (optional cache)          │  │
│  │  Ledger DB │ Auth DB │ Interventions DB │ Export DB │ Responsibility │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Decision Workflow

```
Client Request
     │
     ▼
POST /decide
     │
     ├─► Input Validation (Pydantic)
     │         │ FAIL ──► 422 Validation Error
     │
     ├─► Rate Limit Check
     │         │ BLOCKED ──► 429 Too Many Requests
     │
     ├─► DecisionService.evaluate_request()
     │         │
     │         ├─► PolicyEngine.evaluate()          ← <10ms deterministic
     │         │         │
     │         │         ├─ Load policy graph
     │         │         ├─ Resolve terms (actor, action, resource)
     │         │         ├─ Evaluate relations (permits/forbids/requires)
     │         │         └─ Apply mode (strict/permissive/paranoid)
     │         │
     │         ├─► RiskService.assess()             ← 6-dimension scoring
     │         │         │
     │         │         ├─ Security score
     │         │         ├─ Privacy score
     │         │         ├─ Compliance score
     │         │         ├─ Operational score
     │         │         ├─ Reputational score
     │         │         └─ Financial score
     │         │                   │
     │         │                   └─ Overall ≥80 ──► Auto-escalate
     │         │
     │         ├─► LedgerChain.append()             ← SHA-256 hash chain
     │         │
     │         ├─► EvidenceService.register()       ← Immutable artifact
     │         │
     │         └─► CapabilityToken.issue()          ← Time-limited auth
     │
     └─► JSON Response
           {
             "decision_id": "dec_01HQXYZ...",
             "outcome": "approved|denied|escalated|conditional",
             "reasoning": "...",
             "risk_level": "low|medium|high|critical",
             "capability_token": "cap_...",
             "ledger_entry_id": "entry_42"
           }
```

---

## Policy Evaluation Engine

```
┌─────────────────────────────────────────────────────────────┐
│                    POLICY ENGINE                             │
│                                                             │
│  Input: actor, action, resource, context                    │
│                                                             │
│  TERMS (Nodes in policy graph)                              │
│  ┌─────────────┬──────────────┬────────────────┐           │
│  │   ACTOR     │    ACTION    │    RESOURCE    │           │
│  │ ai_agent:*  │ read:data    │ customer_db    │           │
│  │ human:admin │ write:config │ audit_logs     │           │
│  │ service:api │ execute:cmd  │ payment_data   │           │
│  └─────────────┴──────────────┴────────────────┘           │
│                                                             │
│  RELATIONS (Edges in policy graph)                          │
│  ┌──────────────────────────────────────────────┐           │
│  │  PERMITS:  actor ──permits──► action         │           │
│  │  FORBIDS:  actor ──forbids──► resource       │           │
│  │  REQUIRES: action ──requires──► constraint   │           │
│  └──────────────────────────────────────────────┘           │
│                                                             │
│  MODES                                                      │
│  STRICT    = deny by default (explicit permit required)     │
│  PERMISSIVE = allow unless explicitly forbidden             │
│  PARANOID  = deny high-risk without human confirmation      │
│                                                             │
│  OUTPUT: APPROVED | DENIED | ESCALATED | CONDITIONAL        │
└─────────────────────────────────────────────────────────────┘
```

---

## Cryptographic Ledger Chain

```
  GENESIS ENTRY
  ┌──────────────────────────────────────────┐
  │ entry_id:   "entry_0"                    │
  │ event_type: "genesis"                    │
  │ prev_hash:  "0000000000..."              │
  │ entry_hash: SHA-256(sorted JSON)         │
  └──────────────────┬───────────────────────┘
                     │
                     ▼
  DECISION ENTRY
  ┌──────────────────────────────────────────┐
  │ entry_id:   "entry_1"                    │
  │ event_type: "decision"                   │
  │ prev_hash:  ◄── hash of entry_0          │
  │ entry_hash: SHA-256(this entry)          │
  └──────────────────┬───────────────────────┘
                     │
                     ▼
  RISK ENTRY
  ┌──────────────────────────────────────────┐
  │ entry_id:   "entry_2"                    │
  │ event_type: "risk_assessment"            │
  │ prev_hash:  ◄── hash of entry_1          │
  │ entry_hash: SHA-256(this entry)          │
  └──────────────────┬───────────────────────┘
                     │
                     ▼
                   [n entries]

  Verification: Recompute each entry_hash, check prev_hash chain
  Tamper detection: Any modification breaks subsequent hashes
```

---

## Risk Assessment (6 Dimensions)

```
             RISK ASSESSMENT
             ┌───────────────────────────────────┐
             │                                   │
             │   Security ──────────── Score 0-100│
             │   Privacy  ──────────── Score 0-100│
             │   Compliance ────────── Score 0-100│
             │   Operational ───────── Score 0-100│
             │   Reputational ──────── Score 0-100│
             │   Financial ─────────── Score 0-100│
             │                                   │
             │   Weighted average → Overall Score │
             │                                   │
             │   0-25:  LOW      ──► Normal flow  │
             │   26-50: MEDIUM   ──► Enhanced log │
             │   51-79: HIGH     ──► Alert        │
             │   80+:   CRITICAL ──► Auto-escalate│
             └───────────────────────────────────┘
```

---

## Role-Based Access Control

```
  ROLES & PERMISSIONS MATRIX

  Permission           │ VIEWER │ AUDITOR │ COMPLIANCE_OFFICER │ ADMIN
  ─────────────────────┼────────┼─────────┼────────────────────┼───────
  VIEW_DASHBOARD       │   ✓    │    ✓    │         ✓          │   ✓
  GENERATE_AUDIT       │        │    ✓    │         ✓          │   ✓
  APPROVE_REQUESTS     │        │         │         ✓          │   ✓
  EXPORT_DATA          │        │         │         ✓          │   ✓
  MANAGE_USERS         │        │         │                    │   ✓
  MANAGE_POLICIES      │        │         │                    │   ✓
  VIEW_SENSITIVE       │        │         │                    │   ✓
```

---

## EU AI Act Compliance Automation

```
  EU AI ACT COVERAGE

  Article 11 — Technical Documentation
  ├─ System architecture description
  ├─ Data flow diagrams (auto-generated)
  ├─ Risk assessment reports
  └─ Component traceability matrix

  Article 12 — Record-Keeping
  ├─ 10-year retention (high-risk systems)
  ├─ 6-month retention (standard systems)
  ├─ Legal hold mechanism
  ├─ GDPR data subject rights
  └─ Export: JSON │ CSV │ Markdown

  Article 14 — Human Oversight
  ├─ Intervention logging (rejection/modification/confirmation)
  ├─ Human role tracking (Operator/Manager/Supervisor)
  ├─ Response time metrics
  └─ Resolution outcome recording
```

---

## Compliance Framework Mapping

```
  GOVERNANCE PRIMITIVE ──► FRAMEWORK CONTROLS

  Decision Record ─────────────────────────────────────────────────────┐
                                                                        │
  ┌─────────────────────────────────────────────────────────────────── ▼ ─┐
  │ SOC 2          │ CC6.1 - CC6.8 (Logical Access Controls)              │
  │ ISO 27001      │ A.12.4 (Logging & Monitoring)                        │
  │ GDPR           │ Art.5 (Data Minimization) / Art.25 (Privacy by Design)│
  │ HIPAA          │ §164.312(b) (Audit Controls)                         │
  │ PCI-DSS        │ Req 10.2 (Audit Log Events)                         │
  │ NIST CSF       │ DE.CM (Security Continuous Monitoring)               │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## Service Dependencies

```
  DecisionService
  ├── PolicyEngine (required)
  ├── LedgerChain (required)
  ├── RiskService (optional)
  ├── EscalationService (optional)
  ├── EvidenceService (optional)
  ├── CapabilityToken (optional)
  └── ResponsibilityTracker (optional)

  AuthService
  ├── AuthDatabase (SQLite/PostgreSQL)
  ├── MFAService (optional)
  ├── OIDCService (optional)
  └── PasswordPolicy

  ComplianceMappingService
  ├── EvidenceService
  └── AuditExportService (optional)

  All services wired via ServiceRegistry (singleton)
```

---

## Deployment Architecture

```
  PRODUCTION DEPLOYMENT

  ┌──────────────────────────────────────────────────────────────────┐
  │                        LOAD BALANCER                             │
  └──────────┬───────────────────────────────────────┬──────────────┘
             │                                       │
             ▼                                       ▼
  ┌──────────────────────┐             ┌──────────────────────┐
  │   LEXECON NODE 1     │             │   LEXECON NODE 2     │
  │  FastAPI + Uvicorn   │             │  FastAPI + Uvicorn   │
  │  workers=4           │             │  workers=4           │
  └──────────┬───────────┘             └──────────┬───────────┘
             │                                    │
             └──────────────┬─────────────────────┘
                            │
             ┌──────────────▼──────────────┐
             │       POSTGRESQL DB          │
             │  pool=20  overflow=30        │
             └─────────────────────────────┘
                            │
             ┌──────────────▼──────────────┐
             │         REDIS CACHE          │
             │  Decision caching (80% hit)  │
             └─────────────────────────────┘

  Container: Docker (Dockerfile included)
  Orchestration: Kubernetes (manifests in deployment/kubernetes/)
  Helm Charts: deployment/helm/
  PaaS: Railway (environment variables pre-configured)
```

---

## Performance Targets (Achieved)

| Metric                | Target   | Achieved    |
|-----------------------|----------|-------------|
| Decision latency P50  | <10ms    | <10ms ✓     |
| Decision latency P99  | <20ms    | <20ms ✓     |
| Throughput            | 1,000/s  | 10,000/s ✓  |
| Cache hit rate        | >70%     | ~80% ✓      |
| Ledger 10k verify     | <100ms   | ~50ms ✓     |
| Code coverage         | >80%     | 81% ✓       |

---

## Directory Structure

```
Lexecon/
├── src/lexecon/          # Source code
│   ├── api/              # FastAPI routers, models, validation
│   ├── decision/         # Decision orchestration
│   ├── policy/           # Policy engine (graph evaluation)
│   ├── ledger/           # Cryptographic audit chain
│   ├── security/         # Auth, MFA, OIDC, rate limiting
│   ├── risk/             # 6-dimension risk scoring
│   ├── escalation/       # SLA-tracked escalations
│   ├── override/         # Human intervention
│   ├── evidence/         # Immutable artifact storage
│   ├── compliance/       # EU AI Act articles 11-14
│   ├── compliance_mapping/ # Framework controls (SOC2, ISO27001...)
│   ├── capability/       # Time-limited auth tokens
│   ├── identity/         # Ed25519 / RSA-4096 signing
│   ├── observability/    # Metrics, tracing, health
│   ├── cache/            # Memory + Redis cache
│   ├── cli/              # Click CLI commands
│   └── db/               # SQLAlchemy async DB
├── model_governance_pack/ # Canonical JSON schemas + Python models
├── tests/                # 46 test modules (1,053 tests)
├── docs/                 # This documentation
├── deployment/           # Docker, Kubernetes, Helm
└── scripts/              # Setup, migration utilities
```
