import { useState } from "react";

import { useBacktestRunQuery, useBacktestRunsQuery, useStartBacktestMutation } from "../api/hooks";
import type { BacktestStartPayload, LabVariantOverview, PaperVariant } from "../api/types";

export function useBacktestPageState(
  runsQuery: ReturnType<typeof useBacktestRunsQuery>,
  startBacktestMutation: ReturnType<typeof useStartBacktestMutation>
) {
  const [explicitSelectedRunId, setExplicitSelectedRunId] = useState<number | null>(null);
  const latestRunId = runsQuery.data?.runs[0]?.run_id ?? null;
  const selectedRunId = explicitSelectedRunId ?? latestRunId;
  const selectedRunQuery = useBacktestRunQuery(selectedRunId);

  return {
    selectedRunId,
    selectedRun: selectedRunQuery.data ?? null,
    selectedRunPending: selectedRunQuery.isFetching,
    selectedRunError: firstErrorMessage(selectedRunQuery.error),
    startPending: startBacktestMutation.isPending,
    startError: firstErrorMessage(startBacktestMutation.error),
    startBacktest: (payload: BacktestStartPayload) =>
      startBacktestMutation.mutate(payload, {
        onSuccess: (run) => {
          if (run.run_id !== null) {
            setExplicitSelectedRunId(run.run_id);
          }
        },
      }),
    selectRun: setExplicitSelectedRunId,
  };
}

export function backtestTargetVariant(variants: LabVariantOverview): PaperVariant | null {
  const promoted = variants.variants.find((variant) => variant.status === "promoted");
  if (promoted !== undefined) {
    return promoted;
  }
  const leaderboardVariant = variants.leaderboard.find(
    (row) => row.variant.status === "paper" || row.variant.status === "promoted"
  )?.variant;
  if (leaderboardVariant !== undefined) {
    return leaderboardVariant;
  }
  return variants.variants.find((variant) => variant.status === "paper") ?? null;
}

function firstErrorMessage(...errors: unknown[]) {
  const error = errors.find((item) => item instanceof Error);
  return error instanceof Error ? error.message : null;
}
