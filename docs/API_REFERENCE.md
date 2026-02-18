# Lexecon — API Reference

Base URL: `http://localhost:8000` (development)

All request and response bodies are JSON. All timestamps are ISO 8601 UTC.

---

## Health & Status

### `GET /health`

Returns node health status.

**Response 200**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "node_id": "dev-node"
}
```

---

### `GET /status`

Returns detailed system status including service states.

**Response 200**
```json
{
  "status": "operational",
  "services": {
    "policy_engine": "ready",
    "ledger": "ready",
    "auth": "ready"
  }
}
```

---

### `GET /metrics`

Returns Prometheus metrics in text format.

**Response 200** (text/plain)
```
# HELP lexecon_http_requests_total Total HTTP requests
# TYPE lexecon_http_requests_total counter
lexecon_http_requests_total{method="GET",endpoint_group="/health",status_class="2xx"} 42
```

---

## Decisions

### `POST /decide`

Evaluate a governance decision request.

**Request Body**
```json
{
  "request_id": "req_optional_correlation_id",
  "actor": "ai_agent:assistant",
  "proposed_action": "read customer transaction history",
  "tool": "database_query",
  "user_intent": "answer customer support question about their account",
  "data_classes": ["pii", "financial"],
  "risk_level": 2,
  "requested_output_type": "tool_action",
  "policy_mode": "strict",
  "context": {
    "session_id": "sess_abc123",
    "customer_tier": "premium"
  }
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `actor` | string | Yes | 1–255 chars, `[a-zA-Z0-9_\-\.@:]+` |
| `proposed_action` | string | Yes | 1–255 chars |
| `tool` | string | Yes | 1–100 chars |
| `user_intent` | string | Yes | 1–500 chars |
| `data_classes` | array | No | Max 10 items |
| `risk_level` | integer | No | 1–5 (default: 1) |
| `policy_mode` | string | No | `strict`, `permissive`, `paranoid` |
| `context` | object | No | Max 5 nesting levels, 64KB |

**Response 200**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "request_id": "req_optional_correlation_id",
  "outcome": "approved",
  "reasoning": "Action permitted by policy: ai_agent actors have read access to customer data for support operations",
  "risk_level": "medium",
  "risk_score": 42,
  "allowed": true,
  "policy_mode": "strict",
  "evaluated_at": "2024-02-18T12:00:00Z",
  "capability_token": "cap_eyJ...",
  "ledger_entry_id": "entry_5"
}
```

| Field | Description |
|-------|-------------|
| `outcome` | `approved`, `denied`, `escalated`, or `conditional` |
| `allowed` | Boolean shorthand for `outcome == "approved"` |
| `capability_token` | Time-limited token for the approved action |
| `ledger_entry_id` | Immutable audit trail reference |

**Response 422** — Validation error
```json
{
  "detail": [{"loc": ["body", "actor"], "msg": "Invalid actor format", "type": "value_error"}]
}
```

**Response 429** — Rate limit exceeded
```json
{"detail": "Rate limit exceeded", "retry_after": 60}
```

---

### `POST /decide/verify`

Verify a decision signature.

**Request Body**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "signature": "base64_encoded_signature"
}
```

**Response 200**
```json
{"valid": true, "decision_id": "dec_01HQXYZ..."}
```

---

## Ledger

### `GET /ledger/entries`

Query ledger entries with optional filters.

**Query Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | string | Filter by event type |
| `limit` | integer | Max results (default: 100) |
| `offset` | integer | Pagination offset |

**Response 200**
```json
{
  "entries": [
    {
      "entry_id": "entry_0",
      "event_type": "genesis",
      "timestamp": "2024-02-18T10:00:00Z",
      "entry_hash": "sha256...",
      "previous_hash": "0000000000..."
    }
  ],
  "total": 42
}
```

---

### `GET /ledger/verify`

Verify the cryptographic integrity of the entire ledger chain.

