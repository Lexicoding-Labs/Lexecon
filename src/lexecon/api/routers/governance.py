"""Governance API endpoints: risk, escalation, override, evidence."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from lexecon.api.dependencies import ServiceRegistry, get_services
from lexecon.api.models import (
    EscalationCreateRequest,
    EscalationResolveRequest,
    EvidenceSignRequest,
    EvidenceStoreRequest,
    EvidenceVerifyRequest,
    OverrideCreateRequest,
    RiskAssessmentRequest,
)

try:
    from model_governance_pack.models import (
        ArtifactType,
        EscalationPriority,
        EscalationStatus,
        NewOutcome,
        OriginalOutcome,
        OverrideScope,
        OverrideType,
        RiskDimensions,
    )
except ImportError:
    pass

router = APIRouter()


# ── Risk ──

@router.post("/api/governance/risk/assess")
async def assess_risk(
    request: RiskAssessmentRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.risk_service:
        raise HTTPException(status_code=500, detail="Risk service not initialized")

    try:
        dimensions_dict = request.dimensions.model_dump(exclude_none=True)
        dimensions = RiskDimensions(**dimensions_dict)

        risk = services.risk_service.assess_risk(
            decision_id=request.decision_id, dimensions=dimensions, metadata=request.context,
        )

        return {
            "risk_id": risk.risk_id,
            "decision_id": risk.decision_id,
            "overall_score": risk.overall_score,
            "risk_level": risk.risk_level.value,
            "dimensions": {
                "security": risk.dimensions.security,
                "privacy": risk.dimensions.privacy,
                "compliance": risk.dimensions.compliance,
                "operational": risk.dimensions.operational,
                "reputational": risk.dimensions.reputational,
                "financial": risk.dimensions.financial,
            },
            "timestamp": risk.timestamp.isoformat(),
            "factors": risk.factors,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {e!s}")


@router.get("/api/governance/risk/{risk_id}")
async def get_risk(risk_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.risk_service:
        raise HTTPException(status_code=500, detail="Risk service not initialized")

    risk = services.risk_service.get_risk(risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")

    return {
        "risk_id": risk.risk_id,
        "decision_id": risk.decision_id,
        "overall_score": risk.overall_score,
        "risk_level": risk.risk_level.value,
        "dimensions": {
            "security": risk.dimensions.security,
            "privacy": risk.dimensions.privacy,
            "compliance": risk.dimensions.compliance,
            "operational": risk.dimensions.operational,
            "reputational": risk.dimensions.reputational,
            "financial": risk.dimensions.financial,
        },
        "timestamp": risk.timestamp.isoformat(),
        "factors": risk.factors,
    }


@router.get("/api/governance/risk/decision/{decision_id}")
async def get_risk_for_decision(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.risk_service:
        raise HTTPException(status_code=500, detail="Risk service not initialized")

    risk = services.risk_service.get_risk_for_decision(decision_id)
    if not risk:
        raise HTTPException(status_code=404, detail=f"No risk found for decision {decision_id}")

    return {
        "risk_id": risk.risk_id,
        "decision_id": risk.decision_id,
        "overall_score": risk.overall_score,
        "risk_level": risk.risk_level.value,
        "dimensions": {
            "security": risk.dimensions.security,
            "privacy": risk.dimensions.privacy,
            "compliance": risk.dimensions.compliance,
            "operational": risk.dimensions.operational,
            "reputational": risk.dimensions.reputational,
            "financial": risk.dimensions.financial,
        },
        "timestamp": risk.timestamp.isoformat(),
        "factors": risk.factors,
    }


# ── Escalation ──

@router.post("/api/governance/escalation")
async def create_escalation(
    request: EscalationCreateRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.escalation_service:
        raise HTTPException(status_code=500, detail="Escalation service not initialized")

    try:
        from model_governance_pack.models import EscalationTrigger
        trigger = EscalationTrigger(request.trigger.lower())
        priority = EscalationPriority(request.priority.lower()) if request.priority else None

        escalation = services.escalation_service.create_escalation(
            decision_id=request.decision_id, trigger=trigger, escalated_to=request.escalated_to,
            priority=priority, context_summary=request.context_summary, metadata=request.metadata,
        )

        return {
            "escalation_id": escalation.escalation_id,
            "decision_id": escalation.decision_id,
            "status": escalation.status.value,
            "priority": escalation.priority.value if escalation.priority else None,
            "trigger": escalation.trigger.value,
            "escalated_to": escalation.escalated_to,
            "context_summary": escalation.context_summary,
            "created_at": escalation.created_at.isoformat(),
            "sla_deadline": escalation.sla_deadline.isoformat() if escalation.sla_deadline else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Escalation creation failed: {e!s}")


@router.post("/api/governance/escalation/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    request: EscalationResolveRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.escalation_service:
        raise HTTPException(status_code=500, detail="Escalation service not initialized")

    try:
        from model_governance_pack.models import ResolutionOutcome
        outcome_enum = ResolutionOutcome(request.outcome.lower())

        escalation = services.escalation_service.resolve_escalation(
            escalation_id=escalation_id, resolved_by=request.resolved_by,
            outcome=outcome_enum, notes=request.notes,
        )

        outcome_value = None
        if escalation.resolution and escalation.resolution.outcome:
            if hasattr(escalation.resolution.outcome, "value"):
                outcome_value = escalation.resolution.outcome.value
            else:
                outcome_value = escalation.resolution.outcome

        return {
            "escalation_id": escalation.escalation_id,
            "decision_id": escalation.decision_id,
            "status": escalation.status.value,
            "priority": escalation.priority.value if escalation.priority else None,
            "resolved_at": escalation.resolved_at.isoformat() if escalation.resolved_at else None,
            "outcome": outcome_value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Escalation resolution failed: {e!s}")


@router.get("/api/governance/escalation/{escalation_id}")
async def get_escalation(
    escalation_id: str,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.escalation_service:
        raise HTTPException(status_code=500, detail="Escalation service not initialized")

    escalation = services.escalation_service.get_escalation(escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")

    return {
        "escalation_id": escalation.escalation_id,
        "decision_id": escalation.decision_id,
        "status": escalation.status.value,
        "priority": escalation.priority.value if escalation.priority else None,
        "trigger": escalation.trigger.value,
        "escalated_to": escalation.escalated_to,
        "context_summary": escalation.context_summary,
        "created_at": escalation.created_at.isoformat(),
        "sla_deadline": escalation.sla_deadline.isoformat() if escalation.sla_deadline else None,
        "resolved_at": escalation.resolved_at.isoformat() if escalation.resolved_at else None,
        "resolution": escalation.resolution.model_dump() if escalation.resolution else None,
    }


@router.get("/api/governance/escalation/decision/{decision_id}")
async def get_escalations_for_decision(
    decision_id: str,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.escalation_service:
        raise HTTPException(status_code=500, detail="Escalation service not initialized")

    escalations = services.escalation_service.list_escalations(decision_id=decision_id)
    return {
        "decision_id": decision_id,
        "count": len(escalations),
        "escalations": [
            {
                "escalation_id": e.escalation_id,
                "status": e.status.value,
                "priority": e.priority.value,
                "created_at": e.created_at.isoformat(),
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            }
            for e in escalations
        ],
    }


@router.get("/api/governance/escalation/sla/violations")
async def get_sla_violations(services: ServiceRegistry = Depends(get_services)):
    if not services.escalation_service:
        raise HTTPException(status_code=500, detail="Escalation service not initialized")

    pending_escalations = services.escalation_service.list_escalations(
        status=EscalationStatus.PENDING,
    )

    now = datetime.now(timezone.utc)
    violations = [e for e in pending_escalations if e.sla_deadline and now > e.sla_deadline]

    return {
        "count": len(violations),
        "violations": [
            {
                "escalation_id": e.escalation_id,
                "decision_id": e.decision_id,
                "priority": e.priority.value,
                "sla_deadline": e.sla_deadline.isoformat() if e.sla_deadline else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in violations
        ],
    }


# ── Override ──

@router.post("/api/governance/override")
async def create_override(
    request: OverrideCreateRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.override_service:
        raise HTTPException(status_code=500, detail="Override service not initialized")

    try:
        override_type = OverrideType(request.override_type.lower())
        original_outcome = OriginalOutcome(request.original_outcome.lower()) if request.original_outcome else None
        new_outcome = NewOutcome(request.new_outcome.lower()) if request.new_outcome else None

        expires_at = None
        if request.expires_at:
            expires_at = datetime.fromisoformat(request.expires_at.replace("Z", "+00:00"))

        scope = None
        if request.scope:
            scope = OverrideScope(**request.scope)

        override = services.override_service.create_override(
            decision_id=request.decision_id, override_type=override_type,
            authorized_by=request.authorized_by, justification=request.justification,
            original_outcome=original_outcome, new_outcome=new_outcome,
            expires_at=expires_at, scope=scope, metadata=request.metadata,
        )

        return {
            "override_id": override.override_id,
            "decision_id": override.decision_id,
            "override_type": override.override_type.value,
            "authorized_by": override.authorized_by,
            "justification": override.justification,
            "timestamp": override.timestamp.isoformat(),
            "expires_at": override.expires_at.isoformat() if override.expires_at else None,
            "evidence_ids": override.evidence_ids,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Override creation failed: {e!s}")


@router.get("/api/governance/override/{override_id}")
async def get_override(override_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.override_service:
        raise HTTPException(status_code=500, detail="Override service not initialized")

    override = services.override_service.get_override(override_id)
    if not override:
        raise HTTPException(status_code=404, detail=f"Override {override_id} not found")

    return {
        "override_id": override.override_id,
        "decision_id": override.decision_id,
        "override_type": override.override_type.value,
        "authorized_by": override.authorized_by,
        "justification": override.justification,
        "timestamp": override.timestamp.isoformat(),
        "original_outcome": override.original_outcome.value if override.original_outcome else None,
        "new_outcome": override.new_outcome.value if override.new_outcome else None,
        "expires_at": override.expires_at.isoformat() if override.expires_at else None,
        "evidence_ids": override.evidence_ids,
    }


@router.get("/api/governance/override/decision/{decision_id}")
async def get_overrides_for_decision(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.override_service:
        raise HTTPException(status_code=500, detail="Override service not initialized")

    overrides = services.override_service.get_overrides_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "count": len(overrides),
        "overrides": [
            {
                "override_id": o.override_id,
                "override_type": o.override_type.value,
                "authorized_by": o.authorized_by,
                "timestamp": o.timestamp.isoformat(),
                "expires_at": o.expires_at.isoformat() if o.expires_at else None,
            }
            for o in overrides
        ],
    }


@router.get("/api/governance/override/decision/{decision_id}/active")
async def check_active_override(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.override_service:
        raise HTTPException(status_code=500, detail="Override service not initialized")

    active_override = services.override_service.get_active_override(decision_id)
    is_overridden = active_override is not None

    result = {"decision_id": decision_id, "is_overridden": is_overridden}

    if active_override:
        result["override"] = {
            "override_id": active_override.override_id,
            "override_type": active_override.override_type.value,
            "authorized_by": active_override.authorized_by,
            "timestamp": active_override.timestamp.isoformat(),
            "expires_at": active_override.expires_at.isoformat() if active_override.expires_at else None,
        }

    return result


@router.get("/api/governance/override/decision/{decision_id}/status")
async def get_decision_with_override_status(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.override_service:
        raise HTTPException(status_code=500, detail="Override service not initialized")

    decision_data = {"decision_id": decision_id}
    return services.override_service.get_decision_with_override_status(decision_id, decision_data)


# ── Evidence ──

@router.post("/api/governance/evidence")
async def store_evidence_artifact(
    request: EvidenceStoreRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")

    try:
        artifact_type = ArtifactType(request.artifact_type.lower())

        artifact = services.evidence_service.store_artifact(
            artifact_type=artifact_type, content=request.content, source=request.source,
            related_decision_ids=request.related_decision_ids, related_control_ids=request.related_control_ids,
            content_type=request.content_type, storage_uri=request.storage_uri,
            retention_days=request.retention_days, metadata=request.metadata,
        )

        return {
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type.value,
            "sha256_hash": artifact.sha256_hash,
            "created_at": artifact.created_at.isoformat(),
            "source": artifact.source,
            "size_bytes": artifact.size_bytes,
            "retention_until": artifact.retention_until.isoformat() if artifact.retention_until else None,
            "is_immutable": artifact.is_immutable,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Artifact storage failed: {e!s}")


@router.get("/api/governance/evidence/statistics")
async def get_evidence_statistics(services: ServiceRegistry = Depends(get_services)):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")
    return services.evidence_service.get_statistics()


@router.get("/api/governance/evidence/{artifact_id}")
async def get_evidence_artifact(artifact_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")

    artifact = services.evidence_service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")

    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type.value,
        "sha256_hash": artifact.sha256_hash,
        "created_at": artifact.created_at.isoformat(),
        "source": artifact.source,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "storage_uri": artifact.storage_uri,
        "related_decision_ids": artifact.related_decision_ids,
        "related_control_ids": artifact.related_control_ids,
        "retention_until": artifact.retention_until.isoformat() if artifact.retention_until else None,
        "is_immutable": artifact.is_immutable,
        "has_signature": artifact.digital_signature is not None,
    }


@router.post("/api/governance/evidence/{artifact_id}/verify")
async def verify_evidence_artifact(
    artifact_id: str,
    request: EvidenceVerifyRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")

    try:
        is_valid = services.evidence_service.verify_artifact_integrity(artifact_id, request.content)
        artifact = services.evidence_service.get_artifact(artifact_id)
        return {
            "artifact_id": artifact_id,
            "is_valid": is_valid,
            "stored_hash": artifact.sha256_hash if artifact else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {e!s}")


@router.get("/api/governance/evidence/decision/{decision_id}")
async def get_artifacts_for_decision(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")

    artifacts = services.evidence_service.get_artifacts_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "count": len(artifacts),
        "artifacts": [
            {
                "artifact_id": a.artifact_id,
                "artifact_type": a.artifact_type.value,
                "sha256_hash": a.sha256_hash,
                "created_at": a.created_at.isoformat(),
                "source": a.source,
                "size_bytes": a.size_bytes,
            }
            for a in artifacts
        ],
    }


@router.get("/api/governance/evidence/decision/{decision_id}/lineage")
async def export_artifact_lineage(decision_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")
    return services.evidence_service.export_artifact_lineage(decision_id)


@router.post("/api/governance/evidence/{artifact_id}/sign")
async def sign_evidence_artifact(
    artifact_id: str,
    request: EvidenceSignRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.evidence_service:
        raise HTTPException(status_code=500, detail="Evidence service not initialized")

    try:
        artifact = services.evidence_service.sign_artifact(
            artifact_id=artifact_id, signer_id=request.signer_id,
            signature=request.signature, algorithm=request.algorithm,
        )
        return {
            "artifact_id": artifact.artifact_id,
            "signed": True,
            "signer_id": artifact.digital_signature.signer_id if artifact.digital_signature else None,
            "signed_at": artifact.digital_signature.signed_at.isoformat() if artifact.digital_signature else None,
            "algorithm": artifact.digital_signature.algorithm if artifact.digital_signature else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing failed: {e!s}")
