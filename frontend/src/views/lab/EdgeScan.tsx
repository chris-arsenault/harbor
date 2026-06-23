import { useEdgeScanMutation } from "../../api/hooks";
import type { EdgeScanResult, EdgeScanRow } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Notice, Panel, Tag } from "../../ui/primitives";

function tStatTone(raw: string): "up" | "warn" | "muted" {
  const value = Number(raw);
  if (value >= 2) {
    return "up";
  }
  return value >= 1 ? "warn" : "muted";
}

function ScanRow({ row, rank }: { readonly row: EdgeScanRow; readonly rank: number }) {
  const best = row.best_conditional;
  return (
    <tr>
      <td className="num mute">{rank}</td>
      <td className="cell-strong">{row.instrument}</td>
      <td className="num">{row.horizon}m</td>
      <td className="num">{row.total_sweeps}</td>
      <td className="num">{fmtPct(row.overall.hit_rate)}</td>
      <td className={`num ${valueTone(row.overall.mean_pips) === "down" ? "neg" : ""}`}>
        {fmtNum(row.overall.mean_pips, 1)}p
      </td>
      <td className="num">
        <Tag tone={tStatTone(row.overall.t_stat)}>{fmtNum(row.overall.t_stat, 2)}</Tag>
      </td>
      <td>
        <Tag tone={row.has_edge ? "up" : "muted"}>{row.has_edge ? "edge" : "—"}</Tag>
      </td>
      <td className="mute">{best ? `${best.dimension}:${best.value}` : "—"}</td>
    </tr>
  );
}

function ScanTable({ result }: { readonly result: EdgeScanResult }) {
  if (result.results.length === 0) {
    return (
      <EmptyState
        glyph="∅"
        title="No data"
        hint="Import candles for the research universe first."
      />
    );
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Instrument</th>
            <th className="num">Horizon</th>
            <th className="num">Sweeps</th>
            <th className="num">Hit</th>
            <th className="num">Mean</th>
            <th className="num">t-stat</th>
            <th>Edge</th>
            <th>Best slice</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row, index) => (
            <ScanRow key={`${row.instrument}-${row.horizon}`} row={row} rank={index + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScanSummary({ result }: { readonly result: EdgeScanResult }) {
  const withEdge = result.results.filter((r) => r.has_edge);
  const total = result.results.length;
  return (
    <p className="mute">
      {result.instruments.length} instruments × {result.horizons.length} horizons = {total} combos
      scanned.{" "}
      {withEdge.length > 0 ? `${withEdge.length} show a statistical edge.` : "No edges found."}
    </p>
  );
}

export function EdgeScan() {
  const scan = useEdgeScanMutation();
  const result = scan.data;
  return (
    <Panel
      title="Edge scan"
      note="universe × horizons"
      label="Edge scan"
      actions={
        <button
          type="button"
          className="btn btn--primary"
          disabled={scan.isPending}
          onClick={() => scan.mutate({})}
        >
          {scan.isPending ? "Scanning…" : "Scan universe"}
        </button>
      }
    >
      {scan.error ? <Notice tone="error">{scan.error.message}</Notice> : null}
      {result ? (
        <>
          <ScanSummary result={result} />
          <ScanTable result={result} />
        </>
      ) : (
        <p className="mute">
          Scans all research instruments at 15m, 30m, 60m, and 120m horizons. Ranked by t-statistic.
        </p>
      )}
    </Panel>
  );
}
