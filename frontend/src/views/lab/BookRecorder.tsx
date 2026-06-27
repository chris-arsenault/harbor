import { useBookRecorderStatusQuery } from "../../api/hooks";
import type { BookCoverageRow, BookRecorderStatus } from "../../api/research";
import { fmtDateTime, fmtInt, fmtPrice, NO_VALUE, titleCase } from "../../ui/format";
import { EmptyState, Notice, Panel, StatTile, Tag } from "../../ui/primitives";

interface InstrumentCoverageRow {
  readonly instrument: string;
  readonly order: BookCoverageRow | null;
  readonly position: BookCoverageRow | null;
  readonly from: string | null;
  readonly to: string | null;
}

function byBookType(rows: BookCoverageRow[], instrument: string, bookType: string) {
  return rows.find((row) => row.instrument === instrument && row.book_type === bookType) ?? null;
}

function instrumentRows(status: BookRecorderStatus): InstrumentCoverageRow[] {
  const coverage = status.coverage ?? [];
  const latestByInstrument = status.latest ?? {};
  const instruments = Array.from(
    new Set([...coverage.map((row) => row.instrument), ...Object.keys(latestByInstrument)])
  ).sort((left, right) => left.localeCompare(right));
  return instruments.map((instrument) => {
    const order = byBookType(coverage, instrument, "order");
    const position = byBookType(coverage, instrument, "position");
    return {
      instrument,
      order,
      position,
      from: earliest(order?.from ?? null, position?.from ?? null),
      to: latest(order?.to ?? null, position?.to ?? null),
    };
  });
}

function earliest(left: string | null, right: string | null): string | null {
  if (!left) {
    return right;
  }
  if (!right) {
    return left;
  }
  return new Date(left).getTime() <= new Date(right).getTime() ? left : right;
}

function latest(left: string | null, right: string | null): string | null {
  if (!left) {
    return right;
  }
  if (!right) {
    return left;
  }
  return new Date(left).getTime() >= new Date(right).getTime() ? left : right;
}

function latestCoverageTime(status: BookRecorderStatus): string | null {
  return (status.coverage ?? []).reduce<string | null>(
    (current, row) => latest(current, row.to),
    null
  );
}

function ageText(ts: string | null): string {
  if (!ts) {
    return NO_VALUE;
  }
  const ageMs = Math.max(0, Date.now() - new Date(ts).getTime());
  const minutes = Math.floor(ageMs / 60_000);
  if (minutes < 1) {
    return "<1m";
  }
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return `${hours}h ${minutes % 60}m`;
  }
  return `${Math.floor(hours / 24)}d`;
}

function snapshotTotal(status: BookRecorderStatus | null): number {
  return status?.coverage?.reduce((total, row) => total + row.snapshot_count, 0) ?? 0;
}

function recorderState(status: BookRecorderStatus | null, isLoading: boolean): string {
  if (status?.recorder?.state) {
    return status.recorder.state;
  }
  return isLoading ? "loading" : "disabled";
}

function recorderLabel(status: BookRecorderStatus | null, state: string): string {
  return status?.recorder?.running ? "running" : titleCase(state);
}

function RecorderTiles({
  status,
  state,
}: {
  readonly status: BookRecorderStatus | null;
  readonly state: string;
}) {
  const newest = status ? latestCoverageTime(status) : null;
  return (
    <div className="tiles tiles--tight">
      <StatTile
        label="Recorder"
        value={
          <Tag tone={status?.recorder?.running ? "up" : "muted"}>
            {recorderLabel(status, state)}
          </Tag>
        }
      />
      <StatTile label="Snapshots" value={fmtInt(snapshotTotal(status))} tone="beam" />
      <StatTile label="Instruments" value={fmtInt(status ? instrumentRows(status).length : 0)} />
      <StatTile label="Latest age" value={ageText(newest)} />
    </div>
  );
}

function RecorderMessages({
  status,
  error,
}: {
  readonly status: BookRecorderStatus | null;
  readonly error: Error | null;
}) {
  const recorder = status?.recorder;
  return (
    <>
      <p className="mute">
        Book data is forward-recorded only; history begins when the recorder is enabled.
      </p>
      {recorder?.last_started_at ? (
        <p className="mute">Last started {fmtDateTime(recorder.last_started_at)} UTC.</p>
      ) : null}
      {recorder?.last_error ? <Notice tone="error">{recorder.last_error}</Notice> : null}
      {error ? <Notice tone="error">{error.message}</Notice> : null}
    </>
  );
}

function CoverageTable({ status }: { readonly status: BookRecorderStatus }) {
  const rows = instrumentRows(status);
  if (!rows.length) {
    return (
      <EmptyState
        glyph="∅"
        title="No book coverage yet"
        hint="Enable the recorder to begin collecting forward snapshots."
      />
    );
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Instrument</th>
            <th className="num">Order</th>
            <th className="num">Position</th>
            <th>Earliest</th>
            <th>Latest</th>
            <th>Age</th>
            <th className="num">Order mid</th>
            <th className="num">Position mid</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.instrument}>
              <td className="cell-strong">{row.instrument}</td>
              <td className="num">{fmtInt(row.order?.snapshot_count ?? 0)}</td>
              <td className="num">{fmtInt(row.position?.snapshot_count ?? 0)}</td>
              <td>{fmtDateTime(row.from)}</td>
              <td>{fmtDateTime(row.to)}</td>
              <td>{ageText(row.to)}</td>
              <td className="num">{fmtPrice(row.order?.latest_mid_price)}</td>
              <td className="num">{fmtPrice(row.position?.latest_mid_price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RefreshButton({
  pending,
  onRefresh,
}: {
  readonly pending: boolean;
  readonly onRefresh: () => void;
}) {
  return (
    <button type="button" className="btn btn--ghost btn--sm" disabled={pending} onClick={onRefresh}>
      Refresh
    </button>
  );
}

function RecorderContent({
  status,
  state,
  error,
}: {
  readonly status: BookRecorderStatus | null;
  readonly state: string;
  readonly error: Error | null;
}) {
  return (
    <>
      <RecorderTiles status={status} state={state} />
      <RecorderMessages status={status} error={error} />
      {status ? <CoverageTable status={status} /> : null}
    </>
  );
}

export function BookRecorder() {
  const query = useBookRecorderStatusQuery();
  const status = query.data ?? null;
  const state = recorderState(status, query.isLoading);
  return (
    <Panel
      title="Book recorder"
      note={titleCase(state)}
      label="Book recorder"
      actions={<RefreshButton pending={query.isFetching} onRefresh={() => void query.refetch()} />}
    >
      <RecorderContent status={status} state={state} error={query.error} />
    </Panel>
  );
}
