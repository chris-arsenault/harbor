export interface StatusSnapshot {
  bot_state: string;
  session_phase: string;
  connection_health: string;
  mode: string;
  trading_enabled: boolean;
  trading_controls_available: boolean;
  kill_switch_state: string;
  day_pnl: string;
  trades_today: number;
  max_trades_per_day: number;
  account_nav: string | null;
  open_positions: number | null;
  unrealized_pnl: string | null;
  last_heartbeat: string | null;
  promoted_variant?: { id: number; label: string; status: string } | null;
  reconciliation_state?: Record<string, unknown> | null;
  open_position?: Record<string, unknown> | null;
  notifier_state?: Record<string, unknown> | null;
  deployment?: Record<string, unknown> | null;
}

export interface SessionLevelSnapshot {
  date: string;
  instrument: string;
  asia_high: string;
  asia_low: string;
  london_high: string;
  london_low: string;
  swept_levels: string[];
  taken_levels: string[];
}

export interface CandlePoint {
  instrument: string;
  ts: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  complete: boolean;
}

export interface CandleCoverage {
  instrument: string;
  candle_count: number;
  from: string | null;
  to: string | null;
}

export interface CandleSourceStatus {
  instrument: string;
  primary_source: string;
  granularity: string;
  price_component: string;
  coverage: CandleCoverage;
  instrument_coverages?: CandleCoverage[];
  source_methods: string[];
  research_instruments: string[];
  historical_import: CandleHistoricalImportPolicy;
  oanda_historical_import_configured: boolean;
  live_stream?: CandleLiveStreamStatus;
}

export interface CandleImportRequest {
  instrument?: string;
  instruments?: string[];
  count?: number;
  from?: string;
}

export interface CandleImportResult {
  status: string;
  source: string;
  instrument: string;
  requested_count: number;
  imported_count: number;
  from: string | null;
  coverage: CandleCoverage;
  instruments?: string[];
  results?: CandleImportInstrumentResult[];
}

export interface CandleImportInstrumentResult {
  instrument: string;
  requested_count: number;
  imported_count: number;
  coverage: CandleCoverage;
}

export interface ChartMarker {
  kind: string;
  ts: string;
  instrument: string;
  label: string;
  price: string;
  direction: string | null;
  level_name: string | null;
}

export interface FvgBox {
  id: number;
  ts: string;
  instrument: string;
  type: string;
  top: string;
  bottom: string;
  midpoint: string;
  sweep_id: number;
}

export interface SignalMarker {
  id: number;
  ts: string;
  instrument: string;
  direction: string;
  entry: string;
  stop: string;
  target: string;
  status: string;
}

export interface TradeMarker {
  id: number;
  signal_id: number;
  side: string;
  units: string;
  entry_price: string;
  entry_ts: string;
  exit_price: string | null;
  exit_ts: string | null;
  pnl: string | null;
  r_multiple: string | null;
  exit_reason: string | null;
}

export interface MarkersPayload {
  markers: ChartMarker[];
  fvgs: FvgBox[];
  signals: SignalMarker[];
  trades: TradeMarker[];
}

export interface EventLogItem {
  id: number;
  ts: string;
  level: string;
  module: string;
  type: string;
  message: string;
  data: Record<string, unknown>;
}

export interface WebSocketEnvelope<TPayload = Record<string, unknown>> {
  type: string;
  sent_at: string;
  payload: TPayload;
}

export interface OptimizationStartResponse {
  study_id: number | null;
  status: string;
  trials: OptimizationTrialResult[];
  candidates: unknown[];
  best_trial_history: BestTrialPoint[];
  data_separation: Record<string, unknown>;
  research_protocol?: Record<string, unknown> | null;
}

export interface OptimizationTrialResult {
  trial_no: number;
  params: Record<string, unknown>;
  is_score: string;
  oos_score: string;
  robustness_score: string;
  pruned: boolean;
  status: string;
  failure_reason: string | null;
}

export interface BestTrialPoint {
  trial_no: number;
  oos_score: string;
  robustness_score: string;
}

export interface LabStudyProgress {
  study_id: number;
  status: string;
  trial_count: number;
  candidate_count: number;
  paper_variant_count: number;
  created_ts: string;
}

export interface CandidateScatterPoint {
  trial_id: number;
  trial_no: number;
  params: Record<string, unknown>;
  in_sample_score: string;
  out_of_sample_score: string;
  robustness_score: string;
  pruned: boolean;
  status: string;
  failure_reason: string | null;
  candidate_rejection_reason: string | null;
}

export interface PaperVariant {
  id: number;
  label: string;
  params: Record<string, unknown>;
  source_trial_id: number;
  status: "paper" | "promoted" | "retired";
  created_ts: string | null;
  trial_scores: Record<string, string>;
}

export interface VariantTrade {
  id?: number;
  variant_id: number;
  side: "long" | "short";
  units: string;
  entry_price: string;
  entry_ts: string;
  exit_price: string;
  exit_ts: string;
  pnl: string;
  r_multiple: string;
  exit_reason: string;
}

