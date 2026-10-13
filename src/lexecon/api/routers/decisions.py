"""Decision, ledger, storage, and demo endpoints."""

from datetime import datetime
import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from lexecon.api.dependencies import ServiceRegistry, get_services, get_session_id, get_tenant_id, require_admin, require_session
from lexecon.api.models import DecisionRequestModel
from lexecon.decision.service import DecisionRequest, tool_arguments_digest
from lexecon.responsibility.tracker import DecisionMaker, ResponsibilityLevel
from lexecon.security.auth_service import Role, Session

router = APIRouter()


def _response_digest(response_data: Dict[str, Any]) -> str:
    """Hash every response field except the hash of its own ledger entry."""
    payload = {key: value for key, value in response_data.items() if key != "ledger_entry_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@router.post("/decide")
async def make_decision(
    http_request: Request,
    request_model: DecisionRequestModel,
    services: ServiceRegistry = Depends(get_services),
    tenant_id: str = Depends(get_tenant_id),
    session: Session = Depends(require_session),
):
    if services.decision_service is None:
        raise HTTPException(status_code=500, detail="Decision service not initialized")

    if request_model.actor != session.username and session.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Actor must match authenticated user")
    if request_model.requested_output_type != "tool_action":
        raise HTTPException(status_code=403, detail="Requested output type is not authorized")
    action_decision = services.policy_engine.evaluate(
        actor=request_model.actor, action=request_model.proposed_action,
        data_classes=request_model.data_classes, risk_level=request_model.risk_level,
        context=request_model.context,
    )
    if action_decision.allowed:
        tool_decision = services.policy_engine.evaluate(
            actor=request_model.actor, action=f"tool:{request_model.tool}",
            data_classes=request_model.data_classes, risk_level=request_model.risk_level,
            context=request_model.context,
        )
        if not tool_decision.allowed:
            raise HTTPException(status_code=403, detail="Tool is not permitted by policy")

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
                    "upgrade_url": None,
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
        tool_arguments=request_model.tool_arguments,
    )

    response = services.decision_service.evaluate_request(request, subject=session.user_id)

    ledger_entry = services.ledger.append(
        "decision",
        {
            "decision_id": response.decision_id,
            "request_id": request.request_id,
            "decision": response.decision,
            "actor": request.actor,
            "action": request.proposed_action,
            "tool": request.tool,
            "arguments_digest": (
                tool_arguments_digest(request.tool_arguments)
                if request.tool_arguments is not None else None
            ),
            "risk_level": request.risk_level,
            "policy_version_hash": response.policy_version_hash,
            "tenant_id": tenant_id,
            "response_digest": _response_digest(response.to_dict()),
            "evaluation_source": "policy_engine",
            "demo_requested": request_model.context.get("demo") is True,
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


@router.post("/capability/verify")
async def verify_capability(
    request_data: Dict[str, Any],
    services: ServiceRegistry = Depends(get_services),
    session: Session = Depends(require_session),
):
    """Online preflight for a tool adapter; this endpoint does not execute tools."""
    grant = request_data.get("capability_token")
    action = request_data.get("action")
    tool = request_data.get("tool")
    tool_arguments = request_data.get("tool_arguments")
    consume = request_data.get("consume", False)
    valid = (
        services.decision_service is not None
        and isinstance(grant, dict)
        and isinstance(action, str)
        and isinstance(tool, str)
        and (tool_arguments is None or isinstance(tool_arguments, dict))
        and type(consume) is bool
        and services.decision_service.verify_capability_token(
            grant, session.user_id, action, tool, tool_arguments=tool_arguments, consume=consume,
        )
    )
    return {"valid": bool(valid), "consumed": bool(valid and consume)}


@router.post("/decide/verify")
async def verify_decision(
    request_data: Dict[str, Any],
    services: ServiceRegistry = Depends(get_services),
    tenant_id: str = Depends(get_tenant_id),
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

    if entry.data.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Decision not found in tenant")

    calculated_hash = entry.calculate_hash()
    if calculated_hash != entry.entry_hash:
        return {"verified": False, "error": "Hash mismatch"}

    expected_digest = entry.data.get("response_digest") if entry.event_type == "decision" else None
    if not expected_digest or not hmac.compare_digest(
        expected_digest, _response_digest(decision_response),
    ):
        return {"verified": False, "error": "Decision response does not match ledger"}

    return {"verified": True, "entry": entry.to_dict()}


@router.get("/ledger/verify", dependencies=[Depends(require_admin)])
async def verify_ledger(services: ServiceRegistry = Depends(get_services)):
    return services.ledger.verify_integrity()


@router.get("/ledger/report", dependencies=[Depends(require_admin)])
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
        if e.data.get("tenant_id") == tenant_id
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


@router.get("/storage/stats", dependencies=[Depends(require_admin)])
async def get_storage_statistics(services: ServiceRegistry = Depends(get_services)):
    if not services.storage:
        raise HTTPException(status_code=503, detail="Persistence not configured")

    stats = services.storage.get_statistics()
    return {"storage_enabled": True, **stats}


@router.post("/demo/seed", dependencies=[Depends(require_admin)])
async def seed_demo_data(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
    tenant_id: str = Depends(get_tenant_id),
):
    if os.getenv("LEXECON_ENV") == "production":
        raise HTTPException(status_code=404, detail="Demo seed unavailable")
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
                "Demo: model inference request approved",
                "Demo: high-risk decision escalated",
                "Demo: request denied by policy",
                "Demo: data access approved with constraints",
                "Demo: override illustration",
            ][i % 5],
            "actor": [
                "demo-system",
                "demo-agent-01",
                "demo-agent-02",
                "demo-pipeline",
                "demo-reviewer",
            ][i % 5],
            "decision": ["allow", "escalate", "deny", "allow", "override"][i % 5],
            "risk_level": ["low", "high", "critical", "medium", "medium"][i % 5],
        }
        for i in range(20)
    ]

    for decision_data in sample_decisions:
        services.ledger.append("decision", {
            **decision_data, "tenant_id": tenant_id,
            "evaluation_source": "synthetic_seed",
        })
        created["entries"] += 1
        created["decisions"] += 1

    services.ledger.append(
        "demo_seed",
        {
            "created_by": user_id or "anonymous",
            "tenant_id": tenant_id,
            "decisions_created": created["decisions"],
            "timestamp": created["timestamp"],
        },
    )

    return {
        "ok": True,
        "created": created,
        "message": f"Created {created['decisions']} demo decisions",
    }
