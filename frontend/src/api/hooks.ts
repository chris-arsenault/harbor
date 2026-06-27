import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  createPaperVariant,
  fetchBacktestRun,
  fetchBacktestRuns,
  fetchCandles,
  fetchCandleSource,
  fetchConfig,
  fetchEvents,
  fetchLabStudy,
  fetchLevels,
  fetchMarkers,
  fetchOptimizationStudies,
  fetchStatus,
  fetchTrades,
  fetchVariantDetail,
  fetchVariants,
  flattenNow,
  importHistoricalCandles,
  preflightOptimization,
  promoteVariant,
  retirePaperVariant,
  setTradingEnabled,
  startBacktest,
  startOptimization,
  updateConfig,
} from "./client";
import { fetchCandleBackfill, startCandleBackfill, syncCandles } from "./candles";
import {
  fetchBookRecorderStatus,
  fetchCaptureScan,
  fetchCrossScan,
  fetchEdgeScan,
  fetchEdgeStudy,
} from "./research";
import { createLiveConnection, liveWebSocketUrl } from "./live";
import type { FlattenResult, OptimizationStartPayload, WebSocketEnvelope } from "./types";

export function useStatusQuery() {
  return useQuery({ queryKey: ["status"], queryFn: fetchStatus });
}

export function useLevelsQuery(params: { date: string; instrument: string }) {
  return useQuery({
    queryKey: ["levels", params],
    queryFn: () => fetchLevels(params),
  });
}

export function useCandlesQuery(params: { instrument: string; from: string; to: string }) {
  return useQuery({
    queryKey: ["candles", params],
    queryFn: () => fetchCandles(params),
  });
}

export function useCandleSourceQuery(params: { instrument?: string } = {}) {
  return useQuery({
    queryKey: ["candle-source", params],
    queryFn: () => fetchCandleSource(params),
  });
}

export function useMarkersQuery(params: { date: string; instrument: string }) {
  return useQuery({
    queryKey: ["markers", params],
    queryFn: () => fetchMarkers(params),
  });
}

export function useEventsQuery(params: { level?: string; limit?: number } = {}) {
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => fetchEvents(params),
  });
}

export function useTradesQuery(params: { from: string; to: string; limit?: number }) {
  return useQuery({
    queryKey: ["trades", params],
    queryFn: () => fetchTrades(params),
  });
}

export function useBacktestRunsQuery(params: { limit?: number } = {}) {
  return useQuery({
    queryKey: ["backtest-runs", params],
    queryFn: () => fetchBacktestRuns(params),
  });
}

export function useBacktestRunQuery(runId: number | null) {
  return useQuery({
    queryKey: ["backtest-run", runId],
    queryFn: () => {
      if (runId === null) {
        throw new Error("backtest run id is required");
      }
      return fetchBacktestRun(runId);
    },
    enabled: runId !== null,
  });
}

export function useOptimizationStudiesQuery(params: { limit?: number } = {}) {
  return useQuery({
    queryKey: ["optimization-studies", params],
    queryFn: () => fetchOptimizationStudies(params),
    refetchInterval: 5_000,
  });
}

export function useOptimizationPreflightQuery(payload: OptimizationStartPayload, enabled: boolean) {
  return useQuery({
    queryKey: ["optimization-preflight", payload],
    queryFn: () => preflightOptimization(payload),
    enabled,
    staleTime: 60_000,
  });
}

export function useLabStudyQuery(studyId: number | null) {
  return useQuery({
    queryKey: ["lab-study", studyId],
    queryFn: () => {
      if (studyId === null) {
        throw new Error("study id is required");
      }
      return fetchLabStudy(studyId);
    },
    enabled: studyId !== null,
    refetchInterval: 5_000,
  });
}

export function useEdgeStudyQuery(instrument: string, enabled: boolean, horizon?: number) {
  return useQuery({
    queryKey: ["edge-study", instrument, horizon],
    queryFn: () => fetchEdgeStudy({ instrument, horizon }),
    enabled,
  });
}

export function useEdgeScanMutation() {
  return useMutation({
    mutationFn: fetchEdgeScan,
  });
}

