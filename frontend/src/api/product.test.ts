import { afterEach, expect, test, vi } from "vitest";

import {
  fetchBacktestRun,
  fetchBacktestRuns,
  fetchConfig,
  fetchOptimizationStudies,
  fetchTrades,
  fetchVariantDetail,
  startBacktest,
  updateConfig,
} from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

test("product clients read trades, backtests, tuning studies, variant detail, and config", async () => {
  const fetchMock = mockJsonFetch({ ok: true });

  await fetchTrades({
    from: "2026-01-15T14:00:00Z",
    to: "2026-01-15T17:00:00Z",
    limit: 25,
  });
  await fetchBacktestRuns({ limit: 10 });
  await fetchBacktestRun(42);
  await fetchOptimizationStudies({ limit: 5 });
  await fetchVariantDetail(7);
  await fetchConfig();

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "/api/trades?from=2026-01-15T14%3A00%3A00Z&to=2026-01-15T17%3A00%3A00Z&limit=25",
    { headers: { Accept: "application/json" } }
  );
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/backtests?limit=10", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/backtests/42", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/optimize?limit=5", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(5, "/api/variants/7", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(6, "/api/config", {
    headers: { Accept: "application/json" },
  });
});

test("product clients start experiments and update config with guarded payloads", async () => {
  const fetchMock = mockJsonFetch({ status: "updated" });

  await startBacktest({
    source: "persisted_candles",
    instrument: "EUR_USD",
    candle_range: {
      from: "2026-01-15T14:00:00Z",
      to: "2026-01-15T17:00:00Z",
    },
  });
  await updateConfig({
    updates: { risk_per_trade_pct: { value: 0.7 } },
    confirmation: "APPLY_CONFIG",
  });

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/backtests", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "persisted_candles",
      instrument: "EUR_USD",
      candle_range: {
        from: "2026-01-15T14:00:00Z",
        to: "2026-01-15T17:00:00Z",
      },
    }),
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/config", {
    method: "PUT",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      updates: { risk_per_trade_pct: { value: 0.7 } },
      confirmation: "APPLY_CONFIG",
    }),
  });
});

function mockJsonFetch(payload: unknown) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
    );
}