**Response 200**
```json
{
  "valid": true,
  "entries_verified": 42,
  "chain_intact": true,
  "verified_at": "2024-02-18T12:00:00Z"
}
```

---

### `GET /ledger/report`

Generate a summary report of ledger activity.

**Response 200**
```json
{
  "total_entries": 42,
  "event_type_counts": {
    "decision": 30,
    "risk_assessment": 8,
    "escalation": 3,
    "override": 1
  },
  "first_entry": "2024-02-18T10:00:00Z",
  "last_entry": "2024-02-18T12:00:00Z"
}
```

---

## Policies

### `GET /policies`

List all loaded policies.

**Response 200**
```json
{
  "policies": [
    {
      "policy_id": "pol_abc123",
      "version": "1.0.0",
      "mode": "strict",
      "term_count": 12,
      "relation_count": 8,
      "loaded_at": "2024-02-18T10:00:00Z"
    }
  ]
}
```

---

### `POST /policies/load`

Load a new policy from JSON.

**Request Body**
```json
{
  "policy_id": "my_policy",
  "version": "1.0.0",
  "mode": "strict",
  "terms": [
    {
      "term_id": "t_ai_agent",
      "term_type": "actor",
      "value": "ai_agent:*",
      "description": "Any AI agent"
    },
    {
      "term_id": "t_read_customer",
      "term_type": "action",
      "value": "read:customer_data"
    }
  ],
  "relations": [
    {
      "relation_type": "permits",
      "source_term_id": "t_ai_agent",
      "target_term_id": "t_read_customer"
    }
  ]
}
```

**Response 201**
```json
{
  "policy_id": "my_policy",
  "loaded": true,
  "hash": "sha256...",
  "term_count": 2,
  "relation_count": 1
}
```

---

## Authentication

### `POST /auth/login`

Log in with username and password.

**Request Body**
```json
{
  "username": "alice",
  "password": "MyStr0ng!Pass#2024"
}
```

**Response 200**
```json
{
  "session_id": "sess_abc123...",
  "username": "alice",
  "role": "auditor",
  "expires_at": "2024-02-18T20:00:00Z"
}
```

**Response 401** — Invalid credentials
```json
{"detail": "Invalid username or password"}
```

**Response 423** — Account locked
```json
{"detail": "Account locked until 2024-02-18T13:00:00Z"}
```

---

### `POST /auth/logout`

End the current session.

**Headers:** `Authorization: Bearer <session_id>`

**Response 200**
```json
{"logged_out": true}
```

---

### `GET /auth/me`

Get current user information.

**Headers:** `Authorization: Bearer <session_id>`

**Response 200**
```json
{
  "user_id": "usr_abc123",
  "username": "alice",
  "email": "alice@example.com",
  "role": "auditor",
  "full_name": "Alice Smith",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### `POST /auth/users`

Create a new user. Requires ADMIN role.

**Request Body**
```json
{
  "username": "bob",
  "email": "bob@example.com",
  "password": "Str0ng!Pass#2024",
  "role": "viewer",
  "full_name": "Bob Jones"
}
```

Roles: `viewer`, `auditor`, `compliance_officer`, `admin`

**Response 201**
```json
{
  "user_id": "usr_xyz789",
  "username": "bob",
  "role": "viewer",
  "created_at": "2024-02-18T12:00:00Z"
}
```

---

### `GET /auth/password-policy`

Get current password policy rules.

**Response 200**
```json
{
  "min_length": 12,
  "require_uppercase": true,
  "require_lowercase": true,
  "require_digits": true,
  "require_special": true,
  "disallow_sequential": true,
  "disallow_common": true
}
```

---

### OIDC Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/oidc/providers` | List configured OIDC providers |
| `GET` | `/auth/oidc/login/{provider}` | Begin OIDC login flow |
| `GET` | `/auth/oidc/callback/{provider}` | OIDC callback handler |
| `GET` | `/auth/oidc/linked` | List linked providers for current user |
| `POST` | `/auth/oidc/unlink` | Unlink an OIDC provider |

