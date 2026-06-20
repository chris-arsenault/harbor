import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { DISCOVERY_STUDY_CONFIG, tuningPayloadFromConfig } from "./tuningPayload";

const optimizerConfig = {
  trial_count: DISCOVERY_STUDY_CONFIG.trialCount,
  candidate_count: DISCOVERY_STUDY_CONFIG.candidateCount,
  minimum_trade_count: {
    in_sample: DISCOVERY_STUDY_CONFIG.minInSampleTrades,
    out_of_sample: DISCOVERY_STUDY_CONFIG.minOutOfSampleTrades,
  },
  robustness: {
    neighbor_count: DISCOVERY_STUDY_CONFIG.robustnessNeighborCount,
  },
  walk_forward: {
    train_window_days: DISCOVERY_STUDY_CONFIG.trainWindowDays,
    oos_window_days: DISCOVERY_STUDY_CONFIG.outOfSampleWindowDays,
    step_days: DISCOVERY_STUDY_CONFIG.stepDays,
  },
};

export const preflight = {
  status: "ready",
  instrument: "EUR_USD",
  candle_source: {
    source: "persisted_candles",
    candle_count: 31760,
  },
  study_config: optimizerConfig,
  candidate_gate: {
    requires: "completed trials with positive in-sample and out-of-sample scores",
    min_in_sample_trades: 3,
    min_out_of_sample_trades: 1,
  },
  dataset: {
    candle_count: 31760,
    session_day_count: 18,
    evaluable_session_day_count: 16,
    partial_session_day_count: 2,
    first_evaluable_trading_date: "2026-05-20",
    last_evaluable_trading_date: "2026-06-18",
    day_diagnostics: [],
  },
  walk_forward: {
    window_count: 2,
    required_session_days: 15,
    train_window_days: 10,
    out_of_sample_window_days: 5,
    step_days: 5,
    window_error: null,
    windows: [
      {
        index: 0,
        train_start: "2026-05-20",
        train_end: "2026-06-03",
        out_of_sample_start: "2026-06-04",
        out_of_sample_end: "2026-06-10",
        train_candle_count: 14400,
        out_of_sample_candle_count: 7200,
      },
    ],
    omitted_window_count: 1,
  },
  baseline: {
    status: "candidate_gate_failed",
    window_count: 2,
    in_sample: {
      score: "-0.12",
      stats: { trade_count: 8 },
    },
    out_of_sample: {
      score: "0.75",
      stats: { trade_count: 3 },
    },
  },
  readiness: [
    { name: "candles", status: "pass", message: "31760 persisted closed candles selected" },
    { name: "session_days", status: "pass", message: "16 complete strategy session days" },
    { name: "walk_forward", status: "pass", message: "2 walk-forward windows" },
    { name: "baseline", status: "warn", message: "baseline does not pass" },
  ],
  recommended_payload: tuningPayloadFromConfig(DISCOVERY_STUDY_CONFIG),
} satisfies OptimizationPreflightResponse;
