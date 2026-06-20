import type {
  CandleImportRequest,
  CandleImportResult,
  CandleSourceStatus,
  LabSnapshot,
  LabVariantOverview,
  OptimizationStartResponse,
  OptimizationStartPayload,
} from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { displayValue } from "../../utils/format";
import { CandidateScatter } from "./CandidateScatter";
import { CandleSourcePanel } from "./CandleSourcePanel";
import { LabActions } from "./LabActions";
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
  tuningRun,
  onStartOptimization,
  onCreatePaperVariant,
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
      <StudyResults
        candidates={snapshot.candidates}
        optimizationResult={tuningRun.result}
        paperCandidateCount={tuningRun.result?.candidates.length ?? snapshot.study.candidate_count}
      />
      <TrialDiagnostics candidates={snapshot.candidates} optimizationResult={tuningRun.result} />
      <div className="lab-grid">
        <CandidateScatter candidates={snapshot.candidates} />
        <VariantEquityChart curve={firstCurve} />
      </div>
      <CandidateParameters snapshot={snapshot} />
      <VariantLeaderboard
        rows={variants.leaderboard}
        onRetireVariant={onRetireVariant}
        onPromoteVariant={onPromoteVariant}
      />
      <DataSeparation snapshot={snapshot} variants={variants} />
      <LabActions onCreatePaperVariant={onCreatePaperVariant} />
      {liveStatus ? (
        <p className="lab-live-status" aria-live="polite">
          {liveStatus}
        </p>
      ) : null}
    </section>
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
  if (tuningRun.pending) {
    return (
      <p className="lab-run-notice" aria-live="polite">
        Tuning study is running.
      </p>
    );
  }
  if (tuningRun.errorMessage !== null) {
    return (
      <p className="lab-run-notice lab-run-notice--error" aria-live="polite">
        {tuningRun.errorMessage}
      </p>
    );
  }
  if (tuningRun.result !== null) {
    const studyId = tuningRun.result.study_id;
    const trialCount = tuningRun.result.trials.length;
    const candidateCount = tuningRun.result.candidates.length;
    const explanation = noCandidateExplanation(
      trialDiagnosticRows({ candidates: [], optimizationResult: tuningRun.result })
    );
    return (
      <p className="lab-run-notice" aria-live="polite">
        Study {studyId === null ? "completed" : `#${studyId} completed`}: {trialCount} trials,{" "}
        {candidateCount} candidates.
        {candidateCount === 0 ? ` ${explanation}` : " Candidates are ready for paper variants."}
      </p>
    );
  }
  if (
    snapshot !== null &&
    snapshot.study.status === "completed" &&
    snapshot.study.candidate_count === 0
  ) {
    const explanation = noCandidateExplanation(
      trialDiagnosticRows({
        candidates: snapshot.candidates,
        optimizationResult: null,
      })
    );
    return (
      <p className="lab-run-notice" aria-live="polite">
        Latest study #{snapshot.study.study_id} completed: {snapshot.study.trial_count} trials, 0
        candidates. {explanation}
      </p>
    );
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
    <section className="lab-panel" aria-label="Data separation">
      <h2>Data Separation</h2>
      <ul className="fact-list">
        {Object.entries({ ...snapshot.data_separation, ...variants.data_separation }).map(
          ([key, value]) => (
            <li key={key}>
              {key}: {displayValue(value)}
            </li>
          )
        )}
      </ul>
    </section>
  );
}