Supported providers: `google`, `azure`, `okta`, `auth0`, `custom`

---

## Risk Assessment

### `POST /api/governance/risk/assess`

Perform a 6-dimension risk assessment.

**Request Body**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "actor": "ai_agent:assistant",
  "proposed_action": "export_all_customer_records",
  "tool": "bulk_export",
  "data_classes": ["pii", "financial"],
  "context": {}
}
```

**Response 200**
```json
{
  "risk_id": "risk_abc123",
  "decision_id": "dec_01HQXYZ...",
  "overall_score": 78,
  "risk_level": "high",
  "dimensions": {
    "security": 70,
    "privacy": 90,
    "compliance": 80,
    "operational": 60,
    "reputational": 75,
    "financial": 65
  },
  "factors": [
    {
      "dimension": "privacy",
      "score": 90,
      "reason": "Bulk export of PII data poses high privacy risk"
    }
  ],
  "requires_escalation": false,
  "timestamp": "2024-02-18T12:00:00Z"
}
```

---

### `GET /api/governance/risk/{risk_id}`

Retrieve a specific risk assessment.

**Response 200** — Same as assessment response above.

---

## Escalation

### `POST /api/governance/escalation`

Create a new escalation for human review.

**Request Body**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "trigger": "risk_threshold",
  "escalated_to": ["act_human_user:manager"],
  "priority": "high",
  "context_summary": "Risk score 82 exceeded threshold of 80"
}
```

Priority values: `critical`, `high`, `medium`, `low`

**Response 201**
```json
{
  "escalation_id": "esc_abc123",
  "decision_id": "dec_01HQXYZ...",
  "status": "open",
  "priority": "high",
  "sla_deadline": "2024-02-18T16:00:00Z",
  "created_at": "2024-02-18T12:00:00Z"
}
```

---

### `POST /api/governance/escalation/{escalation_id}/resolve`

Resolve an open escalation.

**Request Body**
```json
{
  "resolved_by": "act_human_user:manager",
  "outcome": "approved",
  "notes": "Reviewed and approved after additional verification"
}
```

Outcome values: `approved`, `denied`, `deferred`, `escalated_further`

**Response 200**
```json
{
  "escalation_id": "esc_abc123",
  "status": "resolved",
  "resolution": {
    "outcome": "approved",
    "resolved_by": "act_human_user:manager",
    "resolved_at": "2024-02-18T13:00:00Z",
    "response_time_ms": 3600000
  }
}
```

---

## Override

### `POST /api/governance/override`

Execute a human override of a governance decision.

