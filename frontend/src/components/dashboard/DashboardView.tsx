import type { PracticeControls } from "../../api/hooks";
import type {
  CandlePoint,
  EventLogItem,
  MarkersPayload,
  SessionLevelSnapshot,
  StatusSnapshot,
} from "../../api/types";
import { GuardedTradingControls } from "../GuardedTradingControls";
import { HealthCards } from "../HealthCards";
import { LiveChart } from "../LiveChart";
import { ReadOnlyTradingState } from "../ReadOnlyTradingState";
import { StatusStrip } from "../StatusStrip";
import type { LiveChartAdapter } from "../chartAdapter";

interface DashboardViewProps {
  readonly status: StatusSnapshot;
  readonly levels: SessionLevelSnapshot | null;
  readonly candles: CandlePoint[];
  readonly markers: MarkersPayload;
  readonly events: EventLogItem[];
  readonly chartAdapter?: LiveChartAdapter;
  readonly controls: PracticeControls;
}

export function DashboardView({
  status,
  levels,
  candles,
  markers,
  events,
  chartAdapter,
  controls,
}: DashboardViewProps) {
  return (
    <>
      <StatusStrip status={status} />
      <div className="dashboard-grid">
        <HealthCards status={status} />
        {status.trading_controls_available ? (
          <GuardedTradingControls
            status={status}
            pending={controls.pending}
            errorMessage={controls.errorMessage}
            onSetTradingEnabled={controls.setTradingEnabled}
            onFlattenNow={controls.flattenNow}
          />
        ) : (
          <ReadOnlyTradingState status={status} />
        )}
      </div>
      <LiveChart candles={candles} levels={levels} markers={markers} adapter={chartAdapter} />
      <section className="events-panel" aria-label="Recent events">
        <h2>Recent events</h2>
        <ul>
          {events.map((event) => (
            <li key={`${event.id}-${event.ts}`}>
              <strong>{event.level}</strong>
              <span>{event.message}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
