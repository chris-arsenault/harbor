from pathlib import Path

REPORT = Path(__file__).resolve().parents[2] / "docs" / "research" / "m6-optimizer-run.md"


def test_m6_optimizer_report_contains_walk_forward_and_data_separation_artifact() -> None:
    text = REPORT.read_text(encoding="utf-8")

    assert "Optuna" in text
    assert "TPESampler" in text
    assert "MedianPruner" in text
    assert "walk-forward" in text
    assert "out-of-sample" in text
    assert "Trial count" in text
    assert "Minimum in-sample trades" in text
    assert "Minimum out-of-sample trades" in text
    assert "Ranked Candidates" in text
    assert "paper" in text
    assert "no live-forward data" in text
    assert "`variant_trades`" in text
    assert "OANDA" in text
    assert "paper engine" in text
    assert "frontend UI" in text
