import { useState } from "react";

import { useDirectionScanMutation } from "../../api/hooks";
import type { DirectionRow, DirectionScanPayload, DirectionScanResult } from "../../api/research";
import { fmtNum } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

const PRESET: DirectionScanPayload = {
  instruments: null,
  algorithms: [
    "weekend_risk_gap_probe",
    "regime_resurrection_probe",
    "range_forecast_probe",
    "book_conditioner_readiness",
    "lead_lag_network_probe",
  ],
  window_days: 730,
};

interface Draft {
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

function draftFromPreset(payload: DirectionScanPayload): Draft {
  return {
    instruments: listText(payload.instruments),
    algorithms: listText(payload.algorithms),
    windowDays: payload.window_days,
  };
}

function buildPayload(draft: Draft): DirectionScanPayload {
  return {
    instruments: parseStringList(draft.instruments),
    algorithms: parseStringList(draft.algorithms),
    window_days: draft.windowDays,
  };
}

function statusTone(status: string): "up" | "warn" | "info" | "muted" {
  if (status === "candidate" || status === "ready") return "up";
  if (status === "collecting") return "info";
  if (status === "data_required") return "warn";
  return "muted";
}

function DirectionWarnings({ result }: { readonly result: DirectionScanResult }) {
  if (!result.warnings.length) return null;
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

function DirectionTable({ result }: { readonly result: DirectionScanResult }) {
  if (!result.results.length) {
    return <EmptyState glyph="∅" title="No direction rows" />;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Hypothesis</th>
            <th>Direction</th>
            <th>Status</th>
            <th>Subject</th>
            <th>Metric</th>
            <th className="num">N</th>
            <th className="num">Effect</th>
            <th className="num">Secondary</th>
            <th className="num">t</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <DirectionTableRow key={`${row.algorithm_id}-${row.subject}`} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DirectionTableRow({ row }: { readonly row: DirectionRow }) {
  return (
    <tr>
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.label}</td>
      <td>
        <Tag tone={statusTone(row.status)}>{row.status}</Tag>
      </td>
      <td className="cell-strong">{row.subject}</td>
      <td className="mute">{row.metric}</td>
      <td className="num">{row.stats.count}</td>
      <td className="num">
        {fmtNum(row.stats.effect, row.unit === "snapshots" ? 0 : 4)} {row.unit}
      </td>
      <td className="num">{fmtNum(row.stats.secondary, 4)}</td>
      <td className="num">{fmtNum(row.stats.t_stat, 2)}</td>
      <td className="mute">{row.details}</td>
    </tr>
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
      <Field label="Instruments">
        <input
          className="input"
          value={draft.instruments}
          placeholder="blank = FX universe + known risk proxies"
          onChange={(event) => onChange({ ...draft, instruments: event.target.value })}
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

export function ResearchDirections() {
  const scan = useDirectionScanMutation();
  const [draft, setDraft] = useState<Draft>(draftFromPreset(PRESET));
  const result = scan.data ?? null;
  return (
    <Panel
      title="Research directions"
      note="H108–H112"
      label="Research directions"
      actions={
        <div className="row">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={scan.isPending}
            onClick={() => setDraft(draftFromPreset(PRESET))}
          >
            H108–H112 preset
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={scan.isPending}
            onClick={() => scan.mutate(buildPayload(draft))}
          >
            {scan.isPending ? "Scanning…" : "Run direction scan"}
          </button>
        </div>
      }
    >
      <p className="mute">
        Tests research directions that change the information source, target variable, or level of
        analysis rather than adding another single-pair price pattern.
      </p>
      <Fields draft={draft} onChange={setDraft} />
      {scan.error ? <Notice tone="error">{scan.error.message}</Notice> : null}
      {result ? (
        <>
          <DirectionWarnings result={result} />
          <DirectionTable result={result} />
        </>
      ) : null}
    </Panel>
  );
}
