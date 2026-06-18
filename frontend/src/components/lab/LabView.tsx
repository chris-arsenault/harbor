import type {
  CandleImportRequest,
  CandleImportResult,
  CandleSourceStatus,
  LabSnapshot,
  LabVariantOverview,
  OptimizationStartResponse,
} from "../../api/types";
import { displayValue } from "../../utils/format";
import { CandidateScatter } from "./CandidateScatter";
import { LabActions } from "./LabActions";
import { StudyProgress } from "./StudyProgress";
import { TrialDiagnostics } from "./TrialDiagnostics";
import { noCandidateExplanation, trialDiagnosticRows } from "./trialDiagnosticsModel";
import { VariantEquityChart } from "./VariantEquityChart";
import { VariantLeaderboard } from "./VariantLeaderboard";
import { DEFAULT_TUNING_PAYLOAD } from "./tuningPayload";

interface LabViewProps {
  readonly snapshot: LabSnapshot;
  readonly variants: LabVariantOverview;
  readonly tuningRun: TuningRunState;
  readonly onStartOptimization: (payload: Record<string, unknown>) => void | Promise<void>;
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
}: LabViewProps) {
  const firstCurve = variants.equity_curves.find((curve) => curve.points.length > 0) ?? null;
  const canStartOptimization = (candleSource?.coverage?.candle_count ?? 0) > 0;

  return (
    <section className="lab-view" aria-label="Lab">
      <section className="lab-actions" aria-label="Tuning controls">
        <span>Optimizer</span>
        <button
          type="button"
          className="lab-button"
          disabled={!canStartOptimization || tuningRun.pending}
          onClick={() => void onStartOptimization(DEFAULT_TUNING_PAYLOAD)}
        >
          {tuningRun.pending ? "Running tuning study" : "Start tuning study"}
        </button>
      </section>
      <CandleSourcePanel
        source={candleSource}
        pending={candleSourcePending}
        errorMessage={candleSourceError}
        importResult={candleImportResult}
        onImportCandles={onImportCandles}
      />
      <TuningRunNotice tuningRun={tuningRun} snapshot={snapshot} />
      <StudyProgress study={snapshot.study} />
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

export function CandleSourcePanel({
  source,
  pending,
  errorMessage,
  importResult,
  onImportCandles,
}: {
  readonly source: CandleSourceStatus | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
}) {
  const facts = candleSourceFacts(source);
  const instrument = facts.instrument;
  const importConfigured = facts.oandaHistoricalImportConfigured;
  const latestPagePayload = {
    instrument,
    count: facts.importPolicy.pageSize,
  };
  return (
    <section className="lab-panel" aria-label="Candle source">
      <div className="lab-panel__header">
        <h2>Candle Dataset</h2>
        <div className="lab-panel__actions">
          <button
            type="button"
            className="lab-button lab-button--quiet"
            disabled={pending || !importConfigured}
            onClick={() => void onImportCandles(latestPagePayload)}
          >
            Refresh latest {facts.importPolicy.pageSize.toLocaleString()} M1
          </button>
          <button
            type="button"
            className="lab-button"
            disabled={pending || !importConfigured}
            onClick={() =>
              void onImportCandles({
                instrument,
                count: facts.importPolicy.defaultCount,
                from: backfillStart(facts.importPolicy.defaultCount),
              })
            }
          >
            Backfill {importDaysLabel(facts.importPolicy.defaultCount)}
          </button>
        </div>
      </div>
      <p className="lab-source-note">{facts.guidance}</p>
      <ul className="fact-list">
        {facts.rows.map((row) => (
          <li key={row.label}>
            {row.label}: {row.value}
          </li>
        ))}
      </ul>
      {errorMessage ? (
        <p className="lab-live-status" aria-live="polite">
          {errorMessage}
        </p>
      ) : null}
      {importResult ? (
        <p className="lab-live-status" aria-live="polite">
          Upserted {importResult.imported_count} of {importResult.requested_count} requested candles
          from {importResult.from ?? "latest page"}. Coverage {importResult.coverage.from ?? "none"}{" "}
          to {importResult.coverage.to ?? "none"}.
        </p>
      ) : null}
    </section>
  );
}

function candleSourceFacts(source: CandleSourceStatus | null) {
  if (source === null) {
    return {
      instrument: "EUR_USD",
      oandaHistoricalImportConfigured: false,
      guidance:
        "Candles come from OANDA practice REST into the persisted M1 midpoint candle store. Configure OANDA_ACCOUNT_ID and OANDA_API_TOKEN before importing.",
      importPolicy: {
        pageSize: 5000,
        defaultCount: 43200,
      },
      rows: candleSourceRows({
        source: "persisted_candles",
        instrument: "EUR_USD",
        granularity: "M1",
        priceComponent: "midpoint",
        candleCount: 0,
        from: "none",
        to: "none",
        configured: false,
        pageSize: 5000,
        defaultCount: 43200,
        upsertKey: "instrument+timestamp",
        replacesExisting: false,
      }),
    };
  }

  const coverage = source.coverage;
  const importPolicy = source.historical_import;
  const guidance = candleSourceGuidance(source);
  return {
    instrument: source.instrument,
    oandaHistoricalImportConfigured: source.oanda_historical_import_configured,
    importPolicy: {
      pageSize: importPolicy.page_size,
      defaultCount: importPolicy.default_count,
    },
    guidance,
    rows: candleSourceRows({
      source: source.primary_source,
      instrument: source.instrument,
      granularity: source.granularity,
      priceComponent: source.price_component,
      candleCount: coverage.candle_count,
      from: coverage.from ?? "none",
      to: coverage.to ?? "none",
      configured: source.oanda_historical_import_configured,
      pageSize: importPolicy.page_size,
      defaultCount: importPolicy.default_count,
      upsertKey: importPolicy.upsert_key,
      replacesExisting: importPolicy.replaces_existing,
    }),
  };
}

function candleSourceRows(input: {
  readonly source: string;
  readonly instrument: string;
  readonly granularity: string;
  readonly priceComponent: string;
  readonly candleCount: number;
  readonly from: string;
  readonly to: string;
  readonly configured: boolean;
  readonly pageSize: number;
  readonly defaultCount: number;
  readonly upsertKey: string;
  readonly replacesExisting: boolean;
}) {
  return [
    { label: "path", value: "OANDA practice REST -> persisted candles -> Lab optimizer" },
    { label: "source", value: input.source },
    { label: "write policy", value: input.replacesExisting ? "replace" : "upsert" },
    { label: "upsert key", value: input.upsertKey },
    { label: "method", value: "OANDA historical import" },
    { label: "instrument", value: input.instrument },
    { label: "granularity", value: input.granularity },
    { label: "price", value: input.priceComponent },
    { label: "candles", value: String(input.candleCount) },
    { label: "from", value: input.from },
    { label: "to", value: input.to },
    { label: "latest-page request", value: `${input.pageSize.toLocaleString()} M1 candles` },
    { label: "backfill request", value: `${input.defaultCount.toLocaleString()} M1 candles` },
    { label: "configured", value: String(input.configured) },
  ];
}

function candleSourceGuidance(source: CandleSourceStatus) {
  if (!source.oanda_historical_import_configured) {
    return "OANDA credentials are missing. Import would load practice M1 midpoint candles into Harbor's database for Lab studies.";
  }
  if (source.coverage.candle_count === 0) {
    return "No persisted M1 midpoint candles are available for Lab tuning.";
  }
  return "Lab tuning reads the persisted M1 midpoint candle dataset shown below.";
}

function backfillStart(count: number): string {
  return new Date(Date.now() - count * 60_000).toISOString();
}

function importDaysLabel(count: number): string {
  const days = Math.round(count / 1440);
  return `${days} days`;
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
