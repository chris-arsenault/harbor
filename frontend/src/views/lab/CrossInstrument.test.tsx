import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ArchivedCrossInstrument, CrossInstrument } from "./CrossInstrument";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("submits active cross-instrument preset and renders factor rows", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/cross/scan")) {
      return Promise.resolve(new Response(JSON.stringify(crossResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<CrossInstrument />);
  fireEvent.click(screen.getByRole("button", { name: "Run cross scan" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/cross/scan",
      {
        body: JSON.stringify({
          instruments: null,
          algorithms: null,
          window_days: 730,
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(screen.getByLabelText("Instruments")).toHaveValue("");
  expect(screen.getByLabelText("Algorithms")).toHaveValue("");
  expect(await screen.findByText("No active cross-instrument rows")).toBeInTheDocument();
});

test("submits archived H100-H102 rerun from archive panel", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/cross/scan")) {
      return Promise.resolve(new Response(JSON.stringify(archivedCrossResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<ArchivedCrossInstrument />);
  fireEvent.click(screen.getByRole("button", { name: "Re-run archived scan" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/cross/scan",
      {
        body: JSON.stringify({
          instruments: null,
          algorithms: [
            "cs_momentum_20d_5d",
            "cs_value_60d_5d",
            "tri_eur_gbp_residual_5d",
            "usd_dispersion_reversion_5d",
          ],
          window_days: 730,
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("USD-factor dispersion reversion")).toBeInTheDocument();
  expect(screen.getByText("H102")).toBeInTheDocument();
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

const crossResult = {
  instruments: ["EUR_USD", "GBP_USD", "EUR_GBP"],
  requested_window_days: 730,
  windows: [],
  warnings: [],
  algorithms: [],
  results: [],
};

const archivedCrossResult = {
  instruments: ["EUR_USD", "GBP_USD", "USD_JPY"],
  requested_window_days: 730,
  windows: [],
  warnings: [],
  algorithms: [
    {
      algorithm_id: "usd_dispersion_reversion_5d",
      hypothesis_id: "H102",
      label: "USD-factor dispersion reversion",
      description: "archived",
      lifecycle: "archived",
    },
  ],
  results: [
    {
      algorithm_id: "usd_dispersion_reversion_5d",
      hypothesis_id: "H102",
      algorithm_label: "USD-factor dispersion reversion",
      instruments: ["EUR_USD", "GBP_USD", "USD_JPY"],
      observation_count: 538,
      stats: {
        count: 538,
        hit_rate: "0.54100000",
        mean_return_bps: "0.79000000",
        median_return_bps: "10.10000000",
        total_return_bps: "427.00000000",
        t_stat: "0.14000000",
      },
    },
  ],
};
