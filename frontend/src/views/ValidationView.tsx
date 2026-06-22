import type {
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStartPayload,
  CandleSourceStatus,
  PaperVariant,
} from "../api/types";
import { fmtDateTime, fmtNum } from "../ui/format";
import { EmptyState, Notice, Panel, ViewHead } from "../ui/primitives";
import { BacktestSummary } from "./validation/BacktestSummary";
import { RunForm } from "./validation/RunForm";
import { runMeta } from "./validation/runModel";

function RunHistory({
  runs,
  selectedRunId,
  onSelectRun,
}: {
  readonly runs: readonly BacktestRunSummary[];
  readonly selectedRunId: number | null;
  readonly onSelectRun: (runId: number) => void;
}) {
  if (runs.length === 0) {
    return <EmptyState glyph="⎍" title="No backtests yet" hint="Run one to populate history." />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Run</th>
            <th>Target</th>
            <th>Window</th>
            <th className="num">Trades</th>
            <th className="num">Expectancy</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const meta = runMeta(run);
            return (
              <tr
                key={run.run_id}
                className={run.run_id === selectedRunId ? "is-selected" : undefined}
              >
                <td>
                  <button type="button" className="row-btn" onClick={() => onSelectRun(run.run_id)}>
                    #{run.run_id}
                  </button>
                </td>
                <td className="cell-strong">{meta.label}</td>
                <td className="mute">{meta.window}</td>
                <td className="num">{run.trade_count}</td>
                <td className="num">{fmtNum(run.stats.expectancy, 2)}</td>
                <td className="mute">{fmtDateTime(run.created_ts)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export interface ValidationViewProps {
  readonly runs: readonly BacktestRunSummary[];
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

export function ValidationView(props: ValidationViewProps) {
  return (
    <section className="view" aria-label="Validation">
      <ViewHead
        kicker="Research"
        title="Validation"
        sub="Replay a candidate over persisted candles before promotion."
      />
      <Panel title="New backtest" label="New backtest">
        <RunForm
          candleSource={props.candleSource}
          targetVariant={props.targetVariant}
          pending={props.pending}
          onStartBacktest={props.onStartBacktest}
        />
        {props.errorMessage ? <Notice tone="error">{props.errorMessage}</Notice> : null}
        {props.selectedRunError ? <Notice tone="error">{props.selectedRunError}</Notice> : null}
      </Panel>
      <BacktestSummary run={props.selectedRun} pending={props.selectedRunPending} />
      <Panel title="Run history" note={`${props.runs.length} runs`} label="Run history">
        <RunHistory
          runs={props.runs}
          selectedRunId={props.selectedRunId}
          onSelectRun={props.onSelectRun}
        />
      </Panel>
    </section>
  );
}
