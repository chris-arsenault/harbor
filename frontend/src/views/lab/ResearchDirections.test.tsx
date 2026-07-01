import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ResearchDirections } from "./ResearchDirections";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("runs H108-H112 direction scan and renders data-gated rows", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/directions/scan")) {
      return Promise.resolve(new Response(JSON.stringify(directionResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<ResearchDirections />);
  fireEvent.click(screen.getByRole("button", { name: "Run direction scan" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/directions/scan",
      {
        body: JSON.stringify({
          instruments: null,
          algorithms: [
            "weekend_risk_gap_probe",
            "regime_resurrection_probe",
            "range_forecast_probe",
            "book_conditioner_readiness",
            "lead_lag_network_probe",
          ],
          window_days: 730,
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("Weekend risk-asset gap lead")).toBeInTheDocument();
  expect(screen.getByText("data_required")).toBeInTheDocument();
  expect(screen.getByText("Book-conditioned sweep readiness")).toBeInTheDocument();
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function requestUrl(input: string | URL | Request): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.toString() : input.url;
}

const directionResult = {
  instruments: ["EUR_USD", "BTC_USD"],
  requested_window_days: 730,
  windows: [],
  warnings: [],
  algorithms: [],
  book_coverage: [],
  results: [
    {
      hypothesis_id: "H108",
      algorithm_id: "weekend_risk_gap_probe",
      label: "Weekend risk-asset gap lead",
      status: "data_required",
      subject: "BTC_USD/ETH_USD",
      metric: "proxy_available",
      unit: "flag",
      stats: { count: 0, effect: "0", secondary: "0", t_stat: "0" },
      details: "No 24/7 risk proxy candles found",
    },
    {
      hypothesis_id: "H111",
      algorithm_id: "book_conditioner_readiness",
      label: "Book-conditioned sweep readiness",
      status: "collecting",
      subject: "EUR_USD",
      metric: "min(order,position)_snapshots",
      unit: "snapshots",
      stats: { count: 0, effect: "120", secondary: "260", t_stat: "0" },
      details: "Need roughly 500 paired snapshots",
    },
  ],
};
