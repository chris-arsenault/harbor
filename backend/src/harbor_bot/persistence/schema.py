from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

price = Numeric(18, 8)
money = Numeric(20, 8)
score = Numeric(20, 8)

candles = Table(
    "candles",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("instrument", String(32), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("o", price, nullable=False),
    Column("h", price, nullable=False),
    Column("l", price, nullable=False),
    Column("c", price, nullable=False),
    Column("volume", BigInteger, nullable=False),
    Column("complete", Boolean, nullable=False),
    Column("bid_h", price, nullable=True),
    Column("bid_l", price, nullable=True),
    Column("ask_h", price, nullable=True),
    Column("ask_l", price, nullable=True),
    UniqueConstraint("instrument", "ts", name="candles_instrument_ts_key"),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("date", Date, nullable=False),
    Column("instrument", String(32), nullable=False),
    Column("asia_high", price, nullable=False),
    Column("asia_low", price, nullable=False),
    Column("london_high", price, nullable=False),
    Column("london_low", price, nullable=False),
    UniqueConstraint("date", "instrument", name="sessions_date_instrument_key"),
)

sweeps = Table(
    "sweeps",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("instrument", String(32), nullable=False),
    Column("level_name", String(64), nullable=False),
    Column("level_price", price, nullable=False),
    Column("direction", String(16), nullable=False),
    Column("sweep_extreme", price, nullable=False),
    CheckConstraint("direction IN ('bullish', 'bearish')", name="sweeps_direction_check"),
)

fvgs = Table(
    "fvgs",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("instrument", String(32), nullable=False),
    Column("type", String(16), nullable=False),
    Column("top", price, nullable=False),
    Column("bottom", price, nullable=False),
    Column("midpoint", price, nullable=False),
    Column("sweep_id", BigInteger, ForeignKey("sweeps.id"), nullable=False),
    CheckConstraint("type IN ('bullish', 'bearish')", name="fvgs_type_check"),
)

signals = Table(
    "signals",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("signal_key", String(256)),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("instrument", String(32), nullable=False),
    Column("direction", String(16), nullable=False),
    Column("entry", price, nullable=False),
    Column("stop", price, nullable=False),
    Column("target", price, nullable=False),
    Column("risk", price, nullable=False),
    Column("rr", Numeric(10, 4), nullable=False),
    Column("status", String(16), nullable=False),
    UniqueConstraint("signal_key", name="signals_signal_key_key"),
    CheckConstraint("direction IN ('long', 'short')", name="signals_direction_check"),
    CheckConstraint("status IN ('pending', 'filled', 'cancelled')", name="signals_status_check"),
)

trades = Table(
    "trades",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("signal_id", BigInteger, ForeignKey("signals.id"), nullable=False),
    Column("broker_order_id", String(128)),
    Column("client_order_id", String(256)),
    Column("broker_trade_id", String(128)),
    Column("open_transaction_id", String(128)),
    Column("close_transaction_id", String(128)),
    Column("side", String(16), nullable=False),
    Column("units", Numeric(20, 4), nullable=False),
    Column("entry_price", price, nullable=False),
    Column("entry_ts", DateTime(timezone=True), nullable=False),
    Column("exit_price", price),
    Column("exit_ts", DateTime(timezone=True)),
    Column("pnl", money),
    Column("r_multiple", Numeric(10, 4)),
    Column("exit_reason", String(64)),
    UniqueConstraint("client_order_id", name="trades_client_order_id_key"),
    CheckConstraint("side IN ('long', 'short')", name="trades_side_check"),
)

broker_transactions = Table(
    "broker_transactions",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("transaction_id", String(128), nullable=False),
    Column("transaction_type", String(64), nullable=False),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("raw_json", JSONB, nullable=False),
    UniqueConstraint("transaction_id", name="broker_transactions_transaction_id_key"),
)

equity_snapshots = Table(
    "equity_snapshots",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("nav", money, nullable=False),
    Column("balance", money, nullable=False),
    Column("unrealized_pnl", money, nullable=False),
    Column("open_positions", BigInteger, nullable=False),
)

events = Table(
    "events",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("level", String(32), nullable=False),
    Column("module", String(64), nullable=False),
    Column("type", String(64), nullable=False),
    Column("message", Text, nullable=False),
    Column("data_json", JSONB, nullable=False, server_default="{}"),
)

config = Table(
    "config",
    metadata,
    Column("key", String(128), primary_key=True),
    Column("value_json", JSONB, nullable=False),
    Column("updated_ts", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created_ts", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("params_json", JSONB, nullable=False),
    Column("stats_json", JSONB, nullable=False),
)

backtest_trades = Table(
    "backtest_trades",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("run_id", BigInteger, ForeignKey("backtest_runs.id"), nullable=False),
    Column("side", String(16), nullable=False),
    Column("units", Numeric(20, 4), nullable=False),
    Column("entry_price", price, nullable=False),
    Column("entry_ts", DateTime(timezone=True), nullable=False),
    Column("exit_price", price, nullable=False),
    Column("exit_ts", DateTime(timezone=True), nullable=False),
    Column("pnl", money, nullable=False),
    Column("r_multiple", Numeric(10, 4), nullable=False),
    Column("exit_reason", String(64), nullable=False),
    CheckConstraint("side IN ('long', 'short')", name="backtest_trades_side_check"),
)

opt_studies = Table(
    "opt_studies",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created_ts", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("search_space_json", JSONB, nullable=False),
    Column("walkforward_json", JSONB, nullable=False),
    Column("status", String(32), nullable=False),
)

opt_trials = Table(
    "opt_trials",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("study_id", BigInteger, ForeignKey("opt_studies.id"), nullable=False),
    Column("trial_no", BigInteger, nullable=False),
    Column("params_json", JSONB, nullable=False),
    Column("is_score", score, nullable=False),
    Column("oos_score", score, nullable=False),
    Column("robustness_score", score, nullable=False),
    Column("pruned", Boolean, nullable=False),
    Column("status", String(32), nullable=False),
    Column("failure_reason", Text),
    UniqueConstraint("study_id", "trial_no", name="opt_trials_study_id_trial_no_key"),
)

variants = Table(
    "variants",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("label", String(128), nullable=False),
    Column("params_json", JSONB, nullable=False),
    Column("source_trial_id", BigInteger, ForeignKey("opt_trials.id"), nullable=False),
    Column("status", String(16), nullable=False),
    CheckConstraint("status IN ('paper', 'promoted', 'retired')", name="variants_status_check"),
)

variant_trades = Table(
    "variant_trades",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("variant_id", BigInteger, ForeignKey("variants.id"), nullable=False),
    Column("side", String(16), nullable=False),
    Column("units", Numeric(20, 4), nullable=False),
    Column("entry_price", price, nullable=False),
    Column("entry_ts", DateTime(timezone=True), nullable=False),
    Column("exit_price", price, nullable=False),
    Column("exit_ts", DateTime(timezone=True), nullable=False),
    Column("pnl", money, nullable=False),
    Column("r_multiple", Numeric(10, 4), nullable=False),
    Column("exit_reason", String(64), nullable=False),
    CheckConstraint("side IN ('long', 'short')", name="variant_trades_side_check"),
)
