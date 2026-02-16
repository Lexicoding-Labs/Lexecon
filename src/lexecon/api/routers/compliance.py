"""Digital signature verification and export audit log endpoints."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from lexecon.api.dependencies import ServiceRegistry, get_services, get_session_id
from lexecon.security.auth_service import Permission

router = APIRouter()


# ── Digital Signature Endpoints ──

@router.post("/compliance/verify-signature")
async def verify_signature(
    packet: Dict[str, Any],
    services: ServiceRegistry = Depends(get_services),
):
    is_valid, message = services.signature_service.verify_packet_signature(packet)
    return {
        "valid": is_valid,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/compliance/public-key")
async def get_public_key(services: ServiceRegistry = Depends(get_services)):
    return {
        "public_key_pem": services.signature_service.get_public_key_pem(),
        "fingerprint": services.signature_service.get_public_key_fingerprint(),
        "algorithm": "RSA-PSS-SHA256",
        "key_size": 4096,
    }


# ── Export Audit Log Endpoints ──

@router.get("/compliance/export-requests")
async def list_export_requests(
    request: Request,
    limit: int = 100,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = services.auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    if not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    requests = services.audit_service.list_export_requests(limit=limit)
    return {
        "requests": [
            {
                "request_id": r.request_id,
                "username": r.username,
                "purpose": r.purpose,
                "case_id": r.case_id,
                "requested_at": r.requested_at,
                "export_status": r.export_status.value,
                "approval_status": r.approval_status.value,
                "completed_at": r.completed_at,
            }
            for r in requests
        ],
    }


@router.get("/compliance/audit-chain-verification")
async def verify_audit_chain(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session, error = services.auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error)

    return services.audit_service.verify_audit_chain()
