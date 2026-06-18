import { useState } from "react";

import type { BacktestStartPayload } from "../../api/types";

interface BacktestRunFormProps {
  readonly pending: boolean;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
}

const DEFAULT_INSTRUMENT = "EUR_USD";
const DEFAULT_FROM = "2026-01-15T14:00:00Z";
const DEFAULT_TO = "2026-01-15T17:00:00Z";

export function BacktestRunForm({ pending, onStartBacktest }: BacktestRunFormProps) {
  const [instrument, setInstrument] = useState(DEFAULT_INSTRUMENT);
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);

  return (
    <form
      className="run-form"
      onSubmit={(event) => {
        event.preventDefault();
        onStartBacktest({
          source: "persisted_candles",
          instrument,
          candle_range: { from, to },
        });
      }}
    >
      <label>
        Instrument
        <input value={instrument} onChange={(event) => setInstrument(event.target.value)} />
      </label>
      <label>
        From
        <input value={from} onChange={(event) => setFrom(event.target.value)} />
      </label>
      <label>
        To
        <input value={to} onChange={(event) => setTo(event.target.value)} />
      </label>
      <button type="submit" disabled={pending}>
        Run backtest
      </button>
    </form>
  );
}
