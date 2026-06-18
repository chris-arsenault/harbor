import type { BacktestRunDetail } from "../../api/types";
import { displayValue } from "../../utils/format";

interface BacktestResultProps {
  readonly run: BacktestRunDetail | null;
}

export function BacktestResult({ run }: BacktestResultProps) {
  if (run === null) {
    return (
      <section className="detail-panel" aria-label="Backtest result">
        <h3>Backtest Result</h3>
        <p>No run selected</p>
      </section>
    );
  }

  return (
    <section className="product-view" aria-label="Backtest result">
      <div className="metric-grid">
        <Metric
          label="Trade count"
          value={displayValue(run.stats.trade_count, String(run.trades.length))}
        />
        <Metric label="Expectancy" value={displayValue(run.stats.expectancy)} />
        <Metric label="Average R" value={displayValue(run.stats.average_r)} />
        <Metric label="Max drawdown" value={displayValue(run.stats.max_drawdown)} />
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Side</th>
            <th>Units</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>P&L</th>
            <th>R</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {run.trades.map((trade, index) => (
            <tr key={`${run.run_id}-${index}`}>
              <td>{displayValue(trade.side)}</td>
              <td>{displayValue(trade.units)}</td>
              <td>{displayValue(trade.entry_price)}</td>
              <td>{displayValue(trade.exit_price)}</td>
              <td>{displayValue(trade.pnl)}</td>
              <td>{displayValue(trade.r_multiple)}</td>
              <td>{displayValue(trade.exit_reason)}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
