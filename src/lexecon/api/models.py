"""Pydantic request/response models for the Lexecon Governance API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from lexecon.api.validation import (
    validate_context,
    validate_data_classes,
    validate_export_email,
    validate_export_formats,
    validate_justification,
    validate_iso_timestamp,
    validate_output_type,
    validate_override_scope,
    validate_policy_mode,
    validate_reason,
    validate_recommendation_dict,
    validate_risk_level,
    validate_string_field,
    validate_time_window,
    ValidationConfig,
)


# ========== Decision Models ==========

class DecisionRequestModel(BaseModel):
    """Model for decision request with comprehensive input validation."""

    request_id: Optional[str] = None
    actor: str = Field(..., description="Actor requesting the action")
    proposed_action: str = Field(..., description="Proposed action to perform")
    tool: str = Field(..., description="Tool to be used")
    user_intent: str = Field(..., description="User's intent for this action")
    data_classes: List[str] = Field(default_factory=list)
    risk_level: int = Field(default=1, ge=1, le=5)
    requested_output_type: str = Field(default="tool_action")
    policy_mode: str = Field(default="strict")
    context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("actor")
    @classmethod
    def validate_actor(cls, v: str) -> str:
        return validate_string_field(
            v, "actor", ValidationConfig.MAX_ACTOR_LENGTH, ValidationConfig.ACTOR_PATTERN,
        )

    @field_validator("proposed_action")
    @classmethod
    def validate_proposed_action(cls, v: str) -> str:
        return validate_string_field(
            v, "proposed_action", ValidationConfig.MAX_ACTION_LENGTH, ValidationConfig.ACTION_PATTERN,
        )

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, v: str) -> str:
        return validate_string_field(
            v, "tool", ValidationConfig.MAX_TOOL_LENGTH, ValidationConfig.TOOL_PATTERN,
        )

    @field_validator("user_intent")
    @classmethod
    def validate_user_intent(cls, v: str) -> str:
        return validate_string_field(v, "user_intent", ValidationConfig.MAX_INTENT_LENGTH)

    @field_validator("data_classes")
    @classmethod
    def validate_data_classes_field(cls, v: List[str]) -> List[str]:
        return validate_data_classes(v)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level_field(cls, v: int) -> int:
        return validate_risk_level(v)

    @field_validator("requested_output_type")
    @classmethod
    def validate_output_type_field(cls, v: str) -> str:
        return validate_output_type(v)

    @field_validator("policy_mode")
    @classmethod
    def validate_policy_mode_field(cls, v: str) -> str:
        return validate_policy_mode(v)

    @field_validator("context", mode="before")
    @classmethod
    def validate_context_field(cls, v: Any) -> Dict[str, Any]:
        if v is None:
            return {}
        return validate_context(v)


# ========== Policy Models ==========

class PolicyLoadModel(BaseModel):
    """Model for loading policy - supports both wrapped and direct formats."""
    policy: Optional[Dict[str, Any]] = Field(default=None, description="Policy data (wrapped format)")
    name: Optional[str] = Field(default=None, description="Policy name")
    version: Optional[str] = Field(default="1.0", description="Policy version")
    mode: Optional[str] = Field(default=None, description="Policy mode")
    terms: Optional[List[Dict[str, Any]]] = Field(default=None, description="Policy terms")
    relations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Policy relations")
    constraints: Optional[List[Dict[str, Any]]] = Field(default=None, description="Policy constraints")


# ========== Intervention Models ==========

class InterventionModel(BaseModel):
    """Model for human intervention request with comprehensive validation."""
    intervention_type: str = Field(..., description="Type of intervention")
    ai_recommendation: Dict[str, Any] = Field(..., description="AI's recommendation (must include 'confidence' key)")
    human_decision: Dict[str, Any] = Field(..., description="Human's decision")
    human_role: str = Field(..., description="Human's role")
    reason: str = Field(..., description="Reason for intervention")
    request_context: Optional[Dict[str, Any]] = Field(default=None, description="Additional request context")
    response_time_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")

    @field_validator("intervention_type")
    @classmethod
    def validate_intervention_type(cls, v: str) -> str:
        return validate_string_field(v, "intervention_type", ValidationConfig.MAX_TOOL_LENGTH)

    @field_validator("ai_recommendation", mode="before")
    @classmethod
    def validate_ai_recommendation(cls, v: Any) -> Dict[str, Any]:
        return validate_recommendation_dict(v, "ai_recommendation")

    @field_validator("human_decision", mode="before")
    @classmethod
    def validate_human_decision(cls, v: Any) -> Dict[str, Any]:
        return validate_recommendation_dict(v, "human_decision")

    @field_validator("human_role")
    @classmethod
    def validate_human_role(cls, v: str) -> str:
        return validate_string_field(v, "human_role", ValidationConfig.MAX_ACTOR_LENGTH)

    @field_validator("reason")
    @classmethod
    def validate_reason_field(cls, v: str) -> str:
        return validate_reason(v)

    @field_validator("request_context", mode="before")
    @classmethod
    def validate_request_context(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        return validate_context(v)


# ========== Health/Status Models ==========

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    node_id: str
    timestamp: str


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    node_id: str
    policy_loaded: bool
    policies_loaded: bool
    policy_hash: Optional[str]
    ledger_entries: int
    uptime_seconds: float
    timestamp: str


# ========== Security/Auth Models ==========

class LoginRequest(BaseModel):
    """Login request."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    success: bool
    session_id: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CreateUserRequest(BaseModel):
    """Create user request."""
    username: str
    email: str
    password: str
    role: str
    full_name: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    old_password: str
    new_password: str


