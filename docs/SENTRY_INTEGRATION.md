# Sentry Integration Guide

Sentry is integrated into Lexecon for comprehensive error tracking, performance monitoring, and production debugging.

## Features

- **Error Tracking**: Automatic capture of unhandled exceptions
- **Performance Monitoring**: APM for FastAPI endpoints
- **User Context**: Track which users are affected by errors
- **Custom Context**: Add governance-specific metadata to errors
- **Breadcrumbs**: Trace user actions leading to errors
- **Release Tracking**: Connect errors to specific code versions

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Required: Your Sentry DSN
SENTRY_DSN=https://[key]@[region].ingest.sentry.io/[project-id]

# Optional: Release version for tracking
SENTRY_RELEASE=lexecon@0.1.0

# Optional: Environment name
LEXECON_ENV=production  # or development, staging
```

### Automatic Initialization

Sentry is automatically initialized when the FastAPI app starts via `initialize_observability()` in `server.py`.

## Usage Examples

### Basic Error Capture

```python
from lexecon.observability import capture_exception, capture_message

try:
    # Your code here
    result = perform_cryptographic_operation()
except Exception as e:
    # Automatically captured and sent to Sentry
    capture_exception(e, context={
        "operation": "signature_verification",
        "policy_id": policy.id,
    })
    raise
```

### Capturing Messages

```python
from lexecon.observability import capture_message

# Log important events
capture_message(
    "Critical governance decision overridden",
    level="warning",
    context={
        "decision_id": decision_id,
        "override_reason": reason,
        "user_id": user_id,
    }
)
```

### Adding User Context

```python
from lexecon.observability import set_user

# Track which user experienced the error
set_user(
    user_id=str(user.id),
    email=user.email,
    username=user.username
)
```

### Custom Context for Governance

```python
from lexecon.observability import set_context

# Add governance-specific context
set_context("governance", {
    "policy_mode": "strict",
    "risk_level": "high",
    "compliance_framework": "EU AI Act",
})

set_context("decision", {
    "decision_id": decision.id,
    "policy_id": policy.id,
    "outcome": decision.outcome,
})
```

### Adding Breadcrumbs

```python
from lexecon.observability import add_breadcrumb

# Track the sequence of events
add_breadcrumb(
    message="Policy evaluation started",
    category="governance",
    data={"policy_id": policy.id}
)

add_breadcrumb(
    message="Risk assessment completed",
    category="governance",
    level="info",
    data={"risk_score": 0.75}
)
```

## Testing the Integration

Run the test script to verify Sentry is working:

```bash
python scripts/test_sentry.py
```

This will:
1. Initialize Sentry
2. Send a test message
3. Send a test exception
4. Confirm events were sent

Check your Sentry dashboard at: https://lexecon.sentry.io/issues/

## Performance Monitoring

Sentry automatically tracks:
- **API endpoint performance**: Response times for all FastAPI routes
- **Database queries**: Slow query detection
- **External API calls**: Track third-party service latency

### Sample Rates

| Environment | Traces | Profiles | Description |
|------------|--------|----------|-------------|
| Development | 100% | 100% | Capture all transactions |
| Staging | 50% | 50% | Capture half of transactions |
| Production | 10% | 10% | Sample to reduce cost |

Adjust in `sentry_config.py` or environment variables.

## Best Practices

### Do Capture:
- ✅ Cryptographic operation failures
- ✅ Policy evaluation errors
- ✅ Failed governance decisions
- ✅ Authentication failures
- ✅ Database connection issues
- ✅ External API failures

### Don't Capture:
- ❌ Expected validation errors (400 responses)
- ❌ Authentication attempts (unless suspicious)
- ❌ Normal business logic flow
- ❌ Debug logging (use structured logging instead)

### Security Considerations

#### PII (Personally Identifiable Information)

By default, Sentry is configured to:
- **Development**: Send PII for better debugging (`send_default_pii=True`)
- **Production**: Block PII (`send_default_pii=False`)

Sensitive data automatically scrubbed:
- Passwords
- API keys
- Tokens
- Credit card numbers

#### Sensitive Context

Avoid sending sensitive data in context:

```python
# ❌ Bad - sends sensitive data
set_context("auth", {
    "password": user_password,  # Never do this!
    "api_key": api_key,
})

# ✅ Good - only metadata
set_context("auth", {
    "auth_method": "password",
    "user_id_hash": hash(user.id),
})
```

## Compliance & Audit

For governance systems, Sentry provides:

1. **Immutable Error Logs**: Once sent, errors cannot be modified
2. **Audit Trail**: Full history of errors and their resolution
3. **Release Tracking**: Connect errors to specific code versions
4. **User Impact**: Track how many users affected by each issue

### Example: EU AI Act Compliance

```python
from lexecon.observability import capture_exception, set_context

try:
    result = evaluate_high_risk_decision(context)
except Exception as e:
    # Add compliance context
    set_context("compliance", {
        "regulation": "EU AI Act Article 14",
        "risk_classification": "high",
        "human_oversight_required": True,
        "record_retention_period": "10 years",
    })

    capture_exception(e)
    raise
```

## Advanced Configuration

### Custom Integrations

Add custom Sentry integrations in `sentry_config.py`:

```python
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=dsn,
    integrations=[
        FastApiIntegration(),
        StarletteIntegration(),
        RedisIntegration(),
        SqlalchemyIntegration(),
    ],
)
```

### Custom Error Filters

Filter out noisy errors:

```python
def before_send(event, hint):
    # Don't send 404 errors
    if event.get('level') == 'error':
        exception = hint.get('exc_info')
        if isinstance(exception, HTTPException) and exception.status_code == 404:
            return None
    return event

sentry_sdk.init(
    dsn=dsn,
    before_send=before_send,
)
```

## Monitoring & Alerts

Configure alerts in Sentry dashboard:

1. **Error Spike**: Alert when error rate increases
2. **New Issue**: Notify on first occurrence of new error
3. **Performance Degradation**: Alert on slow endpoints
4. **User Impact**: Notify when many users affected

## Support

- **Sentry Dashboard**: https://lexecon.sentry.io/
- **Documentation**: https://docs.sentry.io/platforms/python/
- **Integration Code**: `src/lexecon/observability/sentry_config.py`