**Request Body**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "override_type": "executive_override",
  "authorized_by": "act_human_user:executive:cto",
  "justification": "Emergency business requirement necessitates temporary policy exception for critical production deployment. Risk accepted by executive team.",
  "original_outcome": "denied",
  "new_outcome": "approved",
  "expires_at": "2024-02-19T00:00:00Z"
}
```

`justification` must be at least 20 characters.

**Response 201**
```json
{
  "override_id": "ovr_abc123",
  "decision_id": "dec_01HQXYZ...",
  "override_type": "executive_override",
  "authorized_by": "act_human_user:executive:cto",
  "timestamp": "2024-02-18T12:00:00Z",
  "expires_at": "2024-02-19T00:00:00Z"
}
```

---

## Evidence

### `POST /api/governance/evidence`

Register an immutable evidence artifact.

**Request Body**
```json
{
  "artifact_type": "decision_record",
  "content": "base64_encoded_content",
  "linked_decisions": ["dec_01HQXYZ..."],
  "metadata": {
    "source": "decision_service",
    "format": "json"
  }
}
```

Artifact types: `decision_record`, `policy_document`, `audit_log`, `user_action`, `system_event`, `compliance_document`, `risk_assessment`, `investigation_record`

**Response 201**
```json
{
  "artifact_id": "art_sha256hash...",
  "content_hash": "sha256...",
  "artifact_type": "decision_record",
  "created_at": "2024-02-18T12:00:00Z"
}
```

---

### `POST /api/governance/evidence/{artifact_id}/verify`

Verify the integrity of a stored artifact.

**Response 200**
```json
{
  "artifact_id": "art_sha256hash...",
  "valid": true,
  "content_hash_matches": true,
  "signature_valid": true
}
```

---

## Compliance Mapping

### `POST /api/governance/compliance/map`

Map a governance primitive to regulatory controls.

**Request Body**
```json
{
  "primitive_type": "decision",
  "primitive_id": "dec_01HQXYZ...",
  "frameworks": ["soc2", "iso27001", "gdpr"]
}
```

Frameworks: `soc2`, `iso27001`, `gdpr`, `hipaa`, `pci_dss`, `nist_csf`

**Response 200**
```json
{
  "primitive_id": "dec_01HQXYZ...",
  "mappings": [
    {
      "framework": "soc2",
      "controls": ["CC6.1", "CC6.2", "CC7.1"],
      "coverage": "full"
    },
    {
      "framework": "gdpr",
      "controls": ["Art.5", "Art.25", "Art.30"],
      "coverage": "partial"
    }
  ]
}
```

---

### `GET /api/governance/compliance/{framework}/gaps`

Get compliance gap analysis for a framework.

Frameworks: `soc2`, `iso27001`, `gdpr`, `hipaa`, `pci_dss`, `nist_csf`

**Response 200**
```json
{
  "framework": "soc2",
  "total_controls": 64,
  "covered_controls": 52,
  "gap_controls": 12,
  "coverage_percentage": 81.25,
  "gaps": [
    {
      "control_id": "CC9.1",
      "description": "Risk mitigation activities",
      "gap_reason": "No evidence linked"
    }
  ]
}
```

---

## EU AI Act

### `GET /compliance/eu-ai-act/article-11`

Get Article 11 technical documentation for this system.

**Response 200**
```json
{
  "article": "11",
  "title": "Technical Documentation",
  "system_description": "Cryptographic governance engine for AI safety...",
  "architecture_components": [...],
  "data_flows": [...],
  "risk_assessment_summary": {...},
  "generated_at": "2024-02-18T12:00:00Z"
}
```

---

### `GET /compliance/eu-ai-act/article-12/status`

Get Article 12 record-keeping status.

**Response 200**
```json
{
  "article": "12",
  "retention_policy": {
    "high_risk_years": 10,
    "standard_months": 6
  },
  "current_records": 1053,
  "records_under_legal_hold": 0,
  "oldest_record": "2024-01-01T00:00:00Z",
  "gdpr_compliant": true
}
```

---

### `POST /compliance/eu-ai-act/article-12/legal-hold`

Apply a legal hold to prevent record deletion.

**Request Body**
```json
{
  "reason": "Regulatory investigation",
  "decision_ids": ["dec_01HQXYZ..."],
  "held_by": "act_human_user:legal:counsel"
}
```

**Response 200**
```json
{
  "hold_id": "hold_abc123",
  "records_held": 1,
  "applied_at": "2024-02-18T12:00:00Z"
}
```

---

### `POST /compliance/eu-ai-act/article-14/intervention`

Log a human oversight intervention (Article 14).

**Request Body**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "intervention_type": "rejection",
  "human_role": "operator",
  "intervener_id": "act_human_user:operator:alice",
  "reason": "Output did not meet quality requirements for this use case",
  "notes": "Redirected to manual review"
}
```

Intervention types: `rejection`, `modification`, `confirmation`
Human roles: `operator`, `manager`, `supervisor`

**Response 201**
```json
{
  "intervention_id": "int_abc123",
  "decision_id": "dec_01HQXYZ...",
  "intervention_type": "rejection",
  "recorded_at": "2024-02-18T12:00:00Z"
}
```

