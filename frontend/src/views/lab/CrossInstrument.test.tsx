import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { CrossInstrument } from "./CrossInstrument";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("submits cross-instrument preset and renders factor rows", async () => {
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

  expect(await screen.findByText("Cross-sectional momentum 20d→5d")).toBeInTheDocument();
  expect(screen.getByText("H100")).toBeInTheDocument();
  expect(screen.getByText("12.50")).toBeInTheDocument();
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
  algorithms: [
    {
      algorithm_id: "cs_momentum_20d_5d",
      hypothesis_id: "H100",
      label: "Cross-sectional momentum 20d→5d",
      description: "momentum basket",
    },
  ],
  results: [
    {
      algorithm_id: "cs_momentum_20d_5d",
      hypothesis_id: "H100",
      algorithm_label: "Cross-sectional momentum 20d→5d",
      instruments: ["EUR_USD", "GBP_USD", "EUR_GBP"],
      observation_count: 90,
      stats: {
        count: 90,
        hit_rate: "0.57777778",
        mean_return_bps: "12.50000000",
        median_return_bps: "8.00000000",
        total_return_bps: "1125.00000000",
        t_stat: "2.40000000",
      },
    },
  ],
};
