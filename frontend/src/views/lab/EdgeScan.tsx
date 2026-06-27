import { useState } from "react";

import { useEdgeScanMutation } from "../../api/hooks";
import type { EdgeScanPayload, EdgeScanResult, EdgeScanRow } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

interface EdgeScanPreset {
  readonly instruments: string[];
  readonly algorithms: string[];
  readonly horizons: number[];
  readonly window_days: number;
}

interface EdgeScanDraft {
  readonly instruments: string;
  readonly algorithms: string;
  readonly horizons: string;
  readonly windowDays: number;
}

const EDGE_SCAN_PRESETS = {
  h005: {
    instruments: ["GBP_JPY"],
    algorithms: ["clean_level_sweep_reversal"],
    horizons: [15, 30, 60],
    window_days: 730,
  },
  h007: {
    instruments: ["EUR_USD"],
    algorithms: [
      "generic_sweep_continuation",
      "mss_confirmed_sweep_continuation",
      "early_ny_sweep_continuation",
    ],
    horizons: [15, 30, 60, 120],
    window_days: 730,
  },
} as const satisfies Record<string, EdgeScanPreset>;

function listText(values: readonly (string | number)[]): string {
  return values.join(", ");
}

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

function buildPayload(draft: EdgeScanDraft): EdgeScanPayload {
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
            <ScanRow
              key={`${row.hypothesis_id}-${row.algorithm_id}-${row.instrument}-${row.horizon}`}
              row={row}
              rank={index + 1}
            />
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

function ScanWarnings({ result }: { readonly result: EdgeScanResult }) {
  const warnings = result.warnings ?? [];
  if (!warnings.length) {
    return null;
  }
  return (
    <Notice>
      <div className="stack stack--tight">
        <strong>Data window warnings</strong>
        {warnings.map((warning) => (
          <span key={`${warning.instrument}-${warning.type}-${warning.message}`}>
            {warning.instrument}: {warning.message}
          </span>
        ))}
      </div>
    </Notice>
  );
}

function ScanActions({
  pending,
  onPreset,
  onSubmit,
}: {
  readonly pending: boolean;
  readonly onPreset: (preset: EdgeScanPreset) => void;
  readonly onSubmit: () => void;
}) {
  return (
    <div className="row">
      <button
        type="button"
        className="btn btn--ghost btn--sm"
        disabled={pending}
        onClick={() => onPreset(EDGE_SCAN_PRESETS.h005)}
      >
        H005 GBP_JPY confirmatory
      </button>
      <button
        type="button"
        className="btn btn--ghost btn--sm"
        disabled={pending}
        onClick={() => onPreset(EDGE_SCAN_PRESETS.h007)}
      >
        H007 EUR_USD continuation
      </button>
      <button type="button" className="btn btn--primary" disabled={pending} onClick={onSubmit}>
        {pending ? "Scanning…" : "Run edge scan"}
      </button>
    </div>
  );
}

function ScanFields({
  draft,
  onChange,
}: {
  readonly draft: EdgeScanDraft;
  readonly onChange: (draft: EdgeScanDraft) => void;
}) {
  return (
    <div className="fieldset">
      <Field label="Instruments">
        <input
          className="input"
          value={draft.instruments}
          onChange={(event) => onChange({ ...draft, instruments: event.target.value })}
          placeholder="GBP_JPY, EUR_USD"
        />
      </Field>
      <Field label="Algorithms">
        <input
          className="input"
          value={draft.algorithms}
          onChange={(event) => onChange({ ...draft, algorithms: event.target.value })}
          placeholder="generic_sweep_continuation"
        />
      </Field>
      <Field label="Horizons">
        <input
          className="input"
          value={draft.horizons}
          onChange={(event) => onChange({ ...draft, horizons: event.target.value })}
          placeholder="15, 30, 60"
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

function ScanResultView({
  result,
  error,
}: {
  readonly result: EdgeScanResult | null;
  readonly error: Error | null;
}) {
  return (
    <>
      {error ? <Notice tone="error">{error.message}</Notice> : null}
      {result ? (
        <>
          <ScanWarnings result={result} />
          <ScanSummary result={result} />
          <ScanTable result={result} />
        </>
      ) : (
        <p className="mute">
          Scan results are ranked by corrected t-statistic with trading-day clustering and
          multiple-test-adjusted p-values.
        </p>
      )}
    </>
  );
}

export function EdgeScan() {
  const scan = useEdgeScanMutation();
  const [draft, setDraft] = useState<EdgeScanDraft>({
    instruments: "",
    algorithms: "",
    horizons: "",
    windowDays: 730,
  });

  function applyPreset(preset: EdgeScanPreset) {
    setDraft({
      instruments: listText(preset.instruments),
      algorithms: listText(preset.algorithms),
      horizons: listText(preset.horizons),
      windowDays: preset.window_days,
    });
  }

  function submit() {
    scan.mutate(buildPayload(draft));
  }

  return (
    <Panel
      title="Edge scan"
      note="universe × horizons"
      label="Edge scan"
      actions={<ScanActions pending={scan.isPending} onPreset={applyPreset} onSubmit={submit} />}
    >
      <ScanFields draft={draft} onChange={setDraft} />
      <ScanResultView result={scan.data ?? null} error={scan.error ?? null} />
    </Panel>
  );
}
