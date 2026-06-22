import type {
  CandleImportRequest,
  CandleImportResult,
  CandleSourceStatus,
  EventLogItem,
  LabSnapshot,
  LabVariantOverview,
  OptimizationStartResponse,
  OptimizationStartPayload,
} from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { displayValue } from "../../utils/format";
import { CandidateScatter } from "./CandidateScatter";
import { CandleSourcePanel } from "./CandleSourcePanel";
import { SelectedCandidate } from "./SelectedCandidate";
import { StudyResults } from "./StudyResults";
import { StudyWorkbench } from "./StudyWorkbench";
import { StudyProgress } from "./StudyProgress";
import { TrialDiagnostics } from "./TrialDiagnostics";
import { noCandidateExplanation, trialDiagnosticRows } from "./trialDiagnosticsModel";
import type { TuningStudyConfig } from "./tuningPayload";
import { VariantEquityChart } from "./VariantEquityChart";
import { VariantLeaderboard } from "./VariantLeaderboard";

interface LabViewProps {
  readonly snapshot: LabSnapshot;
  readonly variants: LabVariantOverview;
  readonly events: readonly EventLogItem[];
  readonly tuningRun: TuningRunState;
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
  readonly onCreatePaperVariant: (payload: {
    trial_id: number;
    label: string;
  }) => void | Promise<void>;
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
  readonly liveStatus: string | null;
  readonly candleSource: CandleSourceStatus | null;
  readonly candleSourcePending: boolean;
  readonly candleSourceError: string | null;
  readonly candleImportResult: CandleImportResult | null;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
  readonly studyConfig: TuningStudyConfig;
  readonly onStudyConfigChange: (config: TuningStudyConfig) => void;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
}

export interface TuningRunState {
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly result: OptimizationStartResponse | null;
}

export function LabView({
  snapshot,
  variants,
  events,
  tuningRun,
  onStartOptimization,
  onRetireVariant,
  onPromoteVariant,
  liveStatus,
  candleSource,
  candleSourcePending,
  candleSourceError,
  candleImportResult,
  onImportCandles,
  studyConfig,
  onStudyConfigChange,
  studyPayload,
  preflight,
  preflightPending,
  preflightError,
}: LabViewProps) {
  const firstCurve = variants.equity_curves.find((curve) => curve.points.length > 0) ?? null;

  return (
    <section className="lab-view" aria-label="Lab">
      <CandleSourcePanel
        source={candleSource}
        pending={candleSourcePending}
        errorMessage={candleSourceError}
        importResult={candleImportResult}
        onImportCandles={onImportCandles}
      />
      <StudyWorkbench
        studyConfig={studyConfig}
        onStudyConfigChange={onStudyConfigChange}
        studyPayload={studyPayload}
        preflight={preflight}
        preflightPending={preflightPending}
        preflightError={preflightError}
        tuningRun={tuningRun}
        candleSource={candleSource}
        onStartOptimization={onStartOptimization}
      />
      <TuningRunNotice tuningRun={tuningRun} snapshot={snapshot} />
      <StudyProgress study={snapshot.study} />
      <SelectedCandidate
        candidates={snapshot.candidates}
        variants={snapshot.variants}
        liveStatus={liveStatus}
        events={events}
        onRetireVariant={onRetireVariant}
        onPromoteVariant={onPromoteVariant}
      />
      <StudyResults
        candidates={snapshot.candidates}
        optimizationResult={tuningRun.result}
        paperCandidateCount={tuningRun.result?.candidates.length ?? snapshot.study.candidate_count}
      />
      <div className="lab-grid">
        <CandidateScatter candidates={snapshot.candidates} />
        <VariantEquityChart curve={firstCurve} />
      </div>
      <VariantLeaderboard
        rows={variants.leaderboard}
        onRetireVariant={onRetireVariant}
        onPromoteVariant={onPromoteVariant}
      />
      <TrialDiagnostics candidates={snapshot.candidates} optimizationResult={tuningRun.result} />
      <CandidateParameters snapshot={snapshot} />
      <DataSeparation snapshot={snapshot} variants={variants} />
      <LabLiveStatus status={liveStatus} />
    </section>
  );
}

function LabLiveStatus({ status }: { readonly status: string | null }) {
  if (!status) {
    return null;
  }
  return (
    <p className="lab-live-status" aria-live="polite">
      {status}
    </p>
  );
}

