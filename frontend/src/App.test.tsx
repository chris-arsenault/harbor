import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { candle, event, labSnapshot, labVariants, levels, markers, status } from "./App.fixtures";
import type { LiveChartAdapter, LiveChartHandle } from "./components/chartAdapter";

beforeEach(() => {
  fakeWebSocketInstances.length = 0;
  vi.stubGlobal("fetch", vi.fn(fetchResponse));
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("renders the cockpit from REST data as the first screen", async () => {
  renderWithClient(<App chartAdapter={fakeChartAdapter()} />);

  expect(await screen.findByRole("heading", { name: "Cockpit" })).toBeInTheDocument();
  expect((await screen.findAllByText("WAIT_SWEEP")).length).toBeGreaterThan(0);
  expect(screen.getByLabelText("Account vitals")).toHaveTextContent("+60.00");
  expect(screen.getByLabelText("Feed heartbeat")).toHaveTextContent("stale");
});

test("applies live websocket status and candle envelopes", async () => {
  const handle: LiveChartHandle = {
    setCandles: vi.fn(),
    setLevels: vi.fn(),
    setMarkers: vi.fn(),
    destroy: vi.fn(),
  };
  renderWithClient(<App chartAdapter={fakeChartAdapter(handle)} />);
  expect(await screen.findByRole("heading", { name: "Cockpit" })).toBeInTheDocument();
  expect((await screen.findAllByText("WAIT_SWEEP")).length).toBeGreaterThan(0);

  fakeWebSocketInstances[0]?.emit({
    type: "status",
    sent_at: "2026-01-15T14:32:00Z",
    payload: { ...status, bot_state: "WAIT_FVG" },
  });
  fakeWebSocketInstances[0]?.emit({
    type: "candle",
    sent_at: "2026-01-15T14:33:00Z",
    payload: {
      instrument: "EUR_USD",
      ts: "2026-01-15T14:33:00Z",
      open: "1.20000000",
      high: "1.20500000",
      low: "1.19900000",
      close: "1.20400000",
      volume: 75,
      complete: true,
    },
  });

  expect((await screen.findAllByText("WAIT_FVG")).length).toBeGreaterThan(0);
  await waitFor(() =>
    expect(handle.setCandles).toHaveBeenLastCalledWith(
      expect.arrayContaining([expect.objectContaining({ close: "1.20400000" })])
    )
  );
});

test("renders Lab as a secondary view and applies variant live envelopes", async () => {
  renderWithClient(<App chartAdapter={fakeChartAdapter()} />);
  expect(await screen.findByRole("heading", { name: "Cockpit" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Lab" }));

  expect(await screen.findByRole("region", { name: "Study progress" })).toHaveTextContent(
    "completed"
  );
  expect(screen.getByRole("img", { name: "Trial score scatter" })).toHaveAttribute(
    "data-points",
    "0:1.25:1.50"
  );
  expect(screen.getByRole("region", { name: "Variant leaderboard" })).toHaveTextContent(
    "candidate-1"
  );

  fakeWebSocketInstances[0]?.emit({
    type: "variant_equity",
    sent_at: "2026-01-15T14:34:00Z",
    payload: {
      variant_id: 7,
      points: [
        {
          variant_id: 7,
          ts: "2026-01-15T14:44:00Z",
          nav: "10080.00000000",
          drawdown: "0",
        },
      ],
    },
  });
  fakeWebSocketInstances[0]?.emit({
    type: "lab_status",
    sent_at: "2026-01-15T14:35:00Z",
    payload: { status: "paper updated" },
  });

  await waitFor(() =>
    expect(screen.getByLabelText("Variant equity curve")).toHaveAttribute(
      "data-points",
      "2026-01-15T14:44:00Z:10080.00000000"
    )
  );
  expect(screen.getByText("paper updated")).toBeInTheDocument();
});

test("renders guarded practice controls and posts enable requests", async () => {
  renderWithClient(<App chartAdapter={fakeChartAdapter()} />);

  expect(await screen.findByRole("heading", { name: "Cockpit" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Operations" }));
  expect(screen.getByText("5e43815abcde")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Confirmation"), {
    target: { value: "OANDA_PRACTICE" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enable practice trading" }));

  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/control/trading", {
      body: JSON.stringify({ enabled: true, confirmation_token: "OANDA_PRACTICE" }),
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      method: "POST",
    })
  );
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function fakeChartAdapter(handle: LiveChartHandle = defaultChartHandle()): LiveChartAdapter {
  return {
    mount: vi.fn(() => handle),
  };
}

function defaultChartHandle(): LiveChartHandle {
  return {
    setCandles: vi.fn(),
    setLevels: vi.fn(),
    setMarkers: vi.fn(),
    destroy: vi.fn(),
  };
}

type FetchInput = string | URL | Request;

function fetchResponse(input: FetchInput) {
  const url = requestUrl(input);
  return Promise.resolve(new Response(routePayloadJson(url), { status: 200 }));
}

function requestUrl(input: FetchInput) {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function routePayloadJson(url: string): string {
  return JSON.stringify(routePayload(url));
}

function routePayload(url: string): unknown {
  return (
    controlRoutePayload(url) ??
    dashboardRoutePayload(url) ??
    productRoutePayload(url) ??
    labRoutePayload(url) ??
    {}
  );
}

function controlRoutePayload(url: string): unknown {
  if (url.startsWith("/api/status")) {
    return status;
  }
  if (url.startsWith("/api/control/trading")) {
    return { ...status, trading_enabled: true };
  }
  if (url.startsWith("/api/control/flatten")) {
    return {
      requested_ts: "2026-01-15T16:59:00Z",
      reason: "manual",
      closed_trade_ids: ["7001"],
      closed_position_instruments: ["EUR_USD"],
      reconciliation: {
        checked_ts: "2026-01-15T17:00:00Z",
        transaction_count: 0,
        bot_open_trade_count: 0,
        broker_open_trade_count: 0,
        broker_open_position_count: 0,
        drift_detected: false,
        checkpoint_transaction_id: "9201",
      },
    };
  }
  return undefined;
}

function dashboardRoutePayload(url: string): unknown {
  if (url.startsWith("/api/levels")) {
    return levels;
  }
  if (url.startsWith("/api/candles/source")) {
    return {
      instrument: "EUR_USD",
      primary_source: "persisted_candles",
      granularity: "M1",
      price_component: "midpoint",
      coverage: {
        instrument: "GBP_USD",
        candle_count: 70000,
        from: "2026-01-15T00:00:00+00:00",
        to: "2026-01-16T23:59:00+00:00",
      },
      instrument_coverages: [
        {
          instrument: "GBP_USD",
          candle_count: 70000,
          from: "2026-01-15T00:00:00+00:00",
          to: "2026-01-16T23:59:00+00:00",
        },
        {
          instrument: "EUR_USD",
          candle_count: 2880,
          from: "2026-01-15T00:00:00+00:00",
          to: "2026-01-16T23:59:00+00:00",
        },
      ],
      source_methods: ["oanda_historical_import", "oanda_pricing_stream"],
      research_instruments: ["GBP_USD", "EUR_USD", "USD_JPY"],
      historical_import: {
        page_size: 5000,
        default_count: 259200,
        request_interval_seconds: 0.1,
        upsert_key: "instrument+timestamp",
        replaces_existing: false,
      },
      oanda_historical_import_configured: true,
      live_stream: {
        configured: true,
        enabled: true,
        running: true,
        state: "running",
        starts_on_api_boot: true,
        paper_forward_on_closed_candle: true,
        instruments: ["GBP_USD", "EUR_USD", "USD_JPY"],
        heartbeat_timeout_seconds: 20,
        reconnect_initial_seconds: 1,
        reconnect_max_seconds: 30,
        last_started_at: "2026-01-15T13:55:00Z",
        last_stopped_at: null,
        last_error: null,
      },
    };
  }
  if (url.startsWith("/api/candles")) {
    return [candle];
  }
  if (url.startsWith("/api/markers")) {
    return markers;
  }
  if (url.startsWith("/api/events")) {
    return [event];
  }
  return undefined;
}

function productRoutePayload(url: string): unknown {
  if (url.startsWith("/api/trades")) {
    return { trades: [] };
  }
  if (url.startsWith("/api/backtests")) {
    return { runs: [] };
  }
  if (url.startsWith("/api/config")) {
    return { values: [] };
  }
  return undefined;
}

function labRoutePayload(url: string): unknown {
  if (url.startsWith("/api/optimize/preflight")) {
    return preflightRoutePayload();
  }
  if (url.startsWith("/api/optimize?")) {
    return { studies: [{ study_id: 1 }] };
  }
  if (url.startsWith("/api/optimize/1")) {
    return labSnapshot;
  }
  if (url.startsWith("/api/variants")) {
    return labVariants;
  }
  return undefined;
}

function preflightRoutePayload(): unknown {
  return {
    status: "ready",
    instrument: "GBP_USD",
    candle_source: {
      source: "persisted_candles",
      instrument: "GBP_USD",
      from: "2026-01-15T00:00:00+00:00",
      to: "2026-01-16T23:59:00+00:00",
    },
    study_config: {},
    candidate_gate: {
      requires: "completed trials with positive in-sample and out-of-sample scores",
      min_in_sample_trades: 12,
      min_out_of_sample_trades: 4,
    },
    dataset: {
      candle_count: 70000,
      session_day_count: 120,
      evaluable_session_day_count: 120,
      partial_session_day_count: 0,
      first_evaluable_trading_date: "2026-01-15",
      last_evaluable_trading_date: "2026-06-15",
      day_diagnostics: [],
    },
    walk_forward: {
      window_count: 3,
      required_session_days: 80,
      train_window_days: 60,
      out_of_sample_window_days: 20,
      step_days: 20,
      window_error: null,
      windows: [],
      omitted_window_count: 0,
    },
    baseline: null,
    research_protocol: {
      status: "ready",
      message: "ready",
      data_requirements: {
        trial_count: 96,
        candidate_count: 5,
        discovery_candidate_count: 5,
        min_evaluable_days: 120,
        min_discovery_days: 90,
        holdout_days: 30,
        max_session_gap_minutes: 1,
        min_holdout_trades: 5,
        train_window_days: 60,
        oos_window_days: 20,
        step_days: 20,
        min_in_sample_trades: 12,
        min_oos_trades: 4,
      },
      evaluable_day_count: 120,
      partial_day_count: 0,
      evaluable_days: [],
    },
    readiness: [
      { name: "candles", status: "pass", message: "70000 persisted closed candles selected" },
    ],
    recommended_payload: { source: "persisted_candles", instrument: "GBP_USD" },
  };
}

interface FakeWebSocketInstance {
  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  close: () => undefined;
  emit: (envelope: object) => void;
}

const fakeWebSocketInstances: FakeWebSocketInstance[] = [];

function FakeWebSocket(this: FakeWebSocketInstance, url: string) {
  this.url = url;
  this.onmessage = null;
  this.onerror = null;
  this.close = () => undefined;
  this.emit = (envelope) => {
    this.onmessage?.({ data: JSON.stringify(envelope) } as MessageEvent<string>);
  };
  fakeWebSocketInstances.push(this);
}
