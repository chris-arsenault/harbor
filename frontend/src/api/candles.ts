import { apiGet, apiPost } from "./client";

export interface CandleSyncReport {
  instrument: string;
  imported: number;
  candle_count: number;
  from: string | null;
  to: string | null;
}

export interface CandleSyncResult {
  status: string;
  days: number;
  reports: CandleSyncReport[];
}

export interface CandleBackfillMonth {
  month: string;
  expected_days: number;
  loaded_days: number;
  missing_days: number;
  filled_days: number;
  pending_days: number;
  complete_days: number;
  completion_ratio: number;
}

export interface CandleBackfillInstrument {
  instrument: string;
  status: string;
  imported_count: number;
  completed_ranges: number;
  total_ranges: number;
  recent: {
    status: string;
    from: string | null;
    to: string | null;
    imported_count: number;
  };
  historical: {
    expected_days: number;
    loaded_days: number;
    missing_days: number;
    filled_days: number;
    pending_days: number;
    months: CandleBackfillMonth[];
  };
}

export interface CandleBackfillStatus {
  status: "idle" | "running" | "completed" | "failed";
  job_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  current_instrument: string | null;
  imported_count: number;
  completed_ranges: number;
  total_ranges: number;
  historical: {
    start: string | null;
    end: string | null;
    expected_days: number;
    loaded_days: number;
    missing_days: number;
    filled_days: number;
    pending_days: number;
  };
  recent: {
    pending_ranges: number;
    completed_ranges: number;
  };
  instruments: CandleBackfillInstrument[];
}

export function syncCandles(payload: {
  instrument?: string;
  days?: number;
  repair?: boolean;
}): Promise<CandleSyncResult> {
  return apiPost<CandleSyncResult>("/api/candles/sync", payload);
}

export function fetchCandleBackfill(): Promise<CandleBackfillStatus> {
  return apiGet<CandleBackfillStatus>("/api/candles/backfill");
}

export function startCandleBackfill(): Promise<CandleBackfillStatus> {
  return apiPost<CandleBackfillStatus>("/api/candles/backfill", {});
}
