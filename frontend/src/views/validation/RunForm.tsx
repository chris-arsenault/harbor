import { useState } from "react";

import type { BacktestStartPayload, CandleSourceStatus, PaperVariant } from "../../api/types";
import { Field } from "../../ui/primitives";

function sourceInstruments(source: CandleSourceStatus | null, fallback: string): string[] {
  if (source?.instrument_coverages?.length) {
    return source.instrument_coverages.map((coverage) => coverage.instrument);
  }
  return source ? [source.coverage.instrument] : [fallback];
}

function instrumentOptions(source: CandleSourceStatus | null, fallback: string): string[] {
  const coverages = sourceInstruments(source, fallback);
  return coverages.includes(fallback) ? coverages : [fallback, ...coverages];
}

export function RunForm({
  candleSource,
  targetVariant,
  pending,
  onStartBacktest,
}: {
  readonly candleSource: CandleSourceStatus | null;
  readonly targetVariant: PaperVariant | null;
  readonly pending: boolean;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
}) {
  const fallback = candleSource?.coverage.instrument ?? "EUR_USD";
  const [instrument, setInstrument] = useState(fallback);
  const [windowDays, setWindowDays] = useState(30);

  function submit() {
    const payload: BacktestStartPayload = {
      source: "persisted_candles",
      instrument,
      candle_window_days: windowDays,
    };
    if (targetVariant) {
      payload.strategy_params = targetVariant.params;
      payload.variant_id = targetVariant.id;
      payload.variant_label = targetVariant.label;
    }
    onStartBacktest(payload);
  }

  return (
    <div className="fieldset">
      <Field label="Instrument">
        <select
          className="select"
          value={instrument}
          onChange={(event) => setInstrument(event.target.value)}
        >
          {instrumentOptions(candleSource, fallback).map((symbol) => (
            <option key={symbol} value={symbol}>
              {symbol}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Window (days)">
        <input
          className="input"
          type="number"
          min={1}
          value={windowDays}
          onChange={(event) => setWindowDays(Number(event.target.value) || 1)}
        />
      </Field>
      <Field label="Strategy">
        <input className="input" readOnly value={targetVariant?.label ?? "default strategy"} />
      </Field>
      <button type="button" className="btn btn--primary" disabled={pending} onClick={submit}>
        {pending ? "Running…" : "Run backtest"}
      </button>
    </div>
  );
}
