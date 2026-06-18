import type { BacktestRunDetail, BacktestRunSummary, BacktestStartPayload } from "../../api/types";
import { displayValue } from "../../utils/format";
import { BacktestResult } from "./BacktestResult";
import { BacktestRunForm } from "./BacktestRunForm";

interface BacktestsViewProps {
  readonly runs: BacktestRunSummary[];
  readonly selectedRun: BacktestRunDetail | null;
  readonly pending: boolean;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
}

export function BacktestsView({ runs, selectedRun, pending, onStartBacktest }: BacktestsViewProps) {
  return (
    <section className="product-view backtests-view" aria-label="Backtests page">
      <div className="product-view__header">
        <h2>Backtests</h2>
        <BacktestRunForm pending={pending} onStartBacktest={onStartBacktest} />
      </div>

      <div className="two-column-layout">
        <section className="table-panel" aria-label="Backtest runs">
          <h3>Recent Runs</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Trades</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td>{run.run_id}</td>
                  <td>{displayValue(run.stats.status, "completed")}</td>
                  <td>{run.trade_count}</td>
                  <td>{run.created_ts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <BacktestResult run={selectedRun} />
      </div>
    </section>
  );
}
