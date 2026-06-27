"""Store OANDA order-book and position-book snapshots.

Revision ID: 0006_orderbook_positionbook
Revises: 0005_candle_coverage_index
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_orderbook_positionbook"
down_revision: str | None = "0005_candle_coverage_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LATEST_INDEX = "ix_book_snapshots_book_type_instrument_snapshot_time"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "book_snapshots" not in inspector.get_table_names():
        op.create_table(
            "book_snapshots",
            sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
            sa.Column("book_type", sa.String(length=16), nullable=False),
            sa.Column("instrument", sa.String(length=32), nullable=False),
            sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("mid_price", sa.Numeric(18, 8), nullable=False),
            sa.Column("bucket_width", sa.Numeric(18, 8), nullable=False),
            sa.Column("bucket_count", sa.Integer(), nullable=False),
            sa.Column("buckets_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("recorded_ts", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "book_type",
                "instrument",
                "snapshot_time",
                name="book_snapshots_book_type_instrument_snapshot_time_key",
            ),
            sa.CheckConstraint(
                "book_type IN ('order', 'position')",
                name=op.f("ck_book_snapshots_book_type_check"),
            ),
        )
        inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("book_snapshots")}
    if _LATEST_INDEX in existing_indexes:
        op.drop_index(_LATEST_INDEX, table_name="book_snapshots")
    op.execute(
        "CREATE INDEX ix_book_snapshots_book_type_instrument_snapshot_time "
        "ON book_snapshots (book_type, instrument, snapshot_time DESC)"
    )


def downgrade() -> None:
    op.drop_index(_LATEST_INDEX, table_name="book_snapshots")
    op.drop_table("book_snapshots")
