import type { TradeJournalItem } from "../../api/types";
import { toNumber } from "../../ui/format";

export interface ScoreComponent {
  readonly label: string;
  readonly ratio: number;
  readonly display: string;
}

export interface JournalStats {
  readonly total: number;
  readonly closed: number;
  readonly netPnl: number;
  readonly winRate: number;
  readonly avgR: number;
  readonly profitFactor: number | null;
  readonly expectancy: number;
  readonly maxDrawdown: number;
  readonly equity: number[];
  readonly score: number;
  readonly components: ScoreComponent[];
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function closedTrades(trades: readonly TradeJournalItem[]): TradeJournalItem[] {
  return trades.filter((trade) => toNumber(trade.pnl) !== null);
}

function drawdown(equity: number[]): number {
  let peak = 0;
  let worst = 0;
  for (const value of equity) {
    peak = Math.max(peak, value);
    worst = Math.max(worst, peak - value);
  }
  return worst;
}

function buildComponents(
  winRate: number,
  profitFactor: number | null,
  avgR: number,
  ddRatio: number,
  sample: number
): ScoreComponent[] {
  const pf = profitFactor ?? 0;
  return [
    { label: "Win rate", ratio: clamp01(winRate), display: `${(winRate * 100).toFixed(0)}%` },
    {
      label: "Profit factor",
      ratio: clamp01(pf / 3),
      display: profitFactor === null ? "—" : pf.toFixed(2),
    },
    { label: "Avg R", ratio: clamp01((avgR + 1) / 3), display: `${avgR.toFixed(2)}R` },
    {
      label: "Drawdown control",
      ratio: clamp01(ddRatio),
      display: `${(ddRatio * 100).toFixed(0)}%`,
    },
    { label: "Sample size", ratio: clamp01(sample), display: `${Math.round(sample * 20)}/20` },
  ];
}

const WEIGHTS = [0.25, 0.3, 0.2, 0.15, 0.1];

function profitFactorOf(grossWin: number, grossLoss: number): number | null {
  if (grossLoss > 0) {
    return grossWin / grossLoss;
  }
  return grossWin > 0 ? null : 0;
}

export function journalStats(trades: readonly TradeJournalItem[]): JournalStats {
  const closed = closedTrades(trades);
  const pnls = closed.map((trade) => toNumber(trade.pnl) ?? 0);
  const rs = closed
    .map((trade) => toNumber(trade.r_multiple))
    .filter((r): r is number => r !== null);
  const wins = pnls.filter((value) => value > 0);
  const losses = pnls.filter((value) => value < 0);
  const grossWin = wins.reduce((sum, value) => sum + value, 0);
  const grossLoss = Math.abs(losses.reduce((sum, value) => sum + value, 0));
  const netPnl = pnls.reduce((sum, value) => sum + value, 0);
  const winRate = pnls.length > 0 ? wins.length / pnls.length : 0;
  const avgR = rs.length > 0 ? rs.reduce((sum, value) => sum + value, 0) / rs.length : 0;
  const profitFactor = profitFactorOf(grossWin, grossLoss);
  const expectancy = pnls.length > 0 ? netPnl / pnls.length : 0;

  let running = 0;
  const equity = pnls.map((value) => (running += value));
  const maxDrawdown = drawdown(equity);
  const ddRatio = grossWin > 0 ? clamp01(1 - maxDrawdown / grossWin) : 1;
  const sample = closed.length / 20;

  const components = buildComponents(winRate, profitFactor, avgR, ddRatio, sample);
  const score = components.reduce((sum, comp, index) => sum + comp.ratio * WEIGHTS[index], 0) * 100;

  return {
    total: trades.length,
    closed: closed.length,
    netPnl,
    winRate,
    avgR,
    profitFactor,
    expectancy,
    maxDrawdown,
    equity,
    score,
    components,
  };
}
