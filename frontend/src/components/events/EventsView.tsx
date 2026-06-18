import { useMemo, useState } from "react";

import type { EventLogItem } from "../../api/types";
import { displayValue } from "../../utils/format";

interface EventsViewProps {
  readonly events: EventLogItem[];
  readonly loading: boolean;
  readonly errorMessage?: string | null;
}

export function EventsView({ events, loading, errorMessage = null }: EventsViewProps) {
  const [level, setLevel] = useState("all");
  const [moduleFilter, setModuleFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const sortedEvents = useMemo(() => sortEvents(events), [events]);
  const filteredEvents = sortedEvents.filter((event) =>
    matchesFilters(event, { level, moduleFilter, typeFilter, from, to })
  );
  const selectedEvent =
    filteredEvents.find((event) => event.id === selectedEventId) ?? filteredEvents[0] ?? null;

  return (
    <section className="product-view events-view" aria-label="Events page">
      <div className="product-view__header">
        <h2>Events</h2>
        <EventFiltersForm
          events={sortedEvents}
          filters={{ level, moduleFilter, typeFilter, from, to }}
          onLevelChange={setLevel}
          onModuleChange={setModuleFilter}
          onTypeChange={setTypeFilter}
          onFromChange={setFrom}
          onToChange={setTo}
        />
      </div>

      {errorMessage ? <p className="product-error">{errorMessage}</p> : null}
      {loading ? <p className="product-empty">Loading events...</p> : null}
      {!loading && filteredEvents.length === 0 ? (
        <p className="product-empty">No events match the current filters.</p>
      ) : null}

      {filteredEvents.length > 0 ? (
        <div className="two-column-layout">
          <EventsTable events={filteredEvents} onSelectEvent={setSelectedEventId} />
          <EventDetail event={selectedEvent} />
        </div>
      ) : null}
    </section>
  );
}

interface EventFilters {
  readonly level: string;
  readonly moduleFilter: string;
  readonly typeFilter: string;
  readonly from: string;
  readonly to: string;
}

interface EventFiltersFormProps {
  readonly events: EventLogItem[];
  readonly filters: EventFilters;
  readonly onLevelChange: (value: string) => void;
  readonly onModuleChange: (value: string) => void;
  readonly onTypeChange: (value: string) => void;
  readonly onFromChange: (value: string) => void;
  readonly onToChange: (value: string) => void;
}

function EventFiltersForm({
  events,
  filters,
  onLevelChange,
  onModuleChange,
  onTypeChange,
  onFromChange,
  onToChange,
}: EventFiltersFormProps) {
  return (
    <div className="filter-row" aria-label="Event filters">
      <EventFilterSelect
        label="Level"
        value={filters.level}
        values={uniqueValues(events.map((event) => event.level))}
        onChange={onLevelChange}
      />
      <EventFilterSelect
        label="Module"
        value={filters.moduleFilter}
        values={uniqueValues(events.map((event) => event.module))}
        onChange={onModuleChange}
      />
      <EventFilterSelect
        label="Type"
        value={filters.typeFilter}
        values={uniqueValues(events.map((event) => event.type))}
        onChange={onTypeChange}
      />
      <label>
        From
        <input value={filters.from} onChange={(event) => onFromChange(event.target.value)} />
      </label>
      <label>
        To
        <input value={filters.to} onChange={(event) => onToChange(event.target.value)} />
      </label>
    </div>
  );
}

function EventFilterSelect({
  label,
  value,
  values,
  onChange,
}: {
  readonly label: string;
  readonly value: string;
  readonly values: string[];
  readonly onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="all">All</option>
        {values.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function EventsTable({
  events,
  onSelectEvent,
}: {
  readonly events: EventLogItem[];
  readonly onSelectEvent: (eventId: number) => void;
}) {
  return (
    <section className="table-panel" aria-label="Event log">
      <table className="data-table">
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
            <tr key={`${event.id}-${event.ts}`}>
              <td>{event.ts}</td>
              <td>{event.level}</td>
              <td>{event.module}</td>
              <td>{event.type}</td>
              <td>
                <button
                  className="event-row-button"
                  type="button"
                  onClick={() => onSelectEvent(event.id)}
                >
                  {event.message}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function EventDetail({ event }: { readonly event: EventLogItem | null }) {
  if (event === null) {
    return (
      <aside className="detail-panel" aria-label="Event detail">
        <h3>Event Detail</h3>
      </aside>
    );
  }

  return (
    <aside className="detail-panel" aria-label="Event detail">
      <h3>Event Detail</h3>
      <dl>
        <dt>Level</dt>
        <dd>{event.level}</dd>
        <dt>Module</dt>
        <dd>{event.module}</dd>
        <dt>Type</dt>
        <dd>{event.type}</dd>
        <dt>Time</dt>
        <dd>{event.ts}</dd>
      </dl>
      {event.type === "daily_summary" ? <DailySummary data={event.data} /> : null}
      <section aria-label="Structured event data">
        <h4>Structured Data</h4>
        <ul className="fact-list">
          {Object.entries(event.data).map(([key, value]) => (
            <li key={key}>{jsonField(key, value)}</li>
          ))}
        </ul>
        <pre className="json-detail">{JSON.stringify(event.data, null, 2)}</pre>
      </section>
    </aside>
  );
}

function DailySummary({ data }: { readonly data: Record<string, unknown> }) {
  return (
    <section className="daily-summary" aria-label="Daily summary">
      <h4>Daily Summary</h4>
      <dl>
        <dt>Trades Today</dt>
        <dd>{displayValue(data.trades_today, "0")}</dd>
        <dt>Day P&L</dt>
        <dd>{displayValue(data.day_pnl, "0")}</dd>
        <dt>Open Positions</dt>
        <dd>{displayValue(data.open_positions, "unknown")}</dd>
      </dl>
    </section>
  );
}

function matchesFilters(event: EventLogItem, filters: EventFilters) {
  return [
    filters.level === "all" || event.level === filters.level,
    filters.moduleFilter === "all" || event.module === filters.moduleFilter,
    filters.typeFilter === "all" || event.type === filters.typeFilter,
    filters.from === "" || event.ts >= filters.from,
    filters.to === "" || event.ts < filters.to,
  ].every(Boolean);
}

function sortEvents(events: EventLogItem[]) {
  return [...events].sort((left, right) => right.ts.localeCompare(left.ts));
}

function uniqueValues(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function jsonField(key: string, value: unknown): string {
  return `"${key}": ${JSON.stringify(value)}`;
}
