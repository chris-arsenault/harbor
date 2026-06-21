import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { LabSnapshot, LabVariantOverview } from "../../api/types";
import { CandleSourcePanel } from "./CandleSourcePanel";
import { preflight } from "./LabView.fixtures";
import { LabView } from "./LabView";
import { DEFAULT_TUNING_PAYLOAD, DISCOVERY_STUDY_CONFIG } from "./tuningPayload";

test("LabView renders backend study facts, leaderboard, equity, and paper actions", () => {
  const onCreatePaperVariant = vi.fn();
  const onRetireVariant = vi.fn();
  const onStartOptimization = vi.fn();
  const onPromoteVariant = vi.fn();

  renderPopulatedLabView({
    onCreatePaperVariant,
    onRetireVariant,
    onStartOptimization,
    onPromoteVariant,
  });

  expect(
    screen.getByRole("region", { name: "Study progress" }).querySelector("strong")
  ).toHaveTextContent("completed");
  expect(screen.getByText("2 trials")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Trial score scatter" })).toHaveAttribute(
    "data-points",
    "0:1.25:1.50"
  );
  expect(screen.getByLabelText("Study results")).toBeInTheDocument();
  expect(screen.getByText("Paper candidates")).toBeInTheDocument();
  expect(screen.getByText("passes score gate")).toBeInTheDocument();
  expect(
    screen.getByRole("row", { name: /1 candidate-1 1 20.00000000 1.50000000/i })
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Variant equity curve")).toHaveAttribute(
    "data-points",
    "2026-01-15T14:42:00Z:10020.00000000|2026-01-15T14:43:00Z:10060.00000000"
  );
  expect(screen.getByText("variant 7 closed trade")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /live/i })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Start research study" })).toBeInTheDocument();
  expect(screen.getByText("Study Setup")).toBeInTheDocument();
  expect(screen.getByText("124/126")).toBeInTheDocument();
  expect(screen.getByText("124/120")).toBeInTheDocument();
  expect(
    screen.getByText("research protocol: dataset satisfies the fixed research protocol")
  ).toBeInTheDocument();
  expect(screen.getByText("1 parameter")).toBeInTheDocument();
  expect(screen.getByText("fvg_window")).not.toBeVisible();
  fireEvent.click(screen.getByText("Candidate Parameters"));
  expect(screen.getByText("fvg_window")).toBeVisible();
  expect(screen.getByText("Data Separation")).toBeInTheDocument();
  expect(screen.getByText("optimizer_uses_variant_trades: false")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Refresh latest 5,000 M1" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Backfill research dataset" })).toBeInTheDocument();
  expect(
    screen.getByText("path: OANDA practice REST -> persisted candles -> Lab optimizer")
  ).toBeInTheDocument();
  expect(screen.getByText("write policy: upsert")).toBeInTheDocument();
  expect(screen.getByText("upsert key: instrument+timestamp")).toBeInTheDocument();
  expect(screen.getByText("granularity: M1")).toBeInTheDocument();
  expect(screen.getByText("price: midpoint")).toBeInTheDocument();
  expect(
    screen.getByText("Lab research reads the persisted M1 midpoint candle dataset shown below.")
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Upserted 4999 of 259200 requested candles from 2025-12-20T20:00:00.000Z. Coverage 2026-06-15T08:21:00+00:00 to 2026-06-18T19:58:00+00:00."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("latest-page request: 5,000 M1 candles")).toBeInTheDocument();
  expect(screen.getByText("research backfill request: 259,200 M1 candles")).toBeInTheDocument();
  expect(screen.getByText("candles: 2880")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Start research study" }));
  fireEvent.change(screen.getByLabelText("Trial"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Label"), { target: { value: "paper-trial-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Create paper variant" }));
  fireEvent.click(screen.getByRole("button", { name: "Promote practice variant candidate-1" }));
  fireEvent.click(screen.getByRole("button", { name: "Retire paper variant candidate-1" }));

  expect(onStartOptimization).toHaveBeenCalledWith(DEFAULT_TUNING_PAYLOAD);
  expect(onCreatePaperVariant).toHaveBeenCalledWith({ trial_id: 2, label: "paper-trial-1" });
  expect(onPromoteVariant).toHaveBeenCalledWith(7);
  expect(onRetireVariant).toHaveBeenCalledWith(7);
});

function renderPopulatedLabView(handlers: {
  readonly onCreatePaperVariant: (payload: { trial_id: number; label: string }) => void;
  readonly onRetireVariant: (variantId: number) => void;
  readonly onStartOptimization: Parameters<typeof LabView>[0]["onStartOptimization"];
  readonly onPromoteVariant: (variantId: number) => void;
}) {
  render(
    <LabView
      snapshot={snapshot}
      variants={variantOverview}
      tuningRun={{ pending: false, errorMessage: null, result: null }}
      onCreatePaperVariant={handlers.onCreatePaperVariant}
      onRetireVariant={handlers.onRetireVariant}
      onStartOptimization={handlers.onStartOptimization}
      onPromoteVariant={handlers.onPromoteVariant}
      liveStatus="variant 7 closed trade"
      candleSource={candleSource}
      candleSourcePending={false}
      candleSourceError={null}
      candleImportResult={candleImportResult}
      onImportCandles={vi.fn()}
      studyConfig={DISCOVERY_STUDY_CONFIG}
      onStudyConfigChange={vi.fn()}
      studyPayload={DEFAULT_TUNING_PAYLOAD}
      preflight={preflight}
      preflightPending={false}
      preflightError={null}
    />
  );
}

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

  expect(screen.getByRole("button", { name: "Refresh latest 5,000 M1" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Backfill research dataset" })).toBeDisabled();
  expect(
    screen.getByText(
      "OANDA credentials are missing. Import would load practice M1 midpoint candles into Harbor's database for Lab research studies."
    )
  ).toBeInTheDocument();
  expect(screen.getByText("configured: false")).toBeInTheDocument();
});

test("CandleSourcePanel sends explicit latest-page and backfill import requests", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-06-18T20:00:00.000Z"));
  const onImportCandles = vi.fn();

  render(
    <CandleSourcePanel
      source={candleSource}
      pending={false}
      errorMessage={null}
      importResult={null}
      onImportCandles={onImportCandles}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "Refresh latest 5,000 M1" }));
  fireEvent.click(screen.getByRole("button", { name: "Backfill research dataset" }));

  expect(onImportCandles).toHaveBeenNthCalledWith(1, {
    instrument: "EUR_USD",
    count: 5000,
  });
  expect(onImportCandles).toHaveBeenNthCalledWith(2, {
    instrument: "EUR_USD",
    count: 259200,
    from: "2025-12-20T20:00:00.000Z",
  });
  vi.useRealTimers();
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
          trials: [zeroScoreTrial(0), zeroScoreTrial(1), zeroScoreTrial(2), zeroScoreTrial(3)],
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
      studyConfig={DISCOVERY_STUDY_CONFIG}
      onStudyConfigChange={vi.fn()}
      studyPayload={DEFAULT_TUNING_PAYLOAD}
      preflight={preflight}
      preflightPending={false}
      preflightError={null}
    />
  );

  expect(screen.getByText(/Study #3 completed: 4 trials, 0 candidates/)).toBeInTheDocument();
  expect(
    screen.getByText(
      /All 4 trials had non-positive in-sample and out-of-sample scores; see Trial diagnostics/
    )
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Trial diagnostics")).toBeInTheDocument();
  expect(screen.getByLabelText("Study results")).toBeInTheDocument();
  expect(screen.getByText("Passed score gate")).toBeInTheDocument();
  expect(
    screen.getByText(/No paper candidates. Best trial #0 is blocked because/)
  ).toBeInTheDocument();
  expect(screen.getAllByText("in-sample and out-of-sample scores are not positive")).toHaveLength(
    8
  );
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
      status: "completed",
      failure_reason: null,
      candidate_rejection_reason: null,
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

function zeroScoreTrial(trialNo: number) {
  return {
    trial_no: trialNo,
    params: { fvg_window: 8 + trialNo },
    is_score: "0E-8",
    oos_score: "0E-8",
    robustness_score: "0E-8",
    pruned: false,
    status: "completed",
    failure_reason: null,
  };
}

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
  historical_import: {
    page_size: 5000,
    default_count: 259200,
    request_interval_seconds: 0.1,
    upsert_key: "instrument+timestamp",
    replaces_existing: false,
  },
  oanda_historical_import_configured: true,
};

const candleImportResult = {
  status: "completed",
  source: "oanda_historical_import",
  instrument: "EUR_USD",
  requested_count: 259200,
  imported_count: 4999,
  from: "2025-12-20T20:00:00.000Z",
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
