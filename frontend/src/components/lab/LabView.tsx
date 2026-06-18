import type { LabSnapshot, LabVariantOverview } from "../../api/types";
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
}

export function LabView({
  snapshot,
  variants,
  onStartOptimization,
  onCreatePaperVariant,
  onRetireVariant,
  onPromoteVariant,
  liveStatus,
}: LabViewProps) {
  const firstCurve = variants.equity_curves.find((curve) => curve.points.length > 0) ?? null;

  return (
    <section className="lab-view" aria-label="Lab">
      <section className="lab-actions" aria-label="Tuning controls">
        <span>Optimizer</span>
        <button
          type="button"
          className="lab-button"
          onClick={() => void onStartOptimization(DEFAULT_TUNING_PAYLOAD)}
        >
          Start tuning study
        </button>
      </section>
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
