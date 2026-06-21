import type { OptimizationStartPayload } from "./types";

export interface OptimizationPreflightResponse {
  status: string;
  instrument: string;
  candle_source: Record<string, unknown> | null;
  study_config: Record<string, unknown>;
  candidate_gate: {
    requires: string;
    min_in_sample_trades: number;
    min_out_of_sample_trades: number;
  };
  dataset: {
    candle_count: number;
    session_day_count: number;
    evaluable_session_day_count: number;
    partial_session_day_count: number;
    first_evaluable_trading_date: string | null;
    last_evaluable_trading_date: string | null;
    day_diagnostics: StrategyDayDiagnostic[];
  };
  walk_forward: {
    window_count: number;
    required_session_days: number;
    train_window_days: number;
    out_of_sample_window_days: number;
    step_days: number;
    window_error: string | null;
    windows: WalkForwardWindowSummary[];
    omitted_window_count: number;
  };
  baseline: OptimizationBaseline | null;
  research_protocol: ResearchProtocolReadiness;
  readiness: OptimizationReadinessItem[];
  recommended_payload: OptimizationStartPayload;
}

export interface ResearchProtocolReadiness {
  status: string;
  message: string;
  data_requirements: {
    trial_count: number;
    candidate_count: number;
    min_evaluable_days: number;
    min_discovery_days: number;
    holdout_days: number;
    max_session_gap_minutes: number;
    min_holdout_trades: number;
    train_window_days: number;
    oos_window_days: number;
    step_days: number;
    min_in_sample_trades: number;
    min_oos_trades: number;
  };
  evaluable_day_count: number;
  partial_day_count: number;
  evaluable_days: StrategyDayDiagnostic[];
}

export interface StrategyDayDiagnostic {
  trading_date: string;
  candle_count: number;
  evaluable: boolean;
  reason: string | null;
}

export interface WalkForwardWindowSummary {
  index: number;
  train_start: string;
  train_end: string;
  out_of_sample_start: string;
  out_of_sample_end: string;
  train_candle_count: number;
  out_of_sample_candle_count: number;
}

export interface OptimizationBaseline {
  status: string;
  window_count: number;
  in_sample: OptimizationBaselineSide;
  out_of_sample: OptimizationBaselineSide;
}

export interface OptimizationBaselineSide {
  score: string;
  stats: Record<string, unknown>;
}

export interface OptimizationReadinessItem {
  name: string;
  status: string;
  message: string;
}
