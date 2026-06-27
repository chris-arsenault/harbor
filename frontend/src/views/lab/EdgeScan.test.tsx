import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { EdgeScan } from "./EdgeScan";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("applies edge scan presets, submits structured payloads, and renders results", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/edge/scan")) {
      return Promise.resolve(new Response(JSON.stringify(edgeScanResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<EdgeScan />);

  fireEvent.click(screen.getByRole("button", { name: "H005 GBP_JPY confirmatory" }));
  expect(screen.getByLabelText("Instruments")).toHaveValue("GBP_JPY");
  expect(screen.getByLabelText("Algorithms")).toHaveValue("clean_level_sweep_reversal");
  expect(screen.getByLabelText("Horizons")).toHaveValue("15, 30, 60");
  expect(screen.getByLabelText("Window (days)")).toHaveValue(730);

  fireEvent.click(screen.getByRole("button", { name: "Scan universe" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/edge/scan",
      {
        body: JSON.stringify({
          window_days: 730,
          instruments: ["GBP_JPY"],
          algorithms: ["clean_level_sweep_reversal"],
          horizons: [15, 30, 60],
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("clean_level_sweep_reversal")).toBeInTheDocument();
  expect(screen.getByText("GBP_JPY")).toBeInTheDocument();
  expect(screen.getByText("15m")).toBeInTheDocument();
  expect(screen.getByText("edge")).toBeInTheDocument();
  expect(screen.getByText("session:London")).toBeInTheDocument();
  expect(
    screen.getByText(
      "1 instruments × 1 algorithms × 3 horizons = 3 planned tests; 1 returned tests had data. 1 show a statistical edge. Corrected t uses clustered trading-day standard errors; adjusted p uses Bonferroni across 1 observed overall tests."
    )
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "H007 EUR_USD continuation" }));
  expect(screen.getByLabelText("Instruments")).toHaveValue("EUR_USD");
  expect(screen.getByLabelText("Algorithms")).toHaveValue(
    "generic_sweep_continuation, mss_confirmed_sweep_continuation, early_ny_sweep_continuation"
  );
  expect(screen.getByLabelText("Horizons")).toHaveValue("15, 30, 60, 120");
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

const edgeScanResult = {
  instruments: ["GBP_JPY"],
  horizons: [15, 30, 60],
  algorithms: [
    {
      algorithm_id: "clean_level_sweep_reversal",
      hypothesis_id: "H005",
      label: "H005 GBP_JPY confirmatory",
      description: "confirmatory edge scan",
    },
  ],
  results: [
    {
      algorithm_id: "clean_level_sweep_reversal",
      hypothesis_id: "H005",
      algorithm_label: "clean_level_sweep_reversal",
      instrument: "GBP_JPY",
      horizon: 15,
      total_sweeps: 18,
      overall: {
        count: 18,
        mean_pips: "4.25000000",
        median_pips: "4.00000000",
        hit_rate: "0.61111111",
        stddev_pips: "8.00000000",
        t_stat: "2.50000000",
        naive_t_stat: "2.10000000",
        standard_error_pips: "1.70000000",
        effective_sample_size: 12,
        p_value: "0.0123",
        bonferroni_p_value: "0.0345",
        correction: "clustered trading-day standard errors",
      },
      has_edge: true,
      best_conditional: {
        dimension: "session",
        value: "London",
        summary: {
          count: 7,
          mean_pips: "5.50000000",
          median_pips: "5.00000000",
          hit_rate: "0.71428571",
          stddev_pips: "7.00000000",
          t_stat: "2.80000000",
          naive_t_stat: "2.30000000",
          standard_error_pips: "1.50000000",
          effective_sample_size: 5,
          p_value: "0.0099",
          bonferroni_p_value: "0.0198",
          correction: "clustered trading-day standard errors",
        },
        has_edge: true,
        family_test_count: 3,
      },
      statistical_notes: {
        instrument_count: 1,
        algorithm_count: 1,
        horizon_count: 3,
        planned_overall_test_count: 3,
        overall_test_count: 1,
        overall_multiple_test_method: "Bonferroni",
      },
    },
  ],
  statistical_notes: {
    instrument_count: 1,
    algorithm_count: 1,
    horizon_count: 3,
    planned_overall_test_count: 3,
    overall_test_count: 1,
    overall_multiple_test_method: "Bonferroni",
  },
};
