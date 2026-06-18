import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { LabSnapshot, LabVariantOverview } from "../../api/types";
import { CandleSourcePanel, LabView } from "./LabView";

test("LabView renders backend study facts, leaderboard, equity, and paper actions", () => {
  const onCreatePaperVariant = vi.fn();
  const onRetireVariant = vi.fn();
  const onStartOptimization = vi.fn();
  const onPromoteVariant = vi.fn();

  render(
    <LabView
      snapshot={snapshot}
      variants={variantOverview}
      tuningRun={{ pending: false, errorMessage: null, result: null }}
      onCreatePaperVariant={onCreatePaperVariant}
      onRetireVariant={onRetireVariant}
      onStartOptimization={onStartOptimization}
      onPromoteVariant={onPromoteVariant}
      liveStatus="variant 7 closed trade"
      candleSource={candleSource}
      candleSourcePending={false}
      candleSourceError={null}
      candleImportResult={candleImportResult}
      onImportCandles={vi.fn()}
    />
  );

  expect(screen.getByText("completed")).toBeInTheDocument();
  expect(screen.getByText("2 trials")).toBeInTheDocument();
  expect(screen.getByLabelText("Candidate score scatter")).toHaveAttribute(
    "data-points",
    "0:1.25:1.50"
  );
  expect(
    screen.getByRole("row", { name: /1 candidate-1 1 20.00000000 1.50000000/i })
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Variant equity curve")).toHaveAttribute(
    "data-points",
    "2026-01-15T14:42:00Z:10020.00000000|2026-01-15T14:43:00Z:10060.00000000"
  );
  expect(screen.getByText("variant 7 closed trade")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /live/i })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start tuning study" })).toBeInTheDocument();
  expect(screen.getByText("1 parameter")).toBeInTheDocument();
  expect(screen.getByText("fvg_window")).not.toBeVisible();
  fireEvent.click(screen.getByText("Candidate Parameters"));
  expect(screen.getByText("fvg_window")).toBeVisible();
  expect(screen.getByText("Data Separation")).toBeInTheDocument();
  expect(screen.getByText("optimizer_uses_variant_trades: false")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Import/refresh OANDA candles" })).toBeInTheDocument();
  expect(
    screen.getByText("path: OANDA practice REST -> persisted candles -> Lab optimizer")
  ).toBeInTheDocument();
  expect(screen.getByText("granularity: M1")).toBeInTheDocument();
  expect(screen.getByText("price: midpoint")).toBeInTheDocument();
  expect(
    screen.getByText(
      "Lab tuning reads this persisted candle dataset. Import/refresh updates the OANDA M1 midpoint history before rerunning studies."
    )
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Imported 4999 candles. Coverage 2026-06-15T08:21:00+00:00 to 2026-06-18T19:58:00+00:00."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("candles: 2880")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Start tuning study" }));
  fireEvent.change(screen.getByLabelText("Trial"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Label"), { target: { value: "paper-trial-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Create paper variant" }));
  fireEvent.click(screen.getByRole("button", { name: "Promote practice variant candidate-1" }));
  fireEvent.click(screen.getByRole("button", { name: "Retire paper variant candidate-1" }));

  expect(onStartOptimization).toHaveBeenCalledWith({
    source: "persisted_candles",
    instrument: "EUR_USD",
  });
  expect(onCreatePaperVariant).toHaveBeenCalledWith({ trial_id: 2, label: "paper-trial-1" });
  expect(onPromoteVariant).toHaveBeenCalledWith(7);
  expect(onRetireVariant).toHaveBeenCalledWith(7);
});

