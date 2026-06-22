import { useMemo, useState } from "react";

import type { EventLogItem } from "../api/types";
import { displayValue } from "../utils/format";
import { fmtClock, fmtSigned } from "../ui/format";
import { byText } from "../ui/cx";
import { EmptyState, Field, Notice, Panel, Tag, ViewHead } from "../ui/primitives";

const ALL = "all";

function unique(events: readonly EventLogItem[], pick: (event: EventLogItem) => string): string[] {
  return [...new Set(events.map(pick))].sort(byText);
}

function levelTone(level: string): "down" | "warn" | "muted" {
  const normalized = level.toLowerCase();
  if (normalized === "error" || normalized === "critical") {
    return "down";
  }
  return normalized === "warn" || normalized === "warning" ? "warn" : "muted";
}

function EventTable({
  events,
  selectedId,
  onSelect,
}: {
  readonly events: readonly EventLogItem[];
  readonly selectedId: number | null;
  readonly onSelect: (event: EventLogItem) => void;
}) {
  if (events.length === 0) {
    return <EmptyState glyph="❯" title="No events match" hint="Loosen the filters above." />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Time</th>
            <th>Level</th>
            <th>Module</th>
            <th>Type</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={`${event.id}-${event.ts}`}
              className={event.id === selectedId ? "is-selected" : undefined}
              onClick={() => onSelect(event)}
            >
              <td className="num mute">{fmtClock(event.ts)}</td>
              <td>
                <Tag tone={levelTone(event.level)}>{event.level}</Tag>
              </td>
              <td className="mute">{event.module}</td>
              <td className="cell-strong">{event.type}</td>
              <td className="ticker__msg">{event.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DailySummary({ data }: { readonly data: Record<string, unknown> }) {
  return (
    <div className="tiles tiles--tight">
      <div className="fact">
        <span className="fact__label">Trades today</span>
        <span className="fact__value">{displayValue(data.trades_today, "0")}</span>
      </div>
      <div className="fact">
        <span className="fact__label">Day P&L</span>
        <span className="fact__value">{fmtSigned(data.day_pnl)}</span>
      </div>
      <div className="fact">
        <span className="fact__label">Open positions</span>
        <span className="fact__value">{displayValue(data.open_positions, "0")}</span>
      </div>
    </div>
  );
}

function EventDetail({ event }: { readonly event: EventLogItem | null }) {
  if (!event) {
    return <EmptyState glyph="◌" title="No event selected" hint="Select a row to inspect it." />;
  }
  return (
    <div className="stack">
      <div className="row">
        <Tag tone={levelTone(event.level)}>{event.level}</Tag>
        <Tag tone="muted">{event.module}</Tag>
      </div>
      <dl className="kv">
        <dt>Type</dt>
        <dd>{event.type}</dd>
        <dt>Time</dt>
        <dd>{event.ts}</dd>
        <dt>Message</dt>
        <dd>{event.message}</dd>
      </dl>
      {event.type === "daily_summary" ? <DailySummary data={event.data} /> : null}
      <pre className="code">{JSON.stringify(event.data, null, 2)}</pre>
    </div>
  );
}

export function EventsView({
  events,
  loading,
  errorMessage,
}: {
  readonly events: readonly EventLogItem[];
  readonly loading: boolean;
  readonly errorMessage?: string | null;
}) {
  const [level, setLevel] = useState(ALL);
  const [module, setModule] = useState(ALL);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const filtered = useMemo(
    () =>
      events.filter(
        (event) =>
          (level === ALL || event.level === level) && (module === ALL || event.module === module)
      ),
    [events, level, module]
  );
  const selected = filtered.find((event) => event.id === selectedId) ?? null;

  return (
    <section className="view" aria-label="Events">
      <ViewHead
        kicker="System"
        title="Events"
        sub="Structured system journal."
        actions={
          <div className="row">
            <Field label="Level">
              <select className="select" value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value={ALL}>All</option>
                {unique(events, (event) => event.level).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Module">
              <select className="select" value={module} onChange={(e) => setModule(e.target.value)}>
                <option value={ALL}>All</option>
                {unique(events, (event) => event.module).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        }
      />
      {errorMessage ? <Notice tone="error">{errorMessage}</Notice> : null}
      <Panel title="Journal" note={loading ? "loading…" : `${filtered.length}`} label="Journal">
        <div className="split">
          <EventTable
            events={filtered}
            selectedId={selectedId}
            onSelect={(e) => setSelectedId(e.id)}
          />
          <EventDetail event={selected} />
        </div>
      </Panel>
    </section>
  );
}
