"""durable audit ledger

Revision ID: 0005_durable_audit_ledger
Revises: 0004_persistent_approval_workflow
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_durable_audit_ledger"
down_revision: Union[str, None] = "0004_persistent_approval_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GENESIS_HASH = "0" * 64


def upgrade() -> None:
    op.create_table(
        "audit_chain_state",
        sa.Column("chain_key", sa.String(length=80), nullable=False),
        sa.Column("last_sequence_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hash", sa.String(length=64), nullable=False, server_default=GENESIS_HASH),
        sa.Column("last_event_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chain_key"),
    )
    op.add_column("audit_events", sa.Column("sequence_number", sa.Integer(), nullable=True))
    op.create_index("uq_audit_events_sequence_number", "audit_events", ["sequence_number"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_audit_events_sequence_number", table_name="audit_events")
    op.drop_column("audit_events", "sequence_number")
    op.drop_table("audit_chain_state")
