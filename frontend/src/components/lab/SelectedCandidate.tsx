import type {
  CandidateScatterPoint,
  EventLogItem,
  LabVariantOverview,
  PaperVariant,
} from "../../api/types";

interface SelectedCandidateProps {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly variants: LabVariantOverview;
  readonly liveStatus: string | null;
  readonly events: readonly EventLogItem[];
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}

export function SelectedCandidate({
  candidates,
  variants,
  liveStatus,
  events,
  onRetireVariant,
  onPromoteVariant,
}: SelectedCandidateProps) {
  const selected = selectedVariant(candidates, variants);
  if (selected === null) {
    return <NoSelectedCandidate />;
  }

  const row = variants.leaderboard.find((item) => item.variant.id === selected.variant.id) ?? null;
  const tradeCount = row?.stats.trade_count ?? 0;
  const activity = paperForwardActivity(selected.variant, tradeCount, liveStatus, events);
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
        evidenceState={activity.stateLabel}
        liveScore={row?.stats.live_forward_score ?? "waiting"}
        netPnl={row?.stats.net_pnl ?? "waiting"}
      />
      <p className="lab-result-summary">{candidateSummary(selected.variant, tradeCount)}</p>
      <PaperForwardEvidence activity={activity} />
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
  evidenceState,
  liveScore,
  netPnl,
}: {
  readonly variant: PaperVariant;
  readonly candidate: CandidateScatterPoint | null;
  readonly tradeCount: number;
  readonly evidenceState: string;
  readonly liveScore: string;
  readonly netPnl: string;
}) {
  return (
    <>
      <div className="lab-study-status-grid lab-study-status-grid--compact">
        <Fact label="Status" value={variant.status} />
        <Fact label="Source trial" value={`#${candidate?.trial_no ?? variant.source_trial_id}`} />
        <Fact label="Evidence" value={evidenceState} />
        <Fact label="Forward trades" value={tradeCount} />
      </div>
      <div className="lab-study-status-grid lab-study-status-grid--compact">
        <Fact label="IS" value={variant.trial_scores.in_sample_score ?? "unknown"} />
        <Fact label="OOS" value={variant.trial_scores.out_of_sample_score ?? "unknown"} />
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
        title={!canPromote ? "Promotion unlocks after forward paper trades close." : undefined}
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
    return "This candidate passed research validation. Practice promotion is locked until paper-forward closes simulated trades on live candles.";
  }
  return "This candidate has forward paper trades and can be reviewed for practice promotion.";
}

interface PaperForwardActivity {
  readonly stateLabel: string;
  readonly heading: string;
  readonly summary: string;
  readonly feedEvent: EventLogItem | null;
  readonly paperEvent: EventLogItem | null;
  readonly liveStatus: string | null;
}

function PaperForwardEvidence({ activity }: { readonly activity: PaperForwardActivity }) {
  return (
    <section className="paper-forward-state" aria-label="Paper forward evidence">
      <strong>{activity.heading}</strong>
      <p>{activity.summary}</p>
      <ul className="fact-list">
        <li>Latest feed event: {eventSummary(activity.feedEvent)}</li>
        <li>Latest paper event: {eventSummary(activity.paperEvent)}</li>
        <li>Browser live update: {activity.liveStatus ?? "none in this session"}</li>
      </ul>
    </section>
  );
}

function paperForwardActivity(
  variant: PaperVariant,
  tradeCount: number,
  liveStatus: string | null,
  events: readonly EventLogItem[]
): PaperForwardActivity {
  const feedEvent = latestEvent(events, (event) => event.module === "feed.live");
  const paperEvent = latestEvent(events, (event) => event.module === "paper_forward");
  if (variant.status === "promoted") {
    return {
      stateLabel: "promoted",
      heading: "Practice Variant",
      summary:
        "This variant is promoted. Practice execution uses it when guarded trading is enabled.",
      feedEvent,
      paperEvent,
      liveStatus,
    };
  }
  if (tradeCount > 0) {
    return {
      stateLabel: "evidence ready",
      heading: "Forward Evidence Ready",
      summary:
        "Paper-forward has closed simulated trades for this candidate. Review the forward score, equity curve, and trade list before promotion.",
      feedEvent,
      paperEvent,
      liveStatus,
    };
  }
  if (feedEvent?.type === "pricing_stream.heartbeat_timeout") {
    return {
      stateLabel: "feed stale",
      heading: "Forward Evidence Blocked",
      summary:
        "No simulated trades have closed, and the latest live feed event is a heartbeat timeout. Forward evidence will not move until live candle ingestion recovers.",
      feedEvent,
      paperEvent,
      liveStatus,
    };
  }
  if (feedEvent !== null) {
    return {
      stateLabel: "armed",
      heading: "Paper Forward Armed",
      summary:
        "The live candle feed has recent activity. This candidate is evaluated on new closed M1 candles; promotion stays locked until a simulated trade closes.",
      feedEvent,
      paperEvent,
      liveStatus,
    };
  }
  return {
    stateLabel: "no feed seen",
    heading: "No Forward Feed Seen",
    summary:
      "A paper candidate exists, but recent events do not show live candle ingestion. Forward evidence will stay at zero until closed live M1 candles are processed.",
    feedEvent,
    paperEvent,
    liveStatus,
  };
}

function latestEvent(
  events: readonly EventLogItem[],
  predicate: (event: EventLogItem) => boolean
): EventLogItem | null {
  return (
    [...events].filter(predicate).sort((left, right) => right.ts.localeCompare(left.ts))[0] ?? null
  );
}

function eventSummary(event: EventLogItem | null): string {
  if (event === null) {
    return "none in recent events";
  }
  return `${event.ts} ${event.message}`;
}
