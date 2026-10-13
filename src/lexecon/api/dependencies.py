"""Dependency injection for the Lexecon Governance API.

Replaces 24 module-level globals + initialize_services() with a single
ServiceRegistry singleton, exposed as FastAPI Depends callables.
"""

import os
import time
import uuid
from typing import TYPE_CHECKING, Optional

from fastapi import Depends, HTTPException, Request

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
from lexecon.security.auth_service import Permission, Role, Session
from lexecon.security.auth_service_async import AsyncAuthService
from lexecon.security.signature_service import SignatureService
from lexecon.storage.persistence import LedgerStorage
from lexecon.usage.service import UsageService
from lexecon.tenancy.service import TenancyService

if TYPE_CHECKING:
    from lexecon.compliance.eu_ai_act.article_14_oversight import HumanOversightEvidence
    from lexecon.compliance.eu_ai_act.storage import InterventionStorage


class ServiceRegistry:
    """Singleton that owns every service instance.

    Eager services are created in __init__ (same as the old module-level globals).
    Lazy services are created in initialize() (same as the old initialize_services()).
    """

    _instance: Optional["ServiceRegistry"] = None

    def __init__(self) -> None:
        # ── Resolve data directory (honours LEXECON_DATA_DIR in Docker/Railway) ──
        _data_dir = os.getenv("LEXECON_DATA_DIR", ".")
        os.makedirs(_data_dir, exist_ok=True)

        def _db(name: str) -> str:
            return os.path.join(_data_dir, name)

        # ── Eager services (created at import time in the old code) ──
        self.storage: LedgerStorage = LedgerStorage(_db("lexecon_ledger.db"))
        self.ledger: LedgerChain = LedgerChain(storage=self.storage)
        self.responsibility_storage: ResponsibilityStorage = ResponsibilityStorage(_db("lexecon_responsibility.db"))
        self.responsibility_tracker: ResponsibilityTracker = ResponsibilityTracker(storage=self.responsibility_storage)
        self.node_id: str = str(uuid.uuid4())
        self.startup_time: float = time.time()

        # Security services
        self.auth_service: AuthService = AuthService(_db("lexecon_auth.db"))
        self.async_auth_service: AsyncAuthService = AsyncAuthService(self.auth_service)
        self.audit_service: AuditService = AuditService(_db("lexecon_export_audit.db"))
        self.signature_service: SignatureService = SignatureService(_db("lexecon_keys"))

        # OIDC OAuth service
        from lexecon.security.oidc_service import OIDCService
        self.oidc_service = OIDCService(
            db_path=_db("lexecon_auth.db"),
            base_url=os.getenv("LEXECON_BASE_URL", "http://localhost:8000"),
        )
        self._register_oidc_providers()

        # ── Lazy services (None until initialize()) ──
        self.policy_engine: Optional[PolicyEngine] = None
        self.decision_service: Optional[DecisionService] = None
        self.key_manager: Optional[KeyManager] = None
        self.oversight_system: Optional["HumanOversightEvidence"] = None
        self.intervention_storage: Optional["InterventionStorage"] = None
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
            _data_dir = os.getenv("LEXECON_DATA_DIR", ".")
            self.intervention_storage = InterventionStorage(os.path.join(_data_dir, "lexecon_interventions.db"))

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
            _data_dir = os.getenv("LEXECON_DATA_DIR", ".")
            self.usage_service = UsageService(os.path.join(_data_dir, "lexecon_usage.db"))

        if self.tenancy_service is None:
            _data_dir = os.getenv("LEXECON_DATA_DIR", ".")
            self.tenancy_service = TenancyService(os.path.join(_data_dir, "lexecon_auth.db"))

        if self.compliance_mapping_service is None:
            self.compliance_mapping_service = ComplianceMappingService()

        if self.audit_export_service is None:
            self.audit_export_service = AuditExportService()

    # ── OIDC provider registration ──

    def _register_oidc_providers(self) -> None:
        # Google
        google_id = os.getenv("OIDC_GOOGLE_CLIENT_ID")
        google_secret = os.getenv("OIDC_GOOGLE_CLIENT_SECRET")
        if google_id and google_secret:
            self.oidc_service.register_provider(
                provider_name="google",
                discovery_url="https://accounts.google.com/.well-known/openid-configuration",
                client_id=google_id,
                client_secret=google_secret,
            )

        # Azure AD
        azure_id = os.getenv("OIDC_AZURE_CLIENT_ID")
        azure_secret = os.getenv("OIDC_AZURE_CLIENT_SECRET")
        if azure_id and azure_secret:
            tenant_id = os.getenv("OIDC_AZURE_TENANT_ID", "common")
            self.oidc_service.register_provider(
                provider_name="azure",
                discovery_url=f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
                client_id=azure_id,
                client_secret=azure_secret,
            )

        # Custom OIDC provider
        custom_discovery = os.getenv("OIDC_CUSTOM_DISCOVERY_URL")
        custom_id = os.getenv("OIDC_CUSTOM_CLIENT_ID")
        custom_secret = os.getenv("OIDC_CUSTOM_CLIENT_SECRET")
        if custom_discovery and custom_id and custom_secret:
            self.oidc_service.register_provider(
                provider_name="custom",
                discovery_url=custom_discovery,
                client_id=custom_id,
                client_secret=custom_secret,
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


async def require_session(
    services: ServiceRegistry = Depends(get_services),
    session_id: Optional[str] = Depends(get_session_id),
) -> Session:
    """Require an active server-issued session."""
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session, error = await services.async_auth_service.validate_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail=error or "Invalid session")
    return session


async def require_admin(session: Session = Depends(require_session)) -> Session:
    """Require administrative authority for global governance mutations."""
    if session.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator required")
    return session


async def require_audit_access(
    session: Session = Depends(require_session),
    services: ServiceRegistry = Depends(get_services),
) -> Session:
    """Require permission to read audit and evidence records."""
    if not services.auth_service.has_permission(session.role, Permission.VIEW_AUDIT_LOGS):
        raise HTTPException(status_code=403, detail="Audit permission required")
    return session


async def get_tenant_id(
    request: Request,
    session: Session = Depends(require_session),
    services: ServiceRegistry = Depends(get_services),
) -> str:
    """Use the only supported API tenant until every store is tenant scoped."""
    tenant_id = request.headers.get("X-Tenant-ID", "default")
    if tenant_id != "default":
        raise HTTPException(status_code=403, detail="Only the default tenant is supported by this API")
    if services.tenancy_service is None:
        raise HTTPException(status_code=503, detail="Tenant service unavailable")
    if not services.tenancy_service.is_user_in_tenant(session.user_id, tenant_id):
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return tenant_id
