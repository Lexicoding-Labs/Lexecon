"""Decision, ledger, storage, and demo endpoints."""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from lexecon.api.dependencies import ServiceRegistry, get_services, get_session_id, get_tenant_id
from lexecon.api.models import DecisionRequestModel
from lexecon.cache import cache_decision
from lexecon.decision.service import DecisionRequest
from lexecon.responsibility.tracker import DecisionMaker, ResponsibilityLevel

router = APIRouter()


@router.post("/decide")
@cache_decision(ttl=300)
async def make_decision(
    http_request: Request,
    request_model: DecisionRequestModel,
    services: ServiceRegistry = Depends(get_services),
    tenant_id: str = Depends(get_tenant_id),
):
    if services.decision_service is None:
        raise HTTPException(status_code=500, detail="Decision service not initialized")

    if services.usage_service:
        can_proceed, limit_info = services.usage_service.can_create_decision(tenant_id)
        if not can_proceed:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": limit_info.get("code", "PLAN_LIMIT"),
                    "message": f"Plan limit exceeded: {limit_info['metric']}",
                    "metric": limit_info["metric"],
                    "limit": limit_info["limit"],
                    "current": limit_info["current"],
                    "upgrade_url": "mailto:sales@lexecon.ai",
                },
            )

    request = DecisionRequest(
        request_id=request_model.request_id,
        actor=request_model.actor,
        proposed_action=request_model.proposed_action,
        tool=request_model.tool,
        user_intent=request_model.user_intent,
        data_classes=request_model.data_classes,
        risk_level=request_model.risk_level,
        requested_output_type=request_model.requested_output_type,
        policy_mode=request_model.policy_mode,
        context=request_model.context,
    )

    response = services.decision_service.evaluate_request(request)

    ledger_entry = services.ledger.append(
        "decision",
        {
            "request_id": request.request_id,
            "decision": response.decision,
            "actor": request.actor,
            "action": request.proposed_action,
            "tenant_id": tenant_id,
        },
    )

    if services.usage_service:
        services.usage_service.increment_decisions(tenant_id)

    response.ledger_entry_hash = ledger_entry.entry_hash

    services.responsibility_tracker.record_decision(
        decision_id=request.request_id,
        decision_maker=DecisionMaker.AI_SYSTEM,
        responsible_party="system",
        role="AI Decision System",
        reasoning=response.reasoning,
        confidence=response.confidence if hasattr(response, "confidence") else 1.0,
        responsibility_level=ResponsibilityLevel.AUTOMATED,
    )

    return response.to_dict()


@router.post("/decide/verify")
async def verify_decision(
    request_data: Dict[str, Any],
    services: ServiceRegistry = Depends(get_services),
):
    if "decision_response" in request_data:
        decision_response = request_data["decision_response"]
    else:
        decision_response = request_data

    ledger_entry_hash = decision_response.get("ledger_entry_hash")

    if not ledger_entry_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing ledger_entry_hash",
        )

    entry = None
    for e in services.ledger.entries:
        if e.entry_hash == ledger_entry_hash:
            entry = e
            break

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision with hash {ledger_entry_hash} not found in ledger",
        )

    calculated_hash = entry.calculate_hash()
    if calculated_hash != entry.entry_hash:
        return {"verified": False, "error": "Hash mismatch"}

    return {"verified": True, "entry": entry.to_dict()}


@router.get("/ledger/verify")
async def verify_ledger(services: ServiceRegistry = Depends(get_services)):
    return services.ledger.verify_integrity()


@router.get("/ledger/report")
async def get_audit_report(services: ServiceRegistry = Depends(get_services)):
    return services.ledger.generate_audit_report()


@router.get("/ledger/entries")
async def get_ledger_entries(
    request: Request,
    event_type: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    services: ServiceRegistry = Depends(get_services),
    tenant_id: str = Depends(get_tenant_id),
):
    entries = services.ledger.entries

    entries = [
        e for e in entries
        if e.data.get("tenant_id") == tenant_id or e.data.get("tenant_id") is None
    ]

    if event_type:
        entries = [e for e in entries if e.event_type == event_type]

    total = len(entries)
    entries = entries[offset:offset + limit] if limit else entries[offset:]

    return {
        "entries": [entry.to_dict() for entry in entries],
        "total": total,
        "offset": offset,
        "limit": limit,
        "tenant_id": tenant_id,
    }


@router.get("/storage/stats")
async def get_storage_statistics(services: ServiceRegistry = Depends(get_services)):
    if not services.storage:
        raise HTTPException(status_code=503, detail="Persistence not configured")

    stats = services.storage.get_statistics()
    return {"storage_enabled": True, **stats}


@router.post("/demo/seed")
async def seed_demo_data(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    user_id = None
    if session_id:
        session, _ = await services.async_auth_service.validate_session(session_id)
        if session:
            user_id = session.user_id

    created = {
        "decisions": 0,
        "entries": 0,
        "timestamp": datetime.utcnow().isoformat(),
    }

    sample_decisions = [
        {
            "decision_id": f"dec_{i+1000}",
            "action": [
                "Model inference request approved",
                "High-risk decision escalated to human oversight",
                "Request denied - policy violation detected",
                "Data access approved with constraints",
                "Override approved by compliance officer",
            ][i % 5],
            "actor": [
                "system@lexecon.ai",
                "ai-agent-prod-01",
                "ai-agent-prod-02",
                "data-pipeline-service",
                "jane.smith@company.com",
            ][i % 5],
            "decision": ["allow", "escalate", "deny", "allow", "override"][i % 5],
            "risk_level": ["low", "high", "critical", "medium", "medium"][i % 5],
        }
        for i in range(20)
    ]

    for decision_data in sample_decisions:
        services.ledger.append("decision", decision_data)
        created["entries"] += 1
        created["decisions"] += 1

    services.ledger.append(
        "demo_seed",
        {
            "created_by": user_id or "anonymous",
            "decisions_created": created["decisions"],
            "timestamp": created["timestamp"],
        },
    )

    return {
        "ok": True,
        "created": created,
        "message": f"Created {created['decisions']} demo decisions",
    }
