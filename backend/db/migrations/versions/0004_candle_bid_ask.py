"""Add bid/ask extremes to candles for honest backtest fills.

Revision ID: 0004_candle_bid_ask
Revises: 0003_opt_trial_diagnostics
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_candle_bid_ask"
down_revision: str | None = "0003_opt_trial_diagnostics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("bid_h", "bid_l", "ask_h", "ask_l")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, "candles")
    for name in _COLUMNS:
        if name not in existing:
            op.add_column("candles", sa.Column(name, sa.Numeric(18, 8), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _column_names(inspector, "candles")
    for name in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("candles", name)


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}
