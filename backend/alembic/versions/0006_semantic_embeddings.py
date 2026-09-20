"""semantic embeddings

Revision ID: 0006_semantic_embeddings
Revises: 0005_durable_audit_ledger
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_semantic_embeddings"
down_revision: Union[str, None] = "0005_durable_audit_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_embeddings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_material_id", sa.String(length=36), nullable=True),
        sa.Column("national_material_id", sa.String(length=36), nullable=True),
        sa.Column("provider_requested", sa.String(length=80), nullable=False),
        sa.Column("provider_used", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector_values", sa.JSON(), nullable=False),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(source_material_id IS NOT NULL AND national_material_id IS NULL) OR "
            "(source_material_id IS NULL AND national_material_id IS NOT NULL)",
            name="ck_material_embeddings_exactly_one_material",
        ),
        sa.ForeignKeyConstraint(["national_material_id"], ["national_materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_material_id"], ["source_materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_material_embeddings_source_material_id", "material_embeddings", ["source_material_id"])
    op.create_index("ix_material_embeddings_national_material_id", "material_embeddings", ["national_material_id"])
    op.create_index("ix_material_embeddings_source_text_hash", "material_embeddings", ["source_text_hash"])
    op.create_index(
        "uq_material_embeddings_source_provider_model",
        "material_embeddings",
        ["source_material_id", "provider_requested", "provider_used", "model_name", "model_version", "dimensions"],
        unique=True,
        sqlite_where=sa.text("source_material_id IS NOT NULL"),
        postgresql_where=sa.text("source_material_id IS NOT NULL"),
    )
    op.create_index(
        "uq_material_embeddings_national_provider_model",
        "material_embeddings",
        ["national_material_id", "provider_requested", "provider_used", "model_name", "model_version", "dimensions"],
        unique=True,
        sqlite_where=sa.text("national_material_id IS NOT NULL"),
        postgresql_where=sa.text("national_material_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_material_embeddings_national_provider_model", table_name="material_embeddings")
    op.drop_index("uq_material_embeddings_source_provider_model", table_name="material_embeddings")
    op.drop_index("ix_material_embeddings_source_text_hash", table_name="material_embeddings")
    op.drop_index("ix_material_embeddings_national_material_id", table_name="material_embeddings")
    op.drop_index("ix_material_embeddings_source_material_id", table_name="material_embeddings")
    op.drop_table("material_embeddings")
