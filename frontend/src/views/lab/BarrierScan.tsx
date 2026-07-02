import { useState } from "react";

import { useBarrierScanMutation } from "../../api/hooks";
import type { BarrierScanPayload, BarrierScanResult, BarrierScanRow } from "../../api/research";
import { fmtNum, fmtPct } from "../../ui/format";
import { EmptyState, Field, Notice, Panel, Tag } from "../../ui/primitives";

interface BarrierDraft {
  readonly instrument: string;
  readonly algorithms: string;
  readonly horizons: string;
  readonly barrierR: string;
  readonly windowDays: number;
}

const DEFAULT_DRAFT: BarrierDraft = {
  instrument: "EUR_USD",
  algorithms: "generic_sweep_reversal, multi_candle_sweep_reclaim_reversal",
  horizons: "30, 60, 120",
  barrierR: "5.0",
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

function buildPayload(draft: BarrierDraft): BarrierScanPayload {
  const algorithms = parseStringList(draft.algorithms);
  const horizons = parseNumberList(draft.horizons);
  return {
    instrument: draft.instrument.trim().toUpperCase(),
    horizons: horizons.length ? horizons : null,
    barrier_r: draft.barrierR,
    algorithms: algorithms.length ? algorithms : null,
    window_days: draft.windowDays,
  };
}

function tStatTone(raw: string): "up" | "warn" | "muted" {
  const value = Number(raw);
  if (value >= 2) {
    return "up";
  }
  return value >= 1 ? "warn" : "muted";
}

function BarrierRow({ row }: { readonly row: BarrierScanRow }) {
  return (
    <tr>
      <td className="cell-strong">{row.hypothesis_id}</td>
      <td className="mute">{row.algorithm_label}</td>
      <td className="num">{row.horizon}m</td>
      <td className="num">{fmtNum(row.barrier_r, 1)}R</td>
      <td className="num">{row.total_events}</td>
      <td className="num">{row.resolved}</td>
      <td className="num">{row.timeouts}</td>
      <td className="num">{row.ambiguous}</td>
      <td className="num">{row.reversal_first}</td>
      <td className="num">{row.adverse_first}</td>
      <td className="num">{fmtPct(row.overall.hit_rate)}</td>
      <td className="num">
        <Tag tone={tStatTone(row.overall.t_stat)}>{fmtNum(row.overall.t_stat, 2)}</Tag>
      </td>
      <td className="num">{fmtNum(row.overall.bh_q_value ?? "1", 4)}</td>
      <td>
        <Tag tone={row.has_edge ? "up" : "muted"}>{row.has_edge ? "edge" : "—"}</Tag>
      </td>
    </tr>
  );
}

function BarrierTable({ result }: { readonly result: BarrierScanResult }) {
  if (result.results.length === 0) {
    return (
      <EmptyState glyph="∅" title="No data" hint="Import candles for this instrument first." />
    );
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Hypothesis</th>
            <th>Algorithm</th>
            <th className="num">Horizon</th>
            <th className="num">Barrier</th>
            <th className="num">Events</th>
            <th className="num">Resolved</th>
            <th className="num">Timeouts</th>
            <th className="num">Ambig</th>
            <th className="num">Rev first</th>
            <th className="num">Adv first</th>
            <th className="num">Hit</th>
            <th className="num">Corrected t</th>
            <th className="num">BH q</th>
            <th>Edge</th>
          </tr>
        </thead>
        <tbody>
          {result.results.map((row) => (
            <BarrierRow key={`${row.hypothesis_id}-${row.algorithm_id}-${row.horizon}`} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BarrierWarnings({ result }: { readonly result: BarrierScanResult }) {
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

function BarrierIdentityFields({
  draft,
  onChange,
}: {
  readonly draft: BarrierDraft;
  readonly onChange: (draft: BarrierDraft) => void;
}) {
  return (
    <>
      <Field label="Instrument">
        <input
          className="input"
          value={draft.instrument}
          onChange={(event) => onChange({ ...draft, instrument: event.target.value })}
          placeholder="EUR_USD"
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
          placeholder="30, 60, 120"
        />
      </Field>
    </>
  );
}

function BarrierTuningFields({
  draft,
  onChange,
}: {
  readonly draft: BarrierDraft;
  readonly onChange: (draft: BarrierDraft) => void;
}) {
  return (
    <>
      <Field label="Barrier (R × ATR)">
        <input
          className="input"
          value={draft.barrierR}
          onChange={(event) => onChange({ ...draft, barrierR: event.target.value })}
          placeholder="1.0"
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
    </>
  );
}

function BarrierResultView({
  result,
  error,
}: {
  readonly result: BarrierScanResult | null;
  readonly error: Error | null;
}) {
  return (
    <>
      {error ? <Notice tone="error">{error.message}</Notice> : null}
      {result ? (
        <>
          <BarrierWarnings result={result} />
          <p className="mute">
            First touch of entry ± barrier·ATR within the horizon, reversal side versus adverse
            side. Candles spanning both barriers are ambiguous and excluded, like timeouts. ATR is
            candle-timeframe (M1) ATR, so use trade-scale multiples: a high ambiguous count or
            identical rows across horizons means the barrier is too tight. Hit is tested against the
            coin-flip null with day-clustered errors.
          </p>
          <BarrierTable result={result} />
        </>
      ) : (
        <p className="mute">
          Barrier first-touch outcomes match the bracket-trade payoff and carry far less variance
          than fixed-horizon means — the H116 groundwork for a meta-labeled sweep gate.
        </p>
      )}
    </>
  );
}

export function BarrierScan() {
  const scan = useBarrierScanMutation();
  const [draft, setDraft] = useState<BarrierDraft>(DEFAULT_DRAFT);

  function submit() {
    scan.mutate(buildPayload(draft));
  }

  return (
    <Panel
      title="Barrier scan"
      note="triple-barrier first-touch outcomes (H116)"
      label="Barrier scan"
      actions={
        <button
          type="button"
          className="btn btn--primary"
          disabled={scan.isPending}
          onClick={submit}
        >
          {scan.isPending ? "Scanning…" : "Run barrier scan"}
        </button>
      }
    >
      <div className="fieldset">
        <BarrierIdentityFields draft={draft} onChange={setDraft} />
        <BarrierTuningFields draft={draft} onChange={setDraft} />
      </div>
      <BarrierResultView result={scan.data ?? null} error={scan.error ?? null} />
    </Panel>
  );
}
