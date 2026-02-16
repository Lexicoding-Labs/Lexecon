"""Dependency injection for the Lexecon Governance API.

Replaces 24 module-level globals + initialize_services() with a single
ServiceRegistry singleton, exposed as FastAPI Depends callables.
"""

import os
import time
import uuid
from typing import Optional

from fastapi import Request

from lexecon.audit_export.service import AuditExportService
from lexecon.compliance_mapping.service import ComplianceMappingService
from lexecon.decision.service import DecisionService
from lexecon.escalation.service import EscalationService
from lexecon.evidence.service import EvidenceService
from lexecon.evidence_export.service import EvidenceExportService
from lexecon.identity.signing import KeyManager
from lexecon.ledger.chain import LedgerChain
from lexecon.override.service import OverrideService
from lexecon.policy.engine import PolicyEngine, PolicyMode
from lexecon.responsibility.storage import ResponsibilityStorage
from lexecon.responsibility.tracker import ResponsibilityTracker
from lexecon.risk.service import RiskService
from lexecon.security.audit_service import AuditService
from lexecon.security.auth_service import AuthService
from lexecon.security.auth_service_async import AsyncAuthService
from lexecon.security.signature_service import SignatureService
from lexecon.storage.persistence import LedgerStorage
from lexecon.usage.service import UsageService
from lexecon.tenancy.service import TenancyService


class ServiceRegistry:
    """Singleton that owns every service instance.

    Eager services are created in __init__ (same as the old module-level globals).
    Lazy services are created in initialize() (same as the old initialize_services()).
    """

    _instance: Optional["ServiceRegistry"] = None

    def __init__(self) -> None:
        # ── Eager services (created at import time in the old code) ──
        self.storage: LedgerStorage = LedgerStorage("lexecon_ledger.db")
        self.ledger: LedgerChain = LedgerChain(storage=self.storage)
        self.responsibility_storage: ResponsibilityStorage = ResponsibilityStorage("lexecon_responsibility.db")
        self.responsibility_tracker: ResponsibilityTracker = ResponsibilityTracker(storage=self.responsibility_storage)
        self.node_id: str = str(uuid.uuid4())
        self.startup_time: float = time.time()

        # Security services
        self.auth_service: AuthService = AuthService("lexecon_auth.db")
        self.async_auth_service: AsyncAuthService = AsyncAuthService(self.auth_service)
        self.audit_service: AuditService = AuditService("lexecon_export_audit.db")
        self.signature_service: SignatureService = SignatureService("lexecon_keys")

        # OIDC OAuth service
        from lexecon.security.oidc_service import get_oidc_service
        self.oidc_service = get_oidc_service()
        self._register_oidc_providers()

        # ── Lazy services (None until initialize()) ──
        self.policy_engine: Optional[PolicyEngine] = None
        self.decision_service: Optional[DecisionService] = None
        self.key_manager: Optional[KeyManager] = None
        self.oversight_system = None
        self.intervention_storage = None
        self.risk_service: Optional[RiskService] = None
        self.escalation_service: Optional[EscalationService] = None
        self.override_service: Optional[OverrideService] = None
        self.evidence_service: Optional[EvidenceService] = None
        self.evidence_export_service: Optional[EvidenceExportService] = None
        self.usage_service: Optional[UsageService] = None
        self.tenancy_service: Optional[TenancyService] = None
        self.compliance_mapping_service: Optional[ComplianceMappingService] = None
        self.audit_export_service: Optional[AuditExportService] = None

    # ── Singleton access ──

    @classmethod
    def get(cls) -> "ServiceRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    # ── Lazy init (idempotent) ──

    def initialize(self) -> None:
        """Same logic as the old initialize_services(), idempotent."""
        if self.policy_engine is None:
            self.policy_engine = PolicyEngine(mode=PolicyMode.STRICT)

        if self.decision_service is None:
            self.decision_service = DecisionService(policy_engine=self.policy_engine)

        if self.key_manager is None:
            self.key_manager = KeyManager.generate()

        if self.intervention_storage is None:
            from lexecon.compliance.eu_ai_act.storage import InterventionStorage
            self.intervention_storage = InterventionStorage("lexecon_interventions.db")

        if self.oversight_system is None:
            from lexecon.compliance.eu_ai_act.article_14_oversight import HumanOversightEvidence
            self.oversight_system = HumanOversightEvidence(
                key_manager=self.key_manager,
                storage=self.intervention_storage,
            )

        if self.risk_service is None:
            self.risk_service = RiskService()

        if self.escalation_service is None:
            self.escalation_service = EscalationService()

        if self.override_service is None:
            self.override_service = OverrideService()

        if self.evidence_service is None:
            self.evidence_service = EvidenceService()

        if self.evidence_export_service is None:
            self.evidence_export_service = EvidenceExportService(
                ledger=self.ledger,
                signature_service=self.signature_service,
            )

        if self.usage_service is None:
            self.usage_service = UsageService("lexecon_usage.db")

        if self.tenancy_service is None:
            self.tenancy_service = TenancyService("lexecon_auth.db")

        if self.compliance_mapping_service is None:
            self.compliance_mapping_service = ComplianceMappingService()

        if self.audit_export_service is None:
            self.audit_export_service = AuditExportService()

    # ── OIDC provider registration ──

    def _register_oidc_providers(self) -> None:
        # Google
        if os.getenv("OIDC_GOOGLE_CLIENT_ID") and os.getenv("OIDC_GOOGLE_CLIENT_SECRET"):
            self.oidc_service.register_provider(
                provider_name="google",
                discovery_url="https://accounts.google.com/.well-known/openid-configuration",
                client_id=os.getenv("OIDC_GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("OIDC_GOOGLE_CLIENT_SECRET"),
            )

        # Azure AD
        if os.getenv("OIDC_AZURE_CLIENT_ID") and os.getenv("OIDC_AZURE_CLIENT_SECRET"):
            tenant_id = os.getenv("OIDC_AZURE_TENANT_ID", "common")
            self.oidc_service.register_provider(
                provider_name="azure",
                discovery_url=f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
                client_id=os.getenv("OIDC_AZURE_CLIENT_ID"),
                client_secret=os.getenv("OIDC_AZURE_CLIENT_SECRET"),
            )

        # Custom OIDC provider
        if os.getenv("OIDC_CUSTOM_DISCOVERY_URL") and os.getenv("OIDC_CUSTOM_CLIENT_ID"):
            self.oidc_service.register_provider(
                provider_name="custom",
                discovery_url=os.getenv("OIDC_CUSTOM_DISCOVERY_URL"),
                client_id=os.getenv("OIDC_CUSTOM_CLIENT_ID"),
                client_secret=os.getenv("OIDC_CUSTOM_CLIENT_SECRET"),
            )


# ── FastAPI Depends callables ──

def get_services() -> ServiceRegistry:
    """Return the initialized ServiceRegistry. Use as ``Depends(get_services)``."""
    reg = ServiceRegistry.get()
    reg.initialize()
    return reg


def get_session_id(request: Request) -> Optional[str]:
    """Extract session ID from cookie or Authorization header."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            session_id = auth_header[7:].strip()
        elif auth_header:
            session_id = auth_header.replace("Bearer ", "")
    return session_id or None


def get_tenant_id(request: Request) -> str:
    """Extract tenant ID from X-Tenant-ID header (defaults to 'default')."""
    return request.headers.get("X-Tenant-ID", "default")
