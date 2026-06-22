import { useMemo, useState, type ReactNode } from "react";

import {
  useBacktestRunsQuery,
  useCandlesQuery,
  useCandleSourceQuery,
  useConfigQuery,
  useCreatePaperVariantMutation,
  useEventsQuery,
  useImportHistoricalCandlesMutation,
  useLabStudyQuery,
  useLevelsQuery,
  useMarkersQuery,
  useOptimizationPreflightQuery,
  useOptimizationStudiesQuery,
  usePracticeControls,
  usePromoteVariantMutation,
  useRetirePaperVariantMutation,
  useStartBacktestMutation,
  useStartOptimizationMutation,
  useStatusQuery,
  useTradesQuery,
  useUpdateConfigMutation,
  useVariantsQuery,
} from "./api/hooks";
import type { CandleImportRequest, CandleImportResult, VariantEquityCurve } from "./api/types";
import { aggregateImportResult } from "./app/candleImport";
import { backtestTargetVariant, useBacktestPageState } from "./app/backtestPageState";
import {
  emptyMarkers,
  emptyStatus,
  emptyVariantOverview,
  mergeCandles,
  mergeEvents,
  mergeMarkers,
  mergeVariantOverview,
  useLiveState,
  type LiveState,
} from "./app/liveState";
import type { LiveChartAdapter } from "./components/chartAdapter";
import {
  DEFAULT_RESEARCH_INSTRUMENT,
  DISCOVERY_STUDY_CONFIG,
  tuningPayloadFromConfig,
} from "./components/lab/tuningPayload";
import { AppShell } from "./shell/AppShell";
import type { ViewId } from "./shell/nav";
import { CockpitView, type PipelineState } from "./views/CockpitView";
import { JournalView } from "./views/JournalView";
import { LabView, type LabViewModel } from "./views/LabView";
import { ValidationView } from "./views/ValidationView";
import { OperationsView } from "./views/OperationsView";
import { ConfigView } from "./views/ConfigView";
import { EventsView } from "./views/EventsView";

const DEFAULT_INSTRUMENT = "EUR_USD";
const DASHBOARD_EVENTS = 25;

interface AppProps {
  readonly chartAdapter?: LiveChartAdapter;
}

export function App({ chartAdapter }: AppProps) {
  const windowParams = useMemo(() => dashboardWindow(new Date()), []);
  const [activeView, setActiveView] = useState<ViewId>("cockpit");
  const [instrument, setInstrument] = useState(DEFAULT_RESEARCH_INSTRUMENT);

  const live = useLiveState();
  const dashboard = useDashboardData(windowParams, live);
  const trades = useTradesQuery({ from: windowParams.from, to: windowParams.to, limit: 100 });
  const backtests = useBacktestRunsQuery({ limit: 50 });
  const startBacktest = useStartBacktestMutation();
  const backtestPage = useBacktestPageState(backtests, startBacktest);
  const config = useConfigQuery();
  const updateConfig = useUpdateConfigMutation();
  const eventsPage = useEventsQuery({ limit: 200 });
  const lab = useLabData(instrument, live.liveEquityCurves, live.labLiveStatus);
  const controls = usePracticeControls();
  const productEvents = mergeEvents(live.liveEvents, eventsPage.data ?? dashboard.events);

  const pipeline = computePipeline(
    dashboard.status,
    lab.candleSource,
    lab,
    backtests.data?.runs.length ?? 0
  );
  const badges: Partial<Record<ViewId, string>> = {
    journal: String(trades.data?.trades.length ?? 0),
    events: String(productEvents.length),
  };

  return (
    <AppShell
      status={dashboard.status}
      lastMessageAt={live.lastWsMessageAt ?? dashboard.status.last_heartbeat}
      active={activeView}
      badges={badges}
      onSelect={setActiveView}
      onArmClick={() => setActiveView("operations")}
    >
      {renderView(activeView, {
        windowParams,
        dashboard,
        chartAdapter,
        pipeline,
        productEvents,
        trades,
        backtests,
        backtestPage,
        lab,
        config,
        updateConfig,
        eventsPage,
        controls,
        instrument,
        setInstrument,
      })}
    </AppShell>
  );
}

interface ViewContext {
  readonly windowParams: ReturnType<typeof dashboardWindow>;
  readonly dashboard: ReturnType<typeof useDashboardData>;
  readonly chartAdapter?: LiveChartAdapter;
  readonly pipeline: PipelineState;
  readonly productEvents: ReturnType<typeof mergeEvents>;
  readonly trades: ReturnType<typeof useTradesQuery>;
  readonly backtests: ReturnType<typeof useBacktestRunsQuery>;
  readonly backtestPage: ReturnType<typeof useBacktestPageState>;
  readonly lab: ReturnType<typeof useLabData>;
  readonly config: ReturnType<typeof useConfigQuery>;
  readonly updateConfig: ReturnType<typeof useUpdateConfigMutation>;
  readonly eventsPage: ReturnType<typeof useEventsQuery>;
  readonly controls: ReturnType<typeof usePracticeControls>;
  readonly instrument: string;
  readonly setInstrument: (instrument: string) => void;
}

