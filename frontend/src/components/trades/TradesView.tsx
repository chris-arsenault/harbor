import type { TradeJournalItem } from "../../api/types";
import { TradeDetail } from "./TradeDetail";
import { TradesTable } from "./TradesTable";

interface TradesViewProps {
  readonly trades: TradeJournalItem[];
  readonly from: string;
  readonly to: string;
}

export function TradesView({ trades, from, to }: TradesViewProps) {
  const instruments = uniqueValues(trades.map((trade) => trade.instrument));
  const statuses = uniqueValues(trades.map((trade) => trade.signal_status));
  const closedTrades = trades.filter((trade) => trade.pnl !== null);
  const totalPnl = sumDecimalStrings(closedTrades.map((trade) => trade.pnl));
  const averageR = averageDecimalStrings(closedTrades.map((trade) => trade.r_multiple));

  return (
    <section className="product-view trades-view" aria-label="Trades page">
      <div className="product-view__header">
        <h2>Trades</h2>
        <div className="filter-row" aria-label="Trade filters">
          <label>
            From
            <input readOnly value={from} />
          </label>
          <label>
            To
            <input readOnly value={to} />
          </label>
          <label>
            Instrument
            <select defaultValue="all">
              <option value="all">All</option>
              {instruments.map((instrument) => (
                <option key={instrument} value={instrument}>
                  {instrument}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select defaultValue="all">
              <option value="all">All</option>
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="metric-grid">
        <Metric label="Trades" value={String(trades.length)} />
        <Metric label="Closed" value={String(closedTrades.length)} />
        <Metric label="Total P&L" value={totalPnl} />
        <Metric label="Average R" value={averageR} />
      </div>

      <div className="two-column-layout">
        <TradesTable trades={trades} />
        <TradeDetail trade={trades[0] ?? null} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function uniqueValues(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function sumDecimalStrings(values: Array<string | null>): string {
  const total = values.reduce((sum, value) => sum + Number(value ?? 0), 0);
  return total.toFixed(8);
}

function averageDecimalStrings(values: Array<string | null>): string {
  const numeric = values.filter((value): value is string => value !== null);
  if (numeric.length === 0) {
    return "0.0000";
  }
  const total = numeric.reduce((sum, value) => sum + Number(value), 0);
  return (total / numeric.length).toFixed(4);
}
