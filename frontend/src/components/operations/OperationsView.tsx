import type { PracticeControls } from "../../api/hooks";
import type { StatusSnapshot } from "../../api/types";
import { displayValue, lanEndpoint } from "../../utils/format";
import { GuardedTradingControls } from "../GuardedTradingControls";
import { HeartbeatIndicator } from "../HeartbeatIndicator";
import { ReadOnlyTradingState } from "../ReadOnlyTradingState";

interface OperationsViewProps {
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
}

export function OperationsView({ status, controls }: OperationsViewProps) {
  return (
    <section className="product-view operations-view" aria-label="Operations page">
      <div className="product-view__header">
        <h2>Operations</h2>
      </div>
      <OperationMetrics status={status} />
      <div className="operations-grid">
        <TradingControlPanel status={status} controls={controls} />
        <PracticeExecutionState status={status} />
        <AlertState notifierState={status.notifier_state ?? {}} />
        <DeploymentState deployment={status.deployment ?? {}} />
        <FlattenResultState controls={controls} />
      </div>
    </section>
  );
}

function OperationMetrics({ status }: { readonly status: StatusSnapshot }) {
  return (
    <div className="metric-grid">
      <Metric label="Mode" value={status.mode === "practice" ? "practice-only" : status.mode} />
      <Metric label="Trading" value={status.trading_enabled ? "enabled" : "disabled"} />
      <Metric label="Kill Switch" value={status.kill_switch_state} />
      <Metric label="Day P&L" value={status.day_pnl} />
    </div>
  );
}

function TradingControlPanel({
  status,
  controls,
}: {
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
}) {
  if (!status.trading_controls_available) {
    return <ReadOnlyTradingState status={status} />;
  }
  return (
    <GuardedTradingControls
      status={status}
      pending={controls.pending}
      errorMessage={controls.errorMessage}
      onSetTradingEnabled={controls.setTradingEnabled}
      onFlattenNow={controls.flattenNow}
    />
  );
}

function PracticeExecutionState({ status }: { readonly status: StatusSnapshot }) {
  return (
    <section className="detail-panel" aria-label="Practice execution state">
      <h3>Practice Execution</h3>
      <dl>
        <dt>Promoted Variant</dt>
        <dd>{status.promoted_variant?.label ?? "none"}</dd>
        <dt>Reconciliation</dt>
        <dd>{reconciliationLabel(status.reconciliation_state)}</dd>
        <dt>Open Position</dt>
        <dd>{openPositionLabel(status.open_position)}</dd>
        <dt>Open Positions</dt>
        <dd>{displayValue(status.open_positions, "unknown")}</dd>
        <dt>Heartbeat</dt>
        <dd>
          <HeartbeatIndicator lastMessageAt={status.last_heartbeat} />
        </dd>
      </dl>
    </section>
  );
}

function AlertState({ notifierState }: { readonly notifierState: Record<string, unknown> }) {
  return (
    <section className="detail-panel" aria-label="Alert state">
      <h3>Alerts</h3>
      <dl>
        <dt>ntfy</dt>
        <dd>{enabledLabel("ntfy", notifierState.ntfy_enabled)}</dd>
        <dt>telegram</dt>
        <dd>{enabledLabel("telegram", notifierState.telegram_enabled)}</dd>
      </dl>
    </section>
  );
}

function DeploymentState({ deployment }: { readonly deployment: Record<string, unknown> }) {
  return (
    <section className="detail-panel" aria-label="LAN deployment state">
      <h3>Deployment</h3>
      <dl>
        <dt>Access</dt>
        <dd>{displayValue(deployment.access, "LAN")}</dd>
        <dt>Endpoint</dt>
        <dd>{displayValue(deployment.frontend_url, lanEndpoint())}</dd>
        <dt>Public Route</dt>
        <dd>
          {deployment.public_route === true ? "public route enabled" : "public route disabled"}
        </dd>
        <dt>Health</dt>
        <dd>{displayValue(deployment.health_path, "/health")}</dd>
      </dl>
    </section>
  );
}

function FlattenResultState({ controls }: { readonly controls: PracticeControls }) {
  if (!controls.flattenResult) {
    return null;
  }
  return (
    <section className="detail-panel" aria-label="Last flatten result">
      <h3>Last Flatten</h3>
      <dl>
        <dt>Reason</dt>
        <dd>{controls.flattenResult.reason}</dd>
        <dt>Closed Trades</dt>
        <dd>{controls.flattenResult.closed_trade_ids.join(", ") || "none"}</dd>
        <dt>Closed Positions</dt>
        <dd>{controls.flattenResult.closed_position_instruments.join(", ") || "none"}</dd>
      </dl>
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

function reconciliationLabel(state: Record<string, unknown> | null | undefined): string {
  if (!state) {
    return "unknown";
  }
  return state.drift_detected === true ? "drift" : "reconciled";
}

function openPositionLabel(position: Record<string, unknown> | null | undefined): string {
  if (!position) {
    return "flat";
  }
  const instrument = position.instrument;
  return typeof instrument === "string" ? instrument : "open";
}

function enabledLabel(channel: string, value: unknown): string {
  return value === true ? `${channel} enabled` : `${channel} disabled`;
}
