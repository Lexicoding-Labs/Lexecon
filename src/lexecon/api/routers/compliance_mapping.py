"""Compliance mapping endpoints (Phase 7)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from lexecon.api.dependencies import ServiceRegistry, get_services
from lexecon.api.models import ComplianceLinkEvidenceRequest, ComplianceMappingRequest, ComplianceVerifyControlRequest
from lexecon.cache import cache_compliance_mapping
from lexecon.compliance_mapping.service import ControlStatus, GovernancePrimitive, RegulatoryFramework

router = APIRouter()


@router.post("/api/governance/compliance/map")
async def map_primitive_to_controls(
    request: ComplianceMappingRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        primitive_type = GovernancePrimitive(request.primitive_type.lower())
        framework = RegulatoryFramework(request.framework.lower())

        mapping = services.compliance_mapping_service.map_primitive_to_controls(
            primitive_type=primitive_type, primitive_id=request.primitive_id,
            framework=framework, metadata=request.metadata,
        )

        return {
            "mapping_id": mapping.mapping_id,
            "primitive_type": mapping.primitive_type.value,
            "primitive_id": mapping.primitive_id,
            "framework": mapping.framework.value,
            "control_ids": mapping.control_ids,
            "mapped_at": mapping.mapped_at.isoformat(),
            "verification_status": mapping.verification_status,
            "metadata": mapping.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping failed: {e!s}")


@router.get("/api/governance/compliance/{framework}/controls")
async def list_compliance_controls(
    framework: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        status_enum = ControlStatus(status.lower()) if status else None

        controls = services.compliance_mapping_service.list_controls(
            framework=framework_enum, status=status_enum, category=category,
        )

        return {
            "framework": framework,
            "count": len(controls),
            "filters": {"status": status, "category": category},
            "controls": [
                {
                    "control_id": c.control_id,
                    "title": c.title,
                    "description": c.description,
                    "category": c.category,
                    "status": c.status.value,
                    "required_evidence_types": c.required_evidence_types,
                    "mapped_primitives": [p.value for p in c.mapped_primitives],
                    "last_verified": c.last_verified.isoformat() if c.last_verified else None,
                }
                for c in controls
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list controls: {e!s}")


@router.get("/api/governance/compliance/{framework}/{control_id}")
async def get_control_status(
    framework: str, control_id: str,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        control = services.compliance_mapping_service.get_control_status(control_id, framework_enum)

        if not control:
            raise HTTPException(
                status_code=404, detail=f"Control {control_id} not found in framework {framework}",
            )

        return {
            "control_id": control.control_id,
            "framework": control.framework.value,
            "title": control.title,
            "description": control.description,
            "category": control.category,
            "status": control.status.value,
            "required_evidence_types": control.required_evidence_types,
            "mapped_primitives": [p.value for p in control.mapped_primitives],
            "evidence_artifact_ids": control.evidence_artifact_ids,
            "last_verified": control.last_verified.isoformat() if control.last_verified else None,
            "verification_notes": control.verification_notes,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get control status: {e!s}")


@router.post("/api/governance/compliance/{framework}/{control_id}/verify")
async def verify_control(
    framework: str, control_id: str,
    request: ComplianceVerifyControlRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        success = services.compliance_mapping_service.verify_control(
            control_id=control_id, framework=framework_enum, notes=request.notes,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Control {control_id} not found in framework {framework}",
            )

        control = services.compliance_mapping_service.get_control_status(control_id, framework_enum)
        return {
            "success": True,
            "control_id": control_id,
            "framework": framework,
            "status": control.status.value,
            "last_verified": control.last_verified.isoformat() if control.last_verified else None,
            "verification_notes": control.verification_notes,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {e!s}")


@router.post("/api/governance/compliance/{framework}/{control_id}/link-evidence")
async def link_evidence_to_control(
    framework: str, control_id: str,
    request: ComplianceLinkEvidenceRequest,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        success = services.compliance_mapping_service.link_evidence_to_control(
            control_id=control_id, framework=framework_enum,
            evidence_artifact_id=request.evidence_artifact_id,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Control {control_id} not found in framework {framework}",
            )

        control = services.compliance_mapping_service.get_control_status(control_id, framework_enum)
        return {
            "success": True,
            "control_id": control_id,
            "framework": framework,
            "evidence_artifact_id": request.evidence_artifact_id,
            "total_evidence_artifacts": len(control.evidence_artifact_ids),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link evidence: {e!s}")


@router.get("/api/governance/compliance/{framework}/gaps")
async def analyze_compliance_gaps(framework: str, services: ServiceRegistry = Depends(get_services)):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        gaps = services.compliance_mapping_service.analyze_gaps(framework_enum)
        return {"framework": framework, "gap_count": len(gaps), "gaps": gaps}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gap analysis failed: {e!s}")


@router.get("/api/governance/compliance/{framework}/report")
async def generate_compliance_report(framework: str, services: ServiceRegistry = Depends(get_services)):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        report = services.compliance_mapping_service.generate_compliance_report(framework_enum)
        return {
            "report_id": report.report_id,
            "framework": report.framework.value,
            "generated_at": report.generated_at.isoformat(),
            "total_controls": report.total_controls,
            "implemented_controls": report.implemented_controls,
            "verified_controls": report.verified_controls,
            "non_compliant_controls": report.non_compliant_controls,
            "compliance_percentage": report.compliance_percentage,
            "gaps": report.gaps,
            "recommendations": report.recommendations,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e!s}")


@router.get("/api/governance/compliance/{framework}/coverage")
async def get_framework_coverage(framework: str, services: ServiceRegistry = Depends(get_services)):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        framework_enum = RegulatoryFramework(framework.lower())
        return services.compliance_mapping_service.get_framework_coverage(framework_enum)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get coverage: {e!s}")


@router.get("/api/governance/compliance/primitive/{primitive_id}/mappings")
async def get_primitive_mappings(primitive_id: str, services: ServiceRegistry = Depends(get_services)):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        mappings = services.compliance_mapping_service.get_primitive_mappings(primitive_id)
        return {
            "primitive_id": primitive_id,
            "mapping_count": len(mappings),
            "mappings": [
                {
                    "mapping_id": m.mapping_id,
                    "primitive_type": m.primitive_type.value,
                    "framework": m.framework.value,
                    "control_ids": m.control_ids,
                    "mapped_at": m.mapped_at.isoformat(),
                    "verification_status": m.verification_status,
                }
                for m in mappings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get mappings: {e!s}")


@router.get("/api/governance/compliance/statistics")
@cache_compliance_mapping(ttl=900)
async def get_compliance_statistics(services: ServiceRegistry = Depends(get_services)):
    if not services.compliance_mapping_service:
        raise HTTPException(status_code=500, detail="Compliance mapping service not initialized")

    try:
        stats = services.compliance_mapping_service.get_statistics()
        if "frameworks" in stats:
            stats["frameworks"] = [f.value for f in stats["frameworks"]]
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e!s}")
