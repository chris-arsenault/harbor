import { afterEach, expect, test, vi } from "vitest";

import {
  fetchCandles,
  fetchEvents,
  fetchLevels,
  fetchMarkers,
  fetchStatus,
  flattenNow,
  promoteVariant,
  setTradingEnabled,
} from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

test("fetchStatus reads the status endpoint through the shared client", async () => {
  const fetchMock = mockJsonFetch({ bot_state: "WAIT_SWEEP" });

  await expect(fetchStatus()).resolves.toEqual({ bot_state: "WAIT_SWEEP" });

  expect(fetchMock).toHaveBeenCalledWith("/api/status", {
    headers: { Accept: "application/json" },
  });
});

test("fetchLevels and fetchCandles encode query parameters", async () => {
  const fetchMock = mockJsonFetch({ date: "2026-01-15", instrument: "EUR_USD" });

  await fetchLevels({ date: "2026-01-15", instrument: "EUR_USD" });
  await fetchCandles({
    instrument: "EUR_USD",
    from: "2026-01-15T14:00:00Z",
    to: "2026-01-15T15:00:00Z",
  });

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/levels?date=2026-01-15&instrument=EUR_USD", {
    headers: { Accept: "application/json" },
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "/api/candles?instrument=EUR_USD&from=2026-01-15T14%3A00%3A00Z&to=2026-01-15T15%3A00%3A00Z",
    { headers: { Accept: "application/json" } }
  );
});

test("fetchMarkers preserves server-authored overlay payloads", async () => {
  mockJsonFetch({
    markers: [{ kind: "sweep", label: "asia_low swept" }],
    fvgs: [{ sweep_id: 3 }],
    signals: [{ entry: "1.10500000" }],
    trades: [{ exit_reason: "target" }],
  });

  const markers = await fetchMarkers({ date: "2026-01-15", instrument: "EUR_USD" });

  expect(markers.markers[0]?.kind).toBe("sweep");
  expect(markers.fvgs[0]?.sweep_id).toBe(3);
  expect(markers.signals[0]?.entry).toBe("1.10500000");
  expect(markers.trades[0]?.exit_reason).toBe("target");
});

test("fetchEvents supports optional level and limit filters", async () => {
  const fetchMock = mockJsonFetch([{ level: "warn" }]);

  await fetchEvents({ level: "warn", limit: 5 });

  expect(fetchMock).toHaveBeenCalledWith("/api/events?level=warn&limit=5", {
    headers: { Accept: "application/json" },
  });
});

test("practice control clients post guarded mutation payloads", async () => {
  const fetchMock = mockJsonFetch({ status: "promoted" });

  await promoteVariant(7);
  await setTradingEnabled({ enabled: true, confirmation_token: "OANDA_PRACTICE" });
  await flattenNow({ confirmation_token: "OANDA_PRACTICE", reason: "manual" });

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/variants/7/promote", {
    body: "{}",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    method: "POST",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/control/trading", {
    body: JSON.stringify({ enabled: true, confirmation_token: "OANDA_PRACTICE" }),
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    method: "POST",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/control/flatten", {
    body: JSON.stringify({ confirmation_token: "OANDA_PRACTICE", reason: "manual" }),
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    method: "POST",
  });
});

test("api requests throw for non-ok responses", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("missing", { status: 404 }));

  await expect(fetchStatus()).rejects.toThrow("GET /api/status failed with 404");
});

function mockJsonFetch(payload: unknown) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }))
    );
}