test("CandleSourcePanel explains unavailable OANDA historical imports", () => {
  render(
    <CandleSourcePanel
      source={{
        ...candleSource,
        coverage: {
          ...candleSource.coverage,
          candle_count: 0,
          from: null,
          to: null,
        },
        oanda_historical_import_configured: false,
      }}
      pending={false}
      errorMessage={null}
      importResult={null}
      onImportCandles={vi.fn()}
    />
  );

  expect(screen.getByRole("button", { name: "Import/refresh OANDA candles" })).toBeDisabled();
  expect(
    screen.getByText(
      "OANDA credentials are missing. Import would load practice M1 midpoint candles into Harbor's database for Lab studies."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("configured: false")).toBeInTheDocument();
});

test("LabView shows completed zero-candidate studies instead of a blank leaderboard", () => {
  render(
    <LabView
      snapshot={zeroCandidateSnapshot}
      variants={{ variants: [], leaderboard: [], equity_curves: [], data_separation: {} }}
      tuningRun={{
        pending: false,
        errorMessage: null,
        result: {
          study_id: 3,
          status: "completed",
          trials: [{ trial_id: 1 }, { trial_id: 2 }, { trial_id: 3 }, { trial_id: 4 }],
          candidates: [],
          best_trial_history: [],
          data_separation: {},
        },
      }}
      onCreatePaperVariant={vi.fn()}
      onRetireVariant={vi.fn()}
      onStartOptimization={vi.fn()}
      onPromoteVariant={vi.fn()}
      liveStatus={null}
      candleSource={candleSource}
      candleSourcePending={false}
      candleSourceError={null}
      candleImportResult={null}
      onImportCandles={vi.fn()}
    />
  );

  expect(screen.getByText(/Study #3 completed: 4 trials, 0 candidates/)).toBeInTheDocument();
  expect(
    screen.getByText(/No leaderboard row was created because no candidate passed the scoring gates/)
  ).toBeInTheDocument();
  expect(screen.getByText("No paper variants on the leaderboard.")).toBeInTheDocument();
  expect(screen.getByText("0 parameters")).toBeInTheDocument();
});

const snapshot: LabSnapshot = {
  study: {
    study_id: 1,
    status: "completed",
    trial_count: 2,
    candidate_count: 1,
    paper_variant_count: 1,
    created_ts: "2026-01-15T13:00:00Z",
  },
  candidates: [
    {
      trial_id: 2,
      trial_no: 0,
      params: { fvg_window: 8 },
      in_sample_score: "1.25",
      out_of_sample_score: "1.50",
      robustness_score: "1.40",
      pruned: false,
    },
  ],
  variants: {
    variants: [],
    leaderboard: [],
    equity_curves: [],
    data_separation: { optimizer_uses_variant_trades: false },
  },
  data_separation: { optimizer_uses_variant_trades: false },
};

const zeroCandidateSnapshot: LabSnapshot = {
  study: {
    study_id: 3,
    status: "completed",
    trial_count: 4,
    candidate_count: 0,
    paper_variant_count: 0,
    created_ts: "2026-06-18T19:59:43Z",
  },
  candidates: [],
  variants: {
    variants: [],
    leaderboard: [],
    equity_curves: [],
    data_separation: {},
  },
  data_separation: {},
};

const candleSource = {
  instrument: "EUR_USD",
  primary_source: "persisted_candles",
  granularity: "M1",
  price_component: "midpoint",
  coverage: {
    instrument: "EUR_USD",
    candle_count: 2880,
    from: "2026-01-15T00:00:00+00:00",
    to: "2026-01-16T23:59:00+00:00",
  },
  source_methods: ["oanda_historical_import", "oanda_pricing_stream"],
  oanda_historical_import_configured: true,
};

const candleImportResult = {
  status: "completed",
  source: "oanda_historical_import",
  instrument: "EUR_USD",
  requested_count: 5000,
  imported_count: 4999,
  coverage: {
    instrument: "EUR_USD",
    candle_count: 4999,
    from: "2026-06-15T08:21:00+00:00",
    to: "2026-06-18T19:58:00+00:00",
  },
};

const variantOverview: LabVariantOverview = {
  variants: [
    {
      id: 7,
      label: "candidate-1",
      params: { fvg_window: 8 },
      source_trial_id: 2,
      status: "paper",
      created_ts: null,
      trial_scores: {
        in_sample_score: "1.25",
        out_of_sample_score: "1.50",
        robustness_score: "1.40",
      },
    },
  ],
  leaderboard: [
    {
      rank: 1,
      variant: {
        id: 7,
        label: "candidate-1",
        params: { fvg_window: 8 },
        source_trial_id: 2,
        status: "paper",
        created_ts: null,
        trial_scores: {
          in_sample_score: "1.25",
          out_of_sample_score: "1.50",
          robustness_score: "1.40",
        },
      },
      stats: {
        variant_id: 7,
        trade_count: 1,
        win_rate: "1",
        net_pnl: "20.00000000",
        expectancy: "20.00000000",
        average_r: "2.0000",
        max_drawdown: "0",
        ending_nav: "10020.00000000",
        live_forward_score: "20.00000000",
      },
      out_of_sample_score: "1.50000000",
      robustness_score: "1.40000000",
    },
  ],
  equity_curves: [
    {
      variant_id: 7,
      points: [
        {
          variant_id: 7,
          ts: "2026-01-15T14:42:00Z",
          nav: "10020.00000000",
          drawdown: "0",
        },
        {
          variant_id: 7,
          ts: "2026-01-15T14:43:00Z",
          nav: "10060.00000000",
          drawdown: "0",
        },
      ],
    },
  ],
  data_separation: { optimizer_uses_variant_trades: false },
};
