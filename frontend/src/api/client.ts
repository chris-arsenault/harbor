import type {
  BacktestRunDetail,
  BacktestRunsResponse,
  BacktestStartPayload,
  CandleImportRequest,
  CandleImportResult,
  CandlePoint,
  CandleSourceStatus,
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
  OptimizationStartPayload,
  SessionLevelSnapshot,
  StatusSnapshot,
  TradingControlPayload,
  TradesResponse,
  VariantDetail,
} from "./types";
import type { OptimizationPreflightResponse } from "./optimizerTypes";
import { expireAuthSession, getAccessToken, refreshAccessToken } from "../auth/cognito";

const API_BASE_URL = "";

type ApiRequest =
  | { readonly json: false; readonly method: "GET"; readonly path: string }
  | {
      readonly body: string;
      readonly json: true;
      readonly method: "POST" | "PUT";
      readonly path: string;
    };

async function apiHeaders(
  json = false,
  tokenOverride: string | null = null
): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json) headers["Content-Type"] = "application/json";
  const token = tokenOverride ?? (await getAccessToken());
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function apiGet<TResponse>(path: string): Promise<TResponse> {
  return apiRequest<TResponse>({ json: false, method: "GET", path });
}

export async function apiPost<TResponse>(path: string, payload: unknown = {}): Promise<TResponse> {
  return apiRequest<TResponse>({ body: JSON.stringify(payload), json: true, method: "POST", path });
}

export async function apiPut<TResponse>(path: string, payload: unknown): Promise<TResponse> {
  return apiRequest<TResponse>({ body: JSON.stringify(payload), json: true, method: "PUT", path });
}

async function apiRequest<TResponse>(request: ApiRequest): Promise<TResponse> {
  const response = await fetchApi(request);
  const finalResponse =
    response.status === 401 ? await retryAfterAuthRefresh(request, response) : response;
  if (finalResponse.status === 401) {
    expireAuthSession();
  }
  if (!finalResponse.ok) {
    throw new Error(await responseErrorMessage(finalResponse, request.method, request.path));
  }
  return (await finalResponse.json()) as TResponse;
}

async function fetchApi(
  request: ApiRequest,
  tokenOverride: string | null = null
): Promise<Response> {
  const init: RequestInit = {
    headers: await apiHeaders(request.json, tokenOverride),
  };
  if (request.method !== "GET") {
    init.body = request.body;
    init.method = request.method;
  }
  return fetch(`${API_BASE_URL}${request.path}`, init);
}

async function retryAfterAuthRefresh(request: ApiRequest, response: Response): Promise<Response> {
  const refreshedToken = await refreshAccessToken();
  if (!refreshedToken) return response;
  return fetchApi(request, refreshedToken);
}

async function responseErrorMessage(response: Response, method: string, path: string) {
  const fallback = `${method} ${path} failed with ${response.status}`;
  const detail = await responseDetail(response);
  return detail ? `${fallback}: ${detail}` : fallback;
}

async function responseDetail(response: Response): Promise<string | null> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const payload: unknown = await response.json().catch((): null => null);
    if (isRecord(payload) && typeof payload.detail === "string") {
      return payload.detail;
    }
    if (isRecord(payload) && payload.detail !== undefined) {
      return JSON.stringify(payload.detail);
    }
    return null;
  }
  const text = await response.text().catch(() => "");
  return text.trim() || null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function fetchStatus(): Promise<StatusSnapshot> {
  return apiGet<StatusSnapshot>("/api/status");
}

export function fetchLevels(params: {
  date: string;
  instrument: string;
}): Promise<SessionLevelSnapshot | null> {
  return apiGet<SessionLevelSnapshot | null>(withQuery("/api/levels", params));
}

export function fetchCandles(params: {
  instrument: string;
  from: string;
  to: string;
}): Promise<CandlePoint[]> {
  return apiGet<CandlePoint[]>(withQuery("/api/candles", params));
}

export function fetchCandleSource(
  params: { instrument?: string } = {}
): Promise<CandleSourceStatus> {
  return apiGet<CandleSourceStatus>(withQuery("/api/candles/source", params));
}

export function importHistoricalCandles(
  payload: CandleImportRequest = {}
): Promise<CandleImportResult> {
  return apiPost<CandleImportResult>("/api/candles/import", payload);
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
  payload: OptimizationStartPayload
): Promise<OptimizationStartResponse> {
  return apiPost<OptimizationStartResponse>("/api/optimize", payload);
}

export function preflightOptimization(
  payload: OptimizationStartPayload
): Promise<OptimizationPreflightResponse> {
  return apiPost<OptimizationPreflightResponse>("/api/optimize/preflight", payload);
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
