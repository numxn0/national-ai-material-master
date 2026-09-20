from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class AuditAction(str, Enum):
    MAPPING_AUTO_APPROVED = "MAPPING_AUTO_APPROVED"
    MAPPING_REVIEWED = "MAPPING_REVIEWED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    NATIONAL_CODE_GENERATED = "NATIONAL_CODE_GENERATED"
    BATCH_INGESTION_STARTED = "BATCH_INGESTION_STARTED"
    BATCH_INGESTION_COMPLETED = "BATCH_INGESTION_COMPLETED"
    TAXONOMY_SCHEMA_UPDATED = "TAXONOMY_SCHEMA_UPDATED"
    RECORD_FLAGGED = "RECORD_FLAGGED"


class AuditLogBase(BaseModel):
    actor_id: str = Field(..., description="User ID, email, or system process identifier (e.g., officer.sharma@railways.gov.in)")
    actor_role: str = Field(..., description="Role of the actor: NODAL_OFFICER, MINISTRY_ADMIN, SYSTEM_AI_ENGINE")
    action: AuditAction = Field(..., description="Operation performed")
    entity_type: str = Field(..., description="Target entity domain (e.g., source_material, national_material, material_mapping)")
    entity_id: str = Field(..., description="ID or key of the affected record")
    old_value: Optional[Dict[str, Any]] = Field(None, description="State of data before operation")
    new_value: Optional[Dict[str, Any]] = Field(None, description="State of data after operation")
    reason: Optional[str] = Field(None, description="Justification or business rationale provided by the actor")
    ip_address: Optional[str] = Field(None, description="IP address or host from which the action originated")


class AuditLogCreate(AuditLogBase):
    hash_signature: Optional[str] = Field(None, description="Cryptographic SHA-256 tamper-evident checksum")


class AuditLogResponse(AuditLogBase):
    id: UUID = Field(..., description="Globally unique identifier for the audit log record")
    hash_signature: str = Field(..., description="Cryptographic SHA-256 tamper-evident checksum chained to previous log entry")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Immutable timestamp of event recording")

    model_config = ConfigDict(from_attributes=True)


class AuditTrailEvent(BaseModel):
    """
    Cryptographically chained audit trail event model adhering to Prompt 11 requirements.
    """
    audit_id: str = Field(..., description="Unique event identifier (e.g., AUD-2026-001)")
    timestamp: str = Field(..., description="ISO UTC timestamp of the audit event")
    actor: str = Field(..., description="Actor identity (officer name, email, or AI engine)")
    actor_role: str = Field(..., description="Role: NODAL_OFFICER, MINISTRY_AUTHORITY, or SYSTEM_AI_ENGINE")
    action: str = Field(..., description="Audit action verb (e.g., L1_APPROVED, CODE_PROPOSED, MERGE_RATIFIED)")
    entity_type: str = Field(..., description="Domain entity: source_material, national_material, or approval_case")
    entity_id: str = Field(..., description="Target record key or pair ID")
    old_value: Optional[Dict[str, Any]] = Field(default=None, description="Pre-action state")
    new_value: Optional[Dict[str, Any]] = Field(default=None, description="Post-action state")
    reason: Optional[str] = Field(default=None, description="Reviewer rationale or algorithm explanation")
    method_version: str = Field(default="hybrid-rule-v1 + audit-hashchain-v1", description="Engine version string")
    previous_hash: str = Field(..., description="SHA-256 hash of the immediately preceding event")
    hash_signature: str = Field(..., description="SHA-256 cryptographic signature sealing this event into the chain")
    verification_status: str = Field(default="VERIFIED", description="'VERIFIED', 'CORRUPTED', or 'GENESIS'")

    model_config = ConfigDict(from_attributes=True)


class AuditTrailResponse(BaseModel):
    total_events: int = Field(..., description="Total audit events in chain")
    chain_verified: bool = Field(..., description="True if cryptographic SHA-256 links verify from genesis to tip")
    genesis_hash: str = Field(..., description="SHA-256 hash of genesis event")
    latest_hash: str = Field(..., description="SHA-256 hash of the most recent event")
    events: List[AuditTrailEvent] = Field(default_factory=list, description="Ordered cryptographic audit trail")
    tamper_evident: bool = Field(default=True)
    note: str = Field(
        default="Demo-only audit trail: cryptographically hashed in memory without database persistence.",
        description="Non-persistence disclosure"
    )

    model_config = ConfigDict(from_attributes=True)


class AuditChainVerificationResponse(BaseModel):
    chain_status: str = Field(..., description="'CHAIN_INTACT' or 'CHAIN_BROKEN'")
    verified_event_count: int = Field(..., description="Number of sequentially verified events")
    genesis_hash: str = Field(..., description="Starting genesis block hash")
    latest_hash: str = Field(..., description="Ending block hash")
    is_valid: bool = Field(..., description="True if no hash mismatches detected")
    verification_timestamp: str = Field(..., description="ISO UTC timestamp of verification run")
    message: str = Field(..., description="Human-readable verification summary")

    model_config = ConfigDict(from_attributes=True)


class PersistentAuditEventResponse(BaseModel):
    id: UUID
    audit_id: str
    sequence_number: int
    timestamp: datetime
    actor: str
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    method_version: str
    previous_hash: str
    hash_signature: str
    verification_status: str
    created_at: datetime


class PersistentAuditEventsResponse(BaseModel):
    status: str = "success"
    count: int
    total: int
    page: int
    limit: int
    items: List[PersistentAuditEventResponse] = Field(default_factory=list)


class PersistentAuditVerificationResponse(BaseModel):
    status: str
    total_events: int
    verified_events: int
    chain_tip_hash: str
    first_broken_sequence: Optional[int] = None
    first_broken_event_id: Optional[str] = None
    reason: str
    verification_timestamp: datetime

