import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { DataImportView } from "./DataView";

type FetchInput = string | URL | Request;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(fetchResponse));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("shows universe coverage with data quality and syncs the universe", async () => {
  renderWithClient(<DataImportView />);

  expect(await screen.findByRole("heading", { name: "Data" })).toBeInTheDocument();
  expect(await screen.findByRole("region", { name: "Historical backfill" })).toBeInTheDocument();
  expect(screen.getByLabelText("Month coverage")).toHaveTextContent("75%");
  // Per-instrument coverage rows render with bid/ask data-quality tags.
  expect((await screen.findAllByText("GBP_USD")).length).toBeGreaterThan(0);
  expect(screen.getByText("EUR_USD")).toBeInTheDocument();
  expect(screen.getByText("bid/ask 100%")).toBeInTheDocument();
  expect(screen.getByText("bid/ask 0%")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Sync universe" }));

  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/candles/sync", {
      body: JSON.stringify({ days: 180 }),
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      method: "POST",
    })
  );
  expect(await screen.findByText(/new candles\s+sourced/)).toBeInTheDocument();
});

test("starts the one-click backfill job", async () => {
  renderWithClient(<DataImportView />);

  await screen.findByText("ready");
  fireEvent.click(screen.getByRole("button", { name: "Collect missing data" }));

  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/candles/backfill", {
      body: JSON.stringify({}),
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      method: "POST",
    })
  );
});

test("repairs bid/ask on an instrument that lacks it via a forced re-fetch", async () => {
  renderWithClient(<DataImportView />);

  // EUR_USD has bid/ask 0%, so its row action is "Repair" (not "Sync").
  fireEvent.click(await screen.findByRole("button", { name: "Repair" }));

  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/candles/sync", {
      body: JSON.stringify({ instrument: "EUR_USD", days: 180, repair: true }),
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      method: "POST",
    })
  );
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function requestUrl(input: FetchInput): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.toString() : input.url;
}

function fetchResponse(input: FetchInput) {
  const url = requestUrl(input);
  if (url.startsWith("/api/candles/backfill")) {
    return json(backfillStatus);
  }
  if (url.startsWith("/api/candles/sync")) {
    return json({
      status: "completed",
      days: 180,
      reports: [
        { instrument: "GBP_USD", imported: 500, candle_count: 70000, from: null, to: null },
      ],
    });
  }
  if (url.startsWith("/api/candles/source")) {
    return json(sourceStatus);
  }
  return json({});
}

function json(payload: unknown) {
  return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }));
}

const sourceStatus = {
  instrument: "GBP_USD",
  primary_source: "persisted_candles",
  granularity: "M1",
  price_component: "bid_ask_mid",
  coverage: {
    instrument: "GBP_USD",
    candle_count: 70000,
    from: "2026-01-01",
    to: "2026-06-01",
    bid_ask_count: 70000,
  },
  instrument_coverages: [
    {
      instrument: "GBP_USD",
      candle_count: 70000,
      from: "2026-01-01",
      to: "2026-06-01",
      bid_ask_count: 70000,
    },
    {
      instrument: "EUR_USD",
      candle_count: 2880,
      from: "2026-05-01",
      to: "2026-05-02",
      bid_ask_count: 0,
    },
  ],
  source_methods: ["oanda_historical_import"],
  research_instruments: ["GBP_USD", "EUR_USD"],
  historical_import: {
    page_size: 5000,
    default_count: 259200,
    request_interval_seconds: 0.1,
    upsert_key: "instrument+timestamp",
    replaces_existing: false,
  },
  oanda_historical_import_configured: true,
};

const backfillStatus = {
  status: "completed",
  job_id: "job-1",
  started_at: "2026-06-27T12:00:00Z",
  finished_at: "2026-06-27T12:10:00Z",
  error: null,
  current_instrument: null,
  imported_count: 500,
  completed_ranges: 1,
  total_ranges: 4,
  historical: {
    start: "2024-06-27",
    end: "2025-12-27",
    expected_days: 4,
    loaded_days: 3,
    missing_days: 1,
    filled_days: 0,
    pending_days: 1,
  },
  recent: { pending_ranges: 1, completed_ranges: 0 },
  instruments: [
    {
      instrument: "GBP_USD",
      status: "completed",
      imported_count: 500,
      completed_ranges: 1,
      total_ranges: 4,
      recent: {
        status: "pending",
        from: "2026-06-20T12:00:00Z",
        to: "2026-06-27T12:00:00Z",
        imported_count: 0,
      },
      historical: {
        expected_days: 4,
        loaded_days: 3,
        missing_days: 1,
        filled_days: 0,
        pending_days: 1,
        months: [
          {
            month: "2024-06",
            expected_days: 4,
            loaded_days: 3,
            missing_days: 1,
            filled_days: 0,
            pending_days: 1,
            complete_days: 3,
            completion_ratio: 0.75,
          },
        ],
      },
    },
  ],
};
