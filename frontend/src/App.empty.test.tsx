import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { status } from "./App.fixtures";
import type { LiveChartAdapter, LiveChartHandle } from "./components/chartAdapter";

type FetchInput = string | URL | Request;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(emptyDeploymentFetchResponse));
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("does not request a fixed lab study when the empty deployment has no studies", async () => {
  renderWithClient(<App chartAdapter={fakeChartAdapter()} />);

  expect(await screen.findByText("WAIT_SWEEP")).toBeInTheDocument();
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/optimize?limit=50", expect.anything())
  );
  expect(fetch).not.toHaveBeenCalledWith("/api/optimize/1", expect.anything());

  fireEvent.click(screen.getByRole("button", { name: "Lab" }));

  expect(screen.getByText("No tuning studies yet")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Start tuning study" }));

  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/optimize", {
      body: JSON.stringify({
        fixture: "clean_signal_day.json",
        optimizer_config: { trial_count: 25 },
      }),
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

function fakeChartAdapter(): LiveChartAdapter {
  return {
    mount: vi.fn((): LiveChartHandle => {
      return {
        setCandles: vi.fn(),
        setLevels: vi.fn(),
        setMarkers: vi.fn(),
        destroy: vi.fn(),
      };
    }),
  };
}

function emptyDeploymentFetchResponse(input: FetchInput) {
  const url = requestUrl(input);
  if (url.startsWith("/api/levels")) {
    return Promise.resolve(new Response("null", { status: 200 }));
  }
  return Promise.resolve(
    new Response(JSON.stringify(emptyDeploymentRoutePayload(url)), { status: 200 })
  );
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

function emptyDeploymentRoutePayload(url: string): unknown {
  if (url.startsWith("/api/status")) {
    return status;
  }
  if (url.startsWith("/api/candles") || url.startsWith("/api/events")) {
    return [];
  }
  if (url.startsWith("/api/markers")) {
    return { markers: [], fvgs: [], signals: [], trades: [] };
  }
  if (url.startsWith("/api/trades")) {
    return { trades: [] };
  }
  if (url.startsWith("/api/backtests")) {
    return { runs: [] };
  }
  if (url.startsWith("/api/config")) {
    return { values: [] };
  }
  if (url.startsWith("/api/optimize?")) {
    return { studies: [] };
  }
  if (url.startsWith("/api/variants")) {
    return { variants: [], leaderboard: [], equity_curves: [], data_separation: null };
  }
  return {};
}

interface FakeWebSocketInstance {
  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  close: () => undefined;
}

function FakeWebSocket(this: FakeWebSocketInstance, url: string) {
  this.url = url;
  this.onmessage = null;
  this.onerror = null;
  this.close = () => undefined;
}
