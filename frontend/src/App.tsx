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
import { HeartbeatIndicator } from "./components/HeartbeatIndicator";
import { BacktestsView } from "./components/backtests/BacktestsView";
import type { LiveChartAdapter } from "./components/chartAdapter";
import { ConfigView } from "./components/config/ConfigView";
import { DashboardView } from "./components/dashboard/DashboardView";
import { EventsView } from "./components/events/EventsView";
import { LabScreen } from "./components/lab/LabScreen";
import {
  DEFAULT_RESEARCH_INSTRUMENT,
  DISCOVERY_STUDY_CONFIG,
  tuningPayloadFromConfig,
  type TuningStudyConfig,
} from "./components/lab/tuningPayload";
import { ProductNav, type ProductView } from "./components/navigation/ProductNav";
import { OperationsView } from "./components/operations/OperationsView";
import { TradesView } from "./components/trades/TradesView";

const DEFAULT_INSTRUMENT = "EUR_USD";
const DEFAULT_EVENTS_LIMIT = 25;
const APP_VIEWS: ProductView[] = [
  "dashboard",
  "trades",
  "backtests",
  "lab",
  "config",
  "events",
  "operations",
];

interface AppProps {
  readonly chartAdapter?: LiveChartAdapter;
}

export function App({ chartAdapter }: AppProps) {
  const windowParams = useMemo(() => dashboardWindow(new Date()), []);
  const [activeView, setActiveView] = useState<ProductView>("dashboard");
  const live = useLiveState();
  const dashboard = useDashboardData(windowParams, live);
  const trades = useTradesQuery({
    from: windowParams.from,
    to: windowParams.to,
    limit: 100,
  });
  const backtests = useBacktestRunsQuery({ limit: 50 });
  const startBacktest = useStartBacktestMutation();
  const config = useConfigQuery();
  const updateConfig = useUpdateConfigMutation();
  const eventsPage = useEventsQuery({ limit: 200 });
  const lab = useLabData(live.liveEquityCurves, live.labLiveStatus);
  const controls = usePracticeControls();
  const productEvents = mergeEvents(live.liveEvents, eventsPage.data ?? dashboard.events);

  return (
    <main className="app-shell">
      <AppHeader
        activeView={activeView}
        lastMessageAt={live.lastWsMessageAt ?? dashboard.status.last_heartbeat}
        onViewChange={setActiveView}
      />
      <ProductPage
        activeView={activeView}
        windowParams={windowParams}
        dashboard={dashboard}
        trades={trades}
        backtests={backtests}
        startBacktest={startBacktest}
        config={config}
        updateConfig={updateConfig}
        eventsPage={eventsPage}
        productEvents={productEvents}
        lab={lab}
        controls={controls}
        chartAdapter={chartAdapter}
      />
    </main>
  );
}

function useDashboardData(windowParams: ReturnType<typeof dashboardWindow>, live: LiveState) {
  const statusQuery = useStatusQuery();
  const levelsQuery = useLevelsQuery({
    date: windowParams.date,
    instrument: DEFAULT_INSTRUMENT,
  });
  const candlesQuery = useCandlesQuery({
    instrument: DEFAULT_INSTRUMENT,
    from: windowParams.from,
    to: windowParams.to,
  });
  const markersQuery = useMarkersQuery({
    date: windowParams.date,
    instrument: DEFAULT_INSTRUMENT,
  });
  const eventsQuery = useEventsQuery({ limit: DEFAULT_EVENTS_LIMIT });

  return {
    status: live.liveStatus ?? statusQuery.data ?? emptyStatus(),
    levels: live.liveLevels ?? levelsQuery.data ?? null,
    candles: mergeCandles(candlesQuery.data ?? [], live.liveCandles),
    markers: mergeMarkers(markersQuery.data ?? emptyMarkers(), live.liveMarkers),
    events: [...live.liveEvents, ...(eventsQuery.data ?? [])].slice(0, DEFAULT_EVENTS_LIMIT),
  };
}

