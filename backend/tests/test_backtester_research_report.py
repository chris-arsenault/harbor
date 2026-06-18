from pathlib import Path

REPORT = Path(__file__).resolve().parents[2] / "docs" / "research" / "m5-baseline-backtest.md"


def test_m5_baseline_report_contains_research_gate_artifact() -> None:
    text = REPORT.read_text(encoding="utf-8")

    assert "M6_RESEARCH_GATE: pending" in text
    assert "Clean signal day" in text
    assert "No-trade day" in text
    assert "2026-01-15T01:00:00+00:00 to 2026-01-15T16:30:00+00:00" in text
    assert "2026-01-16T01:00:00+00:00 to 2026-01-16T16:30:00+00:00" in text
    assert "Initial NAV" in text
    assert "Spread assumption" in text
    assert "Trade count" in text
    assert "Net PnL" in text
    assert "Max drawdown" in text
    assert "Expectancy" in text
    assert "Average R" in text
    assert "lookahead" in text.lower()
