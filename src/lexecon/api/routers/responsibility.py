"""Responsibility tracking endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from lexecon.api.dependencies import ServiceRegistry, get_services

router = APIRouter()


@router.get("/responsibility/report")
async def get_accountability_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    services: ServiceRegistry = Depends(get_services),
):
    return services.responsibility_tracker.generate_accountability_report(
        start_date=start_date, end_date=end_date,
    )


@router.get("/responsibility/chain/{decision_id}")
async def get_responsibility_chain(
    decision_id: str,
    services: ServiceRegistry = Depends(get_services),
):
    chain = services.responsibility_tracker.get_responsibility_chain(decision_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {
        "decision_id": decision_id,
        "chain_length": len(chain),
        "records": [r.to_dict() for r in chain],
    }


@router.get("/responsibility/party/{party}")
async def get_by_party(
    party: str,
    services: ServiceRegistry = Depends(get_services),
):
    records = services.responsibility_tracker.get_by_responsible_party(party)
    return {
        "responsible_party": party,
        "decision_count": len(records),
        "records": [r.to_dict() for r in records],
    }


@router.get("/responsibility/overrides")
async def get_ai_overrides(services: ServiceRegistry = Depends(get_services)):
    overrides = services.responsibility_tracker.get_ai_overrides()
    return {
        "override_count": len(overrides),
        "records": [r.to_dict() for r in overrides],
    }


@router.get("/responsibility/pending-reviews")
async def get_pending_reviews(services: ServiceRegistry = Depends(get_services)):
    pending = services.responsibility_tracker.get_pending_reviews()
    return {
        "pending_count": len(pending),
        "records": [r.to_dict() for r in pending],
    }


@router.get("/responsibility/legal/{decision_id}")
async def get_legal_export(
    decision_id: str,
    services: ServiceRegistry = Depends(get_services),
):
    return services.responsibility_tracker.export_for_legal(decision_id)


@router.get("/responsibility/storage/stats")
async def get_responsibility_storage_stats(
    services: ServiceRegistry = Depends(get_services),
):
    if not services.responsibility_storage:
        raise HTTPException(status_code=503, detail="Responsibility persistence not configured")
    stats = services.responsibility_storage.get_statistics()
    return {"storage_enabled": True, **stats}
