"""Policy management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from lexecon.api.dependencies import ServiceRegistry, get_services, require_admin
from lexecon.api.models import PolicyLoadModel
from lexecon.policy.engine import PolicyVersionConflict

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/policies")
async def list_policies(services: ServiceRegistry = Depends(get_services)):
    if services.policy_engine is None:
        raise HTTPException(status_code=500, detail="Policy engine not initialized")

    return {
        "policies": [],
        "mode": services.policy_engine.mode.value,
        "terms_count": len(services.policy_engine.terms),
        "relations_count": len(services.policy_engine.relations),
        "policy_hash": services.policy_engine.get_policy_hash(),
    }


@router.get("/policies/export")
async def export_policy(services: ServiceRegistry = Depends(get_services)):
    """Export the active policy for an administrator's conditional rollback."""
    if services.policy_engine is None:
        raise HTTPException(status_code=500, detail="Policy engine not initialized")
    return services.policy_engine.export_policy()


@router.post("/policies/load")
async def load_policy(
    policy_load: PolicyLoadModel,
    services: ServiceRegistry = Depends(get_services),
):
    if services.policy_engine is None:
        raise HTTPException(status_code=500, detail="Policy engine not initialized")
    try:
        if policy_load.policy is not None:
            policy_dict = policy_load.policy
            if not isinstance(policy_dict, dict):
                raise ValueError("Policy must be a dictionary")
            if "terms" not in policy_dict and "relations" not in policy_dict:
                raise ValueError("Policy must contain at least 'terms' or 'relations' field")
        else:
            policy_dict = policy_load.model_dump(exclude={"policy", "expected_policy_hash"}, exclude_none=True)
            if "terms" not in policy_dict and "relations" not in policy_dict:
                raise ValueError("Policy must contain at least 'terms' or 'relations' field")

        snapshot = services.policy_engine.load_policy(
            policy_dict, expected_policy_hash=policy_load.expected_policy_hash,
        )
        loaded = snapshot["policy"]

        services.ledger.append(
            "policy_loaded",
            {
                "policy_hash": snapshot["policy_hash"],
                "previous_policy_hash": snapshot["previous_policy_hash"],
                "terms_count": len(loaded["terms"]),
                "relations_count": len(loaded["relations"]),
            },
        )

        return {
            "status": "success",
            "policy_hash": snapshot["policy_hash"],
            "previous_policy_hash": snapshot["previous_policy_hash"],
            "terms_loaded": len(loaded["terms"]),
            "relations_loaded": len(loaded["relations"]),
        }
    except PolicyVersionConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to load policy: {e!s}",
        )
