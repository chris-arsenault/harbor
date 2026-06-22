import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { BacktestRunDetail, BacktestRunSummary } from "../../api/types";
import { BacktestsView } from "./BacktestsView";

test("renders backtest experiment controls, run history, stats, and trade results", () => {
  const onStartBacktest = vi.fn();

  render(
    <BacktestsView
      runs={[runSummary()]}
      selectedRunId={42}
      selectedRun={runDetail()}
      selectedRunPending={false}
      selectedRunError={null}
      candleSource={candleSource()}
      targetVariant={targetVariant()}
      pending={false}
      errorMessage={null}
      onStartBacktest={onStartBacktest}
      onSelectRun={vi.fn()}
    />
  );

  expect(screen.getByRole("heading", { name: "Backtests" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Run Backtest" })).toBeInTheDocument();
  expect(screen.getByLabelText("Strategy")).toHaveValue("candidate");
  expect(screen.getByLabelText("Instrument")).toHaveValue("GBP_USD");
  fireEvent.click(screen.getByText("Backtest window"));
  expect(screen.getByLabelText("From")).toHaveValue("2026-01-21T12:00:00.000Z");
  expect(screen.getByLabelText("To")).toHaveValue("2026-02-20T12:00:00.000Z");
  expect(
    screen.getByRole("row", { name: /#42 candidate-1 .* 1 18.00000000/i })
  ).toBeInTheDocument();
  expect(screen.getByText("Trade count")).toBeInTheDocument();
  expect(screen.getAllByText("1.50000000")).toHaveLength(2);
  expect(screen.getByText(/candidate-1 produced 1 closed trade/i)).toBeInTheDocument();
  expect(
    screen.getByRole("row", { name: /long asia_low 1000.0000 1.09020000/i })
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  expect(onStartBacktest).toHaveBeenCalledWith({
    source: "persisted_candles",
    instrument: "GBP_USD",
    candle_range: {
      from: "2026-01-21T12:00:00.000Z",
      to: "2026-02-20T12:00:00.000Z",
    },
    strategy_params: { fvg_window: 13 },
    variant_id: 7,
    variant_label: "candidate-1",
  });
});

function runSummary(): BacktestRunSummary {
  return {
    run_id: 42,
    created_ts: "2026-01-15T18:00:00Z",
    params: {
      instrument: "GBP_USD",
      variant_label: "candidate-1",
      candle_range: {
        from: "2026-01-21T12:00:00.000Z",
        to: "2026-02-20T12:00:00.000Z",
      },
    },
    stats: { trade_count: 1, expectancy: "18.00000000" },
    trade_count: 1,
  };
}

function runDetail(): BacktestRunDetail {
  return {
    run_id: 42,
    created_ts: "2026-01-15T18:00:00Z",
    params: { instrument: "GBP_USD", variant_label: "candidate-1" },
    stats: {
      trade_count: 1,
      net_pnl: "18.00000000",
      win_rate: "1",
      expectancy: "18.00000000",
      average_r: "1.50000000",
      max_drawdown: "0",
    },
    trades: [
      {
        side: "long",
        level_name: "asia_low",
        units: "1000.0000",
        entry_price: "1.09020000",
        entry_ts: "2026-01-15T14:34:00Z",
        exit_price: "1.09200000",
        exit_ts: "2026-01-15T14:40:00Z",
        pnl: "18.00000000",
        r_multiple: "1.50000000",
        exit_reason: "take_profit",
      },
    ],
  };
}

function candleSource() {
  return {
    instrument: "GBP_USD",
    primary_source: "persisted_candles",
    granularity: "M1",
    price_component: "midpoint",
    coverage: {
      instrument: "GBP_USD",
      candle_count: 70_000,
      from: "2026-01-01T00:00:00+00:00",
      to: "2026-02-20T12:00:00+00:00",
    },
    source_methods: ["oanda_historical_import", "oanda_pricing_stream"],
    research_instruments: ["GBP_USD", "EUR_USD", "USD_JPY"],
    historical_import: {
      page_size: 5000,
      default_count: 259200,
      request_interval_seconds: 0.1,
      upsert_key: "instrument+timestamp",
      replaces_existing: false,
    },
    oanda_historical_import_configured: true,
  };
}

function targetVariant() {
  return {
    id: 7,
    label: "candidate-1",
    params: { fvg_window: 13 },
    source_trial_id: 2,
    status: "paper" as const,
    created_ts: null,
    trial_scores: {
      in_sample_score: "1.25",
      out_of_sample_score: "1.50",
      robustness_score: "1.40",
    },
  };
}
