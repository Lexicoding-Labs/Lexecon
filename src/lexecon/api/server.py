"""API Server - REST API for Lexecon governance system.

Provides endpoints for health checks, policy management, decision requests,
and audit operations. Serves the React SPA from /static when available.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lexecon.api.dependencies import ServiceRegistry
from lexecon.observability import initialize_observability

# Re-export models so that `from lexecon.api.server import <Model>` still works
from lexecon.api.models import *  # noqa: F401,F403

# ── Import routers ──
from lexecon.api.routers import (  # noqa: E402
    audit,
    auth,
    compliance,
    compliance_mapping,
    decisions,
    eu_compliance,
    governance,
    health,
    policy,
    responsibility,
)

# ── Create FastAPI app ──
app = FastAPI(
    title="Lexecon Governance API",
    description="Cryptographic governance system for AI safety and compliance",
    version="0.1.0",
)

# ── CORS middleware ──
allowed_origins = os.getenv("LEXECON_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

if os.getenv("LEXECON_ENV") == "production" and "*" in allowed_origins:
    raise ValueError("Wildcard CORS origins not allowed in production. Set LEXECON_CORS_ORIGINS environment variable.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Accept", "Origin"],
    max_age=3600,
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Limit"],
)

# ── Rate-limit & security-headers middleware ──
from lexecon.security.rate_limit_middleware import create_rate_limit_middleware  # noqa: E402
from lexecon.security.security_headers import create_security_headers_middleware  # noqa: E402

app.middleware("http")(create_rate_limit_middleware())
app.middleware("http")(create_security_headers_middleware())

# ── Include routers ──
app.include_router(health.router)
app.include_router(policy.router)
app.include_router(decisions.router)
app.include_router(responsibility.router)
app.include_router(auth.router)
app.include_router(compliance.router)
app.include_router(eu_compliance.router)
app.include_router(governance.router)
app.include_router(compliance_mapping.router)
app.include_router(audit.router)

# ── Serve React SPA from /static if available ──
_static_dir = Path(__file__).resolve().parent.parent.parent.parent / "static"
if _static_dir.is_dir():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve React SPA — return index.html for client-side routes."""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")


# ── Startup event ──
@app.on_event("startup")
async def startup_event():
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        environment = os.getenv("LEXECON_ENV", "development")
        initialize_observability(
            service_name="lexecon-api",
            version="0.1.0",
            environment=environment,
            enable_sentry=True,
        )
        logger.info("Observability initialized")

        services = ServiceRegistry.get()
        services.initialize()
        logger.info("Services initialized")
        
        services.ledger.append("system_startup", {"message": "API server started"})
        logger.info("Startup complete")
    except Exception as e:
        logger.error(f"Startup error (non-fatal): {e}")
        # Don't re-raise - allow server to start even if some services fail


# ── Backwards-compatibility shims ──
# Tests import `from lexecon.api.server import initialize_services`
def initialize_services():
    """Legacy shim — delegates to ServiceRegistry."""
    ServiceRegistry.get().initialize()
