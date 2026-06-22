import type { BacktestRunSummary } from "../../api/types";
import { toNumber } from "../../ui/format";

export interface BtTrade {
  readonly side: string;
  readonly level: string;
  readonly units: unknown;
  readonly entry: unknown;
  readonly exit: unknown;
  readonly pnl: unknown;
  readonly r: unknown;
  readonly reason: string;
}

function asText(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

export function readTradeRow(row: Record<string, unknown>): BtTrade {
  return {
    side: asText(row.side, "—"),
    level: asText(row.level_name, "—"),
    units: row.units,
    entry: row.entry_price,
    exit: row.exit_price,
    pnl: row.pnl,
    r: row.r_multiple,
    reason: asText(row.exit_reason, "—"),
  };
}

export function cumulativePnl(trades: readonly Record<string, unknown>[]): number[] {
  let running = 0;
  const series: number[] = [];
  for (const trade of trades) {
    running += toNumber(trade.pnl) ?? 0;
    series.push(running);
  }
  return series;
}

export interface RunMeta {
  readonly label: string;
  readonly window: string;
}

function windowLabel(params: Record<string, unknown>): string {
  if (typeof params.candle_window_days === "number") {
    return `${params.candle_window_days}d`;
  }
  const range = params.candle_range as { from?: string; to?: string } | undefined;
  if (range?.from) {
    return `${range.from.slice(0, 10)} → ${range.to?.slice(0, 10) ?? "?"}`;
  }
  return "—";
}

export function runMeta(run: BacktestRunSummary): RunMeta {
  return {
    label: asText(run.params.variant_label, "default strategy"),
    window: windowLabel(run.params),
  };
}
