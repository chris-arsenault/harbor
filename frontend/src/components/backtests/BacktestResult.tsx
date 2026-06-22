import type { BacktestRunDetail } from "../../api/types";
import { displayValue } from "../../utils/format";

interface BacktestResultProps {
  readonly run: BacktestRunDetail | null;
  readonly pending: boolean;
  readonly selectedRunId: number | null;
}

export function BacktestResult({ run, pending, selectedRunId }: BacktestResultProps) {
  if (pending) {
    return (
      <section className="detail-panel" aria-label="Backtest result">
        <h3>Backtest Result</h3>
        <p>Loading run {selectedRunId === null ? "" : `#${selectedRunId}`}.</p>
      </section>
    );
  }

  if (run === null) {
    return (
      <section className="detail-panel" aria-label="Backtest result">
        <h3>Backtest Result</h3>
        <p>No backtest selected yet.</p>
      </section>
    );
  }

  return (
    <section className="detail-panel backtest-result-panel" aria-label="Backtest result">
      <div className="lab-panel__header">
        <h3>Backtest Result</h3>
        <span>Run #{run.run_id}</span>
      </div>
      <p className="lab-result-summary">{backtestSummary(run)}</p>
      <div className="metric-grid">
        <Metric
          label="Trade count"
          value={displayValue(run.stats.trade_count, String(run.trades.length))}
        />
        <Metric label="Net PnL" value={displayValue(run.stats.net_pnl)} />
        <Metric label="Win rate" value={displayValue(run.stats.win_rate)} />
        <Metric label="Expectancy" value={displayValue(run.stats.expectancy)} />
        <Metric label="Average R" value={displayValue(run.stats.average_r)} />
        <Metric label="Max drawdown" value={displayValue(run.stats.max_drawdown)} />
      </div>
      <BacktestTradesTable run={run} />
    </section>
  );
}

function BacktestTradesTable({ run }: { readonly run: BacktestRunDetail }) {
  return (
    <div className="lab-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Side</th>
            <th>Level</th>
            <th>Units</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>P&L</th>
            <th>R</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {run.trades.length === 0 ? (
            <tr>
              <td colSpan={8}>No trades were opened in this backtest window.</td>
            </tr>
          ) : (
            run.trades.map((trade, index) => (
              <tr key={`${run.run_id}-${index}`}>
                <td>{displayValue(trade.side)}</td>
                <td>{displayValue(trade.level_name)}</td>
                <td>{displayValue(trade.units)}</td>
                <td>
                  {displayValue(trade.entry_price)}
                  <br />
                  <span className="muted-table-text">{displayValue(trade.entry_ts)}</span>
                </td>
                <td>
                  {displayValue(trade.exit_price)}
                  <br />
                  <span className="muted-table-text">{displayValue(trade.exit_ts)}</span>
                </td>
                <td>{displayValue(trade.pnl)}</td>
                <td>{displayValue(trade.r_multiple)}</td>
                <td>{displayValue(trade.exit_reason)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
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

function backtestSummary(run: BacktestRunDetail): string {
  const tradeCount = Number(run.stats.trade_count ?? run.trades.length);
  const target = runTarget(run.params);
  if (tradeCount === 0) {
    return `${target} produced no trades in this historical candle window.`;
  }
  return `${target} produced ${tradeCount} closed ${tradeCount === 1 ? "trade" : "trades"} in this historical candle window.`;
}

function runTarget(params: Record<string, unknown>): string {
  if (typeof params.variant_label === "string") {
    return params.variant_label;
  }
  if (params.strategy_params !== undefined) {
    return "Tuned strategy";
  }
  return "Default strategy";
}
