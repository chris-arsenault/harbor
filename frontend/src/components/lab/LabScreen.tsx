import type { LabVariantOverview } from "../../api/types";
import { LabView } from "./LabView";

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
        <p className="lab-live-status">Loading Lab</p>
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
