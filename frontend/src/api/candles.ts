import { apiPost } from "./client";

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

export function syncCandles(payload: {
  instrument?: string;
  days?: number;
}): Promise<CandleSyncResult> {
  return apiPost<CandleSyncResult>("/api/candles/sync", payload);
}
