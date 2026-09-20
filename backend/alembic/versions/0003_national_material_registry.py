"""national material registry

Revision ID: 0003_national_material_registry
Revises: 0002_durable_ingestion
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_national_material_registry"
down_revision: Union[str, None] = "0002_durable_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "national_materials",
        sa.Column("originating_match_candidate_id", sa.String(length=36), nullable=True),
    )
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_national_materials_originating_match_candidate_id",
            "national_materials",
            "match_candidates",
            ["originating_match_candidate_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_national_materials_originating_match_candidate_id",
        "national_materials",
        ["originating_match_candidate_id"],
    )
    op.create_index(
        "uq_national_materials_originating_match_candidate_id",
        "national_materials",
        ["originating_match_candidate_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("uq_national_materials_originating_match_candidate_id", table_name="national_materials")
    op.drop_index("ix_national_materials_originating_match_candidate_id", table_name="national_materials")
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_national_materials_originating_match_candidate_id",
            "national_materials",
            type_="foreignkey",
        )
    op.drop_column("national_materials", "originating_match_candidate_id")
