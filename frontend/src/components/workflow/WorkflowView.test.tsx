import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { PracticeControls } from "../../api/hooks";
import type {
  CandleSourceStatus,
  LabSnapshot,
  LabVariantOverview,
  StatusSnapshot,
} from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { WorkflowView } from "./WorkflowView";

test("runs a candidate backtest from the selected complete persisted window", () => {
  const onStartBacktest = vi.fn();
  const onInstrumentChange = vi.fn();

  render(
    <WorkflowView
      selectedInstrument="GBP_USD"
      onInstrumentChange={onInstrumentChange}
      candleSource={candleSource()}
      candleSourcePending={false}
      candleSourceError={null}
      importResult={null}
      onImportCandles={vi.fn()}
      studyPayload={{ source: "persisted_candles", instrument: "GBP_USD" }}
      preflight={preflight()}
      preflightPending={false}
      preflightError={null}
      tuningRun={{ pending: false, errorMessage: null, result: null }}
      snapshot={snapshot()}
      variants={variantOverview()}
      events={[]}
      onStartOptimization={vi.fn()}
      backtestRuns={[]}
      selectedBacktestRun={null}
      backtestPending={false}
      backtestError={null}
      onStartBacktest={onStartBacktest}
      status={status()}
      controls={controls()}
      onPromoteVariant={vi.fn()}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "Run Backtest" }));

  expect(onStartBacktest).toHaveBeenCalledWith({
    source: "persisted_candles",
    instrument: "GBP_USD",
    candle_window_days: 30,
    strategy_params: { instrument: "GBP_USD", fvg_window: 13 },
    variant_id: 7,
    variant_label: "candidate-1",
  });

  fireEvent.change(screen.getByLabelText("Instrument"), { target: { value: "EUR_USD" } });

  expect(onInstrumentChange).toHaveBeenCalledWith("EUR_USD");
});

function candleSource(): CandleSourceStatus {
  return {
    instrument: "GBP_USD",
    primary_source: "persisted_candles",
    granularity: "M1",
    price_component: "midpoint",
    coverage: coverage("GBP_USD", 70_000),
    instrument_coverages: [coverage("GBP_USD", 70_000), coverage("EUR_USD", 2_880)],
    source_methods: ["oanda_historical_import", "oanda_pricing_stream"],
    research_instruments: ["GBP_USD", "EUR_USD"],
    historical_import: {
      page_size: 5000,
      default_count: 259200,
      request_interval_seconds: 0.1,
      upsert_key: "instrument+timestamp",
      replaces_existing: false,
    },
    oanda_historical_import_configured: true,
    live_stream: {
      configured: true,
      enabled: true,
      running: true,
      state: "running",
      starts_on_api_boot: true,
      paper_forward_on_closed_candle: true,
      instruments: ["GBP_USD", "EUR_USD"],
      heartbeat_timeout_seconds: 20,
      reconnect_initial_seconds: 1,
      reconnect_max_seconds: 30,
      last_started_at: "2026-01-15T13:55:00Z",
      last_stopped_at: null,
      last_error: null,
    },
  };
}

function coverage(instrument: string, candleCount: number) {
  return {
    instrument,
    candle_count: candleCount,
    from: "2026-01-15T00:00:00+00:00",
    to: "2026-06-15T23:59:00+00:00",
  };
}

function preflight(): OptimizationPreflightResponse {
  return {
    status: "ready",
    instrument: "GBP_USD",
    candle_source: null,
    study_config: {},
    candidate_gate: {
      requires: "completed trials with positive in-sample and out-of-sample scores",
      min_in_sample_trades: 12,
      min_out_of_sample_trades: 4,
    },
    dataset: {
      candle_count: 70_000,
      session_day_count: 120,
      evaluable_session_day_count: 120,
      partial_session_day_count: 0,
      first_evaluable_trading_date: "2026-01-15",
      last_evaluable_trading_date: "2026-06-15",
      day_diagnostics: [],
    },
    walk_forward: {
      window_count: 3,
      required_session_days: 80,
      train_window_days: 60,
      out_of_sample_window_days: 20,
      step_days: 20,
      window_error: null,
      windows: [],
      omitted_window_count: 0,
    },
    baseline: null,
    research_protocol: {
      status: "ready",
      message: "ready",
      data_requirements: {
        trial_count: 96,
        candidate_count: 5,
        discovery_candidate_count: 5,
        min_evaluable_days: 120,
        min_discovery_days: 90,
        holdout_days: 30,
        max_session_gap_minutes: 1,
        min_holdout_trades: 5,
        train_window_days: 60,
        oos_window_days: 20,
        step_days: 20,
        min_in_sample_trades: 12,
        min_oos_trades: 4,
      },
      evaluable_day_count: 120,
      partial_day_count: 0,
      evaluable_days: [],
    },
    readiness: [{ name: "candles", status: "pass", message: "ready" }],
    recommended_payload: { source: "persisted_candles", instrument: "GBP_USD" },
  };
}

function snapshot(): LabSnapshot {
  return {
    study: {
      study_id: 1,
      status: "completed",
      trial_count: 1,
      candidate_count: 1,
      paper_variant_count: 1,
      created_ts: "2026-01-15T13:00:00Z",
    },
    candidates: [
      {
        trial_id: 2,
        trial_no: 0,
        params: { instrument: "GBP_USD", fvg_window: 13 },
        in_sample_score: "1.25",
        out_of_sample_score: "1.50",
        robustness_score: "1.40",
        pruned: false,
        status: "completed",
        failure_reason: null,
        candidate_rejection_reason: null,
      },
    ],
    variants: variantOverview(),
    data_separation: {},
  };
}

function variantOverview(): LabVariantOverview {
  const variant = {
    id: 7,
    label: "candidate-1",
    params: { instrument: "GBP_USD", fvg_window: 13 },
    source_trial_id: 2,
    status: "paper" as const,
    created_ts: null,
    trial_scores: {
      in_sample_score: "1.25",
      out_of_sample_score: "1.50",
      robustness_score: "1.40",
    },
  };
  return {
    variants: [variant],
    leaderboard: [
      {
        rank: 1,
        variant,
        stats: {
          variant_id: 7,
          trade_count: 1,
          win_rate: "1",
          net_pnl: "20",
          expectancy: "20",
          average_r: "1",
          max_drawdown: "0",
          ending_nav: "10020",
          live_forward_score: "20",
        },
        out_of_sample_score: "1.50",
        robustness_score: "1.40",
      },
    ],
    equity_curves: [],
    data_separation: {},
  };
}

function status(): StatusSnapshot {
  return {
    bot_state: "WAIT_SWEEP",
    session_phase: "ny_trade",
    connection_health: "unknown",
    mode: "practice",
    trading_enabled: false,
    trading_controls_available: true,
    kill_switch_state: "armed",
    day_pnl: "0",
    trades_today: 0,
    max_trades_per_day: 2,
    account_nav: "10000",
    open_positions: 0,
    unrealized_pnl: "0",
    last_heartbeat: null,
    promoted_variant: null,
  };
}

function controls(): PracticeControls {
  return {
    pending: false,
    errorMessage: null,
    flattenResult: null,
    setTradingEnabled: vi.fn(),
    flattenNow: vi.fn(),
  };
}
