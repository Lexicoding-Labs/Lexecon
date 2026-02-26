"""Audit export endpoints (Phase 8) and v1 audit dashboard API."""

import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from lexecon.api.dependencies import ServiceRegistry, get_services, get_session_id, get_tenant_id
from lexecon.api.models import AuditExportCreateRequest, EvidenceExportRequest
from lexecon.audit_export.service import ExportFormat, ExportScope
from lexecon.security.audit_service import ExportStatus
from lexecon.security.auth_service import Permission

router = APIRouter()


# ── Evidence Export (PR-03) ──

@router.post("/evidence/export")
async def export_evidence(
    request: Request,
    export_req: EvidenceExportRequest,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
    tenant_id: str = Depends(get_tenant_id),
):
    if services.evidence_export_service is None:
        raise HTTPException(status_code=500, detail="Evidence export service not initialized")

    if services.usage_service:
        can_export, limit_info = services.usage_service.can_export(tenant_id)
        if not can_export:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": limit_info.get("code", "PLAN_LIMIT"),
                    "message": f"Plan limit exceeded: {limit_info['metric']}",
                    "metric": limit_info["metric"],
                    "limit": limit_info["limit"],
                    "current": limit_info["current"],
                    "upgrade_url": "mailto:sales@lexicodinglabs.com",
                },
            )

    if session_id:
        session, error = await services.async_auth_service.validate_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail=error)

    try:
        if services.usage_service:
            services.usage_service.increment_exports(tenant_id)

        zip_bytes = services.evidence_export_service.export(
            tenant_id=tenant_id,
            start_time=export_req.start_time,
            end_time=export_req.end_time,
            limit=export_req.limit,
            include_verification=export_req.include_verification,
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"lexecon_evidence_{tenant_id}_{timestamp}.zip"

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-Timestamp": datetime.utcnow().isoformat(),
                "X-Tenant-ID": tenant_id,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e!s}")


@router.get("/usage")
async def get_usage(
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    tenant_id: str = Depends(get_tenant_id),
):
    if services.usage_service is None:
        raise HTTPException(status_code=503, detail="Usage service not initialized")
    return services.usage_service.get_usage(tenant_id)


# ── Governance Audit Export (Phase 8) ──

