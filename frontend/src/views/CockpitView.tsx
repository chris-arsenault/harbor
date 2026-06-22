import type { PracticeControls } from "../api/hooks";
import type {
  CandlePoint,
  EventLogItem,
  MarkersPayload,
  SessionLevelSnapshot,
  StatusSnapshot,
} from "../api/types";
import type { LiveChartAdapter } from "../components/chartAdapter";
import { LiveChart } from "../components/LiveChart";
import { fmtPrice, titleCase } from "../ui/format";
import { EmptyState, Panel, Tag, ViewHead } from "../ui/primitives";
import { EventTicker } from "./shared/EventTicker";
import { GuardedControls } from "./shared/GuardedControls";

export interface PipelineState {
  readonly dataReady: boolean;
  readonly researchReady: boolean;
  readonly hasCandidate: boolean;
  readonly hasBacktest: boolean;
  readonly hasPaper: boolean;
  readonly hasLive: boolean;
  readonly promotedLabel: string | null;
}

function PipelineStrip({ pipeline }: { readonly pipeline: PipelineState }) {
  const stages = [
    ["Data", pipeline.dataReady, "candles"],
    ["Research", pipeline.researchReady, "preflight"],
    ["Candidate", pipeline.hasCandidate, "variant"],
    ["Backtest", pipeline.hasBacktest, "validated"],
    ["Paper", pipeline.hasPaper, "forward"],
    ["Live", pipeline.hasLive, pipeline.promotedLabel ?? "promote"],
  ] as const;
  return (
    <div className="pipe" aria-label="Strategy pipeline">
      {stages.map(([name, ready, hint], index) => (
        <div className={`pipe__stage${ready ? " pipe__stage--ready" : ""}`} key={name}>
          <span className="pipe__num">{`0${index + 1}`}</span>
          <span className="pipe__name">{name}</span>
          <span className="pipe__state">{ready ? hint : "waiting"}</span>
        </div>
      ))}
    </div>
  );
}

function SessionCard({
  status,
  levels,
}: {
  readonly status: StatusSnapshot;
  readonly levels: SessionLevelSnapshot | null;
}) {
  return (
    <Panel title="Session" note={titleCase(status.session_phase)} label="Session">
      {levels ? (
        <dl className="kv">
          <dt>Asia</dt>
          <dd>
            {fmtPrice(levels.asia_high)} / {fmtPrice(levels.asia_low)}
          </dd>
          <dt>London</dt>
          <dd>
            {fmtPrice(levels.london_high)} / {fmtPrice(levels.london_low)}
          </dd>
          <dt>Swept</dt>
          <dd>{levels.swept_levels.length > 0 ? levels.swept_levels.join(", ") : "none"}</dd>
          <dt>Taken</dt>
          <dd>{levels.taken_levels.length > 0 ? levels.taken_levels.join(", ") : "none"}</dd>
        </dl>
      ) : (
        <EmptyState glyph="≈" title="No session levels" hint="Levels publish at session close." />
      )}
      <div className="row">
        <Tag tone="beam" plain>
          {status.bot_state}
        </Tag>
        <Tag tone="muted">{status.connection_health}</Tag>
      </div>
    </Panel>
  );
}

export function CockpitView({
  status,
  levels,
  candles,
  markers,
  events,
  controls,
  chartAdapter,
  pipeline,
}: {
  readonly status: StatusSnapshot;
  readonly levels: SessionLevelSnapshot | null;
  readonly candles: CandlePoint[];
  readonly markers: MarkersPayload;
  readonly events: readonly EventLogItem[];
  readonly controls: PracticeControls;
  readonly chartAdapter?: LiveChartAdapter;
  readonly pipeline: PipelineState;
}) {
  return (
    <section className="view" aria-label="Cockpit">
      <ViewHead
        kicker="Monitor"
        title="Cockpit"
        sub="Live execution against closed-candle signals."
        actions={
          <Tag tone={status.bot_state === "IDLE" ? "muted" : "beam"}>{status.bot_state}</Tag>
        }
      />
      <PipelineStrip pipeline={pipeline} />
      <div className="split--wide-right">
        <Panel title="Price" note={`${candles.length} candles`} label="Price">
          <div className="chart-shell">
            <LiveChart candles={candles} levels={levels} markers={markers} adapter={chartAdapter} />
            <div className="chart-facts">
              <Tag tone="muted">{markers.markers.length} sweeps</Tag>
              <Tag tone="muted">{markers.fvgs.length} FVGs</Tag>
              <Tag tone="info">{markers.signals.length} signals</Tag>
              <Tag tone="beam">{markers.trades.length} trades</Tag>
            </div>
          </div>
        </Panel>
        <div className="stack">
          <SessionCard status={status} levels={levels} />
          <Panel title="Trading" label="Trading">
            <GuardedControls status={status} controls={controls} />
          </Panel>
          <Panel title="Activity" note="live" label="Activity">
            <EventTicker events={events} max={18} />
          </Panel>
        </div>
      </div>
    </section>
  );
}
