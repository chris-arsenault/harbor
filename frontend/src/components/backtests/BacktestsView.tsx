import type {
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStartPayload,
  CandleSourceStatus,
  PaperVariant,
} from "../../api/types";
import { displayValue } from "../../utils/format";
import { BacktestResult } from "./BacktestResult";
import { BacktestRunForm } from "./BacktestRunForm";

interface BacktestsViewProps {
  readonly runs: BacktestRunSummary[];
  readonly selectedRunId: number | null;
  readonly selectedRun: BacktestRunDetail | null;
  readonly selectedRunPending: boolean;
  readonly selectedRunError: string | null;
  readonly candleSource: CandleSourceStatus | null;
  readonly targetVariant: PaperVariant | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
  readonly onSelectRun: (runId: number) => void;
}

export function BacktestsView({
  runs,
  selectedRunId,
  selectedRun,
  selectedRunPending,
  selectedRunError,
  candleSource,
  targetVariant,
  pending,
  errorMessage,
  onStartBacktest,
  onSelectRun,
}: BacktestsViewProps) {
  return (
    <section className="product-view backtests-view" aria-label="Backtests page">
      <div className="product-view__header">
        <h2>Backtests</h2>
      </div>

      <BacktestRunForm
        key={backtestFormKey(candleSource, targetVariant)}
        coverage={candleSource?.coverage ?? null}
        defaultInstrument={candleSource?.instrument ?? "GBP_USD"}
        targetVariant={targetVariant}
        pending={pending}
        onStartBacktest={onStartBacktest}
      />
      {errorMessage ? (
        <p className="lab-run-notice lab-run-notice--error" aria-live="polite">
          {errorMessage}
        </p>
      ) : null}
      {selectedRunError ? (
        <p className="lab-run-notice lab-run-notice--error" aria-live="polite">
          {selectedRunError}
        </p>
      ) : null}
      <BacktestResult
        run={selectedRun}
        pending={selectedRunPending}
        selectedRunId={selectedRunId}
      />
      <RecentRuns runs={runs} selectedRunId={selectedRunId} onSelectRun={onSelectRun} />
    </section>
  );
}

function RecentRuns({
  runs,
  selectedRunId,
  onSelectRun,
}: {
  readonly runs: BacktestRunSummary[];
  readonly selectedRunId: number | null;
  readonly onSelectRun: (runId: number) => void;
}) {
  return (
    <section className="table-panel" aria-label="Backtest runs">
      <div className="lab-panel__header">
        <h3>Recent Runs</h3>
        <span>{runs.length === 1 ? "1 run" : `${runs.length} runs`}</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Target</th>
            <th>Window</th>
            <th>Trades</th>
            <th>Expectancy</th>
            <th>Created</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {runs.length === 0 ? (
            <tr>
              <td colSpan={7}>No backtests have been run yet.</td>
            </tr>
          ) : (
            runs.map((run) => (
              <tr
                key={run.run_id}
                className={run.run_id === selectedRunId ? "data-table__row--selected" : undefined}
              >
                <td>#{run.run_id}</td>
                <td>{runTarget(run.params)}</td>
                <td>{runWindow(run.params)}</td>
                <td>{run.trade_count}</td>
                <td>{displayValue(run.stats.expectancy)}</td>
                <td>{run.created_ts}</td>
                <td>
                  <button
                    type="button"
                    className="lab-button lab-button--quiet"
                    onClick={() => onSelectRun(run.run_id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
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

function runWindow(params: Record<string, unknown>): string {
  const range = params.candle_range;
  if (!isRecord(range)) {
    return "n/a";
  }
  return `${displayValue(range.from)} to ${displayValue(range.to)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function backtestFormKey(
  candleSource: CandleSourceStatus | null,
  targetVariant: PaperVariant | null
): string {
  const coverage = candleSource?.coverage;
  return [
    candleSource?.instrument ?? "none",
    coverage?.from ?? "none",
    coverage?.to ?? "none",
    targetVariant?.id ?? "default",
  ].join(":");
}
