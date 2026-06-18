"""Add optimizer trial diagnostics.

Revision ID: 0003_opt_trial_diagnostics
Revises: 0002_practice_execution_state
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_opt_trial_diagnostics"
down_revision: str | None = "0002_practice_execution_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "opt_trials")

    if "status" not in columns:
        op.add_column(
            "opt_trials",
            sa.Column("status", sa.String(length=32), nullable=True),
        )
        op.execute(
            sa.text(
                """
                UPDATE opt_trials
                SET status = CASE WHEN pruned THEN 'pruned' ELSE 'completed' END
                """
            )
        )
        op.alter_column("opt_trials", "status", nullable=False)

    if "failure_reason" not in columns:
        op.add_column("opt_trials", sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "opt_trials")

    if "failure_reason" in columns:
        op.drop_column("opt_trials", "failure_reason")
    if "status" in columns:
        op.drop_column("opt_trials", "status")


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
