export interface CandleHistoricalImportPolicy {
  page_size: number;
  default_count: number;
  request_interval_seconds: number;
  upsert_key: string;
  replaces_existing: boolean;
}

export interface CandleLiveStreamStatus {
  configured: boolean;
  enabled: boolean;
  running: boolean;
  state: string;
  starts_on_api_boot: boolean;
  paper_forward_on_closed_candle: boolean;
  instruments: string[];
  heartbeat_timeout_seconds: number;
  reconnect_initial_seconds: number;
  reconnect_max_seconds: number;
  last_started_at: string | null;
  last_stopped_at: string | null;
  last_error: unknown;
}
