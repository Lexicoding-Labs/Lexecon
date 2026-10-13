"""Exercise the artifact function with fake services, without accounts or keys."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lexecon.api.routers.eu_compliance import generate_audit_packet


@pytest.mark.parametrize("output_format", ["json", "text"])
@pytest.mark.parametrize("chain_state", ["VALID", "INVALID", "ERROR"])
def test_evidence_packet_does_not_assert_unassessed_compliance(output_format, chain_state):
    entry = SimpleNamespace(
        entry_id="fixture-entry", timestamp="2026-10-07T00:00:00Z", event_type="decision",
        data={"decision": "permit", "actor": "fixture-actor"},
        entry_hash="fixture-hash", previous_hash="fixture-previous",
    )
    verify = Mock(return_value={"valid": chain_state == "VALID"})
    if chain_state == "ERROR":
        verify.side_effect = RuntimeError("Fixture integrity check unavailable")
    # This fake passes the assembled payload through; it never signs or loads keys.
    enrich = Mock(side_effect=lambda packet: packet)
    services = SimpleNamespace(
        node_id="fixture-node",
        ledger=SimpleNamespace(entries=[entry], verify_integrity=verify),
        oversight_system=None, intervention_storage=None, storage=None, responsibility_storage=None,
        responsibility_tracker=SimpleNamespace(
            generate_accountability_report=Mock(return_value={"fixture": "responsibility-evidence"}),
        ),
        signature_service=SimpleNamespace(sign_and_enrich_packet=enrich),
    )

    result = asyncio.run(generate_audit_packet(time_window="all", format=output_format, services=services))

    verify.assert_called_once_with()
    if output_format == "json":
        status = result["compliance_summary"]["compliance_status"]
        assert status["overall"] == "NOT_ASSESSED"
        assert all(article["status"] == "NOT_ASSESSED" for article in status["articles"].values())
        assert "has not been assessed" in status["limitation"]
        assert "signatures do not establish legal compliance or certification" in status["limitation"]
        assert result["cryptographic_verification"]["chain_integrity"] == chain_state
        assert result["decision_log"]["total_decisions"] == 1
        assert result["decision_log"]["decisions"][0]["entry_id"] == "fixture-entry"
        assert result["responsibility_tracking"] == {"fixture": "responsibility-evidence"}
        enrich.assert_called_once()
    else:
        report = result.body.decode()
        assert "Overall Status: NOT_ASSESSED" in report
        for article in ["Article 11 (Technical Documentation)", "Article 12 (Record Keeping)", "Article 14 (Human Oversight)"]:
            assert f"{article}: NOT_ASSESSED" in report
        assert "has not been assessed" in report
        assert "not a compliance assessment or certification" in report
        assert "COMPLIANT" not in report
        assert f"Chain Integrity: {chain_state}" in report
        assert "Total Decisions: 1" in report
        assert "fixture-actor" in report
        enrich.assert_not_called()
