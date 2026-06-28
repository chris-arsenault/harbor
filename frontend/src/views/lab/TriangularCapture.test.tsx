import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { TriangularCapture } from "./TriangularCapture";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("runs triangular capture and renders net bps rows", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/triangular/capture")) {
      return Promise.resolve(new Response(JSON.stringify(result), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<TriangularCapture />);
  fireEvent.click(screen.getByRole("button", { name: "Run triangular capture" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/triangular/capture",
      {
        body: JSON.stringify({
          thresholds: [1, 1.5, 2],
          horizons: [1, 3, 5, 10],
          window_days: 730,
          cost_bps_per_leg: 1.5,
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("direct_eur_gbp")).toBeInTheDocument();
  expect(screen.getByText("2.10")).toBeInTheDocument();
  expect(screen.getByText("Cost: 1.5000 bps per leg.")).toBeInTheDocument();
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

const result = {
  instruments: ["EUR_USD", "GBP_USD", "EUR_GBP"],
  requested_window_days: 730,
  thresholds: ["1.0000"],
  horizons: [5],
  cost_bps_per_leg: "1.5000",
  windows: [],
  warnings: [],
  results: [
    {
      hypothesis_id: "H101",
      construction: "direct_eur_gbp",
      threshold: "1.5000",
      horizon: 5,
      leg_count: 1,
      cost_bps_per_leg: "1.5000",
      stats: {
        count: 36,
        hit_rate: "0.86111111",
        mean_gross_bps: "3.60000000",
        mean_net_bps: "2.10000000",
        median_net_bps: "1.70000000",
        total_net_bps: "75.60000000",
        t_stat: "4.20000000",
        first_half_mean_net_bps: "2.00000000",
        second_half_mean_net_bps: "2.20000000",
      },
    },
  ],
};
