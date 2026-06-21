import type { OptimizationStartPayload } from "../../api/types";

export interface TuningStudyConfig {
  readonly trialCount: number;
  readonly candidateCount: number;
  readonly trainWindowDays: number;
  readonly outOfSampleWindowDays: number;
  readonly stepDays: number;
  readonly minInSampleTrades: number;
  readonly minOutOfSampleTrades: number;
  readonly robustnessNeighborCount: number;
}

export const DISCOVERY_STUDY_CONFIG = {
  trialCount: 64,
  candidateCount: 5,
  trainWindowDays: 10,
  outOfSampleWindowDays: 5,
  stepDays: 5,
  minInSampleTrades: 3,
  minOutOfSampleTrades: 1,
  robustnessNeighborCount: 0,
} satisfies TuningStudyConfig;

export const QUICK_STUDY_CONFIG = {
  trialCount: 32,
  candidateCount: 3,
  trainWindowDays: 5,
  outOfSampleWindowDays: 2,
  stepDays: 2,
  minInSampleTrades: 1,
  minOutOfSampleTrades: 1,
  robustnessNeighborCount: 0,
} satisfies TuningStudyConfig;

export function tuningPayloadFromConfig(config: TuningStudyConfig): OptimizationStartPayload {
  return {
    source: "persisted_candles",
    instrument: "EUR_USD",
    optimizer_config: {
      trial_count: config.trialCount,
      candidate_count: config.candidateCount,
      minimum_trade_count: {
        in_sample: config.minInSampleTrades,
        out_of_sample: config.minOutOfSampleTrades,
      },
      robustness: {
        neighbor_count: config.robustnessNeighborCount,
      },
      walk_forward: {
        train_window_days: config.trainWindowDays,
        oos_window_days: config.outOfSampleWindowDays,
        step_days: config.stepDays,
      },
    },
  };
}

export const DEFAULT_TUNING_PAYLOAD = tuningPayloadFromConfig(DISCOVERY_STUDY_CONFIG);

export const LEGACY_TUNING_PAYLOAD = {
  source: "persisted_candles",
  instrument: "EUR_USD",
} satisfies OptimizationStartPayload;
