import type { OptimizationStartPayload } from "../../api/types";

export const DEFAULT_TUNING_PAYLOAD = {
  source: "persisted_candles",
  instrument: "EUR_USD",
} satisfies OptimizationStartPayload;
