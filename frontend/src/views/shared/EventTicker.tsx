import type { EventLogItem } from "../../api/types";
import { fmtClock } from "../../ui/format";
import { EmptyState } from "../../ui/primitives";

function levelClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === "error" || normalized === "critical") {
    return "lvl-error";
  }
  return normalized === "warn" || normalized === "warning" ? "lvl-warn" : "lvl-info";
}

export function EventTicker({
  events,
  max = 40,
  onSelect,
}: {
  readonly events: readonly EventLogItem[];
  readonly max?: number;
  readonly onSelect?: (event: EventLogItem) => void;
}) {
  if (events.length === 0) {
    return <EmptyState glyph="∅" title="No events yet" hint="System activity will stream here." />;
  }
  return (
    <div className="ticker" aria-label="Event ticker">
      {events.slice(0, max).map((event) => (
        <div className="ticker__row" key={`${event.id}-${event.ts}`}>
          <span className="ticker__time">{fmtClock(event.ts)}</span>
          <span className="ticker__mod">{event.module}</span>
          {onSelect ? (
            <button
              type="button"
              className={`row-btn ticker__msg ${levelClass(event.level)}`}
              onClick={() => onSelect(event)}
            >
              {event.message}
            </button>
          ) : (
            <span className={`ticker__msg ${levelClass(event.level)}`}>{event.message}</span>
          )}
        </div>
      ))}
    </div>
  );
}
