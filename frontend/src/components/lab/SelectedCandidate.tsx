import type { CandidateScatterPoint, LabVariantOverview, PaperVariant } from "../../api/types";

interface SelectedCandidateProps {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly variants: LabVariantOverview;
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}

export function SelectedCandidate({
  candidates,
  variants,
  onRetireVariant,
  onPromoteVariant,
}: SelectedCandidateProps) {
  const selected = selectedVariant(candidates, variants);
  if (selected === null) {
    return <NoSelectedCandidate />;
  }

  const row = variants.leaderboard.find((item) => item.variant.id === selected.variant.id) ?? null;
  const tradeCount = row?.stats.trade_count ?? 0;
  return (
    <section className="lab-panel lab-primary-result" aria-label="Selected candidate">
      <div className="lab-panel__header">
        <h2>Selected Candidate</h2>
        <span>{selected.variant.label}</span>
      </div>
      <CandidateFacts
        variant={selected.variant}
        candidate={selected.candidate}
        tradeCount={tradeCount}
        liveScore={row?.stats.live_forward_score ?? "waiting"}
        netPnl={row?.stats.net_pnl ?? "waiting"}
      />
      <p className="lab-result-summary">{candidateSummary(selected.variant, tradeCount)}</p>
      <CandidateActions
        variant={selected.variant}
        tradeCount={tradeCount}
        onRetireVariant={onRetireVariant}
        onPromoteVariant={onPromoteVariant}
      />
    </section>
  );
}

function NoSelectedCandidate() {
  return (
    <section className="lab-panel lab-primary-result" aria-label="Selected candidate">
      <div className="lab-panel__header">
        <h2>Selected Candidate</h2>
        <span>No paper candidate</span>
      </div>
      <p className="lab-result-summary">
        Run a research study with enough candle history. Passing candidates are saved as paper
        variants automatically.
      </p>
    </section>
  );
}

function CandidateFacts({
  variant,
  candidate,
  tradeCount,
  liveScore,
  netPnl,
}: {
  readonly variant: PaperVariant;
  readonly candidate: CandidateScatterPoint | null;
  readonly tradeCount: number;
  readonly liveScore: string;
  readonly netPnl: string;
}) {
  return (
    <>
      <div className="lab-study-status-grid lab-study-status-grid--compact">
        <Fact label="Status" value={variant.status} />
        <Fact label="Source trial" value={`#${candidate?.trial_no ?? variant.source_trial_id}`} />
        <Fact label="OOS" value={variant.trial_scores.out_of_sample_score ?? "unknown"} />
        <Fact label="Forward trades" value={tradeCount} />
      </div>
      <div className="lab-study-status-grid lab-study-status-grid--compact">
        <Fact label="IS" value={variant.trial_scores.in_sample_score ?? "unknown"} />
        <Fact label="Robust" value={variant.trial_scores.robustness_score ?? "unknown"} />
        <Fact label="Live score" value={liveScore} />
        <Fact label="Net PnL" value={netPnl} />
      </div>
    </>
  );
}

function Fact({ label, value }: { readonly label: string; readonly value: string | number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function CandidateActions({
  variant,
  tradeCount,
  onRetireVariant,
  onPromoteVariant,
}: {
  readonly variant: PaperVariant;
  readonly tradeCount: number;
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}) {
  const canPromote = variant.status === "paper" && tradeCount > 0;
  const canRetire = variant.status === "paper";
  return (
    <div className="lab-panel__actions">
      <button
        type="button"
        className="lab-button"
        disabled={!canPromote}
        aria-label={`Promote practice variant ${variant.label}`}
        onClick={() => void onPromoteVariant(variant.id)}
      >
        Promote to practice
      </button>
      <button
        type="button"
        className="lab-button lab-button--quiet"
        disabled={!canRetire}
        aria-label={`Retire paper variant ${variant.label}`}
        onClick={() => void onRetireVariant(variant.id)}
      >
        Retire
      </button>
    </div>
  );
}

function selectedVariant(
  candidates: readonly CandidateScatterPoint[],
  variants: LabVariantOverview
): { variant: PaperVariant; candidate: CandidateScatterPoint | null } | null {
  const candidateByTrialId = new Map(
    candidates.map((candidate) => [candidate.trial_id, candidate])
  );
  const studyVariants = variants.variants.filter((variant) =>
    candidateByTrialId.has(variant.source_trial_id)
  );
  const source = studyVariants.length > 0 ? studyVariants : variants.variants;
  if (source.length === 0) {
    return null;
  }
  const variant = source[0];
  return {
    variant,
    candidate: candidateByTrialId.get(variant.source_trial_id) ?? null,
  };
}

function candidateSummary(variant: PaperVariant, tradeCount: number): string {
  if (variant.status === "promoted") {
    return "This candidate is promoted for guarded practice execution.";
  }
  if (tradeCount === 0) {
    return "This candidate passed research validation and is waiting for forward paper trades before practice promotion.";
  }
  return "This candidate has forward paper trades and can be reviewed for practice promotion.";
}