class PasswordPolicyResponse(BaseModel):
    """Password policy configuration response."""
    min_length: int
    max_age_days: Optional[int]
    history_count: int
    require_uppercase: bool
    require_lowercase: bool
    require_digits: bool
    require_special: bool
    special_chars: str


class PasswordStatusResponse(BaseModel):
    """Password status response."""
    password_changed_at: Optional[str]
    password_expires_at: Optional[str]
    days_until_expiration: Optional[int]
    is_expired: bool
    force_password_change: bool
    password_age_days: Optional[int]
    policy: PasswordPolicyResponse


class OIDCProviderInfo(BaseModel):
    """OIDC provider information."""
    name: str
    display_name: str


class OIDCLinkedProvider(BaseModel):
    """Linked OIDC provider."""
    provider_name: str
    provider_email: Optional[str]
    linked_at: str
    last_login: Optional[str]


class OIDCUnlinkRequest(BaseModel):
    """Request to unlink OIDC provider."""
    provider_name: str


# ========== Export Models ==========

class ExportRequestModel(BaseModel):
    """Audit packet export request with comprehensive validation."""
    requester_name: str
    requester_email: str
    purpose: str
    case_id: Optional[str] = None
    notes: Optional[str] = None
    time_window: str = "all"
    formats: List[str] = ["json"]
    include_decisions: bool = True
    include_interventions: bool = True
    include_ledger: bool = True
    include_responsibility: bool = True
    attestation_accepted: bool
    attestation_text: str

    @field_validator("requester_name")
    @classmethod
    def validate_requester_name(cls, v: str) -> str:
        return validate_string_field(v, "requester_name", ValidationConfig.MAX_ACTOR_LENGTH)

    @field_validator("requester_email")
    @classmethod
    def validate_requester_email(cls, v: str) -> str:
        return validate_export_email(v)

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        return validate_string_field(v, "purpose", ValidationConfig.MAX_REASON_LENGTH)

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_string_field(v, "case_id", ValidationConfig.MAX_ACTION_LENGTH)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_string_field(v, "notes", ValidationConfig.MAX_REASON_LENGTH)

    @field_validator("time_window")
    @classmethod
    def validate_time_window_field(cls, v: str) -> str:
        return validate_time_window(v)

    @field_validator("formats")
    @classmethod
    def validate_formats_field(cls, v: List[str]) -> List[str]:
        return validate_export_formats(v)

    @field_validator("attestation_text")
    @classmethod
    def validate_attestation_text(cls, v: str) -> str:
        return validate_string_field(v, "attestation_text", ValidationConfig.MAX_REASON_LENGTH)


# ========== Governance API Models (Phase 5) ==========

class RiskDimensionsModel(BaseModel):
    """Risk dimensions for assessment."""
    security: Optional[int] = Field(None, ge=0, le=100, description="Security risk score")
    privacy: Optional[int] = Field(None, ge=0, le=100, description="Privacy risk score")
    compliance: Optional[int] = Field(None, ge=0, le=100, description="Compliance risk score")
    operational: Optional[int] = Field(None, ge=0, le=100, description="Operational risk score")
    reputational: Optional[int] = Field(None, ge=0, le=100, description="Reputational risk score")
    financial: Optional[int] = Field(None, ge=0, le=100, description="Financial risk score")


class RiskAssessmentRequest(BaseModel):
    """Request to assess risk for a decision."""
    decision_id: str = Field(..., description="Decision ID to assess")
    dimensions: RiskDimensionsModel = Field(..., description="Risk dimensions")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")


class EscalationCreateRequest(BaseModel):
    """Request to create an escalation."""
    decision_id: str = Field(..., description="Decision ID being escalated")
    trigger: str = Field(..., description="What triggered the escalation")
    escalated_to: List[str] = Field(..., description="List of actor IDs to escalate to")
    priority: Optional[str] = Field(default=None, description="Escalation priority")
    context_summary: Optional[str] = Field(default=None, description="Summary for reviewers")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class EscalationResolveRequest(BaseModel):
    """Request to resolve an escalation."""
    resolved_by: str = Field(..., description="Actor ID resolving escalation")
    outcome: str = Field(..., description="Resolution outcome")
    notes: str = Field(..., description="Resolution notes")