export interface VariantEquityPoint {
  variant_id: number;
  ts: string;
  nav: string;
  drawdown: string;
}

export interface VariantStats {
  variant_id: number;
  trade_count: number;
  win_rate: string;
  net_pnl: string;
  expectancy: string;
  average_r: string;
  max_drawdown: string;
  ending_nav: string;
  live_forward_score: string;
}

export interface VariantLeaderboardRow {
  rank: number;
  variant: PaperVariant;
  stats: VariantStats;
  out_of_sample_score: string;
  robustness_score: string;
}

export interface VariantEquityCurve {
  variant_id: number;
  points: VariantEquityPoint[];
}

export interface LabVariantOverview {
  variants: PaperVariant[];
  leaderboard: VariantLeaderboardRow[];
  equity_curves: VariantEquityCurve[];
  data_separation: Record<string, unknown>;
}

export interface LabSnapshot {
  study: LabStudyProgress;
  candidates: CandidateScatterPoint[];
  variants: LabVariantOverview;
  data_separation: Record<string, unknown>;
}

export interface LabActionResult {
  action: "create_paper_variant" | "retire_paper_variant" | "promote_practice_variant";
  variant_id: number;
  status: "paper" | "promoted" | "retired" | "not_found";
}

export interface TradingControlPayload {
  enabled: boolean;
  confirmation_token: string;
}

export interface FlattenControlPayload {
  confirmation_token: string;
  reason: string;
}

export interface ReconciliationSummary {
  checked_ts: string;
  transaction_count: number;
  bot_open_trade_count: number;
  broker_open_trade_count: number;
  broker_open_position_count: number;
  drift_detected: boolean;
  checkpoint_transaction_id: string | null;
}

export interface FlattenResult {
  requested_ts: string;
  reason: string;
  closed_trade_ids: string[];
  closed_position_instruments: string[];
  reconciliation: ReconciliationSummary;
}

export interface TradeJournalItem {
  id: number;
  signal_id: number;
  signal_key: string;
  instrument: string;
  signal_status: string;
  side: "long" | "short";
  units: string;
  entry_price: string;
  entry_ts: string;
  exit_price: string | null;
  exit_ts: string | null;
  pnl: string | null;
  r_multiple: string | null;
  exit_reason: string | null;
  broker_order_id: string | null;
  client_order_id: string | null;
  broker_trade_id: string | null;
  open_transaction_id: string | null;
  close_transaction_id: string | null;
}

export interface TradesResponse {
  trades: TradeJournalItem[];
}

export interface BacktestRunSummary {
  run_id: number;
  created_ts: string;
  params: Record<string, unknown>;
  stats: Record<string, unknown>;
  trade_count: number;
}

export interface BacktestRunsResponse {
  runs: BacktestRunSummary[];
}

export interface BacktestRunDetail {
  run_id: number | null;
  created_ts: string;
  params: Record<string, unknown>;
  stats: Record<string, unknown>;
  trades: Record<string, unknown>[];
}

export interface BacktestStartPayload {
  source?: "persisted_candles";
  instrument: string;
  candle_range?: { from: string; to: string };
  candle_window_days?: number;
  fixture?: string;
  candles?: Record<string, unknown>[];
  strategy_params?: Record<string, unknown>;
  variant_id?: number;
  variant_label?: string;
  backtest_config?: Record<string, unknown>;
  instrument_rules?: Record<string, unknown>;
}

export interface OptimizationStartPayload {
  source?: "persisted_candles";
  instrument?: string;
  candle_range?: { from: string; to: string };
  fixture?: string;
  candles?: Record<string, unknown>[];
  optimizer_config?: Record<string, unknown>;
  backtest_config?: Record<string, unknown>;
  instrument_rules?: Record<string, unknown>;
}

export interface OptimizerStudySummary {
  study_id: number;
  created_ts: string;
  status: string;
  search_space_json: Record<string, unknown>;
  walkforward_json: Record<string, unknown>;
  best_trial_id: number | null;
  trial_count: number;
  candidate_count: number;
}

export interface OptimizationStudiesResponse {
  studies: OptimizerStudySummary[];
}

export interface VariantDetail {
  variant: PaperVariant;
  trades: VariantTrade[];
  equity_curve: VariantEquityPoint[];
}

export interface ConfigEntry {
  key: string;
  value: Record<string, unknown>;
}

export interface ConfigSnapshot {
  values: ConfigEntry[];
}

export interface ConfigUpdateRequest {
  updates: Record<string, Record<string, unknown>>;
  confirmation: string;
}

export interface ConfigDiffItem {
  key: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface ConfigUpdateResult extends ConfigSnapshot {
  status: string;
  updated_ts: string;
  diff: ConfigDiffItem[];
}

export interface VariantEquityEnvelope {
  variant_id: number;
  points: VariantEquityPoint[];
}

export interface LabStatusEnvelope {
  study_id?: number;
  status: string;
  message?: string;
}

export type { OptimizationPreflightResponse } from "./optimizerTypes";
import type { CandleHistoricalImportPolicy, CandleLiveStreamStatus } from "./candleTypes";
