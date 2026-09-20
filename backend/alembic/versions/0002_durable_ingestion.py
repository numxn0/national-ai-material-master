"""durable ingestion

Revision ID: 0002_durable_ingestion
Revises: 0001_database_foundation
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_durable_ingestion"
down_revision: Union[str, None] = "0001_database_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_ingestion_batches_file_hash_sha256", "ingestion_batches", ["file_hash_sha256"])
    op.create_index(
        "uq_ingestion_batch_file_origin",
        "ingestion_batches",
        ["file_hash_sha256", "source_cpse", "source_system"],
        unique=True,
    )

    op.create_table(
        "ingestion_row_errors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ingestion_batch_id", sa.String(length=36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_material_code", sa.String(length=160), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_row_errors_batch_id", "ingestion_row_errors", ["ingestion_batch_id"])
    op.create_index("ix_ingestion_row_errors_row_number", "ingestion_row_errors", ["row_number"])
    op.create_index("ix_ingestion_row_errors_source_material_code", "ingestion_row_errors", ["source_material_code"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_row_errors_source_material_code", table_name="ingestion_row_errors")
    op.drop_index("ix_ingestion_row_errors_row_number", table_name="ingestion_row_errors")
    op.drop_index("ix_ingestion_row_errors_batch_id", table_name="ingestion_row_errors")
    op.drop_table("ingestion_row_errors")
    op.drop_index("uq_ingestion_batch_file_origin", table_name="ingestion_batches")
    op.drop_index("ix_ingestion_batches_file_hash_sha256", table_name="ingestion_batches")
