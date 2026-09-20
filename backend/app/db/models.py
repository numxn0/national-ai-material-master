import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base
from .types import GUID


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    batch_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(160), nullable=False, default="SYSTEM")
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    error_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    source_materials: Mapped[list["SourceMaterial"]] = relationship(
        back_populates="ingestion_batch",
        cascade="all, delete-orphan",
    )
    row_errors: Mapped[list["IngestionRowError"]] = relationship(
        back_populates="ingestion_batch",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("file_hash_sha256", "source_cpse", "source_system", name="uq_ingestion_batch_file_origin"),
        Index("ix_ingestion_batches_file_hash_sha256", "file_hash_sha256"),
        Index("ix_ingestion_batches_source_cpse", "source_cpse"),
        Index("ix_ingestion_batches_status", "status"),
        Index("ix_ingestion_batches_created_at", "created_at"),
    )


class SourceMaterial(Base):
    __tablename__ = "source_materials"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    ingestion_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ingestion_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    source_material_code: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    standard_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(120), nullable=False, default="UNASSIGNED")
    material_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    material_grade: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    uom: Mapped[str] = mapped_column(String(32), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_tokens: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    match_status: Mapped[str] = mapped_column(String(60), nullable=False, default="UNPROCESSED")
    approval_status: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING_INGESTION")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    ingestion_batch: Mapped[Optional[IngestionBatch]] = relationship(back_populates="source_materials")
    mappings: Mapped[list["MaterialMapping"]] = relationship(back_populates="source_material")
    candidate_as_a: Mapped[list["MatchCandidate"]] = relationship(
        back_populates="source_material_a",
        foreign_keys="MatchCandidate.source_material_a_id",
    )
    candidate_as_b: Mapped[list["MatchCandidate"]] = relationship(
        back_populates="source_material_b",
        foreign_keys="MatchCandidate.source_material_b_id",
    )

    __table_args__ = (
        UniqueConstraint("source_cpse", "source_system", "source_material_code", name="uq_source_material_origin_code"),
        Index("ix_source_materials_source_cpse", "source_cpse"),
        Index("ix_source_materials_source_material_code", "source_material_code"),
        Index("ix_source_materials_ingestion_batch_id", "ingestion_batch_id"),
        Index("ix_source_materials_category", "category"),
    )


class IngestionRowError(Base):
    __tablename__ = "ingestion_row_errors"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    ingestion_batch_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ingestion_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_material_code: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    ingestion_batch: Mapped[IngestionBatch] = relationship(back_populates="row_errors")

    __table_args__ = (
        Index("ix_ingestion_row_errors_batch_id", "ingestion_batch_id"),
        Index("ix_ingestion_row_errors_row_number", "row_number"),
        Index("ix_ingestion_row_errors_source_material_code", "source_material_code"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_scope: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_organization_scope", "organization_scope"),
        Index("ix_users_is_active", "is_active"),
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped[User] = relationship(back_populates="roles")

    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
        Index("ix_user_roles_user_id", "user_id"),
        Index("ix_user_roles_role", "role"),
    )


class IntegrationImportRun(Base):
    __tablename__ = "integration_import_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    connector_type: Mapped[str] = mapped_column(String(80), nullable=False)
    connector_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    connection_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    ingestion_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ingestion_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    ingestion_batch: Mapped[Optional[IngestionBatch]] = relationship()

    __table_args__ = (
        UniqueConstraint("connector_type", "idempotency_key", name="uq_integration_import_runs_connector_idempotency"),
        Index("ix_integration_import_runs_connector_type", "connector_type"),
        Index("ix_integration_import_runs_status", "status"),
        Index("ix_integration_import_runs_ingestion_batch_id", "ingestion_batch_id"),
        Index("ix_integration_import_runs_created_at", "created_at"),
    )


class NationalMaterial(Base):
    __tablename__ = "national_materials"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    originating_match_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("match_candidates.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    national_material_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    standard_description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(120), nullable=False, default="UNASSIGNED")
    material_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    material_grade: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    standard_uom: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    classification_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="DRAFT")
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="SYSTEM")
    approved_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    replacement_national_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("national_materials.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    mappings: Mapped[list["MaterialMapping"]] = relationship(back_populates="national_material")
    approval_cases: Mapped[list["ApprovalCase"]] = relationship(back_populates="proposed_national_material")
    originating_match_candidate: Mapped[Optional["MatchCandidate"]] = relationship(
        back_populates="draft_national_material",
        foreign_keys=[originating_match_candidate_id],
    )
    replacement_national_material: Mapped[Optional["NationalMaterial"]] = relationship(
        remote_side=[id],
        foreign_keys=[replacement_national_material_id],
    )

    __table_args__ = (
        Index("ix_national_materials_originating_match_candidate_id", "originating_match_candidate_id"),
        Index("ix_national_materials_national_material_code", "national_material_code"),
        Index("ix_national_materials_status", "status"),
        Index("ix_national_materials_category", "category"),
        Index("ix_national_materials_replacement_id", "replacement_national_material_id"),
    )


class MaterialMapping(Base):
    __tablename__ = "material_mappings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_material_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("source_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    national_material_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("national_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_method: Mapped[str] = mapped_column(String(80), nullable=False)
    match_explanation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approval_status: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING_L1")
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    source_material: Mapped[SourceMaterial] = relationship(back_populates="mappings")
    national_material: Mapped[NationalMaterial] = relationship(back_populates="mappings")

    __table_args__ = (
        UniqueConstraint("source_material_id", "national_material_id", name="uq_material_mapping_source_target"),
        Index("ix_material_mappings_source_material_id", "source_material_id"),
        Index("ix_material_mappings_national_material_id", "national_material_id"),
        Index("ix_material_mappings_approval_status", "approval_status"),
    )


class MaterialEmbedding(Base):
    __tablename__ = "material_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("source_materials.id", ondelete="CASCADE"),
        nullable=True,
    )
    national_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("national_materials.id", ondelete="CASCADE"),
        nullable=True,
    )
    provider_requested: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_used: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(160), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    source_material: Mapped[Optional[SourceMaterial]] = relationship()
    national_material: Mapped[Optional[NationalMaterial]] = relationship()

    __table_args__ = (
        CheckConstraint(
            "(source_material_id IS NOT NULL AND national_material_id IS NULL) OR "
            "(source_material_id IS NULL AND national_material_id IS NOT NULL)",
            name="ck_material_embeddings_exactly_one_material",
        ),
        Index("ix_material_embeddings_source_material_id", "source_material_id"),
        Index("ix_material_embeddings_national_material_id", "national_material_id"),
        Index("ix_material_embeddings_source_text_hash", "source_text_hash"),
        Index(
            "uq_material_embeddings_source_provider_model",
            "source_material_id",
            "provider_requested",
            "provider_used",
            "model_name",
            "model_version",
            "dimensions",
            unique=True,
            sqlite_where=text("source_material_id IS NOT NULL"),
            postgresql_where=text("source_material_id IS NOT NULL"),
        ),
        Index(
            "uq_material_embeddings_national_provider_model",
            "national_material_id",
            "provider_requested",
            "provider_used",
            "model_name",
            "model_version",
            "dimensions",
            unique=True,
            sqlite_where=text("national_material_id IS NOT NULL"),
            postgresql_where=text("national_material_id IS NOT NULL"),
        ),
    )


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    pair_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_material_a_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("source_materials.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_material_b_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("source_materials.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hybrid_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="UNREVIEWED")
    score_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    method_version: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    source_material_a: Mapped[Optional[SourceMaterial]] = relationship(
        back_populates="candidate_as_a",
        foreign_keys=[source_material_a_id],
    )
    source_material_b: Mapped[Optional[SourceMaterial]] = relationship(
        back_populates="candidate_as_b",
        foreign_keys=[source_material_b_id],
    )
    approval_cases: Mapped[list["ApprovalCase"]] = relationship(back_populates="match_candidate")
    draft_national_material: Mapped[Optional[NationalMaterial]] = relationship(
        back_populates="originating_match_candidate",
        foreign_keys="NationalMaterial.originating_match_candidate_id",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_match_candidates_pair_id", "pair_id"),
        Index("ix_match_candidates_source_material_a_id", "source_material_a_id"),
        Index("ix_match_candidates_source_material_b_id", "source_material_b_id"),
        Index("ix_match_candidates_status", "status"),
    )


class ApprovalCase(Base):
    __tablename__ = "approval_cases"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    approval_case_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    match_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("match_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_national_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("national_materials.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_national_material_code: Mapped[str] = mapped_column(String(160), nullable=False)
    proposed_standard_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hybrid_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hybrid_classification: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    required_approval_level: Mapped[str] = mapped_column(String(60), nullable=False, default="L1_AND_L2")
    current_stage: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING_L1")
    approval_status: Mapped[str] = mapped_column(String(80), nullable=False, default="PENDING")
    l1_reviewer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    l1_decision: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    l1_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    l1_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    l2_reviewer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    l2_decision: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    l2_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    l2_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    procurement_impact: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mapping_preview: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    match_candidate: Mapped[Optional[MatchCandidate]] = relationship(back_populates="approval_cases")
    proposed_national_material: Mapped[Optional[NationalMaterial]] = relationship(back_populates="approval_cases")

    __table_args__ = (
        Index("ix_approval_cases_approval_case_id", "approval_case_id"),
        Index("ix_approval_cases_approval_status", "approval_status"),
        Index("ix_approval_cases_current_stage", "current_stage"),
        Index("ix_approval_cases_proposed_national_material_code", "proposed_national_material_code"),
        Index("uq_approval_cases_proposed_national_material_id", "proposed_national_material_id", unique=True),
    )


class AuditChainState(Base):
    __tablename__ = "audit_chain_state"

    chain_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="0" * 64,
    )
    last_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    sequence_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    method_version: Mapped[str] = mapped_column(String(160), nullable=False, default="hybrid-rule-v1 + audit-hashchain-v1")
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(60), nullable=False, default="VERIFIED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_audit_events_audit_id", "audit_id"),
        Index("uq_audit_events_sequence_number", "sequence_number", unique=True),
        Index("ix_audit_events_timestamp", "timestamp"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_action", "action"),
    )


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(120), nullable=False, default="GENERAL")
    material_type: Mapped[str] = mapped_column(String(120), nullable=False, default="GENERAL")
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    allowed_units: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    attributes: Mapped[list["TaxonomyAttributeDefinition"]] = relationship(
        back_populates="taxonomy_node",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("category", "sub_category", "material_type", "version", name="uq_taxonomy_node_version"),
        Index("ix_taxonomy_nodes_category", "category"),
        Index("ix_taxonomy_nodes_lifecycle_status", "lifecycle_status"),
    )


