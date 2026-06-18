import type { CandleSourceStatus, LabSnapshot, LabVariantOverview } from "../../api/types";
import { displayValue } from "../../utils/format";
import { CandidateScatter } from "./CandidateScatter";
import { LabActions } from "./LabActions";
import { StudyProgress } from "./StudyProgress";
import { VariantEquityChart } from "./VariantEquityChart";
import { VariantLeaderboard } from "./VariantLeaderboard";
import { DEFAULT_TUNING_PAYLOAD } from "./tuningPayload";

interface LabViewProps {
  readonly snapshot: LabSnapshot;
  readonly variants: LabVariantOverview;
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
  readonly onImportCandles: (payload: { instrument: string }) => void | Promise<void>;
}

export function LabView({
  snapshot,
  variants,
  onStartOptimization,
  onCreatePaperVariant,
  onRetireVariant,
  onPromoteVariant,
  liveStatus,
  candleSource,
  candleSourcePending,
  candleSourceError,
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
          disabled={!canStartOptimization}
          onClick={() => void onStartOptimization(DEFAULT_TUNING_PAYLOAD)}
        >
          Start tuning study
        </button>
      </section>
      <CandleSourcePanel
        source={candleSource}
        pending={candleSourcePending}
        errorMessage={candleSourceError}
        onImportCandles={onImportCandles}
      />
      <StudyProgress study={snapshot.study} />
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
  onImportCandles,
}: {
  readonly source: CandleSourceStatus | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly onImportCandles: (payload: { instrument: string }) => void | Promise<void>;
}) {
  const facts = candleSourceFacts(source);
  const instrument = facts.instrument;
  return (
    <section className="lab-panel" aria-label="Candle source">
      <div className="lab-panel__header">
        <h2>Candle Source</h2>
        <button
          type="button"
          className="lab-button lab-button--quiet"
          disabled={pending}
          onClick={() => void onImportCandles({ instrument })}
        >
          Import OANDA candles
        </button>
      </div>
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
    </section>
  );
}

function candleSourceFacts(source: CandleSourceStatus | null) {
  if (source === null) {
    return {
      instrument: "EUR_USD",
      rows: candleSourceRows({
        source: "persisted_candles",
        instrument: "EUR_USD",
        candleCount: 0,
        from: "none",
        to: "none",
        configured: false,
      }),
    };
  }

  const coverage = source.coverage;
  return {
    instrument: source.instrument,
    rows: candleSourceRows({
      source: source.primary_source,
      instrument: source.instrument,
      candleCount: coverage.candle_count,
      from: coverage.from ?? "none",
      to: coverage.to ?? "none",
      configured: source.oanda_historical_import_configured,
    }),
  };
}

function candleSourceRows(input: {
  readonly source: string;
  readonly instrument: string;
  readonly candleCount: number;
  readonly from: string;
  readonly to: string;
  readonly configured: boolean;
}) {
  return [
    { label: "source", value: input.source },
    { label: "method", value: "oanda_historical_import" },
    { label: "instrument", value: input.instrument },
    { label: "candles", value: String(input.candleCount) },
    { label: "from", value: input.from },
    { label: "to", value: input.to },
    { label: "configured", value: String(input.configured) },
  ];
}

function CandidateParameters({ snapshot }: { readonly snapshot: LabSnapshot }) {
  return (
    <section className="lab-panel" aria-label="Candidate parameters">
      <h2>Candidate Parameters</h2>
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
            {snapshot.candidates.flatMap((candidate) =>
              Object.entries(candidate.params).map(([key, value]) => (
                <tr key={`${candidate.trial_id}-${key}`}>
                  <td>{candidate.trial_no}</td>
                  <td>{key}</td>
                  <td>{displayValue(value)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
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
