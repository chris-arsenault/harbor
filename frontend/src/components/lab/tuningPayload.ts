import type { OptimizationStartPayload } from "../../api/types";

export const DEFAULT_RESEARCH_INSTRUMENT = "GBP_USD";

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
  trialCount: 96,
  candidateCount: 5,
  trainWindowDays: 60,
  outOfSampleWindowDays: 20,
  stepDays: 20,
  minInSampleTrades: 12,
  minOutOfSampleTrades: 4,
  robustnessNeighborCount: 0,
} satisfies TuningStudyConfig;

export function tuningPayloadFromConfig(config: TuningStudyConfig): OptimizationStartPayload {
  return {
    source: "persisted_candles",
    instrument: DEFAULT_RESEARCH_INSTRUMENT,
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
  instrument: DEFAULT_RESEARCH_INSTRUMENT,
} satisfies OptimizationStartPayload;
