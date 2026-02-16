"""Health, status, and metrics endpoints."""

import time
from datetime import datetime

from fastapi import APIRouter, Depends

from lexecon.api.dependencies import ServiceRegistry, get_services
from lexecon.api.models import HealthResponse, StatusResponse
from lexecon.cache import cache_api_response
from lexecon.observability.metrics import metrics

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(services: ServiceRegistry = Depends(get_services)):
    return {
        "status": "healthy",
        "version": "0.1.0",
        "node_id": services.node_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status", response_model=StatusResponse)
@cache_api_response(ttl=30)
async def get_status(services: ServiceRegistry = Depends(get_services)):
    policy_loaded_status = services.policy_engine is not None and len(services.policy_engine.terms) > 0
    return {
        "status": "operational",
        "node_id": services.node_id,
        "policy_loaded": policy_loaded_status,
        "policies_loaded": policy_loaded_status,
        "policy_hash": services.policy_engine.get_policy_hash() if services.policy_engine else None,
        "ledger_entries": len(services.ledger.entries),
        "uptime_seconds": time.time() - services.startup_time,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/metrics")
async def metrics_endpoint():
    from fastapi.responses import Response
    return Response(content=metrics.export_metrics(), media_type="text/plain")


@router.get("/api/routes")
async def list_routes():
    """List all available API routes."""
    return {
        "service": "Lexecon Governance API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "routes": "/api/routes",
            "policies": "/policies",
            "decide": "/decide",
            "verify": "/decide/verify",
            "ledger_verify": "/ledger/verify",
            "audit_report": "/ledger/report",
            "risk_assess": "/api/governance/risk/assess",
            "escalation_create": "/api/governance/escalation",
            "override_create": "/api/governance/override",
            "evidence_store": "/api/governance/evidence",
            "compliance_map": "/api/governance/compliance/map",
            "audit_export_create": "/api/governance/audit-export/request",
        },
    }