class TaxonomyAttributeDefinition(Base):
    __tablename__ = "taxonomy_attribute_definitions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    taxonomy_node_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"), nullable=False)
    attribute_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(40), nullable=False, default="string")
    allowed_units: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mandatory: Mapped[bool] = mapped_column(nullable=False, default=False)
    matching_critical: Mapped[bool] = mapped_column(nullable=False, default=False)
    validation_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    taxonomy_node: Mapped[TaxonomyNode] = relationship(back_populates="attributes")

    __table_args__ = (
        UniqueConstraint("taxonomy_node_id", "attribute_key", "version", name="uq_taxonomy_attr_node_key_version"),
        Index("ix_taxonomy_attr_node_id", "taxonomy_node_id"),
        Index("ix_taxonomy_attr_key", "attribute_key"),
        Index("ix_taxonomy_attr_lifecycle_status", "lifecycle_status"),
    )


class MigrationJob(Base):
    __tablename__ = "migration_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dry_run: Mapped[bool] = mapped_column(nullable=False, default=True)
    validation_status: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING")
    ingestion_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("ingestion_batches.id", ondelete="SET NULL"), nullable=True)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rollback_status: Mapped[str] = mapped_column(String(60), nullable=False, default="NOT_REQUESTED")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    ingestion_batch: Mapped[Optional[IngestionBatch]] = relationship()
    errors: Mapped[list["MigrationJobError"]] = relationship(back_populates="migration_job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source_cpse", "source_system", "file_hash_sha256", "dry_run", name="uq_migration_job_file_mode"),
        Index("ix_migration_jobs_source_cpse", "source_cpse"),
        Index("ix_migration_jobs_status", "validation_status"),
        Index("ix_migration_jobs_created_at", "created_at"),
    )


