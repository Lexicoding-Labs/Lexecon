"""Health, status, metrics, dashboard, and root endpoints."""

import os
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

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


@router.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "../../../../demo_dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail=f"Dashboard not found at {dashboard_path}")
    return FileResponse(dashboard_path)


@router.get("/dashboard/governance", response_class=HTMLResponse)
async def serve_governance_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "../../../../governance_dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail=f"Governance dashboard not found at {dashboard_path}")
    return FileResponse(dashboard_path)


@router.get("/")
async def root():
    return {
        "service": "Lexecon Governance API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "dashboard": "/dashboard",
            "governance_dashboard": "/dashboard/governance",
            "policies": "/policies",
            "decide": "/decide",
            "verify": "/decide/verify",
            "ledger_verify": "/ledger/verify",
            "audit_report": "/ledger/report",
            "storage_stats": "/storage/stats",
            "responsibility_report": "/responsibility/report",
            "responsibility_overrides": "/responsibility/overrides",
            "compliance_article_11": "/compliance/eu-ai-act/article-11",
            "compliance_article_12_status": "/compliance/eu-ai-act/article-12/status",
            "compliance_article_12_package": "/compliance/eu-ai-act/article-12/regulatory-package",
            "compliance_article_14_intervention": "/compliance/eu-ai-act/article-14/intervention",
            "compliance_article_14_effectiveness": "/compliance/eu-ai-act/article-14/effectiveness",
            "compliance_article_14_evidence": "/compliance/eu-ai-act/article-14/evidence-package",
            "risk_assess": "/api/governance/risk/assess",
            "risk_get": "/api/governance/risk/{risk_id}",
            "risk_decision": "/api/governance/risk/decision/{decision_id}",
            "escalation_create": "/api/governance/escalation",
            "escalation_resolve": "/api/governance/escalation/{escalation_id}/resolve",
            "escalation_get": "/api/governance/escalation/{escalation_id}",
            "escalation_decision": "/api/governance/escalation/decision/{decision_id}",
            "escalation_sla_violations": "/api/governance/escalation/sla/violations",
            "override_create": "/api/governance/override",
            "override_get": "/api/governance/override/{override_id}",
            "override_decision": "/api/governance/override/decision/{decision_id}",
            "override_active": "/api/governance/override/decision/{decision_id}/active",
            "override_status": "/api/governance/override/decision/{decision_id}/status",
            "evidence_store": "/api/governance/evidence",
            "evidence_get": "/api/governance/evidence/{artifact_id}",
            "evidence_verify": "/api/governance/evidence/{artifact_id}/verify",
            "evidence_decision": "/api/governance/evidence/decision/{decision_id}",
            "evidence_lineage": "/api/governance/evidence/decision/{decision_id}/lineage",
            "evidence_sign": "/api/governance/evidence/{artifact_id}/sign",
            "evidence_stats": "/api/governance/evidence/statistics",
            "compliance_map": "/api/governance/compliance/map",
            "compliance_controls": "/api/governance/compliance/{framework}/controls",
            "compliance_control_status": "/api/governance/compliance/{framework}/{control_id}",
            "compliance_verify_control": "/api/governance/compliance/{framework}/{control_id}/verify",
            "compliance_link_evidence": "/api/governance/compliance/{framework}/{control_id}/link-evidence",
            "compliance_gaps": "/api/governance/compliance/{framework}/gaps",
            "compliance_report": "/api/governance/compliance/{framework}/report",
            "compliance_coverage": "/api/governance/compliance/{framework}/coverage",
            "compliance_primitive_mappings": "/api/governance/compliance/primitive/{primitive_id}/mappings",
            "compliance_statistics": "/api/governance/compliance/statistics",
            "audit_export_create": "/api/governance/audit-export/request",
            "audit_export_generate": "/api/governance/audit-export/{export_id}/generate",
            "audit_export_get": "/api/governance/audit-export/{export_id}",
            "audit_export_download": "/api/governance/audit-export/{export_id}/download",
            "audit_export_list": "/api/governance/audit-export/list",
            "audit_export_requests": "/api/governance/audit-export/requests",
            "audit_export_statistics": "/api/governance/audit-export/statistics",
        },
    }
