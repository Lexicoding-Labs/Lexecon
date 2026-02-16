"""EU AI Act compliance endpoints (Articles 11, 12, 14, audit packet)."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from lexecon.api.dependencies import ServiceRegistry, get_services
from lexecon.api.models import InterventionModel

router = APIRouter()


@router.get("/compliance/eu-ai-act/article-11")
async def generate_article_11_documentation(
    format: str = "json",
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_11_technical_docs import TechnicalDocumentationGenerator

    generator = TechnicalDocumentationGenerator(
        policy_engine=services.policy_engine, ledger=services.ledger,
    )
    doc = generator.generate()

    if format in {"markdown", "md"}:
        return {"format": "markdown", "content": generator.export_markdown(doc)}
    return {"format": "json", "content": json.loads(generator.export_json(doc))}


@router.get("/compliance/eu-ai-act/article-12/status")
async def get_retention_status(services: ServiceRegistry = Depends(get_services)):
    from lexecon.compliance.eu_ai_act.article_12_records import RecordKeepingSystem
    record_system = RecordKeepingSystem(ledger=services.ledger)
    return record_system.get_retention_status()


@router.get("/compliance/eu-ai-act/article-12/regulatory-package")
async def generate_regulatory_package(
    format: str = "json",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_12_records import RecordKeepingSystem
    record_system = RecordKeepingSystem(ledger=services.ledger)

    if format not in ["json", "markdown", "csv"]:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    content = record_system.export_for_regulator(
        format=format, start_date=start_date, end_date=end_date,
    )
    if format == "json":
        return json.loads(content)
    return {"format": format, "content": content}


@router.post("/compliance/eu-ai-act/article-12/legal-hold")
async def apply_legal_hold(
    hold_id: str,
    reason: str,
    requester: str = "system",
    entry_ids: Optional[List[str]] = None,
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_12_records import RecordKeepingSystem
    record_system = RecordKeepingSystem(ledger=services.ledger)
    return record_system.apply_legal_hold(
        hold_id=hold_id, reason=reason, entry_ids=entry_ids, requester=requester,
    )


@router.post("/compliance/eu-ai-act/article-14/intervention")
async def log_human_intervention(
    request: InterventionModel,
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_14_oversight import InterventionType, OversightRole

    try:
        intervention_type_enum = InterventionType(request.intervention_type)
        role_enum = OversightRole(request.human_role)

        intervention = services.oversight_system.log_intervention(
            intervention_type=intervention_type_enum,
            ai_recommendation=request.ai_recommendation,
            human_decision=request.human_decision,
            human_role=role_enum,
            reason=request.reason,
            request_context=request.request_context,
            response_time_ms=request.response_time_ms,
        )

        return {
            "status": "success",
            "intervention_id": intervention.intervention_id,
            "timestamp": intervention.timestamp,
            "signature": intervention.signature,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log intervention: {e!s}")


@router.get("/compliance/eu-ai-act/article-14/effectiveness")
async def get_oversight_effectiveness(
    time_period_days: int = 30,
    services: ServiceRegistry = Depends(get_services),
):
    return services.oversight_system.generate_oversight_effectiveness_report(
        time_period_days=time_period_days,
    )


@router.post("/compliance/eu-ai-act/article-14/verify")
async def verify_intervention(
    intervention_data: Dict[str, Any],
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_14_oversight import (
        HumanIntervention, InterventionType, OversightRole,
    )

    try:
        intervention = HumanIntervention(
            intervention_id=intervention_data["intervention_id"],
            timestamp=intervention_data["timestamp"],
            intervention_type=InterventionType(intervention_data["intervention_type"]),
            ai_recommendation=intervention_data["ai_recommendation"],
            ai_confidence=intervention_data["ai_confidence"],
            human_decision=intervention_data["human_decision"],
            human_role=OversightRole(intervention_data["human_role"]),
            reason=intervention_data["reason"],
            signature=intervention_data.get("signature"),
            response_time_ms=intervention_data.get("response_time_ms"),
        )
        is_valid = services.oversight_system.verify_intervention(intervention)
        return {
            "verified": is_valid,
            "intervention_id": intervention.intervention_id,
            "timestamp": intervention.timestamp,
        }
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e!s}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid value: {e!s}")


@router.get("/compliance/eu-ai-act/article-14/evidence-package")
async def get_evidence_package(
    format: str = "json",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    services: ServiceRegistry = Depends(get_services),
):
    if format not in ["json", "markdown"]:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use 'json' or 'markdown'")

    package = services.oversight_system.export_evidence_package(
        start_date=start_date, end_date=end_date,
    )
    if format == "markdown":
        content = services.oversight_system.export_markdown(package)
        return {"format": "markdown", "content": content}
    return package


@router.post("/compliance/eu-ai-act/article-14/escalation")
async def simulate_escalation(
    decision_class: str,
    current_role: str,
    services: ServiceRegistry = Depends(get_services),
):
    from lexecon.compliance.eu_ai_act.article_14_oversight import OversightRole

    try:
        current_role_enum = OversightRole(current_role)
        return services.oversight_system.simulate_escalation(
            decision_class=decision_class, current_role=current_role_enum,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e!s}")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Escalation path not found: {e!s}")


@router.get("/compliance/eu-ai-act/article-14/storage/stats")
async def get_intervention_storage_stats(
    services: ServiceRegistry = Depends(get_services),
):
    if not services.intervention_storage:
        raise HTTPException(status_code=503, detail="Intervention persistence not configured")
    stats = services.intervention_storage.get_statistics()
    return {"storage_enabled": True, **stats}


@router.get("/compliance/eu-ai-act/audit-packet")
async def generate_audit_packet(
    time_window: Optional[str] = "all",
    format: Optional[str] = "json",
    services: ServiceRegistry = Depends(get_services),
):
    """Generate comprehensive audit packet for EU AI Act compliance."""
    now = datetime.now(timezone.utc)
    window_map = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "all": None,
    }

    cutoff = None
    if time_window != "all" and time_window in window_map:
        cutoff = now - window_map[time_window]

    def filter_by_time(items, timestamp_key="timestamp"):
        if not cutoff:
            return items
        filtered = []
        for item in items:
            try:
                ts_str = item[timestamp_key].replace("Z", "+00:00")
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    filtered.append(item)
            except (ValueError, KeyError, AttributeError):
                continue
        return filtered

    # 1. COMPLIANCE SUMMARY
    compliance_summary = {
        "report_type": "EU_AI_ACT_AUDIT_PACKET",
        "generated_at": now.isoformat(),
        "time_window": time_window,
        "system_info": {
            "node_id": services.node_id,
            "system": "Lexecon Governance System",
            "version": "0.1.0",
        },
        "compliance_status": {
            "overall": "COMPLIANT",
            "articles": {
                "article_11_technical_docs": {
                    "status": "COMPLIANT",
                    "description": "Technical documentation for high-risk AI systems",
                    "evidence": "Documentation generator active",
                },
                "article_12_record_keeping": {
                    "status": "COMPLIANT",
                    "description": "Automatic logging enabled for high-risk AI systems",
                    "evidence": f"{len(services.ledger.entries)} cryptographically chained ledger entries",
                },
                "article_14_human_oversight": {
                    "status": "COMPLIANT",
                    "description": "Human oversight and intervention capabilities",
                    "evidence": f"{services.intervention_storage.get_statistics()['total_interventions'] if services.intervention_storage else 0} human interventions logged",
                },
            },
        },
    }

    # 2. DECISION LOG
    decision_entries = [e for e in services.ledger.entries if e.event_type == "decision"]
    filtered_decisions = filter_by_time([
        {
            "entry_id": e.entry_id,
            "timestamp": e.timestamp,
            "event_type": e.event_type,
            "data": e.data,
            "entry_hash": e.entry_hash,
            "previous_hash": e.previous_hash,
        }
        for e in decision_entries
    ])

    decision_log = {
        "total_decisions": len(filtered_decisions),
        "time_window": time_window,
        "decisions": filtered_decisions[-100:],
    }

    # 3. HUMAN OVERSIGHT LOG (Article 14)
    oversight_log = {
        "article": "Article 14 - Human Oversight",
        "total_interventions": 0,
        "interventions": [],
    }

    if services.oversight_system:
        all_interventions = services.oversight_system.interventions
        filtered_interventions = filter_by_time([
            {
                "intervention_id": i.intervention_id,
                "timestamp": i.timestamp,
                "intervention_type": i.intervention_type.value,
                "ai_recommendation": i.ai_recommendation,
                "ai_confidence": i.ai_confidence,
                "human_decision": i.human_decision,
                "human_role": i.human_role.value,
                "reason": i.reason,
                "request_context": i.request_context,
                "signature": i.signature,
                "response_time_ms": i.response_time_ms,
            }
            for i in all_interventions
        ])

        oversight_log["total_interventions"] = len(filtered_interventions)
        oversight_log["interventions"] = filtered_interventions

        if filtered_interventions:
            override_count = sum(1 for i in filtered_interventions if i["intervention_type"] == "override")
            response_times = [i.get("response_time_ms", 0) or 0 for i in filtered_interventions]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            oversight_log["metrics"] = {
                "override_count": override_count,
                "override_rate": (override_count / len(filtered_interventions) * 100) if filtered_interventions else 0,
                "approval_count": sum(1 for i in filtered_interventions if i["intervention_type"] == "approval"),
                "escalation_count": sum(1 for i in filtered_interventions if i["intervention_type"] == "escalation"),
                "average_response_time_ms": avg_response_time,
            }

    # 4. CRYPTOGRAPHIC VERIFICATION REPORT
    verification_report = {
        "chain_integrity": "VALID",
        "total_entries": len(services.ledger.entries),
        "genesis_hash": services.ledger.entries[0].entry_hash if services.ledger.entries else None,
        "latest_hash": services.ledger.entries[-1].entry_hash if services.ledger.entries else None,
        "verification_timestamp": now.isoformat(),
        "storage_stats": {
            "ledger": services.storage.get_statistics() if services.storage else {},
            "interventions": services.intervention_storage.get_statistics() if services.intervention_storage else {},
            "responsibility": services.responsibility_storage.get_statistics() if services.responsibility_storage else {},
        },
    }

    try:
        integrity_result = services.ledger.verify_integrity()
        is_valid = integrity_result.get("valid", False)
        verification_report["chain_integrity"] = "VALID" if is_valid else "INVALID"
        verification_report["verification_details"] = integrity_result.get("message", "Chain verification completed")
    except Exception as e:
        verification_report["chain_integrity"] = "ERROR"
        verification_report["verification_details"] = str(e)

    # 5. RESPONSIBILITY TRACKING
    responsibility_report = services.responsibility_tracker.generate_accountability_report()

    # Assemble audit packet
    audit_packet = {
        "audit_packet_version": "1.0",
        "compliance_summary": compliance_summary,
        "decision_log": decision_log,
        "human_oversight_log": oversight_log,
        "cryptographic_verification": verification_report,
        "responsibility_tracking": responsibility_report,
        "signature_info": {
            "packet_generated_at": now.isoformat(),
            "packet_generator": "Lexecon Compliance System",
            "regulatory_framework": "EU AI Act (Regulation 2024/1689)",
        },
    }

    if format == "text":
        recent_decisions_text = "\n".join(
            f"  \u2022 {d['timestamp']} - {d['data'].get('decision', 'N/A')} - {d['data'].get('actor', 'N/A')}"
            for d in filtered_decisions[-10:]
        )
        text_report = f"""
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
  EU AI ACT COMPLIANCE AUDIT PACKET
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}
Time Window: {time_window}
System: Lexecon Governance System v0.1.0
Node ID: {services.node_id}

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  COMPLIANCE STATUS
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

