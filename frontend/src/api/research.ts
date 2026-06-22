import { apiGet } from "./client";

export interface ForwardSummary {
  count: number;
  mean_pips: string;
  median_pips: string;
  hit_rate: string;
  stddev_pips: string;
  t_stat: string;
}

export interface ConditionalEdge {
  dimension: string;
  value: string;
  summary: ForwardSummary;
  has_edge: boolean;
}

export interface EdgeStudyResult {
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
}

export function fetchEdgeStudy(params: {
  instrument: string;
  horizon?: number;
}): Promise<EdgeStudyResult> {
  const search = new URLSearchParams({ instrument: params.instrument });
  if (params.horizon !== undefined) {
    search.set("horizon", String(params.horizon));
  }
  return apiGet<EdgeStudyResult>(`/api/research/edge?${search.toString()}`);
}
