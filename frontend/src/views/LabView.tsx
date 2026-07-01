import type {
  CandleImportRequest,
  CandleImportResult,
  CandleSourceStatus,
  LabSnapshot,
  LabVariantOverview,
  OptimizationStartPayload,
} from "../api/types";
import type { OptimizationPreflightResponse } from "../api/optimizerTypes";
import { EmptyState, Notice, Panel, ViewHead } from "../ui/primitives";
import { BookRecorder } from "./lab/BookRecorder";
import { CandleSource } from "./lab/CandleSource";
import { ArchivedCrossInstrument, CrossInstrument } from "./lab/CrossInstrument";
import { EdgeCapture } from "./lab/EdgeCapture";
import { EdgeScan } from "./lab/EdgeScan";
import { TriangularCapture } from "./lab/TriangularCapture";
import { EdgeStudy } from "./lab/EdgeStudy";
import { SearchSpacePanel } from "./lab/SearchSpace";
import { StudyResults } from "./lab/StudyResults";
import { Workbench, type TuningRunView } from "./lab/Workbench";

export interface LabViewModel {
  readonly snapshot: LabSnapshot | null;
  readonly variants: LabVariantOverview;
  readonly liveStatus: string | null;
  readonly candleSource: CandleSourceStatus | null;
  readonly candleSourcePending: boolean;
  readonly candleSourceError: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
  readonly selectedInstrument: string;
  readonly onInstrumentChange: (instrument: string) => void;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
  readonly tuningRun: TuningRunView;
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
}

export function LabView({ model }: { readonly model: LabViewModel }) {
  const coverageCount = model.candleSource?.coverage.candle_count ?? 0;
  return (
    <section className="view" aria-label="Lab">
      <ViewHead
        kicker="Research"
        title="Lab"
        sub="Walk-forward hyperparameter search with strict in/out-of-sample separation."
      />
      <CandleSource
        source={model.candleSource}
        selectedInstrument={model.selectedInstrument}
        pending={model.candleSourcePending}
        errorMessage={model.candleSourceError}
        importResult={model.importResult}
        onInstrumentChange={model.onInstrumentChange}
        onImportCandles={model.onImportCandles}
      />
      <BookRecorder />
      <CrossInstrument />
      <TriangularCapture />
      <Workbench
        studyPayload={model.studyPayload}
        preflight={model.preflight}
        preflightPending={model.preflightPending}
        preflightError={model.preflightError}
        tuningRun={model.tuningRun}
        canStart={coverageCount > 0}
        onStartOptimization={model.onStartOptimization}
      />
      <SearchSpacePanel preflight={model.preflight} />
      {model.snapshot ? (
        <StudyResults
          snapshot={model.snapshot}
          variants={model.variants}
          onPromote={model.onPromoteVariant}
          onRetire={model.onRetireVariant}
        />
      ) : (
        <Panel title="Studies" label="Studies">
          <EmptyState
            glyph="⚗"
            title="No tuning studies yet"
            hint="Import candles, confirm preflight is ready, then start a research study."
          />
        </Panel>
      )}
      {model.liveStatus ? <Notice>{model.liveStatus}</Notice> : null}
      <details className="disc" aria-label="Archived hypotheses">
        <summary>Archived hypotheses</summary>
        <div className="disc__body stack">
          <p className="mute">
            Rejected or paused scans live here for reproducibility. Keep active Lab panels focused
            on hypotheses that can still inform future work.
          </p>
          <ArchivedCrossInstrument />
          <EdgeScan />
          <EdgeCapture />
          <EdgeStudy instrument={model.selectedInstrument} />
        </div>
      </details>
    </section>
  );
}