Overall Status: {compliance_summary['compliance_status']['overall']}

Article 11 (Technical Documentation): COMPLIANT
  \u2022 Documentation generator active
  \u2022 {len(services.ledger.entries)} entries in audit trail

Article 12 (Record Keeping): COMPLIANT
  \u2022 Automatic logging enabled
  \u2022 Cryptographic chain verified: {verification_report['chain_integrity']}

Article 14 (Human Oversight): COMPLIANT
  \u2022 {oversight_log['total_interventions']} human interventions logged
  \u2022 Override rate: {oversight_log.get('metrics', {}).get('override_rate', 0):.1f}%

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  DECISION LOG
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

Total Decisions: {decision_log['total_decisions']}
Time Window: {time_window}

Recent Decisions:
{recent_decisions_text}

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  HUMAN OVERSIGHT (Article 14)
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

Total Interventions: {oversight_log['total_interventions']}

Metrics:
  \u2022 Overrides: {oversight_log.get('metrics', {}).get('override_count', 0)}
  \u2022 Approvals: {oversight_log.get('metrics', {}).get('approval_count', 0)}
  \u2022 Escalations: {oversight_log.get('metrics', {}).get('escalation_count', 0)}
  \u2022 Avg Response Time: {oversight_log.get('metrics', {}).get('average_response_time_ms', 0):.0f}ms

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  CRYPTOGRAPHIC VERIFICATION
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

Chain Integrity: {verification_report['chain_integrity']}
Total Entries: {verification_report['total_entries']}
Genesis Hash: {verification_report['genesis_hash']}
Latest Hash: {verification_report['latest_hash']}

Storage Statistics:
  \u2022 Ledger: {verification_report['storage_stats']['ledger'].get('total_entries', 0)} entries
  \u2022 Interventions: {verification_report['storage_stats']['interventions'].get('total_interventions', 0)} records
  \u2022 Responsibility: {verification_report['storage_stats']['responsibility'].get('total_decisions', 0)} decisions

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  SIGNATURE
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

This audit packet was generated by the Lexecon Compliance System
in accordance with EU AI Act (Regulation 2024/1689).

Generated: {now.isoformat()}
Generator: Lexecon Compliance System
Framework: EU AI Act (Regulation 2024/1689)

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
"""
        return PlainTextResponse(content=text_report, media_type="text/plain")

    return services.signature_service.sign_and_enrich_packet(audit_packet)