class MigrationJobError(Base):
    __tablename__ = "migration_job_errors"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    migration_job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("migration_jobs.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_material_code: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    migration_job: Mapped[MigrationJob] = relationship(back_populates="errors")

    __table_args__ = (
        Index("ix_migration_job_errors_job_id", "migration_job_id"),
        Index("ix_migration_job_errors_source_code", "source_material_code"),
        Index("ix_migration_job_errors_resolved", "resolved"),
    )


class ProcurementHistory(Base):
    __tablename__ = "procurement_history"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("source_materials.id", ondelete="SET NULL"), nullable=True)
    national_material_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("national_materials.id", ondelete="SET NULL"), nullable=True)
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    source_material_code: Mapped[str] = mapped_column(String(160), nullable=False)
    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    uom: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vendor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    po_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    import_batch_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(60), nullable=False, default="UNMATCHED")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    source_material: Mapped[Optional[SourceMaterial]] = relationship()
    national_material: Mapped[Optional[NationalMaterial]] = relationship()

    __table_args__ = (
        Index("ix_procurement_history_source_cpse", "source_cpse"),
        Index("ix_procurement_history_source_code", "source_material_code"),
        Index("ix_procurement_history_date", "purchase_date"),
        Index("ix_procurement_history_national_material_id", "national_material_id"),
        Index("ix_procurement_history_reconciliation", "reconciliation_status"),
    )


