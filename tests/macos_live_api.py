"""Disposable real API process for the native integration test (never user storage)."""

import os
import sys

import uvicorn

from lexecon.api.dependencies import ServiceRegistry
from lexecon.api.server import app
from lexecon.policy.relations import PolicyRelation
from lexecon.security.auth_service import Role


def main():
    services = ServiceRegistry.get()
    services.initialize()
    username = os.environ["LEXECON_TEST_USERNAME"]
    services.auth_service.create_user(
        username, "native@example.test", os.environ["LEXECON_TEST_PASSWORD"], Role.ADMIN, "Native Test",
    )
    services.policy_engine.add_relation(PolicyRelation.permits(f"actor:{username}", "action:read"))
    # Historical fixture events exercise paging without consuming the decision quota.
    # The two new examples still go through real authorization and policy evaluation.
    for index in range(201):
        services.ledger.append("decision", {
            "tenant_id": "default", "actor": username, "action": "read", "decision": "permit",
            "decision_id": f"seed-{index}", "evaluation_source": "test_fixture",
        })
    uvicorn.run(app, fd=int(sys.argv[1]), log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