const ROUTES: Record<ViewId, (props: { readonly ctx: ViewContext }) => ReactNode> = {
  cockpit: CockpitRoute,
  journal: JournalRoute,
  lab: LabRoute,
  validation: ValidationRoute,
  operations: OperationsRoute,
  config: ConfigRoute,
  events: EventsRoute,
};

function renderView(view: ViewId, ctx: ViewContext) {
  const Route = ROUTES[view];
  return <Route ctx={ctx} />;
}

function JournalRoute({ ctx }: { readonly ctx: ViewContext }) {
  return (
    <JournalView
      trades={ctx.trades.data?.trades ?? []}
      from={ctx.windowParams.from}
      to={ctx.windowParams.to}
    />
  );
}

function LabRoute({ ctx }: { readonly ctx: ViewContext }) {
  return <LabView model={labModel(ctx)} />;
}

function OperationsRoute({ ctx }: { readonly ctx: ViewContext }) {
  return <OperationsView status={ctx.dashboard.status} controls={ctx.controls} />;
}

function ConfigRoute({ ctx }: { readonly ctx: ViewContext }) {
  return (
    <ConfigView
      snapshot={ctx.config.data ?? { values: [] }}
      pending={ctx.updateConfig.isPending}
      onUpdateConfig={ctx.updateConfig.mutate}
    />
  );
}

function EventsRoute({ ctx }: { readonly ctx: ViewContext }) {
  return (
    <EventsView
      events={ctx.productEvents}
      loading={ctx.eventsPage.isLoading}
      errorMessage={ctx.eventsPage.error instanceof Error ? ctx.eventsPage.error.message : null}
    />
  );
}

function CockpitRoute({ ctx }: { readonly ctx: ViewContext }) {
  return (
    <CockpitView
      status={ctx.dashboard.status}
      levels={ctx.dashboard.levels}
      candles={ctx.dashboard.candles}
      markers={ctx.dashboard.markers}
      events={ctx.productEvents}
      controls={ctx.controls}
      chartAdapter={ctx.chartAdapter}
      pipeline={ctx.pipeline}
    />
  );
}

function ValidationRoute({ ctx }: { readonly ctx: ViewContext }) {
  return (
    <ValidationView
      runs={ctx.backtests.data?.runs ?? []}
      selectedRunId={ctx.backtestPage.selectedRunId}
      selectedRun={ctx.backtestPage.selectedRun}
      selectedRunPending={ctx.backtestPage.selectedRunPending}
      selectedRunError={ctx.backtestPage.selectedRunError}
      candleSource={ctx.lab.candleSource}
      targetVariant={backtestTargetVariant(ctx.lab.variantOverview)}
      pending={ctx.backtestPage.startPending}
      errorMessage={ctx.backtestPage.startError}
      onStartBacktest={ctx.backtestPage.startBacktest}
      onSelectRun={ctx.backtestPage.selectRun}
    />
  );
}

function labModel(ctx: ViewContext): LabViewModel {
  const lab = ctx.lab;
  return {
    snapshot: lab.snapshot,
    variants: lab.variantOverview,
    liveStatus: lab.liveStatus,
    candleSource: lab.candleSource,
    candleSourcePending: lab.candleSourcePending,
    candleSourceError: lab.candleSourceError,
    importResult: lab.importResult,
    onImportCandles: lab.importCandles,
    selectedInstrument: ctx.instrument,
    onInstrumentChange: ctx.setInstrument,
    studyPayload: lab.studyPayload,
    preflight: lab.preflight,
    preflightPending: lab.preflightPending,
    preflightError: lab.preflightError,
    tuningRun: lab.tuningRun,
    onStartOptimization: lab.startOptimization,
    onPromoteVariant: lab.promoteVariant,
    onRetireVariant: lab.retireVariant,
  };
}

function computePipeline(
  status: ReturnType<typeof emptyStatus>,
  candleSource: ReturnType<typeof useLabData>["candleSource"],
  lab: ReturnType<typeof useLabData>,
  backtestRuns: number
): PipelineState {
  const overview = lab.variantOverview;
  return {
    dataReady: (candleSource?.coverage.candle_count ?? 0) > 0,
    researchReady: lab.preflight?.status === "ready",
    hasCandidate: overview.variants.length > 0 || overview.leaderboard.length > 0,
    hasBacktest: backtestRuns > 0,
    hasPaper: overview.leaderboard.some((row) => row.stats.trade_count > 0),
    hasLive: Boolean(status.promoted_variant),
    promotedLabel: status.promoted_variant?.label ?? null,
  };
}

