import { useState } from "react";

import { useCrossScanMutation } from "../../api/hooks";
import type { CrossScanPayload, CrossScanResult, CrossScanRow } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

const CROSS_PRESET: CrossScanPayload = {
  instruments: null,
  algorithms: [
    "cs_momentum_20d_5d",
    "cs_value_60d_5d",
    "tri_eur_gbp_residual_5d",
    "usd_dispersion_reversion_5d",
  ],
  window_days: 730,
};

interface CrossDraft {
  readonly instruments: string;
  readonly algorithms: string;
  readonly windowDays: number;
}

function listText(values: readonly string[] | null): string {
  return values?.join(", ") ?? "";
}

function parseStringList(raw: string): string[] | null {
  const values = raw
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return values.length ? values : null;
}

function draftFromPreset(payload: CrossScanPayload): CrossDraft {
  return {
    instruments: listText(payload.instruments),
    algorithms: listText(payload.algorithms),
    windowDays: payload.window_days,
  };
}

function buildPayload(draft: CrossDraft): CrossScanPayload {
  return {
    instruments: parseStringList(draft.instruments),
    algorithms: parseStringList(draft.algorithms),
    window_days: draft.windowDays,
  };
}

function CrossWarnings({ result }: { readonly result: CrossScanResult }) {
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

function CrossTable({ result }: { readonly result: CrossScanResult }) {
  if (!result.results.length) {
    return <EmptyState glyph="∅" title="No cross-instrument rows" />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Hypothesis</th>
            <th>Algorithm</th>
            <th className="num">Obs</th>
            <th className="num">Hit</th>
            <th className="num">Mean bps</th>
            <th className="num">Median bps</th>
            <th className="num">Total bps</th>
            <th className="num">t-stat</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <CrossRow key={row.algorithm_id} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CrossRow({ row }: { readonly row: CrossScanRow }) {
  const tone = valueTone(row.stats.mean_return_bps);
  return (
    <tr>
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.algorithm_label}</td>
      <td className="num">{row.observation_count}</td>
      <td className="num">{fmtPct(row.stats.hit_rate)}</td>
      <td className={`num ${tone === "down" ? "neg" : ""}`}>
        <Tag tone={tone === "up" ? "up" : "muted"}>{fmtNum(row.stats.mean_return_bps, 2)}</Tag>
      </td>
      <td className="num">{fmtNum(row.stats.median_return_bps, 2)}</td>
      <td className="num">{fmtNum(row.stats.total_return_bps, 1)}</td>
      <td className="num">{fmtNum(row.stats.t_stat, 2)}</td>
    </tr>
  );
}

function CrossFields({
  draft,
  onChange,
}: {
  readonly draft: CrossDraft;
  readonly onChange: (draft: CrossDraft) => void;
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
    </div>
  );
}

export function CrossInstrument() {
  const cross = useCrossScanMutation();
  const [draft, setDraft] = useState<CrossDraft>(draftFromPreset(CROSS_PRESET));
  const result = cross.data ?? null;
  return (
    <Panel
      title="Cross-instrument research"
      note="factor and relative-value tests"
      label="Cross-instrument research"
      actions={
        <div className="row">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={cross.isPending}
            onClick={() => setDraft(draftFromPreset(CROSS_PRESET))}
          >
            H100–H102 preset
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={cross.isPending}
            onClick={() => cross.mutate(buildPayload(draft))}
          >
            {cross.isPending ? "Scanning…" : "Run cross scan"}
          </button>
        </div>
      }
    >
      <p className="mute">
        Tests daily cross-sectional factor baskets and relative-value residuals. Returns are basket
        basis points, not pips.
      </p>
      <CrossFields draft={draft} onChange={setDraft} />
      {cross.error ? <Notice tone="error">{cross.error.message}</Notice> : null}
      {result ? (
        <>
          <CrossWarnings result={result} />
          <CrossTable result={result} />
        </>
      ) : null}
    </Panel>
  );
}
