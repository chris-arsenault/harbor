import type { PracticeControls } from "../api/hooks";
import type { StatusSnapshot } from "../api/types";
import { displayValue } from "../utils/format";
import { fmtSigned, valueTone } from "../ui/format";
import { Notice, Panel, StatTile, Tag, ViewHead } from "../ui/primitives";
import { GuardedControls } from "./shared/GuardedControls";

function rec(value: Record<string, unknown> | null | undefined, key: string): unknown {
  return value ? value[key] : undefined;
}

function bool(value: unknown): "enabled" | "disabled" {
  return value === true ? "enabled" : "disabled";
}

function shortCommit(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) {
    return "unknown";
  }
  return value.length > 12 ? value.slice(0, 12) : value;
}

function ExecutionState({ status }: { readonly status: StatusSnapshot }) {
  const drift = rec(status.reconciliation_state, "drift_detected") === true;
  return (
    <Panel title="Execution state" label="Execution state">
      <dl className="kv">
        <dt>Promoted variant</dt>
        <dd>{status.promoted_variant?.label ?? "none"}</dd>
        <dt>Reconciliation</dt>
        <dd>{drift ? "drift detected" : "in sync"}</dd>
        <dt>Open position</dt>
        <dd>{displayValue(rec(status.open_position, "instrument"), "flat")}</dd>
        <dt>Open positions</dt>
        <dd>{status.open_positions ?? 0}</dd>
        <dt>Heartbeat</dt>
        <dd>{status.last_heartbeat ?? "—"}</dd>
      </dl>
    </Panel>
  );
}

function AlertsAndDeploy({ status }: { readonly status: StatusSnapshot }) {
  const deployment = status.deployment;
  const gitSha = rec(deployment, "git_sha");
  return (
    <div className="duo">
      <Panel title="Alerts" label="Alerts">
        <div className="row">
          <Tag tone={rec(status.notifier_state, "ntfy_enabled") === true ? "up" : "muted"}>
            ntfy {bool(rec(status.notifier_state, "ntfy_enabled"))}
          </Tag>
          <Tag tone={rec(status.notifier_state, "telegram_enabled") === true ? "up" : "muted"}>
            telegram {bool(rec(status.notifier_state, "telegram_enabled"))}
          </Tag>
        </div>
      </Panel>
      <Panel title="Deployment" label="Deployment">
        <dl className="kv">
          <dt>Access</dt>
          <dd>{displayValue(rec(deployment, "access"), "—")}</dd>
          <dt>Frontend</dt>
          <dd>{displayValue(rec(deployment, "frontend_url"), "—")}</dd>
          <dt>Public route</dt>
          <dd>{displayValue(rec(deployment, "public_route"), "—")}</dd>
          <dt>Health</dt>
          <dd>{displayValue(rec(deployment, "health_path"), "—")}</dd>
          <dt>Commit</dt>
          <dd title={typeof gitSha === "string" ? gitSha : undefined}>{shortCommit(gitSha)}</dd>
          <dt>Build</dt>
          <dd>{displayValue(rec(deployment, "build_time"), "unknown")}</dd>
        </dl>
      </Panel>
    </div>
  );
}

function FlattenResult({ controls }: { readonly controls: PracticeControls }) {
  const result = controls.flattenResult;
  if (!result) {
    return null;
  }
  return (
    <Notice tone="ok">
      Flattened ({result.reason}): closed {result.closed_trade_ids.length} trades,{" "}
      {result.closed_position_instruments.join(", ") || "no positions"}.
    </Notice>
  );
}

export function OperationsView({
  status,
  controls,
}: {
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
}) {
  return (
    <section className="view" aria-label="Operations">
      <ViewHead
        kicker="System"
        title="Operations"
        sub="Runtime control and reconciliation state."
      />
      <div className="tiles">
        <StatTile label="Mode" value={status.mode} tone="beam" />
        <StatTile label="Trading" value={status.trading_enabled ? "armed" : "disarmed"} />
        <StatTile label="Kill switch" value={status.kill_switch_state} tone="warn" />
        <StatTile
          label="Day P&L"
          value={fmtSigned(status.day_pnl)}
          tone={valueTone(status.day_pnl)}
        />
      </div>
      <Panel title="Trading control" label="Trading control">
        <GuardedControls status={status} controls={controls} />
        <FlattenResult controls={controls} />
      </Panel>
      <ExecutionState status={status} />
      <AlertsAndDeploy status={status} />
    </section>
  );
}
