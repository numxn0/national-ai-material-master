"""sap odata integration

Revision ID: 0007_sap_odata_integration
Revises: 0006_semantic_embeddings
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_sap_odata_integration"
down_revision: Union[str, None] = "0006_semantic_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_import_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("connector_type", sa.String(length=80), nullable=False),
        sa.Column("connector_mode", sa.String(length=40), nullable=False),
        sa.Column("connection_name", sa.String(length=160), nullable=False),
        sa.Column("source_cpse", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("ingestion_batch_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_type", "idempotency_key", name="uq_integration_import_runs_connector_idempotency"),
    )
    op.create_index("ix_integration_import_runs_connector_type", "integration_import_runs", ["connector_type"])
    op.create_index("ix_integration_import_runs_status", "integration_import_runs", ["status"])
    op.create_index("ix_integration_import_runs_ingestion_batch_id", "integration_import_runs", ["ingestion_batch_id"])
    op.create_index("ix_integration_import_runs_created_at", "integration_import_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_integration_import_runs_created_at", table_name="integration_import_runs")
    op.drop_index("ix_integration_import_runs_ingestion_batch_id", table_name="integration_import_runs")
    op.drop_index("ix_integration_import_runs_status", table_name="integration_import_runs")
    op.drop_index("ix_integration_import_runs_connector_type", table_name="integration_import_runs")
    op.drop_table("integration_import_runs")
