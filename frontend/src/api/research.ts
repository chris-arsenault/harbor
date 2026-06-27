import { apiGet, apiPost } from "./client";

export interface ForwardSummary {
  count: number;
  mean_pips: string;
  median_pips: string;
  hit_rate: string;
  stddev_pips: string;
  t_stat: string;
  naive_t_stat: string;
  standard_error_pips: string;
  effective_sample_size: number;
  p_value: string;
  bonferroni_p_value: string;
  correction: string;
}

export interface ConditionalEdge {
  dimension: string;
  value: string;
  summary: ForwardSummary;
  has_edge: boolean;
  family_test_count: number;
}

export interface EdgeStatisticalNotes {
  mean_null_hypothesis?: string;
  tail?: string;
  alpha?: string;
  minimum_observations?: number;
  minimum_effective_samples?: number;
  t_threshold?: string;
  standard_error_correction?: string;
  effective_sample_unit?: string;
  conditional_test_count?: number;
  conditional_multiple_test_method?: string;
  instrument_count?: number;
  algorithm_count?: number;
  horizon_count?: number;
  planned_overall_test_count?: number;
  overall_test_count?: number;
  overall_multiple_test_method?: string;
}

export interface EdgeStudyResult {
  algorithm_id: string;
  hypothesis_id: string;
  algorithm_label: string;
  instrument: string;
  horizon: number;
  total_candles: number;
  total_sweeps: number;
  overall: ForwardSummary;
  has_edge: boolean;
  baseline_mean_abs_pips: string;
  by_level: ConditionalEdge[];
  by_session: ConditionalEdge[];
  by_volatility: ConditionalEdge[];
  statistical_notes: EdgeStatisticalNotes;
  warnings?: EdgeDataWarning[];
  window?: EdgeDataWindow | null;
}

export function fetchEdgeStudy(params: {
  instrument: string;
  horizon?: number;
  algorithm_id?: string;
  window_days?: number;
}): Promise<EdgeStudyResult> {
  const search = new URLSearchParams({ instrument: params.instrument });
  if (params.horizon !== undefined) {
    search.set("horizon", String(params.horizon));
  }
  if (params.algorithm_id !== undefined) {
    search.set("algorithm_id", params.algorithm_id);
  }
  if (params.window_days !== undefined) {
    search.set("window_days", String(params.window_days));
  }
  return apiGet<EdgeStudyResult>(`/api/research/edge?${search.toString()}`);
}

export interface EdgeScanRow {
  algorithm_id: string;
  hypothesis_id: string;
  algorithm_label: string;
  instrument: string;
  horizon: number;
  total_sweeps: number;
  overall: ForwardSummary;
  has_edge: boolean;
  best_conditional: ConditionalEdge | null;
  statistical_notes: EdgeStatisticalNotes;
}

export interface EdgeScanResult {
  instruments: string[];
  horizons: number[];
  requested_window_days?: number;
  windows?: EdgeDataWindow[];
  warnings?: EdgeDataWarning[];
  algorithms: EdgeAlgorithm[];
  results: EdgeScanRow[];
  statistical_notes?: EdgeStatisticalNotes;
}

export interface EdgeDataWindow {
  instrument: string | null;
  from: string;
  to: string;
  requested_days: number | null;
  available_days: number | null;
  used_days: number | null;
}

export interface EdgeDataWarning {
  instrument: string;
  type: string;
  message: string;
  requested_days?: number;
  available_days?: number;
  used_days?: number;
}

export interface EdgeAlgorithm {
  algorithm_id: string;
  hypothesis_id: string;
  label: string;
  description: string;
}

export interface EdgeScanPayload {
  instruments: string[] | null;
  horizons: number[] | null;
  algorithms: string[] | null;
  window_days: number;
}

export function fetchEdgeScan(payload: EdgeScanPayload): Promise<EdgeScanResult> {
  return apiPost<EdgeScanResult>("/api/research/edge/scan", payload);
}

export interface CaptureStats {
  count: number;
  hit_rate: string;
  mean_gross_pips: string;
  mean_net_pips: string;
  median_net_pips: string;
  total_net_pips: string;
  average_mfe_pips: string;
  average_mae_pips: string;
}

export interface CaptureRow {
  algorithm_id: string;
  hypothesis_id: string;
  algorithm_label: string;
  instrument: string;
  horizon: number;
  event_count: number;
  stats: CaptureStats;
  spread_pips: string;
  slippage_pips: string;
  entry_model: string;
  exit_model: string;
}

export interface CaptureResult {
  instrument: string;
  horizons: number[];
  algorithms: EdgeAlgorithm[];
  spread_pips: string;
  slippage_pips: string;
  requested_window_days: number;
  window: EdgeDataWindow | null;
  warnings: EdgeDataWarning[];
  results: CaptureRow[];
}

export interface CapturePayload {
  instrument: string;
  horizons: number[];
  algorithms: string[];
  window_days: number;
  spread_pips: string;
  slippage_pips: string;
}

export function fetchCaptureScan(payload: CapturePayload): Promise<CaptureResult> {
  return apiPost<CaptureResult>("/api/research/capture", payload);
}

export interface CrossStats {
  count: number;
  hit_rate: string;
  mean_return_bps: string;
  median_return_bps: string;
  total_return_bps: string;
  t_stat: string;
}

export interface CrossScanRow {
  algorithm_id: string;
  hypothesis_id: string;
  algorithm_label: string;
  instruments: string[];
  observation_count: number;
  stats: CrossStats;
}

export interface CrossScanResult {
  instruments: string[];
  requested_window_days: number;
  windows: EdgeDataWindow[];
  warnings: EdgeDataWarning[];
  algorithms: EdgeAlgorithm[];
  results: CrossScanRow[];
}

export interface CrossScanPayload {
  instruments: string[] | null;
  algorithms: string[] | null;
  window_days: number;
}

export function fetchCrossScan(payload: CrossScanPayload): Promise<CrossScanResult> {
  return apiPost<CrossScanResult>("/api/research/cross/scan", payload);
}

export interface BookRecorderRuntime {
  running: boolean;
  state: string;
  last_started_at?: string | null;
  last_stopped_at?: string | null;
  last_error?: string | null;
}

export interface BookCoverageRow {
  book_type: string;
  instrument: string;
  snapshot_count: number;
  from: string | null;
  to: string | null;
  latest_mid_price: string | null;
}

export interface LatestBookSnapshot {
  snapshot_time: string;
  bucket_count: number;
  mid_price?: string | null;
  recorded_ts?: string | null;
}

export interface InstrumentBookLatest {
  order: LatestBookSnapshot | null;
  position: LatestBookSnapshot | null;
}

export interface BookRecorderStatus {
  recorder: BookRecorderRuntime;
  coverage: BookCoverageRow[];
  latest: Record<string, InstrumentBookLatest>;
}

export function fetchBookRecorderStatus(): Promise<BookRecorderStatus> {
  return apiGet<BookRecorderStatus>("/api/research/books/status");
}