function CandidateParameters({ snapshot }: { readonly snapshot: LabSnapshot }) {
  const parameterRows = snapshot.candidates.flatMap((candidate) =>
    Object.entries(candidate.params).map(([key, value]) => ({
      id: `${candidate.trial_id}-${key}`,
      trialNo: candidate.trial_no,
      key,
      value,
    }))
  );
  const parameterLabel =
    parameterRows.length === 1 ? "1 parameter" : `${parameterRows.length} parameters`;

  return (
    <details className="lab-panel lab-disclosure" aria-label="Candidate parameters">
      <summary className="lab-disclosure__summary">
        <h2>Candidate Parameters</h2>
        <span>{parameterLabel}</span>
      </summary>
      <div className="lab-table-wrap">
        <table className="lab-table">
          <thead>
            <tr>
              <th>Trial</th>
              <th>Parameter</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {parameterRows.length === 0 ? (
              <tr>
                <td colSpan={3}>No candidate parameters.</td>
              </tr>
            ) : (
              parameterRows.map((row) => (
                <tr key={row.id}>
                  <td>{row.trialNo}</td>
                  <td>{row.key}</td>
                  <td>{displayValue(row.value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function TuningRunNotice({
  tuningRun,
  snapshot,
}: {
  readonly tuningRun: TuningRunState;
  readonly snapshot: LabSnapshot | null;
}) {
  const notice = tuningRunNotice(tuningRun, snapshot);
  if (notice === null) {
    return null;
  }
  const className =
    notice.level === "error" ? "lab-run-notice lab-run-notice--error" : "lab-run-notice";
  return (
    <p className={className} aria-live="polite">
      {notice.message}
    </p>
  );
}

interface RunNotice {
  readonly level: "info" | "error";
  readonly message: string;
}

function tuningRunNotice(
  tuningRun: TuningRunState,
  snapshot: LabSnapshot | null
): RunNotice | null {
  if (tuningRun.pending) {
    return { level: "info", message: "Research study is running." };
  }
  if (tuningRun.errorMessage !== null) {
    return { level: "error", message: tuningRun.errorMessage };
  }
  return (
    queuedResultNotice(tuningRun, snapshot) ??
    completedResultNotice(tuningRun) ??
    snapshotNotice(snapshot)
  );
}

function queuedResultNotice(
  tuningRun: TuningRunState,
  snapshot: LabSnapshot | null
): RunNotice | null {
  const result = tuningRun.result;
  if (
    result !== null &&
    result.status === "running" &&
    snapshotSupersedesRunningResult(snapshot, result.study_id)
  ) {
    return null;
  }
  if (tuningRun.result !== null && tuningRun.result.status === "running") {
    const studyId = tuningRun.result.study_id;
    return {
      level: "info",
      message: `Study ${
        studyId === null ? "started" : `#${studyId} started`
      }. Trials will appear when the research run completes.`,
    };
  }
  return null;
}

function snapshotSupersedesRunningResult(
  snapshot: LabSnapshot | null,
  studyId: number | null
): boolean {
  return (
    snapshot !== null && snapshot.study.study_id === studyId && snapshot.study.status !== "running"
  );
}

function completedResultNotice(tuningRun: TuningRunState): RunNotice | null {
  const result = tuningRun.result;
  if (result === null || result.status === "running") {
    return null;
  }
  const studyId = result.study_id;
  const trialCount = result.trials.length;
  const candidateCount = result.candidates.length;
  const explanation = noCandidateExplanation(
    trialDiagnosticRows({ candidates: [], optimizationResult: result })
  );
  return {
    level: "info",
    message: `Study ${
      studyId === null ? "completed" : `#${studyId} completed`
    }: ${trialCount} trials, ${candidateCount} candidates.${
      candidateCount === 0 ? ` ${explanation}` : " Candidates are ready for paper variants."
    }`,
  };
}

function snapshotNotice(snapshot: LabSnapshot | null): RunNotice | null {
  if (snapshot === null) {
    return null;
  }
  if (snapshot.study.status === "running") {
    return {
      level: "info",
      message: `Study #${snapshot.study.study_id} is running. Trials will appear when the research run completes.`,
    };
  }
  if (snapshot.study.status === "failed") {
    return {
      level: "error",
      message: `Study #${snapshot.study.study_id} failed before producing candidates.`,
    };
  }
  if (snapshot.study.status === "completed" && snapshot.study.candidate_count === 0) {
    const explanation = noCandidateExplanation(
      trialDiagnosticRows({
        candidates: snapshot.candidates,
        optimizationResult: null,
      })
    );
    return {
      level: "info",
      message: `Latest study #${snapshot.study.study_id} completed: ${snapshot.study.trial_count} trials, 0 candidates. ${explanation}`,
    };
  }
  return null;
}

function DataSeparation({
  snapshot,
  variants,
}: {
  readonly snapshot: LabSnapshot;
  readonly variants: LabVariantOverview;
}) {
  return (
    <details className="lab-panel lab-disclosure" aria-label="Technical data boundaries">
      <summary className="lab-disclosure__summary">
        <h2>Technical Data Boundaries</h2>
        <span>audit</span>
      </summary>
      <ul className="fact-list">
        {Object.entries({ ...snapshot.data_separation, ...variants.data_separation }).map(
          ([key, value]) => (
            <li key={key}>
              {key}: {displayValue(value)}
            </li>
          )
        )}
      </ul>
    </details>
  );
}
