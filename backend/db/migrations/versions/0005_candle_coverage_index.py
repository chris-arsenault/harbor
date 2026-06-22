"""Add partial index on candles(instrument) WHERE complete for fast coverage queries.

Revision ID: 0005_candle_coverage_index
Revises: 0004_candle_bid_ask
Create Date: 2026-06-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_candle_coverage_index"
down_revision: str | None = "0004_candle_bid_ask"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_candles_instrument_complete"


def upgrade() -> None:
    op.create_index(
        _INDEX,
        "candles",
        ["instrument"],
        postgresql_where="complete",
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="candles")
