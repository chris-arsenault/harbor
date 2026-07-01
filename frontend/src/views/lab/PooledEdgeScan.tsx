import { useState } from "react";

import { usePooledEdgeScanMutation } from "../../api/hooks";
import type { EdgeScanPayload, EdgeScanRow, PooledEdgeScanResult } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

interface PooledScanDraft {
  readonly instruments: string;
  readonly algorithms: string;
  readonly horizons: string;
  readonly windowDays: number;
}

const DEFAULT_DRAFT: PooledScanDraft = {
  instruments: "",
  algorithms: "generic_sweep_reversal, multi_candle_sweep_reclaim_reversal",
  horizons: "15, 30, 60, 120",
  windowDays: 730,
};

function parseStringList(raw: string): string[] {
  return raw
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function parseNumberList(raw: string): number[] {
  return raw
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item));
}

function buildPayload(draft: PooledScanDraft): EdgeScanPayload {
  const instruments = parseStringList(draft.instruments);
  const algorithms = parseStringList(draft.algorithms);
  const horizons = parseNumberList(draft.horizons);
  return {
    window_days: draft.windowDays,
    instruments: instruments.length ? instruments : null,
    algorithms: algorithms.length ? algorithms : null,
    horizons: horizons.length ? horizons : null,
  };
}

function tStatTone(raw: string): "up" | "warn" | "muted" {
  const value = Number(raw);
  if (value >= 2) {
    return "up";
  }
  return value >= 1 ? "warn" : "muted";
}

function PooledRow({ row, rank }: { readonly row: EdgeScanRow; readonly rank: number }) {
  return (
    <tr>
      <td className="num mute">{rank}</td>
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.algorithm_label}</td>
      <td className="num">{row.horizon}m</td>
      <td className="num">{row.total_sweeps}</td>
      <td className="num">{row.overall.count}</td>
      <td className="num">{fmtPct(row.overall.hit_rate)}</td>
      <td className={`num ${valueTone(row.overall.mean_pips) === "down" ? "neg" : ""}`}>
        {fmtNum(row.overall.mean_pips, 3)}
      </td>
      <td className="num">
        <Tag tone={tStatTone(row.overall.t_stat)}>{fmtNum(row.overall.t_stat, 2)}</Tag>
      </td>
      <td className="num">{row.overall.effective_sample_size}</td>
      <td className="num">{fmtNum(row.overall.bh_q_value ?? "1", 4)}</td>
      <td>
        <Tag tone={row.has_edge ? "up" : "muted"}>{row.has_edge ? "edge" : "—"}</Tag>
      </td>
    </tr>
  );
}

function PooledTable({ result }: { readonly result: PooledEdgeScanResult }) {
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
            <th className="num">Horizon</th>
            <th className="num">Events</th>
            <th className="num">N</th>
            <th className="num">Hit</th>
            <th className="num">Mean (ATR)</th>
            <th className="num">Corrected t</th>
            <th className="num">Eff N</th>
            <th className="num">BH q</th>
            <th>Edge</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row, index) => (
            <PooledRow
              key={`${row.hypothesis_id}-${row.algorithm_id}-${row.horizon}`}
              row={row}
              rank={index + 1}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PooledSummary({ result }: { readonly result: PooledEdgeScanResult }) {
  const pooled = result.pooled_instruments.join(", ");
  const edgeCount = result.results.filter((row) => row.has_edge).length;
  const edgeText = edgeCount > 0 ? `${edgeCount} rows pass the FDR gate.` : "No edges found.";
  return (
    <p className="mute">
      Pooled {result.pooled_instruments.length} instruments ({pooled}) into one ATR-normalized panel
      per algorithm and horizon, clustered by NY trading day. {edgeText} Judge rows by the BH
      q-value; FDR survivors still need a confirmatory rerun.
    </p>
  );
}

function PooledWarnings({ result }: { readonly result: PooledEdgeScanResult }) {
  if (!result.warnings.length) {
    return null;
  }
  return (
    <Notice>
      <div className="stack stack--tight">
        <strong>Data window warnings</strong>
        {result.warnings.map((warning) => (
          <span key={`${warning.instrument}-${warning.type}-${warning.message}`}>
            {warning.instrument}: {warning.message}
          </span>
        ))}
      </div>
    </Notice>
  );
}

function PooledFields({
  draft,
  onChange,
}: {
  readonly draft: PooledScanDraft;
  readonly onChange: (draft: PooledScanDraft) => void;
}) {
  return (
    <div className="fieldset">
      <Field label="Instruments">
        <input
          className="input"
          value={draft.instruments}
          onChange={(event) => onChange({ ...draft, instruments: event.target.value })}
          placeholder="blank = research universe"
        />
      </Field>
      <Field label="Algorithms">
        <input
          className="input"
          value={draft.algorithms}
          onChange={(event) => onChange({ ...draft, algorithms: event.target.value })}
          placeholder="generic_sweep_reversal"
        />
      </Field>
      <Field label="Horizons">
        <input
          className="input"
          value={draft.horizons}
          onChange={(event) => onChange({ ...draft, horizons: event.target.value })}
          placeholder="15, 30, 60, 120"
        />
      </Field>
      <Field label="Window (days)">
        <input
          className="input"
          type="number"
          min={1}
          value={draft.windowDays}
          onChange={(event) =>
            onChange({
              ...draft,
              windowDays: Math.max(1, Number(event.target.value) || 1),
            })
          }
        />
      </Field>
    </div>
  );
}

function PooledResultView({
  result,
  error,
}: {
  readonly result: PooledEdgeScanResult | null;
  readonly error: Error | null;
}) {
  return (
    <>
      {error ? <Notice tone="error">{error.message}</Notice> : null}
      {result ? (
        <>
          <PooledWarnings result={result} />
          <PooledSummary result={result} />
          <PooledTable result={result} />
        </>
      ) : (
        <p className="mute">
          Per-instrument scans cannot resolve realistic 1–4 pip effects; pooling ATR-normalized
          sweep observations across the whole universe multiplies the sample. This is the
          decision-relevant test for the sweep families.
        </p>
      )}
    </>
  );
}

export function PooledEdgeScan() {
  const scan = usePooledEdgeScanMutation();
  const [draft, setDraft] = useState<PooledScanDraft>(DEFAULT_DRAFT);

  function submit() {
    scan.mutate(buildPayload(draft));
  }

  return (
    <Panel
      title="Pooled panel scan"
      note="ATR-normalized sweep events pooled across instruments"
      label="Pooled panel scan"
      actions={
        <button
          type="button"
          className="btn btn--primary"
          disabled={scan.isPending}
          onClick={submit}
        >
          {scan.isPending ? "Scanning…" : "Run pooled scan"}
        </button>
      }
    >
      <PooledFields draft={draft} onChange={setDraft} />
      <PooledResultView result={scan.data ?? null} error={scan.error ?? null} />
    </Panel>
  );
}
