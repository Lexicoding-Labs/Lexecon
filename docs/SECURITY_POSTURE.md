# Security Posture

## Purpose

This document describes Lexecon's security controls, threat model, and known limitations. It uses evidence-based language to describe implemented mechanisms without claiming certification or compliance.

---

## Threat Model

### Assumptions

**Trusted Components**:
- Application code executing within deployment boundary
- Authorized human reviewers acting in good faith
- Underlying operating system and runtime environment

**Untrusted Components**:
- External API inputs (all data validated against schemas)
- User-submitted decision data and justifications
- External system integrations via webhooks

### Primary Threats

| Threat | Description | Mitigation Status |
|--------|-------------|-------------------|
| **Data Tampering** | Modification of governance records after creation | ✓ Mitigated (SHA-256 hash chain) |
| **Unauthorized Access** | Access to governance data without proper authorization | ✓ Mitigated (RBAC + MFA + OIDC — see `src/lexecon/security/`) |
| **Injection Attacks** | SQL/command injection via inputs | ✓ Mitigated (Pydantic validation + parameterised queries) |
| **Denial of Service** | Resource exhaustion via excessive requests | ✓ Mitigated (rate limiting middleware — `rate_limit_middleware.py`) |
| **Privilege Escalation** | Unauthorized override or escalation resolution | ✓ Mitigated (RBAC permission checks at API layer) |
| **Data Exfiltration** | Unauthorized export of governance data | ⚠ Partial (permission checks exist; encryption at rest not enforced by app) |

---

## Implemented Controls

### 1. Input Validation

**Mechanism**: All API inputs validated against Pydantic models derived from canonical JSON schemas.

**Evidence**:
- Schema definitions: `/model_governance_pack/schemas/*.json`
- Pydantic bindings: `/model_governance_pack/models/*.py`
- Validation tests: `/tests/test_models.py`

**Coverage**:
- ✓ Type validation (strings, numbers, enums, dates)
- ✓ Range validation (min/max length, value bounds)
- ✓ Format validation (ISO 8601 dates, ID patterns)
- ✓ Required field enforcement
- ✓ Enum value validation

**Limitations**:
- Semantic validation limited (e.g., "reasonable" justification length, not quality)
- No rate limiting on validation failures

---

### 2. Immutability & Hash Chaining

**Mechanism**: Evidence artifacts and decision log entries use SHA-256 hash linking to detect tampering.

**Evidence**:
- Implementation: `src/lexecon/evidence/service.py:create_artifact()`
- Hash computation: `hashlib.sha256()` over canonical JSON
- Verification: Audit packet root checksum validation

**Coverage**:
- ✓ EvidenceArtifacts include SHA-256 hash of content
- ✓ Audit packages include root checksum and per-artifact checksums
- ✓ Immutability flag prevents modification after creation

**Limitations**:
- Hash chain validation not performed on every read (performance trade-off)
- No periodic integrity scans
- Storage layer allows modification if immutability flag bypassed

---

### 3. Authorization Checks

**Mechanism**: Permission-based access control for sensitive operations.

**Evidence**:
- Permission definitions: `src/lexecon/api/server.py:check_permission()`
- Required permissions:
  - `CREATE_OVERRIDE`: Override creation
  - `RESOLVE_ESCALATION`: Escalation resolution
  - `VIEW_AUDIT_LOGS`: Audit export access

**Coverage**:
- ✓ Override creation requires authorization
- ✓ Escalation resolution checks assigned reviewer
- ✓ Audit export requires specific permission

**Limitations**:
- No role-based access control (RBAC) framework
- No centralized authorization policy engine
- Permission checks embedded in endpoint logic
- No audit of authorization failures

---

### 4. Audit Logging

**Mechanism**: All governance actions recorded in immutable ledger.

**Evidence**:
- Decision log: `src/lexecon/core/immutable_ledger.py`
- Evidence artifacts: `src/lexecon/evidence/service.py`
- Audit export: `src/lexecon/audit_export/service.py`

**Coverage**:
- ✓ Decision creation logged with timestamp and actor
- ✓ Risk assessments linked to decisions
- ✓ Escalations tracked with resolution details
- ✓ Overrides captured with justification and authorization
- ✓ Evidence artifacts include source and creation metadata

**Limitations**:
- No separate security audit log for authentication/authorization events
- Log retention policy not enforced (relies on external log management)
- No real-time alerting on suspicious patterns

---

### 5. Data Handling

**Mechanism**: Structured handling of potentially sensitive data.

**Evidence**:
- Schema definitions explicitly mark fields
- No credentials or encryption keys in schemas
- PII guidance in documentation

**Coverage**:
- ✓ Actor identifiers recorded (necessary for accountability)
- ✓ Decision context captured (necessary for audit)
- ✓ Justifications stored (necessary for evidence)
- ✓ No credential or key fields in schemas

**Limitations**:
- No automatic PII detection or redaction
- No encryption at rest for stored data
- No data retention/deletion enforcement
- Audit exports may contain sensitive decision context

---

## Implemented — But Requiring Deployment Configuration

The following controls are built into the application but rely on correct deployment
configuration to be effective:

### Authentication & Authorization
- Built-in auth service: `src/lexecon/security/auth_service.py` (RBAC, 4 roles)
- MFA (TOTP): `src/lexecon/security/mfa_service.py`
- OIDC (Google / Azure / Okta): `src/lexecon/security/oidc_service.py`
- Password policy: `src/lexecon/security/password_policy.py`
- Session keys and DB encryption keys must be set via environment variables (see `.env.example`)

