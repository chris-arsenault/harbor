import { useState } from "react";

import type { CandleSyncResult } from "../api/candles";
import { useCandleSourceQuery, useCandleSyncMutation } from "../api/hooks";
import type { CandleCoverage, CandleSourceStatus } from "../api/types";
import { fmtDateTime, fmtInt } from "../ui/format";
import { EmptyState, Field, Notice, Panel, StatTile, Tag, ViewHead } from "../ui/primitives";

type Tone = "up" | "warn" | "muted";

interface Badge {
  readonly label: string;
  readonly tone: Tone;
}

type SyncMutation = ReturnType<typeof useCandleSyncMutation>;

function freshness(to: string | null): Badge {
  if (!to) {
    return { label: "no data", tone: "muted" };
  }
  const days = (Date.now() - Date.parse(to)) / 86_400_000;
  if (!Number.isFinite(days)) {
    return { label: "no data", tone: "muted" };
  }
  if (days <= 2) {
    return { label: "current", tone: "up" };
  }
  return { label: `${Math.floor(days)}d behind`, tone: "warn" };
}

function quality(coverage: CandleCoverage): Badge {
  if (!coverage.candle_count) {
    return { label: "—", tone: "muted" };
  }
  const pct = ((coverage.bid_ask_count ?? 0) / coverage.candle_count) * 100;
  let tone: Tone = "muted";
  if (pct >= 99) {
    tone = "up";
  } else if (pct > 0) {
    tone = "warn";
  }
  return { label: `${pct.toFixed(0)}%`, tone };
}

function universeCoverages(status: CandleSourceStatus | undefined): CandleCoverage[] {
  if (!status) {
    return [];
  }
  return status.instrument_coverages?.length ? status.instrument_coverages : [status.coverage];
}

function SourceConfig({ status }: { readonly status: CandleSourceStatus }) {
  const ready = status.oanda_historical_import_configured;
  return (
    <div className="tiles">
      <StatTile label="Granularity" value={status.granularity} />
      <StatTile label="Price" value={status.price_component} tone="beam" />
      <StatTile label="Page size" value={fmtInt(status.historical_import.page_size)} />
      <StatTile
        label="OANDA import"
        value={ready ? "ready" : "unconfigured"}
        tone={ready ? "up" : "warn"}
      />
    </div>
  );
}

function CoverageRow({
  coverage,
  pending,
  onSync,
}: {
  readonly coverage: CandleCoverage;
  readonly pending: boolean;
  readonly onSync: (instrument: string, repair: boolean) => void;
}) {
  const fresh = freshness(coverage.to);
  const dataQuality = quality(coverage);
  const incomplete =
    coverage.candle_count > 0 && (coverage.bid_ask_count ?? 0) < coverage.candle_count;
  return (
    <tr>
      <td className="cell-strong">{coverage.instrument}</td>
      <td className="num">{fmtInt(coverage.candle_count)}</td>
      <td>
        <Tag tone={dataQuality.tone}>bid/ask {dataQuality.label}</Tag>
      </td>
      <td className="mute">{coverage.from ? coverage.from.slice(0, 10) : "—"}</td>
      <td className="mute">{coverage.to ? coverage.to.slice(0, 16).replace("T", " ") : "—"}</td>
      <td>
        <Tag tone={fresh.tone}>{fresh.label}</Tag>
      </td>
      <td>
        <button
          type="button"
          className={incomplete ? "btn btn--sm btn--primary" : "btn btn--sm"}
          disabled={pending}
          onClick={() => onSync(coverage.instrument, incomplete)}
          title={incomplete ? "Re-fetch to backfill bid/ask data" : "Fetch missing candles"}
        >
          {incomplete ? "Repair" : "Sync"}
        </button>
      </td>
    </tr>
  );
}

function CoverageTable({
  coverages,
  pending,
  onSync,
}: {
  readonly coverages: CandleCoverage[];
  readonly pending: boolean;
  readonly onSync: (instrument: string, repair: boolean) => void;
}) {
  if (coverages.length === 0) {
    return <EmptyState glyph="⛁" title="No instruments" hint="Configure the research universe." />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Instrument</th>
            <th className="num">Candles</th>
            <th>Data quality</th>
            <th>From</th>
            <th>To (UTC)</th>
            <th>Freshness</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {coverages.map((coverage) => (
            <CoverageRow
              key={coverage.instrument}
              coverage={coverage}
              pending={pending}
              onSync={onSync}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SyncControls({
  days,
  onDaysChange,
  ready,
  sync,
}: {
  readonly days: number;
  readonly onDaysChange: (days: number) => void;
  readonly ready: boolean;
  readonly sync: SyncMutation;
}) {
  return (
    <div className="row">
      <Field label="Window (days)">
        <input
          className="input"
          type="number"
          min={1}
          value={days}
          onChange={(event) => onDaysChange(Number(event.target.value) || 1)}
        />
      </Field>
      <button
        type="button"
        className="btn btn--primary"
        disabled={sync.isPending || !ready}
        onClick={() => sync.mutate({ days })}
      >
        {sync.isPending ? "Syncing…" : "Sync universe"}
      </button>
      <button
        type="button"
        className="btn btn--ghost"
        disabled={sync.isPending || !ready}
        title="Re-fetch covered ranges to backfill bid/ask on instruments that lack it"
        onClick={() => sync.mutate({ days, repair: true })}
      >
        Repair bid/ask
      </button>
    </div>
  );
}

function SyncResults({ result }: { readonly result: CandleSyncResult }) {
  const total = result.reports.reduce((sum, report) => sum + report.imported, 0);
  return (
    <Notice tone="ok">
      Synced {result.reports.length} instruments over {result.days}d — {fmtInt(total)} new candles
      sourced. Latest: {fmtDateTime(result.reports[0]?.to ?? null)}.
    </Notice>
  );
}

export function DataImportView() {
  const source = useCandleSourceQuery();
  const sync = useCandleSyncMutation();
  const [days, setDays] = useState(180);
  const status = source.data;
  const coverages = universeCoverages(status);
  const ready = status?.oanda_historical_import_configured ?? false;

  return (
    <section className="view" aria-label="Data">
      <ViewHead
        kicker="Research"
        title="Data"
        sub="Source real OANDA bid/ask candles. Sync fetches only the missing gaps."
        actions={<SyncControls days={days} onDaysChange={setDays} ready={ready} sync={sync} />}
      />
      {status ? <SourceConfig status={status} /> : null}
      {status && !ready ? (
        <Notice tone="error">
          OANDA practice credentials are not configured — set OANDA_API_TOKEN and OANDA_ACCOUNT_ID
          (run the API via the credential broker) before sourcing data.
        </Notice>
      ) : null}
      <Panel
        title="Universe coverage"
        note={`${coverages.length} instruments`}
        label="Universe coverage"
      >
        <CoverageTable
          coverages={coverages}
          pending={sync.isPending}
          onSync={(instrument, repair) => sync.mutate({ instrument, days, repair })}
        />
      </Panel>
      {sync.error ? <Notice tone="error">{sync.error.message}</Notice> : null}
      {sync.data ? <SyncResults result={sync.data} /> : null}
    </section>
  );
}
