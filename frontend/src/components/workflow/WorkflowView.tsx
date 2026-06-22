/* eslint-disable complexity, max-lines, max-lines-per-function */
import type { PracticeControls } from "../../api/hooks";
import type {
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStartPayload,
  CandleCoverage,
  CandleImportRequest,
  CandleImportResult,
  CandleSourceStatus,
  CandidateScatterPoint,
  EventLogItem,
  LabSnapshot,
  LabVariantOverview,
  OptimizationStartPayload,
  PaperVariant,
  StatusSnapshot,
  VariantLeaderboardRow,
} from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { displayValue } from "../../utils/format";
import type { TuningRunState } from "../lab/LabView";

const SELECTED_BACKFILL_COUNT = 259_200;
const BACKTEST_WINDOW_DAYS = 30;

export interface WorkflowViewProps {
  readonly selectedInstrument: string;
  readonly onInstrumentChange: (instrument: string) => void;
  readonly candleSource: CandleSourceStatus | null;
  readonly candleSourcePending: boolean;
  readonly candleSourceError: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
  readonly tuningRun: TuningRunState;
  readonly snapshot: LabSnapshot | null;
  readonly variants: LabVariantOverview;
  readonly events: readonly EventLogItem[];
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
  readonly backtestRuns: readonly BacktestRunSummary[];
  readonly selectedBacktestRun: BacktestRunDetail | null;
  readonly backtestPending: boolean;
  readonly backtestError: string | null;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}

export function WorkflowView(props: WorkflowViewProps) {
  const coverages = coverageRows(props.candleSource, props.selectedInstrument);
  const selectedCoverage = selectedCoverageRow(coverages, props.selectedInstrument);
  const target = workflowTargetVariant(props.variants);
  const targetInstrument = variantInstrument(target?.variant) ?? props.selectedInstrument;
  const backtestCoverage = selectedCoverageRow(coverages, targetInstrument);
  const latestFeedEvent = latestEvent(props.events, (event) => event.module === "feed.live");
  const latestPaperEvent = latestEvent(props.events, (event) => event.module === "paper_forward");
  const backtestDisabled = props.backtestPending || backtestCoverage.candle_count === 0;

  return (
    <section className="workflow-view" aria-label="Workflow">
      <WorkflowHeader
        dataReady={selectedCoverage.candle_count > 0}
        researchReady={props.preflight?.status === "ready"}
        hasCandidate={target !== null}
        hasBacktest={props.backtestRuns.length > 0}
        hasPaperEvidence={(target?.tradeCount ?? 0) > 0}
        hasPromotion={
          props.status.promoted_variant !== null && props.status.promoted_variant !== undefined
        }
      />

      <DataStage
        selectedInstrument={props.selectedInstrument}
        coverages={coverages}
        source={props.candleSource}
        pending={props.candleSourcePending}
        errorMessage={props.candleSourceError}
        importResult={props.importResult}
        onInstrumentChange={props.onInstrumentChange}
        onImportCandles={props.onImportCandles}
        latestFeedEvent={latestFeedEvent}
      />

      <ResearchStage
        selectedInstrument={props.selectedInstrument}
        studyPayload={props.studyPayload}
        preflight={props.preflight}
        preflightPending={props.preflightPending}
        preflightError={props.preflightError}
        tuningRun={props.tuningRun}
        snapshot={props.snapshot}
        onStartOptimization={props.onStartOptimization}
      />

      <CandidateStage
        snapshot={props.snapshot}
        target={target}
        onPromoteVariant={props.onPromoteVariant}
      />

      <BacktestStage
        target={target?.variant ?? null}
        selectedInstrument={targetInstrument}
        selectedCoverage={backtestCoverage}
        runs={props.backtestRuns}
        selectedRun={props.selectedBacktestRun}
        pending={props.backtestPending}
        errorMessage={props.backtestError}
        disabled={backtestDisabled}
        onStartBacktest={props.onStartBacktest}
      />

      <PaperAndPracticeStage
        target={target}
        liveStream={props.candleSource?.live_stream ?? null}
        latestFeedEvent={latestFeedEvent}
        latestPaperEvent={latestPaperEvent}
        status={props.status}
        controls={props.controls}
        onPromoteVariant={props.onPromoteVariant}
      />
    </section>
  );
}

