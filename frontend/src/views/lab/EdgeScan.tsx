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
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.algorithm_label}</td>
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
      <td className="num">{fmtNum(row.overall.naive_t_stat, 2)}</td>
      <td className="num">{row.overall.effective_sample_size}</td>
      <td className="num">{fmtNum(row.overall.bonferroni_p_value, 4)}</td>
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
            <th>Hypothesis</th>
            <th>Algorithm</th>
            <th>Instrument</th>
            <th className="num">Horizon</th>
            <th className="num">Sweeps</th>
            <th className="num">Hit</th>
            <th className="num">Mean</th>
            <th className="num">Corrected t</th>
            <th className="num">Naive t</th>
            <th className="num">Eff N</th>
            <th className="num">p adj</th>
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

interface ScanCounts {
  readonly instrumentCount: number;
  readonly algorithmCount: number;
  readonly horizonCount: number;
  readonly plannedTests: number;
  readonly observedTests: number;
  readonly edgeCount: number;
}

function scanCounts(result: EdgeScanResult): ScanCounts {
  const notes = result.statistical_notes ?? {};
  const instrumentCount = notes.instrument_count ?? result.instruments.length;
  const algorithmCount = notes.algorithm_count ?? result.algorithms.length;
  const horizonCount = notes.horizon_count ?? result.horizons.length;
  const plannedTests =
    notes.planned_overall_test_count ?? instrumentCount * algorithmCount * horizonCount;
  const observedTests = notes.overall_test_count ?? result.results.length;
  const edgeCount = result.results.filter((r) => r.has_edge).length;
  return {
    instrumentCount,
    algorithmCount,
    horizonCount,
    plannedTests,
    observedTests,
    edgeCount,
  };
}

function ScanSummary({ result }: { readonly result: EdgeScanResult }) {
  const counts = scanCounts(result);
  const edgeText =
    counts.edgeCount > 0 ? `${counts.edgeCount} show a statistical edge.` : "No edges found.";
  return (
    <p className="mute">
      {counts.instrumentCount} instruments × {counts.algorithmCount} algorithms ×{" "}
      {counts.horizonCount} horizons = {counts.plannedTests} planned tests; {counts.observedTests}{" "}
      returned tests had data. {edgeText} Corrected t uses clustered trading-day standard errors;
      adjusted p uses Bonferroni across {counts.observedTests} observed overall tests.
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
          Scans all research instruments, all active hypothesis algorithms, and 15m/30m/60m/120m
          horizons. Ranked by corrected t-statistic with trading-day clustering and
          multiple-test-adjusted p-values.
        </p>
      )}
    </Panel>
  );
}
