import { useState } from "react";

import type {
  CandleBackfillInstrument,
  CandleBackfillMonth,
  CandleBackfillStatus,
} from "../api/candles";
import type { useStartCandleBackfillMutation } from "../api/hooks";
import { fmtInt } from "../ui/format";
import { EmptyState, Field, Panel, Tag } from "../ui/primitives";

type BackfillMutation = ReturnType<typeof useStartCandleBackfillMutation>;

function monthTone(month: CandleBackfillMonth): "complete" | "partial" | "missing" {
  if (month.pending_days === 0) {
    return "complete";
  }
  if (month.complete_days > 0) {
    return "partial";
  }
  return "missing";
}

function selectedBackfillInstrument(
  instruments: CandleBackfillInstrument[],
  selectedInstrument: string
): CandleBackfillInstrument | null {
  return (
    instruments.find((instrument) => instrument.instrument === selectedInstrument) ??
    instruments[0] ??
    null
  );
}

export function BackfillControls({
  ready,
  running,
  mutation,
}: {
  readonly ready: boolean;
  readonly running: boolean;
  readonly mutation: BackfillMutation;
}) {
  return (
    <button
      type="button"
      className="btn btn--primary"
      disabled={!ready || running || mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      {running || mutation.isPending ? "Collecting data…" : "Collect missing data"}
    </button>
  );
}

function BackfillInstrumentHeader({
  instruments,
  selected,
  onInstrumentChange,
}: {
  readonly instruments: CandleBackfillInstrument[];
  readonly selected: CandleBackfillInstrument;
  readonly onInstrumentChange: (instrument: string) => void;
}) {
  return (
    <div className="backfill-head">
      <Field label="Instrument">
        <select
          className="input"
          value={selected.instrument}
          onChange={(event) => onInstrumentChange(event.target.value)}
        >
          {instruments.map((instrument) => (
            <option key={instrument.instrument} value={instrument.instrument}>
              {instrument.instrument}
            </option>
          ))}
        </select>
      </Field>
      <div className="backfill-metrics">
        <Tag tone="up">{selected.historical.loaded_days} loaded</Tag>
        <Tag tone={selected.historical.pending_days ? "warn" : "up"}>
          {selected.historical.pending_days} pending
        </Tag>
        <Tag tone="muted">{fmtInt(selected.imported_count)} imported</Tag>
      </div>
    </div>
  );
}

function BackfillMonthGrid({
  months,
  selectedMonth,
  onMonthChange,
}: {
  readonly months: CandleBackfillMonth[];
  readonly selectedMonth: string | null;
  readonly onMonthChange: (month: string) => void;
}) {
  return (
    <div className="month-grid" aria-label="Month coverage">
      {months.map((month) => (
        <button
          type="button"
          key={month.month}
          className={`month-cell month-cell--${monthTone(month)}`}
          title={`${month.month}: ${month.complete_days}/${month.expected_days} weekdays loaded, ${month.pending_days} pending`}
          aria-pressed={selectedMonth === month.month}
          onClick={() => onMonthChange(month.month)}
        >
          <span>{month.month.slice(5)}</span>
          <strong>{Math.round(month.completion_ratio * 100)}%</strong>
        </button>
      ))}
    </div>
  );
}

function BackfillMonthDetail({ month }: { readonly month: CandleBackfillMonth | null }) {
  if (!month) {
    return null;
  }
  return (
    <dl className="kv backfill-detail">
      <dt>Month</dt>
      <dd>{month.month}</dd>
      <dt>Loaded</dt>
      <dd>{month.loaded_days}</dd>
      <dt>Filled</dt>
      <dd>{month.filled_days}</dd>
      <dt>Pending</dt>
      <dd>{month.pending_days}</dd>
    </dl>
  );
}

function BackfillSummary({
  instruments,
  selectedInstrument,
  onInstrumentChange,
}: {
  readonly instruments: CandleBackfillInstrument[];
  readonly selectedInstrument: string;
  readonly onInstrumentChange: (instrument: string) => void;
}) {
  const [activeMonth, setActiveMonth] = useState<string | null>(null);
  if (instruments.length === 0) {
    return (
      <Panel title="Historical backfill" label="Historical backfill">
        <EmptyState glyph="▦" title="No backfill run recorded" />
      </Panel>
    );
  }
  const selected = selectedBackfillInstrument(instruments, selectedInstrument);
  if (!selected) {
    return null;
  }
  const monthDetail =
    selected.historical.months.find((month) => month.month === activeMonth) ??
    selected.historical.months[0] ??
    null;
  return (
    <Panel
      title="Historical backfill"
      note={`${selected.historical.pending_days} days remaining`}
      label="Historical backfill"
    >
      <BackfillInstrumentHeader
        instruments={instruments}
        selected={selected}
        onInstrumentChange={onInstrumentChange}
      />
      <BackfillMonthGrid
        months={selected.historical.months}
        selectedMonth={monthDetail?.month ?? null}
        onMonthChange={setActiveMonth}
      />
      <BackfillMonthDetail month={monthDetail} />
    </Panel>
  );
}

export function BackfillSummaryPanel({
  status,
  selectedInstrument,
  onInstrumentChange,
}: {
  readonly status: CandleBackfillStatus | null;
  readonly selectedInstrument: string;
  readonly onInstrumentChange: (instrument: string) => void;
}) {
  if (!status) {
    return null;
  }
  return (
    <BackfillSummary
      instruments={status.instruments}
      selectedInstrument={selectedInstrument}
      onInstrumentChange={onInstrumentChange}
    />
  );
}
