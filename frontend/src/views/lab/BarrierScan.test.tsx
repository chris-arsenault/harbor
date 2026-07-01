import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BarrierScan } from "./BarrierScan";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("submits the barrier scan payload and renders first-touch outcomes", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.startsWith("/api/research/edge/barriers")) {
      return Promise.resolve(new Response(JSON.stringify(barrierResult), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });

  renderWithClient(<BarrierScan />);

  expect(screen.getByLabelText("Instrument")).toHaveValue("EUR_USD");
  expect(screen.getByLabelText("Barrier (R × ATR)")).toHaveValue("1.0");
  expect(screen.getByLabelText("Window (days)")).toHaveValue(730);

  fireEvent.change(screen.getByLabelText("Instrument"), { target: { value: "gbp_jpy" } });
  fireEvent.click(screen.getByRole("button", { name: "Run barrier scan" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/research/edge/barriers",
      {
        body: JSON.stringify({
          instrument: "GBP_JPY",
          horizons: [30, 60, 120],
          barrier_r: "1.0",
          algorithms: ["generic_sweep_reversal", "multi_candle_sweep_reclaim_reversal"],
          window_days: 730,
        }),
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        method: "POST",
      },
    ])
  );

  expect(await screen.findByText("Generic session sweep reversal")).toBeInTheDocument();
  expect(screen.getByText("60m")).toBeInTheDocument();
  expect(screen.getByText("1.0R")).toBeInTheDocument();
  expect(screen.getByText("102")).toBeInTheDocument();
  expect(screen.getByText("edge")).toBeInTheDocument();
  expect(screen.getByText(/Ambiguous candles resolve adverse/)).toBeInTheDocument();
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

const barrierResult = {
  instrument: "GBP_JPY",
  horizons: [60],
  barrier_r: "1.0",
  requested_window_days: 730,
  window: null,
  warnings: [],
  algorithms: [
    {
      algorithm_id: "generic_sweep_reversal",
      hypothesis_id: "H001",
      label: "Generic session sweep reversal",
      description: "barrier-scored baseline",
    },
  ],
  results: [
    {
      algorithm_id: "generic_sweep_reversal",
      hypothesis_id: "H001",
      algorithm_label: "Generic session sweep reversal",
      instrument: "GBP_JPY",
      horizon: 60,
      barrier_r: "1.0",
      total_events: 120,
      resolved: 102,
      timeouts: 18,
      reversal_first: 61,
      adverse_first: 41,
      overall: {
        count: 102,
        mean_pips: "0.19607843",
        median_pips: "1.00000000",
        hit_rate: "0.59803922",
        stddev_pips: "0.98000000",
        t_stat: "2.10000000",
        naive_t_stat: "2.20000000",
        standard_error_pips: "0.09300000",
        effective_sample_size: 64,
        p_value: "0.0179",
        bonferroni_p_value: "0.0537",
        bh_q_value: "0.0240",
        correction: "cluster_by_trading_day",
      },
      has_edge: true,
      statistical_notes: {
        ambiguous_candle_policy: "adverse_first",
        overall_multiple_test_method: "benjamini_hochberg",
      },
    },
  ],
};