@router.post("/api/governance/audit-export/request")
async def create_audit_export_request(
    request: AuditExportCreateRequest,
    http_request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if session_id:
        session, _error = services.auth_service.validate_session(session_id)
        if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
            raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        scope = ExportScope(request.scope.upper())
        format_enum = ExportFormat(request.format.upper())

        start_date = None
        if request.start_date:
            start_date = datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)

        end_date = None
        if request.end_date:
            end_date = datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

        export_request = services.audit_export_service.create_export_request(
            requester=request.requester, purpose=request.purpose,
            scope=scope, format=format_enum, start_date=start_date, end_date=end_date,
            include_deleted=request.include_deleted, metadata=request.metadata,
        )

        return {
            "export_id": export_request.export_id,
            "requester": export_request.requester,
            "purpose": export_request.purpose,
            "scope": export_request.scope.value,
            "format": export_request.format.value,
            "start_date": export_request.start_date.isoformat() if export_request.start_date else None,
            "end_date": export_request.end_date.isoformat() if export_request.end_date else None,
            "include_deleted": export_request.include_deleted,
            "requested_at": export_request.requested_at.isoformat(),
            "status": export_request.status.value,
            "metadata": export_request.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create export request: {e!s}")


@router.post("/api/governance/audit-export/{export_id}/generate")
async def generate_audit_export(
    export_id: str, http_request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    session = None
    if session_id:
        session, _error = services.auth_service.validate_session(session_id)
        if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
            raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        export_request = services.audit_export_service._requests.get(export_id)
        if not export_request:
            raise HTTPException(status_code=404, detail=f"Export request {export_id} not found")

        existing_export = services.audit_export_service.get_export(export_id)
        if existing_export:
            raise HTTPException(status_code=400, detail=f"Export {export_id} already generated")

        package = services.audit_export_service.generate_export(
            request=export_request,
            risk_service=services.risk_service,
            escalation_service=services.escalation_service,
            override_service=services.override_service,
            evidence_service=services.evidence_service,
            compliance_service=services.compliance_mapping_service,
            ledger=services.ledger,
        )

        services.audit_service.log_access(
            endpoint=f"/api/governance/audit-export/{export_id}/generate",
            method="POST", status_code=200,
            user_id=session.user_id if session else None,
            ip_address=http_request.client.host if http_request.client else None,
        )

        return {
            "export_id": package.export_id,
            "generated_at": package.generated_at.isoformat(),
            "format": package.format.value,
            "size_bytes": package.size_bytes,
            "record_count": package.record_count,
            "checksum": package.checksum,
            "signature": package.signature,
            "statistics": package.data.get("statistics", {}),
            "request": {
                "requester": package.request.requester,
                "purpose": package.request.purpose,
                "scope": package.request.scope.value,
                "status": package.request.status.value,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export generation failed: {e!s}")


@router.get("/api/governance/audit-export/{export_id}")
async def get_audit_export(
    export_id: str, include_content: bool = False,
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if http_request:
        session_id = (http_request.cookies.get("session_id")
                      or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if session_id:
            session, _error = services.auth_service.validate_session(session_id)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        package = services.audit_export_service.get_export(export_id)
        if not package:
            raise HTTPException(status_code=404, detail=f"Export {export_id} not found")

        response = {
            "export_id": package.export_id,
            "generated_at": package.generated_at.isoformat(),
            "format": package.format.value,
            "size_bytes": package.size_bytes,
            "record_count": package.record_count,
            "checksum": package.checksum,
            "signature": package.signature,
            "statistics": package.data.get("statistics", {}),
            "request": {
                "requester": package.request.requester,
                "purpose": package.request.purpose,
                "scope": package.request.scope.value,
                "format": package.request.format.value,
                "status": package.request.status.value,
                "requested_at": package.request.requested_at.isoformat(),
            },
            "metadata": package.metadata,
        }

        if include_content:
            response["content"] = package.content
        else:
            response["content_preview"] = package.content[:500] if len(package.content) > 500 else package.content

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get export: {e!s}")


@router.get("/api/governance/audit-export/{export_id}/download")
async def download_audit_export(
    export_id: str, http_request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    session = None
    if session_id:
        session, _error = services.auth_service.validate_session(session_id)
        if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
            raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        package = services.audit_export_service.get_export(export_id)
        if not package:
            raise HTTPException(status_code=404, detail=f"Export {export_id} not found")

        services.audit_service.log_access(
            endpoint=f"/api/governance/audit-export/{export_id}/download",
            method="GET", status_code=200,
            user_id=session.user_id if session else None,
            ip_address=http_request.client.host if http_request.client else None,
        )

        content_type_map = {"json": "application/json", "csv": "text/csv", "markdown": "text/markdown", "html": "text/html"}
        extension_map = {"json": "json", "csv": "csv", "markdown": "md", "html": "html"}

        format_str = package.format.value
        content_type = content_type_map.get(format_str, "text/plain")
        extension = extension_map.get(format_str, "txt")
        timestamp = package.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"export_{export_id}_{timestamp}.{extension}"

        return PlainTextResponse(
            content=package.content, media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e!s}")


@router.get("/api/governance/audit-export/list")
async def list_audit_exports(
    requester: Optional[str] = None,
    scope: Optional[str] = None,
    format: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")

        exports = services.audit_export_service.list_exports(requester=requester, limit=limit)

        if scope:
            try:
                scope_enum = ExportScope(scope.upper())
                exports = [e for e in exports if e.request.scope == scope_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")

        if format:
            try:
                format_enum = ExportFormat(format.upper())
                exports = [e for e in exports if e.format == format_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid format: {format}")

        if status:
            try:
                status_enum = ExportStatus(status.upper())
                exports = [e for e in exports if e.request.status == status_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        return {
            "count": len(exports), "limit": limit,
            "filters": {"requester": requester, "scope": scope, "format": format, "status": status},
            "exports": [
                {
                    "export_id": e.export_id,
                    "requester": e.request.requester,
                    "purpose": e.request.purpose,
                    "scope": e.request.scope.value,
                    "format": e.format.value,
                    "status": e.request.status.value,
                    "generated_at": e.generated_at.isoformat(),
                    "size_bytes": e.size_bytes,
                    "record_count": e.record_count,
                }
                for e in exports
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list exports: {e!s}")


@router.get("/api/governance/audit-export/requests")
async def list_audit_export_requests(
    status: Optional[str] = None, limit: int = 100,
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")

        requests = list(services.audit_export_service._requests.values())

        if status:
            try:
                status_enum = ExportStatus(status.upper())
                requests = [r for r in requests if r.status == status_enum]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        requests.sort(key=lambda r: r.requested_at, reverse=True)
        requests = requests[:limit]

        return {
            "count": len(requests),
            "requests": [
                {
                    "export_id": r.export_id,
                    "requester": r.requester,
                    "purpose": r.purpose,
                    "scope": r.scope.value,
                    "format": r.format.value,
                    "status": r.status.value,
                    "requested_at": r.requested_at.isoformat(),
                    "start_date": r.start_date.isoformat() if r.start_date else None,
                    "end_date": r.end_date.isoformat() if r.end_date else None,
                }
                for r in requests
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list requests: {e!s}")


@router.get("/api/governance/audit-export/statistics")
async def get_audit_export_statistics(
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        return services.audit_export_service.get_export_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e!s}")


# ── Audit Dashboard API (v1) ──

@router.get("/api/v1/audit/decisions")
async def get_audit_decisions(
    search: Optional[str] = None, risk_level: Optional[str] = None,
    outcome: Optional[str] = None, start_date: Optional[str] = None,
    end_date: Optional[str] = None, verified_only: bool = False,
    limit: int = 100, offset: int = 0,
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit logs")

    try:
        entries = [e for e in services.ledger.entries if e.event_type == "decision"]

        filtered_entries = []
        for entry in entries:
            data = entry.data

            if search:
                search_lower = search.lower()
                searchable_text = f"{entry.entry_id} {data.get('action', '')} {data.get('actor', '')}".lower()
                if search_lower not in searchable_text:
                    continue

            if risk_level:
                entry_risk = data.get("risk_level", "low")
                if isinstance(entry_risk, int):
                    risk_map = {1: "minimal", 2: "low", 3: "medium", 4: "high", 5: "critical"}
                    entry_risk = risk_map.get(entry_risk, "low")
                if entry_risk.lower() != risk_level.lower():
                    continue

            if outcome:
                entry_outcome = data.get("outcome", "approved")
                if entry_outcome.lower() != outcome.lower():
                    continue

            if start_date:
                entry_time = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                filter_time = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if entry_time < filter_time:
                    continue

            if end_date:
                entry_time = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                filter_time = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if entry_time > filter_time:
                    continue

            if verified_only:
                calculated_hash = entry.calculate_hash()
                if calculated_hash != entry.entry_hash:
                    continue

            filtered_entries.append(entry)

        filtered_entries.sort(key=lambda e: e.timestamp, reverse=True)

        total = len(filtered_entries)
        paginated_entries = filtered_entries[offset:offset + limit]

        decisions = []
        for entry in paginated_entries:
            data = entry.data
            risk = data.get("risk_level", "low")
            if isinstance(risk, int):
                risk_map = {1: "minimal", 2: "low", 3: "medium", 4: "high", 5: "critical"}
                risk = risk_map.get(risk, "low")

            applied_policies = []
            if "policy_results" in data:
                for policy_name, result in data.get("policy_results", {}).items():
                    applied_policies.append({"name": policy_name, "result": "passed" if result else "failed"})

            decisions.append({
                "id": entry.entry_id,
                "timestamp": entry.timestamp,
                "action": data.get("action", data.get("proposed_action", "Unknown action")),
                "actor": data.get("actor", "system@lexicodinglabs.com"),
                "riskLevel": risk,
                "outcome": data.get("outcome", "approved"),
                "signature": entry.entry_hash,
                "previousHash": entry.previous_hash,
                "policyVersion": data.get("policy_version", "v1.0.0"),
                "verified": entry.calculate_hash() == entry.entry_hash,
                "appliedPolicies": applied_policies,
                "context": data.get("context", {}),
            })

        return {"decisions": decisions, "total": total, "offset": offset, "limit": limit}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve decisions: {e!s}")


@router.get("/api/v1/audit/decisions/{decision_id}")
async def get_decision_details(
    decision_id: str, http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit logs")

    try:
        entry = None
        for e in services.ledger.entries:
            if e.entry_id == decision_id and e.event_type == "decision":
                entry = e
                break

        if not entry:
            raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

        data = entry.data
        risk = data.get("risk_level", "low")
        if isinstance(risk, int):
            risk_map = {1: "minimal", 2: "low", 3: "medium", 4: "high", 5: "critical"}
            risk = risk_map.get(risk, "low")

        applied_policies = []
        if "policy_results" in data:
            for policy_name, result in data.get("policy_results", {}).items():
                applied_policies.append({"name": policy_name, "result": "passed" if result else "failed"})

        calculated_hash = entry.calculate_hash()
        hash_valid = calculated_hash == entry.entry_hash

        chain_valid = True
        entry_index = services.ledger.entries.index(entry)
        if entry_index > 0:
            prev_entry = services.ledger.entries[entry_index - 1]
            chain_valid = entry.previous_hash == prev_entry.entry_hash

        return {
            "id": entry.entry_id,
            "timestamp": entry.timestamp,
            "action": data.get("action", data.get("proposed_action", "Unknown action")),
            "actor": data.get("actor", "system@lexicodinglabs.com"),
            "riskLevel": risk,
            "outcome": data.get("outcome", "approved"),
            "signature": entry.entry_hash,
            "previousHash": entry.previous_hash,
            "policyVersion": data.get("policy_version", "v1.0.0"),
            "verified": hash_valid and chain_valid,
            "appliedPolicies": applied_policies,
            "context": data.get("context", {}),
            "verification": {
                "signatureValid": hash_valid,
                "chainIntegrityValid": chain_valid,
                "calculatedHash": calculated_hash,
                "recordedHash": entry.entry_hash,
            },
            "fullData": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve decision: {e!s}")


@router.get("/api/v1/audit/stats")
async def get_audit_statistics(
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit logs")

    try:
        decision_entries = [e for e in services.ledger.entries if e.event_type == "decision"]
        total_decisions = len(decision_entries)

        verified_count = sum(1 for e in decision_entries if e.calculate_hash() == e.entry_hash)

        escalations = approvals = denials = overrides = 0
        high_risk_count = critical_risk_count = 0

        for entry in decision_entries:
            data = entry.data
            oc = data.get("outcome", "approved").lower()
            if oc == "escalated":
                escalations += 1
            elif oc == "approved":
                approvals += 1
            elif oc == "denied":
                denials += 1
            elif oc == "override":
                overrides += 1

            risk = data.get("risk_level", "low")
            if isinstance(risk, int):
                if risk >= 4:
                    high_risk_count += 1
                if risk == 5:
                    critical_risk_count += 1
            elif isinstance(risk, str):
                if risk.lower() in ["high", "critical"]:
                    high_risk_count += 1
                if risk.lower() == "critical":
                    critical_risk_count += 1

        verified_percentage = (verified_count / total_decisions * 100) if total_decisions > 0 else 100

        return {
            "totalDecisions": total_decisions,
            "totalDecisionsChange": "+12%",
            "verifiedEntries": verified_count,
            "verifiedPercentage": round(verified_percentage, 1),
            "escalations": escalations,
            "escalationsChange": "-8%",
            "highRiskCount": high_risk_count,
            "criticalRiskCount": critical_risk_count,
            "highRiskStatus": "Requiring oversight" if high_risk_count > 0 else "Normal",
            "outcomeBreakdown": {
                "approved": approvals, "denied": denials,
                "escalated": escalations, "override": overrides,
            },
            "riskBreakdown": {"high": high_risk_count, "critical": critical_risk_count},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate statistics: {e!s}")


@router.post("/api/v1/audit/verify")
async def verify_audit_ledger(
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit verification")

    try:
        verification_result = services.ledger.verify_integrity()

        total_entries = len(services.ledger.entries)
        verified_entries = 0
        failed_entries = []

        for i, entry in enumerate(services.ledger.entries):
            calculated_hash = entry.calculate_hash()
            hash_valid = calculated_hash == entry.entry_hash

            chain_valid = True
            if i > 0:
                prev_entry = services.ledger.entries[i - 1]
                chain_valid = entry.previous_hash == prev_entry.entry_hash

            if hash_valid and chain_valid:
                verified_entries += 1
            else:
                failed_entries.append({
                    "entry_id": entry.entry_id, "index": i,
                    "hash_valid": hash_valid, "chain_valid": chain_valid,
                })

        return {
            "verified": verification_result["valid"],
            "totalEntries": total_entries,
            "verifiedEntries": verified_entries,
            "failedEntries": failed_entries,
            "integrityPercentage": round((verified_entries / total_entries * 100), 2) if total_entries > 0 else 100,
            "details": verification_result,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {e!s}")


@router.post("/api/v1/audit/export")
async def create_audit_export_v1(
    request: AuditExportCreateRequest, http_request: Request,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    return await create_audit_export_request(request, http_request, services, session_id)


@router.get("/api/v1/audit/exports")
async def list_audit_exports_v1(
    status: Optional[str] = None, limit: int = 50, offset: int = 0,
    http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
):
    if not services.audit_export_service:
        raise HTTPException(status_code=500, detail="Audit export service not initialized")

    if http_request:
        sid = (http_request.cookies.get("session_id")
               or http_request.headers.get("Authorization", "").replace("Bearer ", ""))
        if sid:
            session, _error = services.auth_service.validate_session(sid)
            if session and not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
                raise HTTPException(status_code=403, detail="Insufficient permissions for audit exports")

    try:
        all_requests = list(services.audit_export_service._requests.values())

        if status:
            status_enum = ExportStatus(status.upper())
            all_requests = [r for r in all_requests if r.status == status_enum]

        all_requests.sort(key=lambda r: r.requested_at, reverse=True)

        total = len(all_requests)
        paginated = all_requests[offset:offset + limit]

        exports = []
        for req in paginated:
            package = services.audit_export_service.get_export(req.export_id)
            exports.append({
                "exportId": req.export_id,
                "requester": req.requester,
                "purpose": req.purpose,
                "format": req.format.value,
                "scope": req.scope.value,
                "status": req.status.value,
                "requestedAt": req.requested_at.isoformat(),
                "startDate": req.start_date.isoformat() if req.start_date else None,
                "endDate": req.end_date.isoformat() if req.end_date else None,
                "generatedAt": package.generated_at.isoformat() if package else None,
                "sizeBytes": package.size_bytes if package else None,
                "recordCount": package.record_count if package else None,
            })

        return {"exports": exports, "total": total, "offset": offset, "limit": limit}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list exports: {e!s}")


@router.get("/api/v1/audit/exports/{export_id}/download")
async def download_audit_export_v1(
    export_id: str, http_request: Request = None,
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
):
    return await download_audit_export(export_id, http_request, services, session_id)