function useLabData(liveEquityCurves: VariantEquityCurve[], liveStatus: string | null) {
  const [studyConfig, setStudyConfig] = useState<TuningStudyConfig>(DISCOVERY_STUDY_CONFIG);
  const studyPayload = useMemo(() => tuningPayloadFromConfig(studyConfig), [studyConfig]);
  const studiesQuery = useOptimizationStudiesQuery({ limit: 50 });
  const startOptimizationMutation = useStartOptimizationMutation();
  const selectedStudyId = latestLabStudyId(studiesQuery.data, startOptimizationMutation.data);
  const labStudyQuery = useLabStudyQuery(selectedStudyId);
  const variantsQuery = useVariantsQuery();
  const candleSource = useLabCandleSource();
  const canPreflight = (candleSource.status?.coverage?.candle_count ?? 0) > 0;
  const preflightQuery = useOptimizationPreflightQuery(studyPayload, canPreflight);
  const createVariantMutation = useCreatePaperVariantMutation();
  const retireVariantMutation = useRetirePaperVariantMutation();
  const promoteVariantMutation = usePromoteVariantMutation();

  return {
    snapshot: labStudyQuery.data ?? null,
    variantOverview: mergeVariantOverview(
      variantsQuery.data ?? labStudyQuery.data?.variants ?? emptyVariantOverview(),
      liveEquityCurves
    ),
    liveStatus,
    candleSource: candleSource.status,
    candleSourcePending: candleSource.pending,
    candleSourceError: candleSource.errorMessage,
    importCandles: candleSource.importCandles,
    importResult: candleSource.importResult,
    studyConfig,
    setStudyConfig,
    studyPayload,
    preflight: preflightQuery.data ?? null,
    preflightPending: preflightQuery.isFetching,
    preflightError: preflightQuery.error instanceof Error ? preflightQuery.error.message : null,
    startOptimization: startOptimizationMutation.mutate,
    tuningRun: tuningRunState(startOptimizationMutation),
    createPaperVariant: createVariantMutation.mutate,
    retireVariant: retireVariantMutation.mutate,
    promoteVariant: promoteVariantMutation.mutate,
  };
}

function latestLabStudyId(
  studies: ReturnType<typeof useOptimizationStudiesQuery>["data"],
  startedStudy: ReturnType<typeof useStartOptimizationMutation>["data"]
) {
  return startedStudy?.study_id ?? studies?.studies[0]?.study_id ?? null;
}

function tuningRunState(mutation: ReturnType<typeof useStartOptimizationMutation>) {
  return {
    pending: mutation.isPending,
    errorMessage: firstErrorMessage(mutation.error),
    result: mutation.data ?? null,
  };
}

function useLabCandleSource() {
  const candleSourceQuery = useCandleSourceQuery({ instrument: DEFAULT_RESEARCH_INSTRUMENT });
  const importCandlesMutation = useImportHistoricalCandlesMutation();
  const [batchImportPending, setBatchImportPending] = useState(false);
  const [batchImportResult, setBatchImportResult] = useState<CandleImportResult | null>(null);

  async function importCandles(payload: CandleImportRequest) {
    if (payload.instrument !== "research_universe" || !payload.instruments?.length) {
      setBatchImportResult(null);
      await importCandlesMutation.mutateAsync(payload);
      return;
    }

    setBatchImportPending(true);
    setBatchImportResult(null);
    try {
      const results: CandleImportResult[] = [];
      for (const instrument of payload.instruments) {
        results.push(
          await importCandlesMutation.mutateAsync({
            instrument,
            count: payload.count,
            from: payload.from,
          })
        );
      }
      setBatchImportResult(aggregateImportResult(results, payload));
    } finally {
      setBatchImportPending(false);
    }
  }

  return {
    status: candleSourceQuery.data ?? null,
    pending: candleSourceQuery.isLoading || importCandlesMutation.isPending || batchImportPending,
    errorMessage: firstErrorMessage(candleSourceQuery.error, importCandlesMutation.error),
    importCandles,
    importResult: batchImportResult ?? importCandlesMutation.data ?? null,
  };
}

function aggregateImportResult(
  results: CandleImportResult[],
  payload: CandleImportRequest
): CandleImportResult {
  const first = results[0];
  return {
    status: "completed",
    source: "oanda_historical_import",
    instrument: "research_universe",
    instruments: results.map((result) => result.instrument),
    requested_count: results.reduce((total, result) => total + result.requested_count, 0),
    imported_count: results.reduce((total, result) => total + result.imported_count, 0),
    from: payload.from ?? first?.from ?? null,
    coverage: first?.coverage ?? {
      instrument: "research_universe",
      candle_count: 0,
      from: null,
      to: null,
    },
    results: results.map((result) => ({
      instrument: result.instrument,
      requested_count: result.requested_count,
      imported_count: result.imported_count,
      coverage: result.coverage,
    })),
  };
}

function firstErrorMessage(...errors: unknown[]) {
  const error = errors.find((item) => item instanceof Error);
  return error instanceof Error ? error.message : null;
}

