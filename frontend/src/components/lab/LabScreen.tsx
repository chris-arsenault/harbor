import type { LabVariantOverview } from "../../api/types";
import { LabView } from "./LabView";
import { DEFAULT_TUNING_PAYLOAD } from "./tuningPayload";

interface LabScreenProps {
  readonly snapshot: Parameters<typeof LabView>[0]["snapshot"] | null;
  readonly variants: LabVariantOverview;
  readonly liveStatus: string | null;
  readonly onStartOptimization: Parameters<typeof LabView>[0]["onStartOptimization"];
  readonly onCreatePaperVariant: Parameters<typeof LabView>[0]["onCreatePaperVariant"];
  readonly onRetireVariant: Parameters<typeof LabView>[0]["onRetireVariant"];
  readonly onPromoteVariant: Parameters<typeof LabView>[0]["onPromoteVariant"];
}

export function LabScreen({
  snapshot,
  variants,
  liveStatus,
  onStartOptimization,
  onCreatePaperVariant,
  onRetireVariant,
  onPromoteVariant,
}: LabScreenProps) {
  if (snapshot === null) {
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
        <section className="lab-panel" aria-label="Lab empty state">
          <h2>No tuning studies yet</h2>
        </section>
        {liveStatus ? (
          <p className="lab-live-status" aria-live="polite">
            {liveStatus}
          </p>
        ) : null}
      </section>
    );
  }
  return (
    <LabView
      snapshot={snapshot}
      variants={variants}
      onStartOptimization={onStartOptimization}
      onCreatePaperVariant={onCreatePaperVariant}
      onRetireVariant={onRetireVariant}
      onPromoteVariant={onPromoteVariant}
      liveStatus={liveStatus}
    />
  );
}
