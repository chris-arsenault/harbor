import type { CandleImportRequest, CandleImportResult } from "../api/types";

export function aggregateImportResult(
  results: CandleImportResult[],
  payload: CandleImportRequest
): CandleImportResult {
  const first = results[0];
  return {
    status: "completed",
    source: "oanda_historical_import",
    instrument: "research_universe",
    instruments: results.map((result) => result.instrument),
    requested_count: results.reduce((total, result) => total + result.requested_count, 0),
    imported_count: results.reduce((total, result) => total + result.imported_count, 0),
    from: payload.from ?? first?.from ?? null,
    coverage: first?.coverage ?? {
      instrument: "research_universe",
      candle_count: 0,
      from: null,
      to: null,
    },
    results: results.map((result) => ({
      instrument: result.instrument,
      requested_count: result.requested_count,
      imported_count: result.imported_count,
      coverage: result.coverage,
    })),
  };
}