### Rate Limiting
- Rate limiting middleware: `src/lexecon/security/rate_limit_middleware.py`
- Configurable per-IP and per-user limits via `LEXECON_RATE_LIMIT_*` env vars
- Defaults in `.env.example`; must be tuned for production traffic

### Security Headers
- `src/lexecon/security/security_headers.py` sets HSTS, CSP, X-Frame-Options, etc.
- Effective only when app is behind TLS termination

## Out of Scope (Explicitly Not Implemented)

The following controls are **not** handled by the application and must be provided
by the deployment environment:

### Network Security
- TLS/HTTPS termination (use reverse proxy: nginx, Caddy, AWS ALB, etc.)
- mTLS for service-to-service calls
- Network segmentation policies

### Encryption at Rest
- Database-level encryption (use PostgreSQL TDE or encrypted RDS)
- Field-level encryption for high-sensitivity values
- KMS integration (roadmap: v0.3.0)

### Monitoring / SIEM
- Real-time anomaly detection
- Security event forwarding to SIEM
- Automated alerting on auth failure patterns

---

## Data Classification

### Public Data
- API endpoint definitions
- Schema documentation
- Governance primitive specifications

### Internal Data
- Decision IDs and metadata
- Risk scores and thresholds
- Escalation assignments
- Override types (not justifications)

### Sensitive Data
- Decision context (may contain business-sensitive information)
- Override justifications (may contain incident details)
- Evidence artifact content (varies by artifact type)
- Audit exports (contain complete governance history)

### Prohibited Data
- User passwords or credentials
- Encryption keys or secrets
- Payment card information (PCI data)
- Protected health information (PHI) beyond necessary identifiers

---

## Secure Development Practices

### Code Review
- All changes reviewed before merge
- Security-relevant changes require explicit review callout

### Dependency Management
- Dependencies declared in `requirements.txt` / `pyproject.toml`
- Known vulnerability scanning recommended (not automated)

### Testing
- Unit tests for core services
- Integration tests for API endpoints
- Schema validation tests
- No automated security testing (SAST/DAST)

### Secrets Management
- No hardcoded credentials in source code
- Configuration via environment variables recommended
- No secrets management system integration

---

## Deployment Recommendations

To achieve a production-ready security posture, deployers should:

1. **Authentication Layer**: Deploy behind authentication proxy (OAuth, SAML, etc.)
2. **TLS**: Enforce HTTPS for all connections
3. **Network Isolation**: Use network policies to restrict access
4. **Encryption at Rest**: Enable database/filesystem encryption
5. **Rate Limiting**: Implement request throttling at load balancer
6. **Monitoring**: Integrate with SIEM for security event tracking
7. **Backup & Recovery**: Implement encrypted backups with tested restore procedures
8. **Secrets Management**: Use Vault or equivalent for configuration secrets
9. **Regular Updates**: Monitor dependencies for security advisories

---

## Known Limitations & Risks

### Critical Limitations

| Limitation | Risk | Recommended Mitigation |
|------------|------|------------------------|
| No encryption at rest | Data exposure if storage compromised | Deploy with encrypted filesystem/database |
| No rate limiting | Resource exhaustion attacks | Add WAF or API gateway with rate limits |
| No SSO integration | Account management complexity | Implement OAuth 2.0 / OIDC |
| In-memory stores default | Data loss on restart | Deploy with persistent database backend |

### Medium Limitations

| Limitation | Risk | Recommended Mitigation |
|------------|------|------------------------|
| No audit of auth failures | Undetected access attempts | Implement security event logging |
| No automatic PII redaction | Sensitive data in exports | Manual review of exports before sharing |
| No integrity verification on read | Undetected tampering between exports | Implement periodic integrity scans |
| No session management | Replay attacks possible | Deploy behind session-aware proxy |

---

## Security Contact

For security issues or questions:
- **Sensitive disclosures**: follow the process in [SECURITY.md](../SECURITY.md) (do not open public issues)
- **General questions**: GitHub Discussions or GitHub Issues

---

## Compliance Considerations

### What Lexecon Provides

Lexecon provides **evidence and mechanisms** that support compliance efforts:

- Immutable audit trails (supports SOC 2 CC6.1, ISO 27001 A.12.4.1)
- Authorization controls for sensitive operations (supports SOC 2 CC6.2)
- Evidence linking to compliance controls (supports control mapping)
- Deterministic audit exports (supports regulatory disclosure)

### What Lexecon Does Not Provide

Lexecon **does not certify, guarantee, or claim**:

- Compliance with any specific regulation or framework
- Satisfaction of regulatory requirements without additional controls
- Replacement for comprehensive security management program
- Legal or regulatory advice

Organizations using Lexecon must:
- Perform independent compliance assessments
- Implement additional controls as required by their regulatory context
- Engage qualified auditors for certification processes
- Maintain comprehensive security and compliance documentation beyond Lexecon

---

## Version History

- **v0.2.0** (2026-03-05): Updated to reflect built-in auth, rate limiting, MFA, and OIDC
  - Corrected "out-of-scope" section — these controls ARE implemented in `src/lexecon/security/`
  - Separated "built-in but needs deployment config" from "truly out of scope"
  - Updated security contact to point to SECURITY.md
- **v0.1.0** (2026-01-04): Initial security posture documentation