function useDashboardData(windowParams: ReturnType<typeof dashboardWindow>, live: LiveState) {
  const statusQuery = useStatusQuery();
  const levelsQuery = useLevelsQuery({ date: windowParams.date, instrument: DEFAULT_INSTRUMENT });
  const candlesQuery = useCandlesQuery({
    instrument: DEFAULT_INSTRUMENT,
    from: windowParams.from,
    to: windowParams.to,
  });
  const markersQuery = useMarkersQuery({ date: windowParams.date, instrument: DEFAULT_INSTRUMENT });
  const eventsQuery = useEventsQuery({ limit: DASHBOARD_EVENTS });

  return {
    status: live.liveStatus ?? statusQuery.data ?? emptyStatus(),
    levels: live.liveLevels ?? levelsQuery.data ?? null,
    candles: mergeCandles(candlesQuery.data ?? [], live.liveCandles),
    markers: mergeMarkers(markersQuery.data ?? emptyMarkers(), live.liveMarkers),
    events: [...live.liveEvents, ...(eventsQuery.data ?? [])].slice(0, DASHBOARD_EVENTS),
  };
}

type StudiesData = ReturnType<typeof useOptimizationStudiesQuery>["data"];
type StartData = ReturnType<typeof useStartOptimizationMutation>["data"];
type CandleSourceState = ReturnType<typeof useLabCandleSource>;

function pickStudyId(started: StartData, studies: StudiesData): number | null {
  return started?.study_id ?? studies?.studies[0]?.study_id ?? null;
}

function hasCandles(state: CandleSourceState): boolean {
  return (state.status?.coverage?.candle_count ?? 0) > 0;
}

function candleFields(state: CandleSourceState) {
  return {
    candleSource: state.status,
    candleSourcePending: state.pending,
    candleSourceError: state.errorMessage,
    importCandles: state.importCandles,
    importResult: state.importResult,
  };
}

function preflightFields(query: ReturnType<typeof useOptimizationPreflightQuery>) {
  return {
    preflight: query.data ?? null,
    preflightPending: query.isFetching,
    preflightError: query.error instanceof Error ? query.error.message : null,
  };
}

function tuningRunView(mutation: ReturnType<typeof useStartOptimizationMutation>) {
  return {
    pending: mutation.isPending,
    errorMessage: firstErrorMessage(mutation.error),
    resultStatus: mutation.data?.status ?? null,
  };
}

function useLabData(
  selectedInstrument: string,
  liveEquityCurves: VariantEquityCurve[],
  liveStatus: string | null
) {
  const studyPayload = useMemo(
    () => tuningPayloadFromConfig(DISCOVERY_STUDY_CONFIG, selectedInstrument),
    [selectedInstrument]
  );
  const studiesQuery = useOptimizationStudiesQuery({ limit: 50 });
  const startOptimization = useStartOptimizationMutation();
  const labStudyQuery = useLabStudyQuery(pickStudyId(startOptimization.data, studiesQuery.data));
  const variantsQuery = useVariantsQuery();
  const candleSource = useLabCandleSource(selectedInstrument);
  const preflightQuery = useOptimizationPreflightQuery(studyPayload, hasCandles(candleSource));
  const createVariant = useCreatePaperVariantMutation();
  const retireVariant = useRetirePaperVariantMutation();
  const promoteVariant = usePromoteVariantMutation();
  const baseVariants = variantsQuery.data ?? labStudyQuery.data?.variants ?? emptyVariantOverview();

  return {
    snapshot: labStudyQuery.data ?? null,
    variantOverview: mergeVariantOverview(baseVariants, liveEquityCurves),
    liveStatus,
    studyPayload,
    startOptimization: startOptimization.mutate,
    tuningRun: tuningRunView(startOptimization),
    createPaperVariant: createVariant.mutate,
    retireVariant: retireVariant.mutate,
    promoteVariant: promoteVariant.mutate,
    ...candleFields(candleSource),
    ...preflightFields(preflightQuery),
  };
}

function useLabCandleSource(selectedInstrument: string) {
  const candleSourceQuery = useCandleSourceQuery({ instrument: selectedInstrument });
  const importCandlesMutation = useImportHistoricalCandlesMutation();
  const [batchPending, setBatchPending] = useState(false);
  const [batchResult, setBatchResult] = useState<CandleImportResult | null>(null);

  async function importCandles(payload: CandleImportRequest) {
    if (payload.instrument !== "research_universe" || !payload.instruments?.length) {
      setBatchResult(null);
      await importCandlesMutation.mutateAsync(payload);
      return;
    }
    setBatchPending(true);
    setBatchResult(null);
    try {
      const results: CandleImportResult[] = [];
      for (const symbol of payload.instruments) {
        results.push(
          await importCandlesMutation.mutateAsync({
            instrument: symbol,
            count: payload.count,
            from: payload.from,
          })
        );
      }
      setBatchResult(aggregateImportResult(results, payload));
    } finally {
      setBatchPending(false);
    }
  }

  return {
    status: candleSourceQuery.data ?? null,
    pending: candleSourceQuery.isLoading || importCandlesMutation.isPending || batchPending,
    errorMessage: firstErrorMessage(candleSourceQuery.error, importCandlesMutation.error),
    importCandles,
    importResult: batchResult ?? importCandlesMutation.data ?? null,
  };
}

function firstErrorMessage(...errors: unknown[]) {
  const error = errors.find((item) => item instanceof Error);
  return error instanceof Error ? error.message : null;
}

function dashboardWindow(now: Date) {
  const end = now.toISOString();
  const start = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
  return { date: end.slice(0, 10), from: start, to: end };
}