class MLModelRun(Base):
    __tablename__ = "ml_model_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(120), nullable=False)
    training_data_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluation_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calibration_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING")
    artifact_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, default="SYSTEM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ml_model_runs_status", "status"),
        Index("ix_ml_model_runs_model_version", "model_version"),
        Index("ix_ml_model_runs_created_at", "created_at"),
    )


class SapSyncConfiguration(Base):
    __tablename__ = "sap_sync_configurations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    connection_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    source_cpse: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_set: Mapped[str] = mapped_column(String(160), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False, default="mock")
    base_url_sanitized: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    auth_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_successful_import_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_delta_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ACTIVE")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_sap_sync_configurations_source_cpse", "source_cpse"),
        Index("ix_sap_sync_configurations_status", "lifecycle_status"),
    )


class NationalMaterialRevision(Base):
    __tablename__ = "national_material_revisions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    national_material_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("national_materials.id", ondelete="CASCADE"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="RECORDED")
    previous_value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    new_value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approval_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("approval_cases.id", ondelete="SET NULL"), nullable=True)
    actor: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    national_material: Mapped[NationalMaterial] = relationship()
    approval_case: Mapped[Optional[ApprovalCase]] = relationship()

    __table_args__ = (
        UniqueConstraint("national_material_id", "revision_number", name="uq_national_revision_number"),
        Index("ix_national_revisions_material_id", "national_material_id"),
        Index("ix_national_revisions_created_at", "created_at"),
    )


class NationalMaterialChangeRequest(Base):
    __tablename__ = "national_material_change_requests"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    national_material_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("national_materials.id", ondelete="CASCADE"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="PENDING_APPROVAL")
    approval_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("approval_cases.id", ondelete="SET NULL"), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    national_material: Mapped[NationalMaterial] = relationship()
    approval_case: Mapped[Optional[ApprovalCase]] = relationship()

    __table_args__ = (
        Index("ix_national_change_requests_material_id", "national_material_id"),
        Index("ix_national_change_requests_status", "status"),
        Index("ix_national_change_requests_created_at", "created_at"),
    )
