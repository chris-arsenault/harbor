import { useState } from "react";

import { useCrossScanMutation } from "../../api/hooks";
import type { CrossScanPayload, CrossScanResult, CrossScanRow } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

const ACTIVE_CROSS_PRESET: CrossScanPayload = {
  instruments: null,
  algorithms: ["cs_reversal_20d_5d_tranched"],
  window_days: 730,
};

const ARCHIVED_CROSS_PRESET: CrossScanPayload = {
  instruments: null,
  algorithms: [
    "cs_momentum_20d_5d",
    "cs_value_60d_5d",
    "tri_eur_gbp_residual_5d",
    "usd_dispersion_reversion_5d",
  ],
  window_days: 730,
};

interface CrossPanelCopy {
  readonly title: string;
  readonly note: string;
  readonly label: string;
  readonly presetLabel: string;
  readonly runLabel: string;
  readonly pendingLabel: string;
  readonly intro: string;
  readonly emptyTitle: string;
}

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

function CrossTable({
  result,
  emptyTitle,
}: {
  readonly result: CrossScanResult;
  readonly emptyTitle: string;
}) {
  if (!result.results.length) {
    return <EmptyState glyph="∅" title={emptyTitle} />;
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

function CrossInstrumentPanel({
  preset,
  copy,
}: {
  readonly preset: CrossScanPayload;
  readonly copy: CrossPanelCopy;
}) {
  const cross = useCrossScanMutation();
  const [draft, setDraft] = useState<CrossDraft>(draftFromPreset(preset));
  const result = cross.data ?? null;
  return (
    <Panel
      title={copy.title}
      note={copy.note}
      label={copy.label}
      actions={
        <div className="row">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={cross.isPending}
            onClick={() => setDraft(draftFromPreset(preset))}
          >
            {copy.presetLabel}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={cross.isPending}
            onClick={() => cross.mutate(buildPayload(draft))}
          >
            {cross.isPending ? copy.pendingLabel : copy.runLabel}
          </button>
        </div>
      }
    >
      <p className="mute">{copy.intro}</p>
      <CrossFields draft={draft} onChange={setDraft} />
      {cross.error ? <Notice tone="error">{cross.error.message}</Notice> : null}
      {result ? (
        <>
          <CrossWarnings result={result} />
          <CrossTable result={result} emptyTitle={copy.emptyTitle} />
        </>
      ) : null}
    </Panel>
  );
}

export function CrossInstrument() {
  return (
    <CrossInstrumentPanel
      preset={ACTIVE_CROSS_PRESET}
      copy={{
        title: "Cross-instrument research",
        note: "H113 tranched cross-sectional reversal",
        label: "Cross-instrument research",
        presetLabel: "H113 reversal preset",
        runLabel: "Run cross scan",
        pendingLabel: "Scanning…",
        intro:
          "H113: long recent 20-day losers, short winners, inverse-vol weighted, one fifth of " +
          "risk rebalanced daily on a 5-day hold. Observations are non-overlapping daily " +
          "portfolio returns, so judge the t-stat directly. Archived H100/H101/H102 reruns " +
          "live under Archived hypotheses.",
        emptyTitle: "No active cross-instrument rows",
      }}
    />
  );
}

export function ArchivedCrossInstrument() {
  return (
    <CrossInstrumentPanel
      preset={ARCHIVED_CROSS_PRESET}
      copy={{
        title: "Archived cross-instrument hypotheses",
        note: "rejected; reproducibility only",
        label: "Archived cross-instrument hypotheses",
        presetLabel: "H100–H102 archived preset",
        runLabel: "Re-run archived scan",
        pendingLabel: "Scanning archive…",
        intro:
          "Keeps rejected cross-instrument scans out of the active Lab while preserving exact rerun paths for audit or future comparison.",
        emptyTitle: "No archived cross-instrument rows",
      }}
    />
  );
}
