import type { StatusSnapshot } from "./api/types";

export const status: StatusSnapshot = {
  bot_state: "WAIT_SWEEP",
  session_phase: "ny_trade",
  connection_health: "unknown",
  mode: "practice",
  trading_enabled: false,
  trading_controls_available: true,
  kill_switch_state: "armed",
  day_pnl: "60.00000000",
  trades_today: 1,
  max_trades_per_day: 2,
  account_nav: "10060.00000000",
  open_positions: 0,
  unrealized_pnl: "0E-8",
  last_heartbeat: "2026-01-15T14:31:00Z",
  promoted_variant: { id: 7, label: "promoted", status: "promoted" },
  reconciliation_state: { drift_detected: false },
  open_position: null,
};

export const levels = {
  date: "2026-01-15",
  instrument: "EUR_USD",
  asia_high: "1.11000000",
  asia_low: "1.10000000",
  london_high: "1.11500000",
  london_low: "1.10500000",
  swept_levels: ["asia_low"],
  taken_levels: [],
};

export const candle = {
  instrument: "EUR_USD",
  ts: "2026-01-15T14:00:00Z",
  open: "1.10000000",
  high: "1.10500000",
  low: "1.09900000",
  close: "1.10400000",
  volume: 100,
  complete: true,
};

export const markers = {
  markers: [
    {
      kind: "sweep",
      ts: "2026-01-15T14:31:00Z",
      instrument: "EUR_USD",
      label: "asia_low swept",
      price: "1.10000000",
      direction: "bullish",
      level_name: "asia_low",
    },
  ],
  fvgs: [],
  signals: [],
  trades: [],
};

export const event = {
  id: 13,
  ts: "2026-01-15T14:31:00Z",
  level: "warn",
  module: "feed",
  type: "heartbeat.stale",
  message: "heartbeat stale",
  data: { seconds: 31 },
};

export const labSnapshot = {
  study: {
    study_id: 1,
    status: "completed",
    trial_count: 2,
    candidate_count: 1,
    paper_variant_count: 1,
    created_ts: "2026-01-15T13:00:00Z",
  },
  candidates: [
    {
      trial_id: 2,
      trial_no: 0,
      params: { instrument: "GBP_USD", fvg_window: 8 },
      in_sample_score: "1.25",
      out_of_sample_score: "1.50",
      robustness_score: "1.40",
      pruned: false,
      status: "completed",
      failure_reason: null,
      candidate_rejection_reason: null,
    },
  ],
  variants: {
    variants: [],
    leaderboard: [],
    equity_curves: [],
    data_separation: { optimizer_uses_variant_trades: false },
  },
  data_separation: { optimizer_uses_variant_trades: false },
};

export const labVariants = {
  variants: [
    {
      id: 7,
      label: "candidate-1",
      params: { instrument: "GBP_USD", fvg_window: 8 },
      source_trial_id: 2,
      status: "paper",
      created_ts: null,
      trial_scores: {
        in_sample_score: "1.25",
        out_of_sample_score: "1.50",
        robustness_score: "1.40",
      },
    },
  ],
  leaderboard: [
    {
      rank: 1,
      variant: {
        id: 7,
        label: "candidate-1",
        params: { instrument: "GBP_USD", fvg_window: 8 },
        source_trial_id: 2,
        status: "paper",
        created_ts: null,
        trial_scores: {
          in_sample_score: "1.25",
          out_of_sample_score: "1.50",
          robustness_score: "1.40",
        },
      },
      stats: {
        variant_id: 7,
        trade_count: 1,
        win_rate: "1",
        net_pnl: "20.00000000",
        expectancy: "20.00000000",
        average_r: "2.0000",
        max_drawdown: "0",
        ending_nav: "10020.00000000",
        live_forward_score: "20.00000000",
      },
      out_of_sample_score: "1.50000000",
      robustness_score: "1.40000000",
    },
  ],
  equity_curves: [
    {
      variant_id: 7,
      points: [
        {
          variant_id: 7,
          ts: "2026-01-15T14:42:00Z",
          nav: "10020.00000000",
          drawdown: "0",
        },
      ],
    },
  ],
  data_separation: { optimizer_uses_variant_trades: false },
};
