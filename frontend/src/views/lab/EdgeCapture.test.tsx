import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { EdgeCapture } from "./EdgeCapture";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("submits the H007 capture preset and renders net capture rows", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/capture")) {
      return Promise.resolve(new Response(JSON.stringify(captureResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<EdgeCapture />);

  fireEvent.click(screen.getByRole("button", { name: "Run capture test" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/capture",
      {
        body: JSON.stringify({
          instrument: "EUR_USD",
          algorithms: [
            "generic_sweep_continuation",
            "mss_confirmed_sweep_continuation",
            "early_ny_sweep_continuation",
          ],
          horizons: [15, 30, 60],
          window_days: 730,
          spread_pips: "0.8",
          slippage_pips: "0.1",
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("Generic session sweep continuation")).toBeInTheDocument();
  expect(screen.getByText("1.20p")).toBeInTheDocument();
  expect(screen.getByText("Costs: 0.8p spread + 0.1p slippage per side.")).toBeInTheDocument();
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function requestUrl(input: string | URL | Request): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.toString() : input.url;
}

const captureResult = {
  instrument: "EUR_USD",
  horizons: [15],
  algorithms: [
    {
      algorithm_id: "generic_sweep_continuation",
      hypothesis_id: "H007",
      label: "Generic session sweep continuation",
      description: "continuation capture",
    },
  ],
  spread_pips: "0.8",
  slippage_pips: "0.1",
  requested_window_days: 730,
  window: null,
  warnings: [],
  results: [
    {
      algorithm_id: "generic_sweep_continuation",
      hypothesis_id: "H007",
      algorithm_label: "Generic session sweep continuation",
      instrument: "EUR_USD",
      horizon: 15,
      event_count: 443,
      spread_pips: "0.8",
      slippage_pips: "0.1",
      entry_model: "next_open",
      exit_model: "fixed_horizon_close",
      stats: {
        count: 440,
        hit_rate: "0.54",
        mean_gross_pips: "2.20",
        mean_net_pips: "1.20",
        median_net_pips: "0.80",
        total_net_pips: "528.00",
        average_mfe_pips: "5.20",
        average_mae_pips: "3.10",
      },
    },
  ],
};
