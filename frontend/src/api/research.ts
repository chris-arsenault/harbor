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
