import type { OptimizationStartPayload } from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { Notice, Panel, StatTile, Tag } from "../../ui/primitives";

export interface TuningRunView {
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly resultStatus: string | null;
}

function readinessTone(status: string): "up" | "warn" | "down" | "muted" {
  if (status === "pass") {
    return "up";
  }
  if (status === "warn") {
    return "warn";
  }
  return status === "fail" ? "down" : "muted";
}

function researchDays(preflight: OptimizationPreflightResponse | null): string {
  const protocol = preflight?.research_protocol;
  if (!protocol) {
    return "—";
  }
  return `${protocol.evaluable_day_count}/${protocol.data_requirements.min_evaluable_days}`;
}

function ReadinessList({
  preflight,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
}) {
  const rows = preflight?.readiness ?? [];
  if (rows.length === 0) {
    return <p className="mute">Preflight has not selected a complete research window yet.</p>;
  }
  return (
    <div className="stack">
      {rows.map((row) => (
        <div className="row" key={row.name}>
          <Tag tone={readinessTone(row.status)}>{row.status}</Tag>
          <span className="cell-strong">{row.name}</span>
          <span className="mute">{row.message}</span>
        </div>
      ))}
    </div>
  );
}

function gateLabel(preflight: OptimizationPreflightResponse | null): string {
  const gate = preflight?.candidate_gate;
  return gate ? `${gate.min_in_sample_trades}/${gate.min_out_of_sample_trades}` : "—";
}

function WorkbenchTiles({
  preflight,
  preflightPending,
  ready,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly ready: boolean;
}) {
  return (
    <div className="tiles tiles--tight">
      <StatTile
        label="Preflight"
        value={preflightPending ? "checking" : (preflight?.status ?? "not run")}
        tone={ready ? "up" : "warn"}
      />
      <StatTile label="Research days" value={researchDays(preflight)} />
      <StatTile
        label="Walk-forward"
        value={String(preflight?.walk_forward.window_count ?? 0)}
        sub="windows"
      />
      <StatTile label="Min trades" value={gateLabel(preflight)} sub="IS / OOS" />
    </div>
  );
}

export function Workbench({
  studyPayload,
  preflight,
  preflightPending,
  preflightError,
  tuningRun,
  canStart,
  onStartOptimization,
}: {
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
  readonly tuningRun: TuningRunView;
  readonly canStart: boolean;
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
}) {
  const ready = preflight?.status === "ready";
  const start = () => void onStartOptimization(preflight?.recommended_payload ?? studyPayload);
  return (
    <Panel
      title="Study workbench"
      label="Study workbench"
      actions={
        <button
          type="button"
          className="btn btn--primary"
          disabled={!ready || tuningRun.pending || !canStart}
          onClick={start}
        >
          {tuningRun.pending ? "Running study…" : "Start research study"}
        </button>
      }
    >
      <WorkbenchTiles preflight={preflight} preflightPending={preflightPending} ready={ready} />
      <ReadinessList preflight={preflight} />
      {preflightError ? <Notice tone="error">{preflightError}</Notice> : null}
      {tuningRun.errorMessage ? <Notice tone="error">{tuningRun.errorMessage}</Notice> : null}
      {tuningRun.resultStatus ? <Notice tone="ok">Study {tuningRun.resultStatus}.</Notice> : null}
    </Panel>
  );
}