function WorkflowHeader({
  dataReady,
  researchReady,
  hasCandidate,
  hasBacktest,
  hasPaperEvidence,
  hasPromotion,
}: {
  readonly dataReady: boolean;
  readonly researchReady: boolean;
  readonly hasCandidate: boolean;
  readonly hasBacktest: boolean;
  readonly hasPaperEvidence: boolean;
  readonly hasPromotion: boolean;
}) {
  const steps = [
    ["Data", dataReady],
    ["Research", researchReady],
    ["Candidate", hasCandidate],
    ["Backtest", hasBacktest],
    ["Paper", hasPaperEvidence],
    ["Practice", hasPromotion],
  ] as const;
  return (
    <div className="workflow-header">
      <h2>Strategy Workflow</h2>
      <div className="workflow-step-strip" aria-label="Workflow stage status">
        {steps.map(([label, ready]) => (
          <span
            key={label}
            className={ready ? "workflow-step workflow-step--ready" : "workflow-step"}
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function DataStage({
  selectedInstrument,
  coverages,
  source,
  pending,
  errorMessage,
  importResult,
  onInstrumentChange,
  onImportCandles,
  latestFeedEvent,
}: {
  readonly selectedInstrument: string;
  readonly coverages: readonly CandleCoverage[];
  readonly source: CandleSourceStatus | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onInstrumentChange: (instrument: string) => void;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
  readonly latestFeedEvent: EventLogItem | null;
}) {
  const policy = source?.historical_import;
  const researchInstruments = instrumentOptions(source, selectedInstrument);
  const latestPayload = { instrument: selectedInstrument, count: policy?.page_size ?? 5000 };
  const backfillPayload = {
    instrument: selectedInstrument,
    count: Math.max(policy?.default_count ?? SELECTED_BACKFILL_COUNT, SELECTED_BACKFILL_COUNT),
    from: backfillStart(
      Math.max(policy?.default_count ?? SELECTED_BACKFILL_COUNT, SELECTED_BACKFILL_COUNT)
    ),
  };
  const universePayload = {
    instrument: "research_universe",
    instruments: researchInstruments,
    count: backfillPayload.count,
    from: backfillPayload.from,
  };
  return (
    <section className="workflow-panel" aria-label="Data stage">
      <div className="workflow-panel__header">
        <div>
          <span className="workflow-kicker">1. Data</span>
          <h3>Candle Coverage and Live Feed</h3>
        </div>
        <label className="workflow-select">
          Instrument
          <select
            value={selectedInstrument}
            onChange={(event) => onInstrumentChange(event.target.value)}
          >
            {researchInstruments.map((instrument) => (
              <option key={instrument} value={instrument}>
                {instrument}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="workflow-metrics">
        <Metric
          label="Selected candles"
          value={selectedCoverageRow(coverages, selectedInstrument).candle_count.toLocaleString()}
        />
        <Metric
          label="Coverage"
          value={coverageRange(selectedCoverageRow(coverages, selectedInstrument))}
        />
        <Metric label="Live stream" value={liveStreamLabel(source)} />
        <Metric label="Latest feed event" value={eventLabel(latestFeedEvent)} />
      </div>
      <div className="workflow-actions">
        <button
          type="button"
          className="lab-button lab-button--quiet"
          disabled={pending || !source?.oanda_historical_import_configured}
          onClick={() => void onImportCandles(latestPayload)}
        >
          Refresh Latest
        </button>
        <button
          type="button"
          className="lab-button"
          disabled={pending || !source?.oanda_historical_import_configured}
          onClick={() => void onImportCandles(backfillPayload)}
        >
          Fill Selected History
        </button>
        <button
          type="button"
          className="lab-button lab-button--quiet"
          disabled={pending || !source?.oanda_historical_import_configured}
          onClick={() => void onImportCandles(universePayload)}
        >
          Fill Research Universe
        </button>
      </div>
      <CoverageTable coverages={coverages} selectedInstrument={selectedInstrument} />
      <p className="workflow-status-line">
        Historical import uses M1 midpoint candles and upserts by instrument plus timestamp.
        {policy
          ? ` Page size ${policy.page_size.toLocaleString()}, ${policy.request_interval_seconds}s between pages.`
          : ""}
      </p>
      {errorMessage ? <p className="lab-run-notice lab-run-notice--error">{errorMessage}</p> : null}
      {importResult ? <p className="lab-run-notice">{importNotice(importResult)}</p> : null}
    </section>
  );
}

function ResearchStage({
  selectedInstrument,
  studyPayload,
  preflight,
  preflightPending,
  preflightError,
  tuningRun,
  snapshot,
  onStartOptimization,
}: {
  readonly selectedInstrument: string;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
  readonly tuningRun: TuningRunState;
  readonly snapshot: LabSnapshot | null;
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
}) {
  const ready = preflight?.status === "ready";
  return (
    <section className="workflow-panel" aria-label="Research stage">
      <div className="workflow-panel__header">
        <div>
          <span className="workflow-kicker">2. Research</span>
          <h3>Study Preflight and Optimization</h3>
        </div>
        <button
          type="button"
          className="lab-button"
          disabled={!ready || tuningRun.pending}
          onClick={() => void onStartOptimization(preflight?.recommended_payload ?? studyPayload)}
        >
          {tuningRun.pending ? "Running Study" : "Start Research Study"}
        </button>
      </div>
      <div className="workflow-metrics">
        <Metric label="Instrument" value={selectedInstrument} />
        <Metric
          label="Preflight"
          value={preflightPending ? "checking" : (preflight?.status ?? "not run")}
        />
        <Metric label="Research days" value={researchDays(preflight)} />
        <Metric label="Candidates" value={String(snapshot?.study.candidate_count ?? 0)} />
      </div>
      <ReadinessList preflight={preflight} />
      {preflightError ? (
        <p className="lab-run-notice lab-run-notice--error">{preflightError}</p>
      ) : null}
      {tuningRun.errorMessage ? (
        <p className="lab-run-notice lab-run-notice--error">{tuningRun.errorMessage}</p>
      ) : null}
      {tuningRun.result ? (
        <p className="lab-run-notice">
          {studyNotice(
            tuningRun.result.status,
            tuningRun.result.trials.length,
            tuningRun.result.candidates.length
          )}
        </p>
      ) : null}
    </section>
  );
}

function CandidateStage({
  snapshot,
  target,
  onPromoteVariant,
}: {
  readonly snapshot: LabSnapshot | null;
  readonly target: WorkflowTarget | null;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}) {
  const candidate = candidateForVariant(snapshot, target?.variant ?? null);
  return (
    <section className="workflow-panel" aria-label="Candidate stage">
      <div className="workflow-panel__header">
        <div>
          <span className="workflow-kicker">3. Candidate</span>
          <h3>Saved Research Candidate</h3>
        </div>
        <button
          type="button"
          className="lab-button lab-button--quiet"
          disabled={target === null || target.variant.status !== "paper" || target.tradeCount === 0}
          onClick={() => target && void onPromoteVariant(target.variant.id)}
        >
          Promote to Practice
        </button>
      </div>
      {target === null ? (
        <p className="workflow-status-line">No saved paper candidate is available.</p>
      ) : (
        <>
          <div className="workflow-metrics">
            <Metric label="Variant" value={target.variant.label} />
            <Metric label="Instrument" value={variantInstrument(target.variant) ?? "unknown"} />
            <Metric
              label="IS / OOS"
              value={`${score(target.variant, "in_sample_score")} / ${score(target.variant, "out_of_sample_score")}`}
            />
            <Metric label="Forward trades" value={String(target.tradeCount)} />
          </div>
          <details className="workflow-disclosure">
            <summary>Candidate parameters</summary>
            <ParameterTable params={candidate?.params ?? target.variant.params} />
          </details>
        </>
      )}
    </section>
  );
}

function BacktestStage({
  target,
  selectedInstrument,
  selectedCoverage,
  runs,
  selectedRun,
  pending,
  errorMessage,
  disabled,
  onStartBacktest,
}: {
  readonly target: PaperVariant | null;
  readonly selectedInstrument: string;
  readonly selectedCoverage: CandleCoverage;
  readonly runs: readonly BacktestRunSummary[];
  readonly selectedRun: BacktestRunDetail | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly disabled: boolean;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
}) {
  return (
    <section className="workflow-panel" aria-label="Backtest stage">
      <div className="workflow-panel__header">
        <div>
          <span className="workflow-kicker">4. Backtest</span>
          <h3>Candidate Validation</h3>
        </div>
        <button
          type="button"
          className="lab-button"
          disabled={disabled}
          onClick={() => onStartBacktest(backtestPayload(target, selectedInstrument))}
        >
          {pending ? "Running Backtest" : "Run Backtest"}
        </button>
      </div>
      <div className="workflow-metrics">
        <Metric label="Target" value={target?.label ?? "Default strategy"} />
        <Metric label="Instrument" value={selectedInstrument} />
        <Metric label="Window" value={`${BACKTEST_WINDOW_DAYS} complete days`} />
        <Metric label="Coverage" value={coverageRange(selectedCoverage)} />
      </div>
      {selectedRun ? <BacktestSummary run={selectedRun} /> : <RecentRunSummary runs={runs} />}
      {errorMessage ? <p className="lab-run-notice lab-run-notice--error">{errorMessage}</p> : null}
    </section>
  );
}

function PaperAndPracticeStage({
  target,
  liveStream,
  latestFeedEvent,
  latestPaperEvent,
  status,
  controls,
  onPromoteVariant,
}: {
  readonly target: WorkflowTarget | null;
  readonly liveStream: CandleSourceStatus["live_stream"] | null;
  readonly latestFeedEvent: EventLogItem | null;
  readonly latestPaperEvent: EventLogItem | null;
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}) {
  const canPromote = target !== null && target.variant.status === "paper" && target.tradeCount > 0;
  return (
    <section className="workflow-panel" aria-label="Paper and practice stage">
      <div className="workflow-panel__header">
        <div>
          <span className="workflow-kicker">5-6. Paper and Practice</span>
          <h3>Forward Evidence and Execution State</h3>
        </div>
        <button
          type="button"
          className="lab-button"
          disabled={!canPromote}
          onClick={() => target && void onPromoteVariant(target.variant.id)}
        >
          Promote Candidate
        </button>
      </div>
      <div className="workflow-metrics">
        <Metric label="Live stream" value={liveStream?.state ?? "unknown"} />
        <Metric label="Paper trades" value={String(target?.tradeCount ?? 0)} />
        <Metric label="Promoted" value={status.promoted_variant?.label ?? "none"} />
        <Metric label="Trading" value={status.trading_enabled ? "enabled" : "disabled"} />
      </div>
      <dl className="workflow-facts">
        <dt>Latest feed event</dt>
        <dd>{eventLabel(latestFeedEvent)}</dd>
        <dt>Latest paper event</dt>
        <dd>{eventLabel(latestPaperEvent)}</dd>
        <dt>Practice controls</dt>
        <dd>{status.trading_controls_available ? "available" : "read-only"}</dd>
        <dt>Control request</dt>
        <dd>{controls.errorMessage ?? (controls.pending ? "pending" : "idle")}</dd>
      </dl>
    </section>
  );
}

function CoverageTable({
  coverages,
  selectedInstrument,
}: {
  readonly coverages: readonly CandleCoverage[];
  readonly selectedInstrument: string;
}) {
  return (
    <div className="workflow-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Instrument</th>
            <th>Candles</th>
            <th>From</th>
            <th>To</th>
          </tr>
        </thead>
        <tbody>
          {coverages.map((coverage) => (
            <tr
              key={coverage.instrument}
              className={
                coverage.instrument === selectedInstrument ? "data-table__row--selected" : undefined
              }
            >
              <td>{coverage.instrument}</td>
              <td>{coverage.candle_count.toLocaleString()}</td>
              <td>{displayValue(coverage.from, "none")}</td>
              <td>{displayValue(coverage.to, "none")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReadinessList({
  preflight,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
}) {
  const rows = preflight?.readiness ?? [];
  if (rows.length === 0) {
    return (
      <p className="workflow-status-line">
        Preflight has not selected a complete research window yet.
      </p>
    );
  }
  return (
    <ul className="workflow-readiness">
      {rows.map((row) => (
        <li key={row.name}>
          <span className={`workflow-badge workflow-badge--${row.status}`}>{row.status}</span>
          <strong>{row.name}</strong>
          <span>{row.message}</span>
        </li>
      ))}
    </ul>
  );
}

function ParameterTable({ params }: { readonly params: Record<string, unknown> }) {
  const rows = Object.entries(params);
  return (
    <table className="data-table">
      <tbody>
        {rows.map(([key, value]) => (
          <tr key={key}>
            <th>{key}</th>
            <td>{displayValue(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BacktestSummary({ run }: { readonly run: BacktestRunDetail }) {
  return (
    <div className="workflow-run-summary">
      <Metric label="Run" value={run.run_id === null ? "latest" : `#${run.run_id}`} />
      <Metric label="Trades" value={displayValue(run.stats.trade_count, "0")} />
      <Metric label="Expectancy" value={displayValue(run.stats.expectancy, "0")} />
      <Metric label="Net P&L" value={displayValue(run.stats.net_pnl, "0")} />
    </div>
  );
}

function RecentRunSummary({ runs }: { readonly runs: readonly BacktestRunSummary[] }) {
  const run = runs[0];
  if (!run) {
    return <p className="workflow-status-line">No backtest has been saved yet.</p>;
  }
  return (
    <p className="workflow-status-line">
      Latest backtest #{run.run_id}: {run.trade_count} trades, expectancy{" "}
      {displayValue(run.stats.expectancy, "0")}.
    </p>
  );
}

interface WorkflowTarget {
  readonly variant: PaperVariant;
  readonly row: VariantLeaderboardRow | null;
  readonly tradeCount: number;
}

function workflowTargetVariant(variants: LabVariantOverview): WorkflowTarget | null {
  const row = variants.leaderboard[0] ?? null;
  const variant =
    row?.variant ??
    variants.variants.find((item) => item.status === "promoted") ??
    variants.variants[0];
  if (!variant) {
    return null;
  }
  return {
    variant,
    row,
    tradeCount: row?.stats.trade_count ?? 0,
  };
}

function backtestPayload(target: PaperVariant | null, instrument: string): BacktestStartPayload {
  const payload: BacktestStartPayload = {
    source: "persisted_candles",
    instrument,
    candle_window_days: BACKTEST_WINDOW_DAYS,
  };
  if (target !== null) {
    payload.strategy_params = target.params;
    payload.variant_id = target.id;
    payload.variant_label = target.label;
  }
  return payload;
}

function coverageRows(
  source: CandleSourceStatus | null,
  selectedInstrument: string
): CandleCoverage[] {
  if (source === null) {
    return [{ instrument: selectedInstrument, candle_count: 0, from: null, to: null }];
  }
  const coverages = source.instrument_coverages?.length
    ? source.instrument_coverages
    : [source.coverage];
  return coverages.some((coverage) => coverage.instrument === selectedInstrument)
    ? coverages
    : [...coverages, { instrument: selectedInstrument, candle_count: 0, from: null, to: null }];
}

function selectedCoverageRow(
  coverages: readonly CandleCoverage[],
  selectedInstrument: string
): CandleCoverage {
  return (
    coverages.find((coverage) => coverage.instrument === selectedInstrument) ?? {
      instrument: selectedInstrument,
      candle_count: 0,
      from: null,
      to: null,
    }
  );
}

function instrumentOptions(
  source: CandleSourceStatus | null,
  selectedInstrument: string
): string[] {
  const values = source?.research_instruments?.length
    ? source.research_instruments
    : [selectedInstrument];
  return values.includes(selectedInstrument) ? values : [selectedInstrument, ...values];
}

function coverageRange(coverage: CandleCoverage): string {
  if (coverage.candle_count === 0) {
    return "none";
  }
  return `${displayValue(coverage.from, "none")} to ${displayValue(coverage.to, "none")}`;
}

function liveStreamLabel(source: CandleSourceStatus | null): string {
  const stream = source?.live_stream;
  if (!stream) {
    return "unknown";
  }
  if (!stream.configured) {
    return "not configured";
  }
  if (!stream.enabled) {
    return "disabled";
  }
  return stream.running ? "running" : stream.state;
}

function researchDays(preflight: OptimizationPreflightResponse | null): string {
  const protocol = preflight?.research_protocol;
  if (!protocol) {
    return "0";
  }
  return `${protocol.evaluable_day_count}/${protocol.data_requirements.min_evaluable_days}`;
}

function studyNotice(status: string, trialCount: number, candidateCount: number): string {
  return `Study ${status}: ${trialCount} trials, ${candidateCount} candidates.`;
}

function importNotice(result: CandleImportResult): string {
  const target =
    result.instrument === "research_universe"
      ? `${result.results?.length ?? 0} instruments`
      : result.instrument;
  return `Imported ${result.imported_count.toLocaleString()} of ${result.requested_count.toLocaleString()} requested candles for ${target}.`;
}

function candidateForVariant(
  snapshot: LabSnapshot | null,
  variant: PaperVariant | null
): CandidateScatterPoint | null {
  if (snapshot === null || variant === null) {
    return null;
  }
  return (
    snapshot.candidates.find((candidate) => candidate.trial_id === variant.source_trial_id) ?? null
  );
}

function variantInstrument(variant: PaperVariant | null | undefined): string | null {
  const value = variant?.params.instrument;
  return typeof value === "string" ? value : null;
}

function score(variant: PaperVariant, key: string): string {
  return variant.trial_scores[key] ?? "unknown";
}

function latestEvent(
  events: readonly EventLogItem[],
  predicate: (event: EventLogItem) => boolean
): EventLogItem | null {
  return events.find(predicate) ?? null;
}

function eventLabel(event: EventLogItem | null): string {
  if (event === null) {
    return "none";
  }
  return `${event.type} at ${event.ts}`;
}

function backfillStart(count: number): string {
  return new Date(Date.now() - count * 60_000).toISOString();
}
