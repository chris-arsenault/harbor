import { useState } from "react";

import type { BacktestStartPayload, CandleCoverage, PaperVariant } from "../../api/types";
import { displayValue } from "../../utils/format";

interface BacktestRunFormProps {
  readonly coverage: CandleCoverage | null;
  readonly defaultInstrument: string;
  readonly targetVariant: PaperVariant | null;
  readonly pending: boolean;
  readonly onStartBacktest: (payload: BacktestStartPayload) => void;
}

const DEFAULT_BACKTEST_WINDOW_DAYS = 30;
type StrategyMode = "candidate" | "default";
interface FormDraft {
  readonly strategyMode: StrategyMode;
  readonly instrument: string;
  readonly from: string;
  readonly to: string;
}

export function BacktestRunForm({
  coverage,
  defaultInstrument,
  targetVariant,
  pending,
  onStartBacktest,
}: BacktestRunFormProps) {
  const [draft, setDraft] = useState<FormDraft>(() =>
    defaultBacktestDraft(defaultInstrument, coverage, targetVariant)
  );
  const strategyMode = targetVariant === null ? "default" : draft.strategyMode;
  const hasCoverage = Boolean(
    coverage !== null && coverage.candle_count > 0 && coverage.from && coverage.to
  );

  return (
    <form
      className="backtest-run-panel"
      onSubmit={(event) => {
        event.preventDefault();
        const payload: BacktestStartPayload = {
          source: "persisted_candles",
          instrument: draft.instrument.trim().toUpperCase(),
          candle_range: { from: draft.from, to: draft.to },
        };
        if (strategyMode === "candidate" && targetVariant !== null) {
          payload.strategy_params = targetVariant.params;
          payload.variant_id = targetVariant.id;
          payload.variant_label = targetVariant.label;
        }
        onStartBacktest(payload);
      }}
    >
      <BacktestRunHeader
        coverage={coverage}
        draft={draft}
        pending={pending}
        disabled={pending || !hasCoverage}
      />
      <BacktestFormFields
        draft={{ ...draft, strategyMode }}
        coverage={coverage}
        targetVariant={targetVariant}
        onDraftChange={setDraft}
      />
      <BacktestWindowEditor draft={draft} onDraftChange={setDraft} />
    </form>
  );
}

function BacktestRunHeader({
  coverage,
  draft,
  pending,
  disabled,
}: {
  readonly coverage: CandleCoverage | null;
  readonly draft: FormDraft;
  readonly pending: boolean;
  readonly disabled: boolean;
}) {
  return (
    <div className="lab-panel__header">
      <div>
        <h3>Run Backtest</h3>
        <p className="backtest-run-panel__summary">
          {backtestSummary(coverage, draft.from, draft.to)}
        </p>
      </div>
      <button type="submit" disabled={disabled}>
        {pending ? "Running..." : "Run backtest"}
      </button>
    </div>
  );
}

function BacktestFormFields({
  draft,
  coverage,
  targetVariant,
  onDraftChange,
}: {
  readonly draft: FormDraft;
  readonly coverage: CandleCoverage | null;
  readonly targetVariant: PaperVariant | null;
  readonly onDraftChange: (draft: FormDraft) => void;
}) {
  return (
    <div className="backtest-form-grid">
      <label>
        Strategy
        <select
          value={draft.strategyMode}
          onChange={(event) =>
            onDraftChange({ ...draft, strategyMode: event.target.value as StrategyMode })
          }
        >
          {targetVariant !== null ? (
            <option value="candidate">Selected candidate: {targetVariant.label}</option>
          ) : null}
          <option value="default">Default strategy</option>
        </select>
      </label>
      <label>
        Instrument
        <input
          value={draft.instrument}
          onChange={(event) => onDraftChange({ ...draft, instrument: event.target.value })}
        />
      </label>
      <Fact label="Candles" value={coverage?.candle_count.toLocaleString() ?? "none"} />
      <Fact label="Coverage" value={coverageRange(coverage)} />
    </div>
  );
}

function BacktestWindowEditor({
  draft,
  onDraftChange,
}: {
  readonly draft: FormDraft;
  readonly onDraftChange: (draft: FormDraft) => void;
}) {
  return (
    <details className="backtest-window-editor">
      <summary>Backtest window</summary>
      <div className="backtest-form-grid">
        <label>
          From
          <input
            value={draft.from}
            onChange={(event) => onDraftChange({ ...draft, from: event.target.value })}
          />
        </label>
        <label>
          To
          <input
            value={draft.to}
            onChange={(event) => onDraftChange({ ...draft, to: event.target.value })}
          />
        </label>
      </div>
    </details>
  );
}

function Fact({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="backtest-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function defaultBacktestDraft(
  instrument: string,
  coverage: CandleCoverage | null,
  targetVariant: PaperVariant | null
): FormDraft {
  return {
    strategyMode: targetVariant === null ? "default" : "candidate",
    ...defaultBacktestWindow(instrument, coverage),
  };
}

function defaultBacktestWindow(
  instrument: string,
  coverage: CandleCoverage | null
): Omit<FormDraft, "strategyMode"> {
  if (coverage?.from && coverage.to) {
    const coverageStart = new Date(coverage.from);
    const coverageEnd = new Date(coverage.to);
    const preferredStart = new Date(
      coverageEnd.getTime() - DEFAULT_BACKTEST_WINDOW_DAYS * 24 * 60 * 60 * 1000
    );
    const from = preferredStart > coverageStart ? preferredStart : coverageStart;
    return {
      instrument: coverage.instrument || instrument,
      from: from.toISOString(),
      to: coverageEnd.toISOString(),
    };
  }

  const to = new Date();
  const from = new Date(to.getTime() - DEFAULT_BACKTEST_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  return { instrument, from: from.toISOString(), to: to.toISOString() };
}

function backtestSummary(coverage: CandleCoverage | null, from: string, to: string): string {
  if (coverage === null || coverage.candle_count === 0) {
    return "No persisted M1 candles are available for backtesting.";
  }
  return `Persisted M1 candles, selected historical window: ${from} to ${to}.`;
}

function coverageRange(coverage: CandleCoverage | null): string {
  if (coverage === null) {
    return "loading";
  }
  return `${displayValue(coverage.from, "none")} to ${displayValue(coverage.to, "none")}`;
}
