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
    min_in_sample_trades: DISCOVERY_STUDY_CONFIG.minInSampleTrades,
    min_out_of_sample_trades: DISCOVERY_STUDY_CONFIG.minOutOfSampleTrades,
  },
  dataset: {
    candle_count: 178560,
    session_day_count: 126,
    evaluable_session_day_count: 124,
    partial_session_day_count: 2,
    first_evaluable_trading_date: "2026-01-05",
    last_evaluable_trading_date: "2026-06-18",
    day_diagnostics: [],
  },
  walk_forward: {
    window_count: 2,
    required_session_days:
      DISCOVERY_STUDY_CONFIG.trainWindowDays + DISCOVERY_STUDY_CONFIG.outOfSampleWindowDays,
    train_window_days: DISCOVERY_STUDY_CONFIG.trainWindowDays,
    out_of_sample_window_days: DISCOVERY_STUDY_CONFIG.outOfSampleWindowDays,
    step_days: DISCOVERY_STUDY_CONFIG.stepDays,
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
    { name: "candles", status: "pass", message: "178560 persisted closed candles selected" },
    { name: "session_days", status: "pass", message: "124 complete strategy session days" },
    { name: "walk_forward", status: "pass", message: "2 walk-forward windows" },
    { name: "baseline", status: "warn", message: "baseline does not pass" },
  ],
  research_protocol: {
    status: "ready",
    message: "dataset satisfies the fixed research protocol",
    data_requirements: {
      trial_count: DISCOVERY_STUDY_CONFIG.trialCount,
      candidate_count: DISCOVERY_STUDY_CONFIG.candidateCount,
      discovery_candidate_count: 30,
      min_evaluable_days: 120,
      min_discovery_days: 90,
      holdout_days: 30,
      max_session_gap_minutes: 1,
      min_holdout_trades: 5,
      train_window_days: DISCOVERY_STUDY_CONFIG.trainWindowDays,
      oos_window_days: DISCOVERY_STUDY_CONFIG.outOfSampleWindowDays,
      step_days: DISCOVERY_STUDY_CONFIG.stepDays,
      min_in_sample_trades: DISCOVERY_STUDY_CONFIG.minInSampleTrades,
      min_oos_trades: DISCOVERY_STUDY_CONFIG.minOutOfSampleTrades,
    },
    evaluable_day_count: 124,
    partial_day_count: 2,
    evaluable_days: [],
  },
  recommended_payload: tuningPayloadFromConfig(DISCOVERY_STUDY_CONFIG),
} satisfies OptimizationPreflightResponse;
