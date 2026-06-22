import { useMemo, useState } from "react";

import type { TradeJournalItem } from "../api/types";
import { byText } from "../ui/cx";
import { fmtDate, fmtNum, fmtPct, fmtR, fmtSigned, valueTone } from "../ui/format";
import { Field, Meter, Panel, StatTile, ViewHead } from "../ui/primitives";
import { AreaCurve, ScoreGauge } from "../ui/viz";
import { journalStats, type JournalStats } from "./journal/model";
import { TradeDetail, TradeTable } from "./journal/TradeTable";

const ALL = "all";

function uniqueValues(values: readonly string[]): string[] {
  return [...new Set(values)].sort(byText);
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  readonly label: string;
  readonly value: string;
  readonly options: readonly string[];
  readonly onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <select className="select" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value={ALL}>All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Field>
  );
}

function HealthPanel({ stats }: { readonly stats: JournalStats }) {
  return (
    <Panel title="Trading health" note="composite 0–100" label="Trading health">
      <div className="gauge">
        <ScoreGauge score={stats.score} caption="HARBOR SCORE" />
        <div className="gauge__legend">
          {stats.components.map((component) => (
            <div className="gauge__row" key={component.label}>
              <span className="mute">{component.label}</span>
              <Meter ratio={component.ratio} />
              <span className="num">{component.display}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function EquityPanel({ stats }: { readonly stats: JournalStats }) {
  const points = useMemo(() => stats.equity.map((v) => ({ v })), [stats.equity]);
  const tone = stats.netPnl >= 0 ? "up" : "down";
  return (
    <Panel title="Cumulative P&L" note={`${stats.closed} closed`} label="Cumulative P&L">
      <AreaCurve points={points} ariaLabel="Cumulative realised P&L" tone={tone} height={150} />
    </Panel>
  );
}

export function JournalView({
  trades,
  from,
  to,
}: {
  readonly trades: readonly TradeJournalItem[];
  readonly from: string;
  readonly to: string;
}) {
  const [instrument, setInstrument] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const filtered = useMemo(
    () =>
      trades.filter(
        (trade) =>
          (instrument === ALL || trade.instrument === instrument) &&
          (statusFilter === ALL || trade.signal_status === statusFilter)
      ),
    [trades, instrument, statusFilter]
  );
  const stats = useMemo(() => journalStats(filtered), [filtered]);
  const selected = filtered.find((trade) => trade.id === selectedId) ?? null;
  const filters = (
    <div className="row">
      <SelectFilter
        label="Instrument"
        value={instrument}
        options={uniqueValues(trades.map((trade) => trade.instrument))}
        onChange={setInstrument}
      />
      <SelectFilter
        label="Status"
        value={statusFilter}
        options={uniqueValues(trades.map((trade) => trade.signal_status))}
        onChange={setStatusFilter}
      />
    </div>
  );

  return (
    <section className="view" aria-label="Journal">
      <ViewHead
        kicker="Monitor"
        title="Journal"
        sub={`Realised trade ledger · ${fmtDate(from)} → ${fmtDate(to)}`}
      />
      <div className="duo">
        <HealthPanel stats={stats} />
        <EquityPanel stats={stats} />
      </div>
      <JournalTiles stats={stats} />
      <Panel title="Trades" actions={filters}>
        <div className="split">
          <TradeTable trades={filtered} selectedId={selectedId} onSelect={setSelectedId} />
          <TradeDetail trade={selected} />
        </div>
      </Panel>
    </section>
  );
}

function JournalTiles({ stats }: { readonly stats: JournalStats }) {
  return (
    <div className="tiles">
      <StatTile label="Net P&L" value={fmtSigned(stats.netPnl)} tone={valueTone(stats.netPnl)} />
      <StatTile label="Trades" value={fmtNum(stats.total, 0)} sub={`${stats.closed} closed`} />
      <StatTile label="Win rate" value={fmtPct(stats.winRate)} tone="beam" />
      <StatTile label="Avg R" value={fmtR(stats.avgR)} tone={valueTone(stats.avgR)} />
      <StatTile
        label="Profit factor"
        value={stats.profitFactor === null ? "∞" : fmtNum(stats.profitFactor, 2)}
      />
      <StatTile label="Max drawdown" value={fmtNum(stats.maxDrawdown, 2)} tone="warn" />
    </div>
  );
}
