import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { BacktestRunDetail, BacktestRunSummary } from "../../api/types";
import { BacktestsView } from "./BacktestsView";

test("renders backtest experiment controls, run history, stats, and trade results", () => {
  const onStartBacktest = vi.fn();

  render(
    <BacktestsView
      runs={[runSummary()]}
      selectedRun={runDetail()}
      pending={false}
      onStartBacktest={onStartBacktest}
    />
  );

  expect(screen.getByRole("heading", { name: "Backtests" })).toBeInTheDocument();
  expect(screen.getByLabelText("Instrument")).toHaveValue("EUR_USD");
  expect(screen.getByLabelText("From")).toHaveValue("2026-01-15T14:00:00Z");
  expect(screen.getByLabelText("To")).toHaveValue("2026-01-15T17:00:00Z");
  expect(screen.getByRole("row", { name: /42 completed 1/i })).toBeInTheDocument();
  expect(screen.getByText("Trade count")).toBeInTheDocument();
  expect(screen.getAllByText("1.50000000")).toHaveLength(2);
  expect(screen.getByRole("row", { name: /long 1000.0000 1.09020000/i })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  expect(onStartBacktest).toHaveBeenCalledWith({
    source: "persisted_candles",
    instrument: "EUR_USD",
    candle_range: {
      from: "2026-01-15T14:00:00Z",
      to: "2026-01-15T17:00:00Z",
    },
  });
});

function runSummary(): BacktestRunSummary {
  return {
    run_id: 42,
    created_ts: "2026-01-15T18:00:00Z",
    params: { instrument: "EUR_USD" },
    stats: { trade_count: 1, expectancy: "18.00000000" },
    trade_count: 1,
  };
}

function runDetail(): BacktestRunDetail {
  return {
    run_id: 42,
    created_ts: "2026-01-15T18:00:00Z",
    params: { instrument: "EUR_USD" },
    stats: {
      trade_count: 1,
      expectancy: "18.00000000",
      average_r: "1.50000000",
      max_drawdown: "0",
    },
    trades: [
      {
        side: "long",
        units: "1000.0000",
        entry_price: "1.09020000",
        exit_price: "1.09200000",
        pnl: "18.00000000",
        r_multiple: "1.50000000",
        exit_reason: "take_profit",
      },
    ],
  };
}