class OverrideCreateRequest(BaseModel):
    """Request to create an override with comprehensive validation."""
    decision_id: str = Field(..., description="Decision ID to override")
    override_type: str = Field(..., description="Type of override")
    authorized_by: str = Field(..., description="Actor ID authorizing override")
    justification: str = Field(..., min_length=20, description="Justification (min 20 chars)")
    original_outcome: Optional[str] = Field(default=None, description="Original decision outcome")
    new_outcome: Optional[str] = Field(default=None, description="New outcome after override")
    expires_at: Optional[str] = Field(default=None, description="Expiration timestamp (ISO 8601)")
    scope: Optional[Dict[str, Any]] = Field(default=None, description="Override scope limitations")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    @field_validator("decision_id")
    @classmethod
    def validate_decision_id(cls, v: str) -> str:
        return validate_string_field(v, "decision_id", ValidationConfig.MAX_ACTOR_LENGTH)

    @field_validator("override_type")
    @classmethod
    def validate_override_type(cls, v: str) -> str:
        return validate_string_field(v, "override_type", ValidationConfig.MAX_TOOL_LENGTH)

    @field_validator("authorized_by")
    @classmethod
    def validate_authorized_by(cls, v: str) -> str:
        return validate_string_field(
            v, "authorized_by", ValidationConfig.MAX_ACTOR_LENGTH, ValidationConfig.ACTOR_PATTERN,
        )

    @field_validator("justification")
    @classmethod
    def validate_justification_field(cls, v: str) -> str:
        return validate_justification(v)

    @field_validator("original_outcome")
    @classmethod
    def validate_original_outcome(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_string_field(v, "original_outcome", ValidationConfig.MAX_ACTION_LENGTH)

    @field_validator("new_outcome")
    @classmethod
    def validate_new_outcome(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_string_field(v, "new_outcome", ValidationConfig.MAX_ACTION_LENGTH)

    @field_validator("expires_at", mode="before")
    @classmethod
    def validate_expires_at(cls, v: Optional[str]) -> Optional[str]:
        return validate_iso_timestamp(v, "expires_at")

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        return validate_override_scope(v)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        return validate_context(v)


# ========== Evidence Service Models ==========

class EvidenceStoreRequest(BaseModel):
    """Request to store an evidence artifact."""
    artifact_type: str = Field(..., description="Type of artifact")
    content: str = Field(..., description="Artifact content")
    source: str = Field(..., description="System/process that created artifact")
    related_decision_ids: Optional[List[str]] = Field(default=None, description="Related decision IDs")
    related_control_ids: Optional[List[str]] = Field(default=None, description="Related control IDs")
    content_type: Optional[str] = Field(default=None, description="MIME type")
    storage_uri: Optional[str] = Field(default=None, description="External storage location")
    retention_days: Optional[int] = Field(default=None, description="Custom retention period")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class EvidenceVerifyRequest(BaseModel):
    """Request to verify artifact integrity."""
    content: str = Field(..., description="Content to verify against stored hash")


class EvidenceSignRequest(BaseModel):
    """Request to sign an artifact."""
    signer_id: str = Field(..., description="Actor ID of signer")
    signature: str = Field(..., description="Signature value (base64 encoded)")
    algorithm: str = Field(default="RSA-SHA256", description="Signature algorithm")


# ========== Compliance Mapping API Models (Phase 7) ==========

class ComplianceMappingRequest(BaseModel):
    """Request to map a primitive to compliance controls."""
    primitive_type: str = Field(..., description="Type of governance primitive")
    primitive_id: str = Field(..., description="ID of primitive instance")
    framework: str = Field(..., description="Regulatory framework")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class ComplianceLinkEvidenceRequest(BaseModel):
    """Request to link evidence to a control."""
    evidence_artifact_id: str = Field(..., description="Evidence artifact ID")


class ComplianceVerifyControlRequest(BaseModel):
    """Request to verify a control."""
    notes: Optional[str] = Field(default=None, description="Verification notes")


# ========== Audit Export API Models (Phase 8) ==========

class AuditExportCreateRequest(BaseModel):
    """Request to create an audit export."""
    requester: str = Field(..., min_length=1, description="User or system requesting export")
    purpose: str = Field(..., min_length=10, description="Purpose of the export (min 10 chars)")
    scope: str = Field(default="all", description="Scope of data")
    format: str = Field(default="json", description="Output format: json, csv, markdown, html")
    start_date: Optional[str] = Field(default=None, description="Start date filter (ISO 8601)")
    end_date: Optional[str] = Field(default=None, description="End date filter (ISO 8601)")
    include_deleted: bool = Field(default=False, description="Include deleted records")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# ========== Evidence Export Models (PR-03) ==========

class EvidenceExportRequest(BaseModel):
    """Request body for evidence export."""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)
    include_verification: bool = True
    include_policies: bool = True
