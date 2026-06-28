import { useState } from "react";

import { useTriangularCaptureMutation } from "../../api/hooks";
import type {
  TriangularCapturePayload,
  TriangularCaptureResult,
  TriangularCaptureRow,
} from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { Field, Notice, Panel, Tag } from "../../ui/primitives";

const PRESET: TriangularCapturePayload = {
  thresholds: [1.0, 1.5, 2.0],
  horizons: [1, 3, 5, 10],
  window_days: 730,
  cost_bps_per_leg: 1.5,
};

interface Draft {
  readonly thresholds: string;
  readonly horizons: string;
  readonly windowDays: number;
  readonly costBpsPerLeg: number;
}

function text(values: readonly number[]): string {
  return values.join(", ");
}

function parseNumberList(raw: string): number[] {
  return raw
    .split(/[\n,]/)
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value));
}

function draftFromPreset(payload: TriangularCapturePayload): Draft {
  return {
    thresholds: text(payload.thresholds),
    horizons: text(payload.horizons),
    windowDays: payload.window_days,
    costBpsPerLeg: payload.cost_bps_per_leg,
  };
}

function buildPayload(draft: Draft): TriangularCapturePayload {
  return {
    thresholds: parseNumberList(draft.thresholds),
    horizons: parseNumberList(draft.horizons),
    window_days: draft.windowDays,
    cost_bps_per_leg: draft.costBpsPerLeg,
  };
}

function TriangularWarnings({ result }: { readonly result: TriangularCaptureResult }) {
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

function CaptureRow({ row }: { readonly row: TriangularCaptureRow }) {
  const tone = valueTone(row.stats.mean_net_bps);
  return (
    <tr>
      <td className="cell-strong">{row.construction}</td>
      <td className="num">{row.threshold}</td>
      <td className="num">{row.horizon}d</td>
      <td className="num">{row.leg_count}</td>
      <td className="num">{row.stats.count}</td>
      <td className="num">{fmtPct(row.stats.hit_rate)}</td>
      <td className="num">{fmtNum(row.stats.mean_gross_bps, 2)}</td>
      <td className={`num ${tone === "down" ? "neg" : ""}`}>
        <Tag tone={tone === "up" ? "up" : "muted"}>{fmtNum(row.stats.mean_net_bps, 2)}</Tag>
      </td>
      <td className="num">{fmtNum(row.stats.t_stat, 2)}</td>
      <td className="num">{fmtNum(row.stats.first_half_mean_net_bps, 2)}</td>
      <td className="num">{fmtNum(row.stats.second_half_mean_net_bps, 2)}</td>
    </tr>
  );
}

function CaptureTable({ result }: { readonly result: TriangularCaptureResult }) {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Construction</th>
            <th className="num">Z</th>
            <th className="num">Hold</th>
            <th className="num">Legs</th>
            <th className="num">Obs</th>
            <th className="num">Hit</th>
            <th className="num">Gross bps</th>
            <th className="num">Net bps</th>
            <th className="num">t</th>
            <th className="num">1H net</th>
            <th className="num">2H net</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <CaptureRow key={`${row.construction}-${row.threshold}-${row.horizon}`} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Fields({
  draft,
  onChange,
}: {
  readonly draft: Draft;
  readonly onChange: (d: Draft) => void;
}) {
  return (
    <div className="fieldset">
      <Field label="Z thresholds">
        <input
          className="input"
          value={draft.thresholds}
          onChange={(event) => onChange({ ...draft, thresholds: event.target.value })}
        />
      </Field>
      <Field label="Holding days">
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
      <Field label="Cost bps / leg">
        <input
          className="input"
          type="number"
          step="0.1"
          min={0}
          value={draft.costBpsPerLeg}
          onChange={(event) => onChange({ ...draft, costBpsPerLeg: Number(event.target.value) })}
        />
      </Field>
    </div>
  );
}

export function TriangularCapture() {
  const capture = useTriangularCaptureMutation();
  const [draft, setDraft] = useState<Draft>(draftFromPreset(PRESET));
  const result = capture.data ?? null;
  return (
    <Panel
      title="Triangular capture"
      note="H101 residual convergence"
      label="Triangular capture"
      actions={
        <button
          type="button"
          className="btn btn--primary"
          disabled={capture.isPending}
          onClick={() => capture.mutate(buildPayload(draft))}
        >
          {capture.isPending ? "Capturing…" : "Run triangular capture"}
        </button>
      }
    >
      <p className="mute">
        Tests direct EUR_GBP and synthetic triangle convergence after configurable per-leg costs.
      </p>
      <Fields draft={draft} onChange={setDraft} />
      {capture.error ? <Notice tone="error">{capture.error.message}</Notice> : null}
      {result ? (
        <>
          <TriangularWarnings result={result} />
          <p className="mute">Cost: {result.cost_bps_per_leg} bps per leg.</p>
          <CaptureTable result={result} />
        </>
      ) : null}
    </Panel>
  );
}
