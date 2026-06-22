import type { ProductPageProps } from "../../App";
import { WorkflowView } from "./WorkflowView";

export function AppWorkflowRoute({
  selectedResearchInstrument,
  onResearchInstrumentChange,
  lab,
  backtests,
  backtestPage,
  productEvents,
  dashboard,
  controls,
}: ProductPageProps) {
  return (
    <WorkflowView
      selectedInstrument={selectedResearchInstrument}
      onInstrumentChange={onResearchInstrumentChange}
      candleSource={lab.candleSource}
      candleSourcePending={lab.candleSourcePending}
      candleSourceError={lab.candleSourceError}
      importResult={lab.importResult}
      onImportCandles={lab.importCandles}
      studyPayload={lab.studyPayload}
      preflight={lab.preflight}
      preflightPending={lab.preflightPending}
      preflightError={lab.preflightError}
      tuningRun={lab.tuningRun}
      snapshot={lab.snapshot}
      variants={lab.variantOverview}
      events={productEvents}
      onStartOptimization={lab.startOptimization}
      backtestRuns={backtests.data?.runs ?? []}
      selectedBacktestRun={backtestPage.selectedRun}
      backtestPending={backtestPage.startPending}
      backtestError={backtestPage.startError ?? backtestPage.selectedRunError}
      onStartBacktest={backtestPage.startBacktest}
      status={dashboard.status}
      controls={controls}
      onPromoteVariant={lab.promoteVariant}
    />
  );
}
