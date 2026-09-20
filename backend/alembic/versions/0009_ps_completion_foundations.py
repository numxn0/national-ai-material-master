"""ps completion foundations

Revision ID: 0009_ps_completion_foundations
Revises: 0008_basic_auth_rbac
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0009_ps_completion_foundations"
down_revision: Union[str, None] = "0008_basic_auth_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"namm-taxonomy-{seed}"))


def upgrade() -> None:
    op.add_column("national_materials", sa.Column("replacement_national_material_id", sa.String(length=36), nullable=True))
    op.add_column("national_materials", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_national_materials_replacement_id", "national_materials", ["replacement_national_material_id"])

    op.create_table(
        "taxonomy_nodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("sub_category", sa.String(length=120), nullable=False),
        sa.Column("material_type", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("allowed_units", sa.JSON(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "sub_category", "material_type", "version", name="uq_taxonomy_node_version"),
    )
    op.create_index("ix_taxonomy_nodes_category", "taxonomy_nodes", ["category"])
    op.create_index("ix_taxonomy_nodes_lifecycle_status", "taxonomy_nodes", ["lifecycle_status"])

    op.create_table(
        "taxonomy_attribute_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_node_id", sa.String(length=36), nullable=False),
        sa.Column("attribute_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("data_type", sa.String(length=40), nullable=False),
        sa.Column("allowed_units", sa.JSON(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("matching_critical", sa.Boolean(), nullable=False),
        sa.Column("validation_rules", sa.JSON(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["taxonomy_node_id"], ["taxonomy_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_node_id", "attribute_key", "version", name="uq_taxonomy_attr_node_key_version"),
    )
    op.create_index("ix_taxonomy_attr_node_id", "taxonomy_attribute_definitions", ["taxonomy_node_id"])
    op.create_index("ix_taxonomy_attr_key", "taxonomy_attribute_definitions", ["attribute_key"])
    op.create_index("ix_taxonomy_attr_lifecycle_status", "taxonomy_attribute_definitions", ["lifecycle_status"])

    op.create_table(
        "migration_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("validation_status", sa.String(length=60), nullable=False),
        sa.Column("ingestion_batch_id", sa.String(length=36), nullable=True),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("valid_records", sa.Integer(), nullable=False),
        sa.Column("rejected_records", sa.Integer(), nullable=False),
        sa.Column("duplicate_records", sa.Integer(), nullable=False),
        sa.Column("rollback_status", sa.String(length=60), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_cpse", "source_system", "file_hash_sha256", "dry_run", name="uq_migration_job_file_mode"),
    )
    op.create_index("ix_migration_jobs_source_cpse", "migration_jobs", ["source_cpse"])
    op.create_index("ix_migration_jobs_status", "migration_jobs", ["validation_status"])
    op.create_index("ix_migration_jobs_created_at", "migration_jobs", ["created_at"])

    op.create_table(
        "migration_job_errors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("migration_job_id", sa.String(length=36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_material_code", sa.String(length=160), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["migration_job_id"], ["migration_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_job_errors_job_id", "migration_job_errors", ["migration_job_id"])
    op.create_index("ix_migration_job_errors_source_code", "migration_job_errors", ["source_material_code"])
    op.create_index("ix_migration_job_errors_resolved", "migration_job_errors", ["resolved"])

    op.create_table(
        "procurement_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_material_id", sa.String(length=36), nullable=True),
        sa.Column("national_material_id", sa.String(length=36), nullable=True),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("source_material_code", sa.String(length=160), nullable=False),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("uom", sa.String(length=32), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("po_reference", sa.String(length=200), nullable=True),
        sa.Column("import_batch_id", sa.String(length=160), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=60), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_material_id"], ["source_materials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["national_material_id"], ["national_materials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_procurement_history_source_cpse", "procurement_history", ["source_cpse"])
    op.create_index("ix_procurement_history_source_code", "procurement_history", ["source_material_code"])
    op.create_index("ix_procurement_history_date", "procurement_history", ["purchase_date"])
    op.create_index("ix_procurement_history_national_material_id", "procurement_history", ["national_material_id"])
    op.create_index("ix_procurement_history_reconciliation", "procurement_history", ["reconciliation_status"])

    op.create_table(
        "ml_model_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("feature_set_version", sa.String(length=120), nullable=False),
        sa.Column("training_data_size", sa.Integer(), nullable=False),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=False),
        sa.Column("calibration_metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ml_model_runs_status", "ml_model_runs", ["status"])
    op.create_index("ix_ml_model_runs_model_version", "ml_model_runs", ["model_version"])
    op.create_index("ix_ml_model_runs_created_at", "ml_model_runs", ["created_at"])

    op.create_table(
        "sap_sync_configurations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connection_name", sa.String(length=160), nullable=False),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("entity_set", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("base_url_sanitized", sa.String(length=500), nullable=True),
        sa.Column("auth_mode", sa.String(length=40), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("last_successful_import_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delta_token", sa.String(length=500), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_name"),
    )
    op.create_index("ix_sap_sync_configurations_source_cpse", "sap_sync_configurations", ["source_cpse"])
    op.create_index("ix_sap_sync_configurations_status", "sap_sync_configurations", ["lifecycle_status"])

    op.create_table(
        "national_material_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("national_material_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=False),
        sa.Column("new_value", sa.JSON(), nullable=False),
        sa.Column("approval_case_id", sa.String(length=36), nullable=True),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["national_material_id"], ["national_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_case_id"], ["approval_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("national_material_id", "revision_number", name="uq_national_revision_number"),
    )
    op.create_index("ix_national_revisions_material_id", "national_material_revisions", ["national_material_id"])
    op.create_index("ix_national_revisions_created_at", "national_material_revisions", ["created_at"])

    op.create_table(
        "national_material_change_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("national_material_id", sa.String(length=36), nullable=False),
        sa.Column("change_type", sa.String(length=80), nullable=False),
        sa.Column("requested_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("approval_case_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("reviewed_by", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["national_material_id"], ["national_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_case_id"], ["approval_cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_national_change_requests_material_id", "national_material_change_requests", ["national_material_id"])
    op.create_index("ix_national_change_requests_status", "national_material_change_requests", ["status"])
    op.create_index("ix_national_change_requests_created_at", "national_material_change_requests", ["created_at"])

    now = datetime.now(timezone.utc)
    nodes = [
        ("BEARINGS", "GENERAL", "BEARING", "Bearings", ["EA", "SET"]),
        ("PIPES_AND_TUBES", "GENERAL", "PIPE", "Pipes and Tubes", ["M", "FT", "EA"]),
        ("VALVES", "GENERAL", "VALVE", "Valves", ["EA"]),
        ("ELECTRICAL_CABLES", "GENERAL", "CABLE", "Electrical Cables", ["M", "ROLL"]),
        ("MOTORS", "GENERAL", "MOTOR", "Motors", ["EA"]),
        ("FASTENERS", "GENERAL", "FASTENER", "Fasteners", ["EA", "KG", "SET"]),
    ]
    taxonomy_table = sa.table(
        "taxonomy_nodes",
        sa.column("id"), sa.column("category"), sa.column("sub_category"), sa.column("material_type"),
        sa.column("display_name"), sa.column("allowed_units", sa.JSON()), sa.column("lifecycle_status"), sa.column("version"),
        sa.column("metadata_json", sa.JSON()), sa.column("created_at"), sa.column("updated_at"),
    )
    op.bulk_insert(taxonomy_table, [
        {
            "id": _id(cat),
            "category": cat,
            "sub_category": sub,
            "material_type": mat_type,
            "display_name": label,
            "allowed_units": units,
            "lifecycle_status": "ACTIVE",
            "version": 1,
            "metadata_json": {"seeded": True},
            "created_at": now,
            "updated_at": now,
        }
        for cat, sub, mat_type, label, units in nodes
    ])
    attr_table = sa.table(
        "taxonomy_attribute_definitions",
        sa.column("id"), sa.column("taxonomy_node_id"), sa.column("attribute_key"), sa.column("display_name"),
        sa.column("data_type"), sa.column("allowed_units", sa.JSON()), sa.column("mandatory"), sa.column("matching_critical"),
        sa.column("validation_rules", sa.JSON()), sa.column("lifecycle_status"), sa.column("version"), sa.column("created_at"),
        sa.column("updated_at"),
    )
    attr_rows = []
    for cat, _, _, _, _ in nodes:
        for key, label, mandatory, critical in [
            ("material_type", "Material Type", True, True),
            ("material_grade", "Material Grade", False, True),
            ("size", "Size / Dimension", False, True),
        ]:
            attr_rows.append({
                "id": _id(f"{cat}-{key}"),
                "taxonomy_node_id": _id(cat),
                "attribute_key": key,
                "display_name": label,
                "data_type": "string",
                "allowed_units": [],
                "mandatory": mandatory,
                "matching_critical": critical,
                "validation_rules": {},
                "lifecycle_status": "ACTIVE",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            })
    op.bulk_insert(attr_table, attr_rows)


def downgrade() -> None:
    op.drop_index("ix_national_change_requests_created_at", table_name="national_material_change_requests")
    op.drop_index("ix_national_change_requests_status", table_name="national_material_change_requests")
    op.drop_index("ix_national_change_requests_material_id", table_name="national_material_change_requests")
    op.drop_table("national_material_change_requests")
    op.drop_index("ix_national_revisions_created_at", table_name="national_material_revisions")
    op.drop_index("ix_national_revisions_material_id", table_name="national_material_revisions")
    op.drop_table("national_material_revisions")
    op.drop_index("ix_sap_sync_configurations_status", table_name="sap_sync_configurations")
    op.drop_index("ix_sap_sync_configurations_source_cpse", table_name="sap_sync_configurations")
    op.drop_table("sap_sync_configurations")
    op.drop_index("ix_ml_model_runs_created_at", table_name="ml_model_runs")
    op.drop_index("ix_ml_model_runs_model_version", table_name="ml_model_runs")
    op.drop_index("ix_ml_model_runs_status", table_name="ml_model_runs")
    op.drop_table("ml_model_runs")
    op.drop_index("ix_procurement_history_reconciliation", table_name="procurement_history")
    op.drop_index("ix_procurement_history_national_material_id", table_name="procurement_history")
    op.drop_index("ix_procurement_history_date", table_name="procurement_history")
    op.drop_index("ix_procurement_history_source_code", table_name="procurement_history")
    op.drop_index("ix_procurement_history_source_cpse", table_name="procurement_history")
    op.drop_table("procurement_history")
    op.drop_index("ix_migration_job_errors_resolved", table_name="migration_job_errors")
    op.drop_index("ix_migration_job_errors_source_code", table_name="migration_job_errors")
    op.drop_index("ix_migration_job_errors_job_id", table_name="migration_job_errors")
    op.drop_table("migration_job_errors")
    op.drop_index("ix_migration_jobs_created_at", table_name="migration_jobs")
    op.drop_index("ix_migration_jobs_status", table_name="migration_jobs")
    op.drop_index("ix_migration_jobs_source_cpse", table_name="migration_jobs")
    op.drop_table("migration_jobs")
    op.drop_index("ix_taxonomy_attr_lifecycle_status", table_name="taxonomy_attribute_definitions")
    op.drop_index("ix_taxonomy_attr_key", table_name="taxonomy_attribute_definitions")
    op.drop_index("ix_taxonomy_attr_node_id", table_name="taxonomy_attribute_definitions")
    op.drop_table("taxonomy_attribute_definitions")
    op.drop_index("ix_taxonomy_nodes_lifecycle_status", table_name="taxonomy_nodes")
    op.drop_index("ix_taxonomy_nodes_category", table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")
    op.drop_index("ix_national_materials_replacement_id", table_name="national_materials")
    op.drop_column("national_materials", "version")
    op.drop_column("national_materials", "replacement_national_material_id")
