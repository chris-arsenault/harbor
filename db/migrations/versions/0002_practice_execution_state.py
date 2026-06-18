"""Add practice execution state.

Revision ID: 0002_practice_execution_state
Revises: 0001_persistence_foundation
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_practice_execution_state"
down_revision: str | None = "0001_persistence_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    signal_columns = _column_names(inspector, "signals")
    if "signal_key" not in signal_columns:
        op.add_column("signals", sa.Column("signal_key", sa.String(length=256), nullable=True))
    if "signals_signal_key_key" not in _unique_names(inspector, "signals"):
        op.create_unique_constraint("signals_signal_key_key", "signals", ["signal_key"])

    trade_columns = _column_names(inspector, "trades")
    if "broker_order_id" not in trade_columns:
        op.add_column("trades", sa.Column("broker_order_id", sa.String(length=128), nullable=True))
    if "client_order_id" not in trade_columns:
        op.add_column("trades", sa.Column("client_order_id", sa.String(length=256), nullable=True))
    if "open_transaction_id" not in trade_columns:
        op.add_column("trades", sa.Column("open_transaction_id", sa.String(length=128), nullable=True))
    if "close_transaction_id" not in trade_columns:
        op.add_column(
            "trades",
            sa.Column("close_transaction_id", sa.String(length=128), nullable=True),
        )
    if "trades_client_order_id_key" not in _unique_names(inspector, "trades"):
        op.create_unique_constraint("trades_client_order_id_key", "trades", ["client_order_id"])

    if not inspector.has_table("broker_transactions"):
        op.create_table(
            "broker_transactions",
            sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
            sa.Column("transaction_id", sa.String(length=128), nullable=False),
            sa.Column("transaction_type", sa.String(length=64), nullable=False),
            sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.UniqueConstraint(
                "transaction_id",
                name="broker_transactions_transaction_id_key",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("broker_transactions"):
        op.drop_table("broker_transactions")

    trade_unique_names = _unique_names(inspector, "trades")
    if "trades_client_order_id_key" in trade_unique_names:
        op.drop_constraint("trades_client_order_id_key", "trades", type_="unique")
    for column_name in (
        "close_transaction_id",
        "open_transaction_id",
        "client_order_id",
        "broker_order_id",
    ):
        if column_name in _column_names(inspector, "trades"):
            op.drop_column("trades", column_name)

    signal_unique_names = _unique_names(inspector, "signals")
    if "signals_signal_key_key" in signal_unique_names:
        op.drop_constraint("signals_signal_key_key", "signals", type_="unique")
    if "signal_key" in _column_names(inspector, "signals"):
        op.drop_column("signals", "signal_key")


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint["name"] is not None
    }
