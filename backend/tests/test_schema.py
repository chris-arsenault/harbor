from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from harbor_bot.persistence.schema import metadata

EXPECTED_TABLES = {
    "backtest_runs",
    "backtest_trades",
    "broker_transactions",
    "candles",
    "config",
    "equity_snapshots",
    "events",
    "fvgs",
    "opt_studies",
    "opt_trials",
    "sessions",
    "signals",
    "sweeps",
    "trades",
    "variant_trades",
    "variants",
}


def test_metadata_defines_m2_tables() -> None:
    assert set(metadata.tables) == EXPECTED_TABLES


def test_market_fact_tables_match_spec_shape() -> None:
    candles = metadata.tables["candles"]
    assert {"instrument", "ts", "o", "h", "l", "c", "volume", "complete"} <= set(
        candles.columns.keys()
    )
    assert _has_unique_constraint(candles, ["instrument", "ts"])

    sessions = metadata.tables["sessions"]
    assert {
        "date",
        "instrument",
        "asia_high",
        "asia_low",
        "london_high",
        "london_low",
    } <= set(sessions.columns.keys())
    assert _has_unique_constraint(sessions, ["date", "instrument"])


def test_decision_tables_have_relationships_and_enumerated_checks() -> None:
    assert _has_check_constraint(metadata.tables["sweeps"], "sweeps_direction_check")
    assert _has_check_constraint(metadata.tables["fvgs"], "fvgs_type_check")
    assert _has_foreign_key(metadata.tables["fvgs"], ["sweep_id"], "sweeps")

    assert _has_check_constraint(metadata.tables["signals"], "signals_direction_check")
    assert _has_check_constraint(metadata.tables["signals"], "signals_status_check")
    assert _has_unique_constraint(metadata.tables["signals"], ["signal_key"])

    trades = metadata.tables["trades"]
    assert _has_check_constraint(trades, "trades_side_check")
    assert _has_foreign_key(trades, ["signal_id"], "signals")
    assert _has_unique_constraint(trades, ["client_order_id"])

    variant_trades = metadata.tables["variant_trades"]
    assert _has_foreign_key(variant_trades, ["variant_id"], "variants")


def test_research_tables_have_json_and_relationship_constraints() -> None:
    assert _is_jsonb("backtest_runs", "params_json")
    assert _is_jsonb("backtest_runs", "stats_json")
    assert _has_foreign_key(metadata.tables["backtest_trades"], ["run_id"], "backtest_runs")

    assert _is_jsonb("opt_studies", "search_space_json")
    assert _is_jsonb("opt_studies", "walkforward_json")
    assert _is_jsonb("opt_trials", "params_json")
    assert _has_unique_constraint(metadata.tables["opt_trials"], ["study_id", "trial_no"])
    assert _has_foreign_key(metadata.tables["opt_trials"], ["study_id"], "opt_studies")

    variants = metadata.tables["variants"]
    assert _is_jsonb("variants", "params_json")
    assert _has_foreign_key(variants, ["source_trial_id"], "opt_trials")
    assert _has_check_constraint(variants, "variants_status_check")


def test_config_and_events_store_jsonb_payloads() -> None:
    assert _is_jsonb("config", "value_json")
    assert _is_jsonb("events", "data_json")
    assert _is_jsonb("broker_transactions", "raw_json")
    assert _has_unique_constraint(metadata.tables["broker_transactions"], ["transaction_id"])


def _has_unique_constraint(table, columns: list[str]) -> bool:
    expected = set(columns)
    return any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == expected
        for constraint in table.constraints
    )


def _has_foreign_key(table, columns: list[str], referred_table: str) -> bool:
    expected = set(columns)
    return any(
        isinstance(constraint, ForeignKeyConstraint)
        and {column.name for column in constraint.columns} == expected
        and next(iter(constraint.elements)).column.table.name == referred_table
        for constraint in table.constraints
    )


def _has_check_constraint(table, name: str) -> bool:
    expected_names = {name, f"ck_{table.name}_{name}"}
    return any(
        isinstance(constraint, CheckConstraint) and constraint.name in expected_names
        for constraint in table.constraints
    )


def _is_jsonb(table_name: str, column_name: str) -> bool:
    return isinstance(metadata.tables[table_name].c[column_name].type, JSONB)