export function useCaptureScanMutation() {
  return useMutation({
    mutationFn: fetchCaptureScan,
  });
}

export function useCrossScanMutation() {
  return useMutation({
    mutationFn: fetchCrossScan,
  });
}

export function useBookRecorderStatusQuery() {
  return useQuery({
    queryKey: ["book-recorder-status"],
    queryFn: fetchBookRecorderStatus,
    refetchInterval: 30_000,
  });
}

export function useVariantsQuery() {
  return useQuery({
    queryKey: ["variants"],
    queryFn: fetchVariants,
  });
}

export function useVariantDetailQuery(variantId: number) {
  return useQuery({
    queryKey: ["variant-detail", variantId],
    queryFn: () => fetchVariantDetail(variantId),
  });
}

export function useConfigQuery() {
  return useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
  });
}

export function useStartOptimizationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startOptimization,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["optimization-studies"] });
      if (result.study_id !== null) {
        await queryClient.invalidateQueries({ queryKey: ["lab-study", result.study_id] });
      }
      await queryClient.invalidateQueries({ queryKey: ["variants"] });
    },
  });
}

export function useCandleSyncMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncCandles,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["candle-source"] });
      await queryClient.invalidateQueries({ queryKey: ["candles"] });
    },
  });
}

export function useCandleBackfillQuery() {
  return useQuery({
    queryKey: ["candle-backfill"],
    queryFn: fetchCandleBackfill,
    refetchInterval: 3_000,
  });
}

export function useStartCandleBackfillMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startCandleBackfill,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["candle-backfill"] });
      await queryClient.invalidateQueries({ queryKey: ["candle-source"] });
    },
  });
}

export function useImportHistoricalCandlesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importHistoricalCandles,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["candle-source"] });
      await queryClient.invalidateQueries({ queryKey: ["candles"] });
      await queryClient.invalidateQueries({ queryKey: ["optimization-preflight"] });
    },
  });
}

export function useStartBacktestMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startBacktest,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
    },
  });
}

export function useUpdateConfigMutation() {
  return useMutation({ mutationFn: updateConfig });
}

export function useCreatePaperVariantMutation() {
  return useMutation({ mutationFn: createPaperVariant });
}

export function useRetirePaperVariantMutation() {
  return useMutation({ mutationFn: retirePaperVariant });
}

export function usePromoteVariantMutation() {
  return useMutation({ mutationFn: promoteVariant });
}

export function useSetTradingEnabledMutation() {
  return useMutation({ mutationFn: setTradingEnabled });
}

export function useFlattenNowMutation() {
  return useMutation({ mutationFn: flattenNow });
}

export interface PracticeControls {
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly flattenResult?: FlattenResult | null;
  readonly setTradingEnabled: (enabled: boolean, confirmationToken: string) => void;
  readonly flattenNow: (confirmationToken: string) => void;
}

export function usePracticeControls(): PracticeControls {
  const setTradingMutation = useSetTradingEnabledMutation();
  const flattenMutation = useFlattenNowMutation();
  const error = setTradingMutation.error ?? flattenMutation.error;

  return {
    pending: setTradingMutation.isPending || flattenMutation.isPending,
    errorMessage: error instanceof Error ? error.message : null,
    flattenResult: flattenMutation.data ?? null,
    setTradingEnabled: (enabled, confirmationToken) =>
      setTradingMutation.mutate({ enabled, confirmation_token: confirmationToken }),
    flattenNow: (confirmationToken) =>
      flattenMutation.mutate({ confirmation_token: confirmationToken, reason: "manual" }),
  };
}

export function useLiveConnection(options: {
  enabled?: boolean;
  url?: string;
  onEnvelope: (envelope: WebSocketEnvelope) => void;
  onHeartbeat?: (sentAt: string) => void;
  onError?: (event: Event) => void;
}) {
  const enabled = options.enabled ?? true;
  const url = options.url ?? liveWebSocketUrl(window.location);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const connection = createLiveConnection({
      url,
      onEnvelope: options.onEnvelope,
      onHeartbeat: options.onHeartbeat,
      onError: options.onError,
    });
    return () => connection.close();
  }, [enabled, options.onEnvelope, options.onHeartbeat, options.onError, url]);
}
