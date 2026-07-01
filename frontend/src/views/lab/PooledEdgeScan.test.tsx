import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { PooledEdgeScan } from "./PooledEdgeScan";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("submits the pooled scan payload and renders FDR-gated rows", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/edge/pooled")) {
      return Promise.resolve(new Response(JSON.stringify(pooledResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<PooledEdgeScan />);

  expect(screen.getByLabelText("Instruments")).toHaveValue("");
  expect(screen.getByLabelText("Algorithms")).toHaveValue(
    "generic_sweep_reversal, multi_candle_sweep_reclaim_reversal"
  );
  expect(screen.getByLabelText("Horizons")).toHaveValue("15, 30, 60, 120");
  expect(screen.getByLabelText("Window (days)")).toHaveValue(730);

  fireEvent.click(screen.getByRole("button", { name: "Run pooled scan" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/edge/pooled",
      {
        body: JSON.stringify({
          window_days: 730,
          instruments: null,
          algorithms: ["generic_sweep_reversal", "multi_candle_sweep_reclaim_reversal"],
          horizons: [15, 30, 60, 120],
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("Generic session sweep reversal")).toBeInTheDocument();
  expect(screen.getByText("60m")).toBeInTheDocument();
  expect(screen.getByText("edge")).toBeInTheDocument();
  expect(screen.getByText(/Pooled 2 instruments \(EUR_USD, GBP_USD\)/)).toBeInTheDocument();
  expect(screen.getByText(/1 rows pass the FDR gate\./)).toBeInTheDocument();
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

const pooledResult = {
  instruments: ["EUR_USD", "GBP_USD"],
  pooled_instruments: ["EUR_USD", "GBP_USD"],
  horizons: [60],
  requested_window_days: 730,
  windows: [],
  warnings: [],
  algorithms: [
    {
      algorithm_id: "generic_sweep_reversal",
      hypothesis_id: "H001",
      label: "Generic session sweep reversal",
      description: "pooled baseline",
    },
  ],
  results: [
    {
      algorithm_id: "generic_sweep_reversal",
      hypothesis_id: "H001",
      algorithm_label: "Generic session sweep reversal",
      instrument: "POOLED[EUR_USD,GBP_USD]",
      horizon: 60,
      total_sweeps: 420,
      overall: {
        count: 400,
        mean_pips: "0.08000000",
        median_pips: "0.05000000",
        hit_rate: "0.54000000",
        stddev_pips: "0.70000000",
        t_stat: "2.30000000",
        naive_t_stat: "2.40000000",
        standard_error_pips: "0.03500000",
        effective_sample_size: 180,
        p_value: "0.0107",
        bonferroni_p_value: "0.0428",
        bh_q_value: "0.0214",
        correction: "cluster_by_trading_day",
      },
      has_edge: true,
      best_conditional: null,
      statistical_notes: {
        outcome_unit: "atr",
        overall_test_count: 4,
        overall_multiple_test_method: "benjamini_hochberg",
      },
    },
  ],
  statistical_notes: {
    outcome_unit: "atr",
    overall_test_count: 4,
    overall_multiple_test_method: "benjamini_hochberg",
  },
};