---

## Audit Export

### `POST /api/governance/audit-export/request`

Request an audit package export.

**Request Body**
```json
{
  "scope": "custom",
  "format": "json",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-02-18T23:59:59Z",
  "include_decisions": true,
  "include_risks": true,
  "include_overrides": true,
  "include_escalations": false,
  "requested_by": "alice"
}
```

Scopes: `all`, `recent`, `custom`
Formats: `json`, `csv`, `markdown`, `html`

**Response 202**
```json
{
  "export_id": "exp_abc123",
  "status": "pending",
  "estimated_size_mb": 2.4,
  "created_at": "2024-02-18T12:00:00Z"
}
```

---

### `GET /api/governance/audit-export/{export_id}/download`

Download a completed audit export.

**Response 200** — Binary file download

**Response 202** — Export still processing
```json
{"status": "processing", "progress_pct": 65}
```

---

## Responsibility Tracking

### `GET /responsibility/report`

Get full accountability report.

**Response 200**
```json
{
  "report": {
    "total_decisions": 1053,
    "by_responsibility_level": {
      "automated": 980,
      "delegated": 50,
      "reviewed": 15,
      "human_made": 8
    },
    "by_responsible_party": {
      "ai_agent:assistant": 750,
      "ai_agent:analyst": 230,
      "act_human_user:manager": 73
    }
  },
  "generated_at": "2024-02-18T12:00:00Z"
}
```

---

### `GET /responsibility/chain/{decision_id}`

Get the full accountability chain for a decision.

**Response 200**
```json
{
  "decision_id": "dec_01HQXYZ...",
  "chain": [
    {
      "responsibility_level": "automated",
      "decision_maker": "ai_agent:assistant",
      "role": "initiator",
      "confidence": 0.95,
      "reasoning": "Policy evaluation completed"
    },
    {
      "responsibility_level": "reviewed",
      "decision_maker": "act_human_user:manager",
      "role": "reviewer",
      "reasoning": "Risk reviewed and accepted"
    }
  ]
}
```

---

## Compliance Verification

### `GET /compliance/public-key`

Get the node's public key for signature verification.

**Response 200**
```json
{
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0B...\n-----END PUBLIC KEY-----",
  "algorithm": "RSA-PSS-SHA256",
  "fingerprint": "9eb2c96a7de192e5..."
}
```

---

### `GET /compliance/audit-chain-verification`

Verify the cryptographic integrity of the full audit chain.

**Response 200**
```json
{
  "chain_valid": true,
  "entries_checked": 1053,
  "first_entry_hash": "sha256...",
  "last_entry_hash": "sha256...",
  "verified_at": "2024-02-18T12:00:00Z"
}
```

---

## Legacy v1 Audit API

For backwards compatibility. Prefer the governance API endpoints above.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/audit/decisions` | Query decisions |
| `GET` | `/api/v1/audit/decisions/{id}` | Get decision |
| `GET` | `/api/v1/audit/stats` | Audit statistics |
| `POST` | `/api/v1/audit/verify` | Verify decision |
| `POST` | `/api/v1/audit/export` | Export audit |
| `GET` | `/api/v1/audit/exports` | List exports |
| `GET` | `/api/v1/audit/exports/{id}/download` | Download export |

---

## Error Responses

| Code | Meaning |
|------|---------|
| 400 | Bad Request — invalid business logic |
| 401 | Unauthorized — missing or invalid session |
| 403 | Forbidden — insufficient role |
| 404 | Not Found — resource does not exist |
| 409 | Conflict — duplicate resource |
| 422 | Unprocessable Entity — input validation failed |
| 429 | Too Many Requests — rate limit exceeded |
| 500 | Internal Server Error |

Standard error body:
```json
{
  "detail": "Human-readable error message"
}
```

---

## Interactive Documentation

When the server is running, OpenAPI docs are available at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
