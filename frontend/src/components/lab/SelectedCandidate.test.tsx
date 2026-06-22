import { render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { CandidateScatterPoint, EventLogItem, LabVariantOverview } from "../../api/types";
import { SelectedCandidate } from "./SelectedCandidate";

test("SelectedCandidate explains paper-forward state before promotion evidence exists", () => {
  const onPromoteVariant = vi.fn();
  render(
    <SelectedCandidate
      candidates={[candidate]}
      variants={waitingVariantOverview}
      liveStatus={null}
      events={[feedEvent]}
      onRetireVariant={vi.fn()}
      onPromoteVariant={onPromoteVariant}
    />
  );

  const selected = within(screen.getByLabelText("Selected candidate"));
  expect(selected.getByText("Paper Forward Armed")).toBeInTheDocument();
  expect(
    selected.getByText(/evaluated on new closed M1 candles; promotion stays locked/i)
  ).toBeInTheDocument();
  expect(selected.getByText(/Latest feed event: .*pricing stream connected/i)).toBeInTheDocument();
  expect(
    selected.getByRole("button", { name: "Promote practice variant candidate-1" })
  ).toBeDisabled();
  expect(onPromoteVariant).not.toHaveBeenCalled();
});

const candidate: CandidateScatterPoint = {
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
};

const waitingVariantOverview: LabVariantOverview = {
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
        trade_count: 0,
        win_rate: "0",
        net_pnl: "0",
        expectancy: "0",
        average_r: "0",
        max_drawdown: "0",
        ending_nav: "10000.00000000",
        live_forward_score: "0",
      },
      out_of_sample_score: "1.50000000",
      robustness_score: "1.40000000",
    },
  ],
  equity_curves: [],
  data_separation: { optimizer_uses_variant_trades: false },
};

const feedEvent: EventLogItem = {
  id: 12,
  ts: "2026-01-15T14:30:00Z",
  level: "info",
  module: "feed.live",
  type: "pricing_stream.connected",
  message: "pricing stream connected",
  data: { instrument: "GBP_USD" },
};
