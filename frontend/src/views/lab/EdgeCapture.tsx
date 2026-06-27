import { useState } from "react";

import { useCaptureScanMutation } from "../../api/hooks";
import type { CapturePayload, CaptureResult, CaptureRow } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

const H007_CAPTURE_PRESET: CapturePayload = {
  instrument: "EUR_USD",
  algorithms: [
    "generic_sweep_continuation",
    "mss_confirmed_sweep_continuation",
    "early_ny_sweep_continuation",
  ],
  horizons: [15, 30, 60],
  window_days: 730,
  spread_pips: "0.8",
  slippage_pips: "0.1",
};

interface CaptureDraft {
  readonly instrument: string;
  readonly algorithms: string;
  readonly horizons: string;
  readonly windowDays: number;
  readonly spreadPips: string;
  readonly slippagePips: string;
}

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
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
}

function draftFromPreset(preset: CapturePayload): CaptureDraft {
  return {
    instrument: preset.instrument,
    algorithms: listText(preset.algorithms),
    horizons: listText(preset.horizons),
    windowDays: preset.window_days,
    spreadPips: preset.spread_pips,
    slippagePips: preset.slippage_pips,
  };
}

function buildPayload(draft: CaptureDraft): CapturePayload {
  return {
    instrument: draft.instrument.trim().toUpperCase() || "EUR_USD",
    algorithms: parseStringList(draft.algorithms),
    horizons: parseNumberList(draft.horizons),
    window_days: draft.windowDays,
    spread_pips: draft.spreadPips,
    slippage_pips: draft.slippagePips,
  };
}

function CaptureWarnings({ result }: { readonly result: CaptureResult }) {
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

function CaptureTable({ result }: { readonly result: CaptureResult }) {
  if (!result.results.length) {
    return <EmptyState glyph="∅" title="No capture rows" hint="Import candles first." />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Hypothesis</th>
            <th>Algorithm</th>
            <th className="num">Horizon</th>
            <th className="num">Events</th>
            <th className="num">Captured</th>
            <th className="num">Hit</th>
            <th className="num">Gross</th>
            <th className="num">Net</th>
            <th className="num">Total net</th>
            <th className="num">MFE</th>
            <th className="num">MAE</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <CaptureTableRow key={`${row.algorithm_id}-${row.horizon}`} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaptureTableRow({ row }: { readonly row: CaptureRow }) {
  const netTone = valueTone(row.stats.mean_net_pips);
  return (
    <tr>
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.algorithm_label}</td>
      <td className="num">{row.horizon}m</td>
      <td className="num">{row.event_count}</td>
      <td className="num">{row.stats.count}</td>
      <td className="num">{fmtPct(row.stats.hit_rate)}</td>
      <td className="num">{fmtNum(row.stats.mean_gross_pips, 2)}p</td>
      <td className={`num ${netTone === "down" ? "neg" : ""}`}>
        <Tag tone={netTone === "up" ? "up" : "muted"}>{fmtNum(row.stats.mean_net_pips, 2)}p</Tag>
      </td>
      <td className="num">{fmtNum(row.stats.total_net_pips, 1)}p</td>
      <td className="num">{fmtNum(row.stats.average_mfe_pips, 1)}p</td>
      <td className="num">{fmtNum(row.stats.average_mae_pips, 1)}p</td>
    </tr>
  );
}

function CaptureFields({
  draft,
  onChange,
}: {
  readonly draft: CaptureDraft;
  readonly onChange: (draft: CaptureDraft) => void;
}) {
  return (
    <div className="fieldset">
      <Field label="Instrument">
        <input
          className="input"
          value={draft.instrument}
          onChange={(event) => onChange({ ...draft, instrument: event.target.value })}
        />
      </Field>
      <Field label="Algorithms">
        <input
          className="input"
          value={draft.algorithms}
          onChange={(event) => onChange({ ...draft, algorithms: event.target.value })}
        />
      </Field>
      <Field label="Horizons">
        <input
          className="input"
          value={draft.horizons}
          onChange={(event) => onChange({ ...draft, horizons: event.target.value })}
        />
      </Field>
      <Field label="Window days">
        <input
          className="input"
          type="number"
          min={1}
          value={draft.windowDays}
          onChange={(event) =>
            onChange({ ...draft, windowDays: Math.max(1, Number(event.target.value) || 1) })
          }
        />
      </Field>
      <Field label="Spread pips">
        <input
          className="input"
          value={draft.spreadPips}
          onChange={(event) => onChange({ ...draft, spreadPips: event.target.value })}
        />
      </Field>
      <Field label="Slippage pips">
        <input
          className="input"
          value={draft.slippagePips}
          onChange={(event) => onChange({ ...draft, slippagePips: event.target.value })}
        />
      </Field>
    </div>
  );
}

export function EdgeCapture() {
  const capture = useCaptureScanMutation();
  const [draft, setDraft] = useState<CaptureDraft>(draftFromPreset(H007_CAPTURE_PRESET));
  const result = capture.data ?? null;
  return (
    <Panel
      title="Event capture"
      note="cost-aware fixed horizon"
      label="Event capture"
      actions={
        <div className="row">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={capture.isPending}
            onClick={() => setDraft(draftFromPreset(H007_CAPTURE_PRESET))}
          >
            H007 EUR_USD capture
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={capture.isPending}
            onClick={() => capture.mutate(buildPayload(draft))}
          >
            {capture.isPending ? "Capturing…" : "Run capture test"}
          </button>
        </div>
      }
    >
      <p className="mute">
        Tests whether edge-scan events are capturable after spread and slippage. Entry is next M1
        open; exit is fixed-horizon close.
      </p>
      <CaptureFields draft={draft} onChange={setDraft} />
      {capture.error ? <Notice tone="error">{capture.error.message}</Notice> : null}
      {result ? (
        <>
          <CaptureWarnings result={result} />
          <p className="mute">
            Costs: {result.spread_pips}p spread + {result.slippage_pips}p slippage per side.
          </p>
          <CaptureTable result={result} />
        </>
      ) : null}
    </Panel>
  );
}
