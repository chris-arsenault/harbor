import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { LabSnapshot, LabVariantOverview } from "../../api/types";
import { LabView } from "./LabView";

test("LabView renders backend study facts, leaderboard, equity, and paper actions", () => {
  const onCreatePaperVariant = vi.fn();
  const onRetireVariant = vi.fn();
  const onStartOptimization = vi.fn();
  const onPromoteVariant = vi.fn();

  render(
    <LabView
      snapshot={snapshot}
      variants={variantOverview}
      onCreatePaperVariant={onCreatePaperVariant}
      onRetireVariant={onRetireVariant}
      onStartOptimization={onStartOptimization}
      onPromoteVariant={onPromoteVariant}
      liveStatus="variant 7 closed trade"
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
  expect(screen.getByText("Candidate Parameters")).toBeInTheDocument();
  expect(screen.getByText("fvg_window")).toBeInTheDocument();
  expect(screen.getByText("Data Separation")).toBeInTheDocument();
  expect(screen.getByText("optimizer_uses_variant_trades: false")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Start tuning study" }));
  fireEvent.change(screen.getByLabelText("Trial"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Label"), { target: { value: "paper-trial-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Create paper variant" }));
  fireEvent.click(screen.getByRole("button", { name: "Promote practice variant candidate-1" }));
  fireEvent.click(screen.getByRole("button", { name: "Retire paper variant candidate-1" }));

  expect(onStartOptimization).toHaveBeenCalledWith({
    fixture: "clean_signal_day.json",
    optimizer_config: { trial_count: 25 },
  });
  expect(onCreatePaperVariant).toHaveBeenCalledWith({ trial_id: 2, label: "paper-trial-1" });
  expect(onPromoteVariant).toHaveBeenCalledWith(7);
  expect(onRetireVariant).toHaveBeenCalledWith(7);
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