interface ProductPageProps {
  readonly activeView: ProductView;
  readonly windowParams: ReturnType<typeof dashboardWindow>;
  readonly dashboard: ReturnType<typeof useDashboardData>;
  readonly trades: ReturnType<typeof useTradesQuery>;
  readonly backtests: ReturnType<typeof useBacktestRunsQuery>;
  readonly startBacktest: ReturnType<typeof useStartBacktestMutation>;
  readonly config: ReturnType<typeof useConfigQuery>;
  readonly updateConfig: ReturnType<typeof useUpdateConfigMutation>;
  readonly eventsPage: ReturnType<typeof useEventsQuery>;
  readonly productEvents: ReturnType<typeof mergeEvents>;
  readonly lab: ReturnType<typeof useLabData>;
  readonly controls: ReturnType<typeof usePracticeControls>;
  readonly chartAdapter?: LiveChartAdapter;
}

const PRODUCT_ROUTES = {
  dashboard: DashboardRoute,
  trades: TradesRoute,
  backtests: BacktestsRoute,
  lab: LabRoute,
  config: ConfigRoute,
  events: EventsRoute,
  operations: OperationsRoute,
} satisfies Record<ProductView, (props: ProductPageProps) => ReactNode>;

function ProductPage(props: ProductPageProps) {
  const ProductRoute = PRODUCT_ROUTES[props.activeView];
  return ProductRoute(props);
}

function DashboardRoute({
  dashboard,
  chartAdapter,
  controls,
}: Pick<ProductPageProps, "dashboard" | "chartAdapter" | "controls">) {
  return (
    <DashboardView
      status={dashboard.status}
      levels={dashboard.levels}
      candles={dashboard.candles}
      markers={dashboard.markers}
      events={dashboard.events}
      chartAdapter={chartAdapter}
      controls={controls}
    />
  );
}

function TradesRoute({ trades, windowParams }: ProductPageProps) {
  return (
    <TradesView trades={trades.data?.trades ?? []} from={windowParams.from} to={windowParams.to} />
  );
}

function BacktestsRoute({ backtests, startBacktest }: ProductPageProps) {
  return (
    <BacktestsView
      runs={backtests.data?.runs ?? []}
      selectedRun={null}
      pending={startBacktest.isPending}
      onStartBacktest={startBacktest.mutate}
    />
  );
}

function ConfigRoute({ config, updateConfig }: ProductPageProps) {
  return (
    <ConfigView
      snapshot={config.data ?? { values: [] }}
      pending={updateConfig.isPending}
      onUpdateConfig={updateConfig.mutate}
    />
  );
}

function EventsRoute({ productEvents, eventsPage }: ProductPageProps) {
  return (
    <EventsView
      events={productEvents}
      loading={eventsPage.isLoading}
      errorMessage={eventsPage.error instanceof Error ? eventsPage.error.message : null}
    />
  );
}

function LabRoute({ lab }: ProductPageProps) {
  return (
    <LabScreen
      snapshot={lab.snapshot}
      variants={lab.variantOverview}
      liveStatus={lab.liveStatus}
      onStartOptimization={lab.startOptimization}
      onCreatePaperVariant={lab.createPaperVariant}
      onRetireVariant={lab.retireVariant}
      onPromoteVariant={lab.promoteVariant}
      candleSource={lab.candleSource}
      candleSourcePending={lab.candleSourcePending}
      candleSourceError={lab.candleSourceError}
      candleImportResult={lab.importResult}
      onImportCandles={lab.importCandles}
      studyConfig={lab.studyConfig}
      onStudyConfigChange={lab.setStudyConfig}
      studyPayload={lab.studyPayload}
      preflight={lab.preflight}
      preflightPending={lab.preflightPending}
      preflightError={lab.preflightError}
      tuningRun={lab.tuningRun}
    />
  );
}

function OperationsRoute({ dashboard, controls }: ProductPageProps) {
  return <OperationsView status={dashboard.status} controls={controls} />;
}

interface AppHeaderProps {
  readonly activeView: ProductView;
  readonly lastMessageAt: string | null;
  readonly onViewChange: (view: ProductView) => void;
}

function AppHeader({ activeView, lastMessageAt, onViewChange }: AppHeaderProps) {
  return (
    <header className="dashboard-header">
      <div className="app-title">
        <h1>Harbor</h1>
        <ProductNav activeView={activeView} views={APP_VIEWS} onViewChange={onViewChange} />
      </div>
      <HeartbeatIndicator lastMessageAt={lastMessageAt} />
    </header>
  );
}

function dashboardWindow(now: Date) {
  const end = now.toISOString();
  const start = new Date(now.getTime() - 60 * 60 * 1000).toISOString();
  return { date: end.slice(0, 10), from: start, to: end };
}
