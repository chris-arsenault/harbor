import type {
  BacktestRunDetail,
  BacktestRunsResponse,
  BacktestStartPayload,
  CandlePoint,
  ConfigSnapshot,
  ConfigUpdateRequest,
  ConfigUpdateResult,
  EventLogItem,
  FlattenControlPayload,
  FlattenResult,
  LabActionResult,
  LabSnapshot,
  LabVariantOverview,
  MarkersPayload,
  OptimizationStudiesResponse,
  OptimizationStartResponse,
  SessionLevelSnapshot,
  StatusSnapshot,
  TradingControlPayload,
  TradesResponse,
  VariantDetail,
} from "./types";

const API_BASE_URL = "";

export async function apiGet<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return (await response.json()) as TResponse;
}

export async function apiPost<TResponse>(path: string, payload: unknown = {}): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}`);
  }
  return (await response.json()) as TResponse;
}

export async function apiPut<TResponse>(path: string, payload: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`PUT ${path} failed with ${response.status}`);
  }
  return (await response.json()) as TResponse;
}

export function fetchStatus(): Promise<StatusSnapshot> {
  return apiGet<StatusSnapshot>("/api/status");
}

export function fetchLevels(params: {
  date: string;
  instrument: string;
}): Promise<SessionLevelSnapshot> {
  return apiGet<SessionLevelSnapshot>(withQuery("/api/levels", params));
}

export function fetchCandles(params: {
  instrument: string;
  from: string;
  to: string;
}): Promise<CandlePoint[]> {
  return apiGet<CandlePoint[]>(withQuery("/api/candles", params));
}

export function fetchMarkers(params: {
  date: string;
  instrument: string;
}): Promise<MarkersPayload> {
  return apiGet<MarkersPayload>(withQuery("/api/markers", params));
}

export function fetchEvents(
  params: {
    level?: string;
    limit?: number;
  } = {}
): Promise<EventLogItem[]> {
  return apiGet<EventLogItem[]>(withQuery("/api/events", params));
}

export function fetchTrades(params: {
  from: string;
  to: string;
  limit?: number;
}): Promise<TradesResponse> {
  return apiGet<TradesResponse>(withQuery("/api/trades", params));
}

export function startBacktest(payload: BacktestStartPayload): Promise<BacktestRunDetail> {
  return apiPost<BacktestRunDetail>("/api/backtests", payload);
}

export function fetchBacktestRuns(params: { limit?: number } = {}): Promise<BacktestRunsResponse> {
  return apiGet<BacktestRunsResponse>(withQuery("/api/backtests", params));
}

export function fetchBacktestRun(runId: number): Promise<BacktestRunDetail> {
  return apiGet<BacktestRunDetail>(`/api/backtests/${runId}`);
}

export function fetchOptimizationStudies(
  params: { limit?: number } = {}
): Promise<OptimizationStudiesResponse> {
  return apiGet<OptimizationStudiesResponse>(withQuery("/api/optimize", params));
}

export function startOptimization(
  payload: Record<string, unknown>
): Promise<OptimizationStartResponse> {
  return apiPost<OptimizationStartResponse>("/api/optimize", payload);
}

export function fetchLabStudy(studyId: number): Promise<LabSnapshot> {
  return apiGet<LabSnapshot>(`/api/optimize/${studyId}`);
}

export function fetchVariants(): Promise<LabVariantOverview> {
  return apiGet<LabVariantOverview>("/api/variants");
}

export function fetchVariantDetail(variantId: number): Promise<VariantDetail> {
  return apiGet<VariantDetail>(`/api/variants/${variantId}`);
}

export function createPaperVariant(payload: {
  trial_id: number;
  label?: string;
}): Promise<LabActionResult> {
  return apiPost<LabActionResult>("/api/variants", payload);
}

export function retirePaperVariant(variantId: number): Promise<LabActionResult> {
  return apiPost<LabActionResult>(`/api/variants/${variantId}/retire`);
}

export function promoteVariant(variantId: number): Promise<LabActionResult> {
  return apiPost<LabActionResult>(`/api/variants/${variantId}/promote`);
}

export function setTradingEnabled(payload: TradingControlPayload): Promise<StatusSnapshot> {
  return apiPost<StatusSnapshot>("/api/control/trading", payload);
}

export function flattenNow(payload: FlattenControlPayload): Promise<FlattenResult> {
  return apiPost<FlattenResult>("/api/control/flatten", payload);
}

export function fetchConfig(): Promise<ConfigSnapshot> {
  return apiGet<ConfigSnapshot>("/api/config");
}

export function updateConfig(payload: ConfigUpdateRequest): Promise<ConfigUpdateResult> {
  return apiPut<ConfigUpdateResult>("/api/config", payload);
}

function withQuery(path: string, params: Record<string, string | number | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}
