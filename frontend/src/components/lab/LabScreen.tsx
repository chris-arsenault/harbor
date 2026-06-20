import type {
  CandleSourceStatus,
  LabVariantOverview,
  OptimizationStartPayload,
} from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { CandleSourcePanel } from "./CandleSourcePanel";
import { LabView, TuningRunNotice } from "./LabView";
import { StudyWorkbench } from "./StudyWorkbench";
import type { TuningStudyConfig } from "./tuningPayload";

interface LabScreenProps {
  readonly snapshot: Parameters<typeof LabView>[0]["snapshot"] | null;
  readonly variants: LabVariantOverview;
  readonly liveStatus: string | null;
  readonly tuningRun: Parameters<typeof LabView>[0]["tuningRun"];
  readonly onStartOptimization: Parameters<typeof LabView>[0]["onStartOptimization"];
  readonly onCreatePaperVariant: Parameters<typeof LabView>[0]["onCreatePaperVariant"];
  readonly onRetireVariant: Parameters<typeof LabView>[0]["onRetireVariant"];
  readonly onPromoteVariant: Parameters<typeof LabView>[0]["onPromoteVariant"];
  readonly candleSource: CandleSourceStatus | null;
  readonly candleSourcePending: boolean;
  readonly candleSourceError: string | null;
  readonly candleImportResult: Parameters<typeof LabView>[0]["candleImportResult"];
  readonly onImportCandles: Parameters<typeof LabView>[0]["onImportCandles"];
  readonly studyConfig: TuningStudyConfig;
  readonly onStudyConfigChange: (config: TuningStudyConfig) => void;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
}

export function LabScreen(props: LabScreenProps) {
  const {
    snapshot,
    variants,
    liveStatus,
    tuningRun,
    onStartOptimization,
    onCreatePaperVariant,
    onRetireVariant,
    onPromoteVariant,
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
  } = props;
  if (snapshot === null) {
    return <EmptyLabScreen {...props} />;
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
      tuningRun={tuningRun}
      candleSource={candleSource}
      candleSourcePending={candleSourcePending}
      candleSourceError={candleSourceError}
      candleImportResult={candleImportResult}
      onImportCandles={onImportCandles}
      studyConfig={studyConfig}
      onStudyConfigChange={onStudyConfigChange}
      studyPayload={studyPayload}
      preflight={preflight}
      preflightPending={preflightPending}
      preflightError={preflightError}
    />
  );
}

function EmptyLabScreen({
  tuningRun,
  onStartOptimization,
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
}: LabScreenProps) {
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
      <TuningRunNotice tuningRun={tuningRun} snapshot={null} />
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
