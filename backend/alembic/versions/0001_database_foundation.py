"""database foundation

Revision ID: 0001_database_foundation
Revises: None
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_database_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_name", sa.String(length=160), nullable=False),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=True),
        sa.Column("uploaded_by", sa.String(length=160), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("processed_records", sa.Integer(), nullable=False),
        sa.Column("failed_records", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_batches_created_at", "ingestion_batches", ["created_at"])
    op.create_index("ix_ingestion_batches_source_cpse", "ingestion_batches", ["source_cpse"])
    op.create_index("ix_ingestion_batches_status", "ingestion_batches", ["status"])

    op.create_table(
        "national_materials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("national_material_code", sa.String(length=160), nullable=False),
        sa.Column("standard_description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("sub_category", sa.String(length=120), nullable=False),
        sa.Column("material_type", sa.String(length=120), nullable=True),
        sa.Column("material_grade", sa.String(length=120), nullable=True),
        sa.Column("standard_uom", sa.String(length=32), nullable=False),
        sa.Column("canonical_attributes", sa.JSON(), nullable=False),
        sa.Column("classification_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("approved_by", sa.String(length=160), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("national_material_code"),
    )
    op.create_index("ix_national_materials_category", "national_materials", ["category"])
    op.create_index("ix_national_materials_national_material_code", "national_materials", ["national_material_code"])
    op.create_index("ix_national_materials_status", "national_materials", ["status"])

    op.create_table(
        "source_materials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ingestion_batch_id", sa.String(length=36), nullable=True),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("source_material_code", sa.String(length=160), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=False),
        sa.Column("cleaned_description", sa.Text(), nullable=True),
        sa.Column("standard_description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("sub_category", sa.String(length=120), nullable=False),
        sa.Column("material_type", sa.String(length=120), nullable=True),
        sa.Column("material_grade", sa.String(length=120), nullable=True),
        sa.Column("manufacturer", sa.String(length=160), nullable=True),
        sa.Column("part_number", sa.String(length=160), nullable=True),
        sa.Column("model_number", sa.String(length=160), nullable=True),
        sa.Column("uom", sa.String(length=32), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("normalized_tokens", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("match_status", sa.String(length=60), nullable=False),
        sa.Column("approval_status", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_cpse", "source_system", "source_material_code", name="uq_source_material_origin_code"),
    )
    op.create_index("ix_source_materials_category", "source_materials", ["category"])
    op.create_index("ix_source_materials_ingestion_batch_id", "source_materials", ["ingestion_batch_id"])
    op.create_index("ix_source_materials_source_cpse", "source_materials", ["source_cpse"])
    op.create_index("ix_source_materials_source_material_code", "source_materials", ["source_material_code"])

    op.create_table(
        "match_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pair_id", sa.String(length=255), nullable=False),
        sa.Column("source_material_a_id", sa.String(length=36), nullable=True),
        sa.Column("source_material_b_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_score", sa.Float(), nullable=False),
        sa.Column("hybrid_score", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("score_details", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("method_version", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_material_a_id"], ["source_materials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_material_b_id"], ["source_materials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pair_id"),
    )
    op.create_index("ix_match_candidates_pair_id", "match_candidates", ["pair_id"])
    op.create_index("ix_match_candidates_source_material_a_id", "match_candidates", ["source_material_a_id"])
    op.create_index("ix_match_candidates_source_material_b_id", "match_candidates", ["source_material_b_id"])
    op.create_index("ix_match_candidates_status", "match_candidates", ["status"])

    op.create_table(
        "material_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_material_id", sa.String(length=36), nullable=False),
        sa.Column("national_material_id", sa.String(length=36), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("match_method", sa.String(length=80), nullable=False),
        sa.Column("match_explanation", sa.JSON(), nullable=False),
        sa.Column("approval_status", sa.String(length=60), nullable=False),
        sa.Column("reviewer_id", sa.String(length=160), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["national_material_id"], ["national_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_material_id"], ["source_materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_material_id", "national_material_id", name="uq_material_mapping_source_target"),
    )
    op.create_index("ix_material_mappings_approval_status", "material_mappings", ["approval_status"])
    op.create_index("ix_material_mappings_national_material_id", "material_mappings", ["national_material_id"])
    op.create_index("ix_material_mappings_source_material_id", "material_mappings", ["source_material_id"])

    op.create_table(
        "approval_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("approval_case_id", sa.String(length=255), nullable=False),
        sa.Column("match_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("proposed_national_material_id", sa.String(length=36), nullable=True),
        sa.Column("proposed_national_material_code", sa.String(length=160), nullable=False),
        sa.Column("proposed_standard_description", sa.Text(), nullable=True),
        sa.Column("hybrid_score", sa.Float(), nullable=True),
        sa.Column("hybrid_classification", sa.String(length=80), nullable=True),
        sa.Column("required_approval_level", sa.String(length=60), nullable=False),
        sa.Column("current_stage", sa.String(length=60), nullable=False),
        sa.Column("approval_status", sa.String(length=80), nullable=False),
        sa.Column("l1_reviewer", sa.String(length=160), nullable=True),
        sa.Column("l1_decision", sa.String(length=60), nullable=True),
        sa.Column("l1_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("l1_notes", sa.Text(), nullable=True),
        sa.Column("l2_reviewer", sa.String(length=160), nullable=True),
        sa.Column("l2_decision", sa.String(length=60), nullable=True),
        sa.Column("l2_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("l2_notes", sa.Text(), nullable=True),
        sa.Column("procurement_impact", sa.JSON(), nullable=False),
        sa.Column("mapping_preview", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["match_candidate_id"], ["match_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposed_national_material_id"], ["national_materials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_case_id"),
    )
    op.create_index("ix_approval_cases_approval_case_id", "approval_cases", ["approval_case_id"])
    op.create_index("ix_approval_cases_approval_status", "approval_cases", ["approval_status"])
    op.create_index("ix_approval_cases_current_stage", "approval_cases", ["current_stage"])
    op.create_index("ix_approval_cases_proposed_national_material_code", "approval_cases", ["proposed_national_material_code"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("audit_id", sa.String(length=160), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("actor_role", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("method_version", sa.String(length=160), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("hash_signature", sa.String(length=64), nullable=False),
        sa.Column("verification_status", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_audit_id", "audit_events", ["audit_id"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_audit_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_approval_cases_proposed_national_material_code", table_name="approval_cases")
    op.drop_index("ix_approval_cases_current_stage", table_name="approval_cases")
    op.drop_index("ix_approval_cases_approval_status", table_name="approval_cases")
    op.drop_index("ix_approval_cases_approval_case_id", table_name="approval_cases")
    op.drop_table("approval_cases")

    op.drop_index("ix_material_mappings_source_material_id", table_name="material_mappings")
    op.drop_index("ix_material_mappings_national_material_id", table_name="material_mappings")
    op.drop_index("ix_material_mappings_approval_status", table_name="material_mappings")
    op.drop_table("material_mappings")

    op.drop_index("ix_match_candidates_status", table_name="match_candidates")
    op.drop_index("ix_match_candidates_source_material_b_id", table_name="match_candidates")
    op.drop_index("ix_match_candidates_source_material_a_id", table_name="match_candidates")
    op.drop_index("ix_match_candidates_pair_id", table_name="match_candidates")
    op.drop_table("match_candidates")

    op.drop_index("ix_source_materials_source_material_code", table_name="source_materials")
    op.drop_index("ix_source_materials_source_cpse", table_name="source_materials")
    op.drop_index("ix_source_materials_ingestion_batch_id", table_name="source_materials")
    op.drop_index("ix_source_materials_category", table_name="source_materials")
    op.drop_table("source_materials")

    op.drop_index("ix_national_materials_status", table_name="national_materials")
    op.drop_index("ix_national_materials_national_material_code", table_name="national_materials")
    op.drop_index("ix_national_materials_category", table_name="national_materials")
    op.drop_table("national_materials")

    op.drop_index("ix_ingestion_batches_status", table_name="ingestion_batches")
    op.drop_index("ix_ingestion_batches_source_cpse", table_name="ingestion_batches")
    op.drop_index("ix_ingestion_batches_created_at", table_name="ingestion_batches")
    op.drop_table("ingestion_batches")
