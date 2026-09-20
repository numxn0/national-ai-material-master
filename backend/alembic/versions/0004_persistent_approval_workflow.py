"""persistent approval workflow

Revision ID: 0004_persistent_approval_workflow
Revises: 0003_national_material_registry
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_persistent_approval_workflow"
down_revision: Union[str, None] = "0003_national_material_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_approval_cases_proposed_national_material_id",
        "approval_cases",
        ["proposed_national_material_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_approval_cases_proposed_national_material_id", table_name="approval_cases")
