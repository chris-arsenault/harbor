import type { CandleSourceStatus, OptimizationStartPayload } from "../../api/types";
import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import {
  DISCOVERY_STUDY_CONFIG,
  QUICK_STUDY_CONFIG,
  type TuningStudyConfig,
} from "./tuningPayload";
import type { TuningRunState } from "./LabView";

interface StudyWorkbenchProps {
  readonly studyConfig: TuningStudyConfig;
  readonly onStudyConfigChange: (config: TuningStudyConfig) => void;
  readonly studyPayload: OptimizationStartPayload;
  readonly preflight: OptimizationPreflightResponse | null;
  readonly preflightPending: boolean;
  readonly preflightError: string | null;
  readonly tuningRun: TuningRunState;
  readonly candleSource: CandleSourceStatus | null;
  readonly onStartOptimization: (payload: OptimizationStartPayload) => void | Promise<void>;
}

export function StudyWorkbench(props: StudyWorkbenchProps) {
  const hasCandles = (props.candleSource?.coverage?.candle_count ?? 0) > 0;
  const ready = props.preflight?.status === "ready";
  const startPayload = props.preflight?.recommended_payload ?? props.studyPayload;
  return (
    <section className="lab-panel" aria-label="Study setup">
      <StudyWorkbenchHeader
        disabled={!hasCandles || !ready || props.tuningRun.pending}
        pending={props.tuningRun.pending}
        onDiscovery={() => props.onStudyConfigChange(DISCOVERY_STUDY_CONFIG)}
        onQuick={() => props.onStudyConfigChange(QUICK_STUDY_CONFIG)}
        onStart={() => void props.onStartOptimization(startPayload)}
      />
      <StudyStatusCards preflight={props.preflight} pending={props.preflightPending} />
      {props.preflightError ? (
        <p className="lab-run-notice lab-run-notice--error" aria-live="polite">
          {props.preflightError}
        </p>
      ) : null}
      <StudyConfigControls config={props.studyConfig} onChange={props.onStudyConfigChange} />
      <StudyFacts preflight={props.preflight} />
      <StudyWindowDiagnostics preflight={props.preflight} pending={props.preflightPending} />
    </section>
  );
}

function StudyWorkbenchHeader({
  disabled,
  pending,
  onDiscovery,
  onQuick,
  onStart,
}: {
  readonly disabled: boolean;
  readonly pending: boolean;
  readonly onDiscovery: () => void;
  readonly onQuick: () => void;
  readonly onStart: () => void;
}) {
  return (
    <div className="lab-panel__header">
      <h2>Study Setup</h2>
      <div className="lab-panel__actions">
        <button type="button" className="lab-button lab-button--quiet" onClick={onDiscovery}>
          Discovery preset
        </button>
        <button type="button" className="lab-button lab-button--quiet" onClick={onQuick}>
          Quick preset
        </button>
        <button type="button" className="lab-button" disabled={disabled} onClick={onStart}>
          {pending ? "Running tuning study" : "Start tuning study"}
        </button>
      </div>
    </div>
  );
}

function StudyStatusCards({
  preflight,
  pending,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
  readonly pending: boolean;
}) {
  return (
    <div className="lab-study-status-grid">
      {studyStatusCards(preflight, pending).map((card) => (
        <div key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </div>
      ))}
    </div>
  );
}

function StudyConfigControls({
  config,
  onChange,
}: {
  readonly config: TuningStudyConfig;
  readonly onChange: (config: TuningStudyConfig) => void;
}) {
  return (
    <div className="lab-study-controls" aria-label="Study configuration">
      <NumberControl
        label="Trials"
        value={config.trialCount}
        min={1}
        max={500}
        onChange={(value) => onChange({ ...config, trialCount: value })}
      />
      <NumberControl
        label="Candidates"
        value={config.candidateCount}
        min={1}
        max={20}
        onChange={(value) => onChange({ ...config, candidateCount: value })}
      />
      <NumberControl
        label="Train days"
        value={config.trainWindowDays}
        min={1}
        max={120}
        onChange={(value) => onChange({ ...config, trainWindowDays: value })}
      />
      <NumberControl
        label="OOS days"
        value={config.outOfSampleWindowDays}
        min={1}
        max={60}
        onChange={(value) => onChange({ ...config, outOfSampleWindowDays: value })}
      />
      <NumberControl
        label="Step days"
        value={config.stepDays}
        min={1}
        max={60}
        onChange={(value) => onChange({ ...config, stepDays: value })}
      />
      <NumberControl
        label="Min IS trades"
        value={config.minInSampleTrades}
        min={0}
        max={200}
        onChange={(value) => onChange({ ...config, minInSampleTrades: value })}
      />
      <NumberControl
        label="Min OOS trades"
        value={config.minOutOfSampleTrades}
        min={0}
        max={200}
        onChange={(value) => onChange({ ...config, minOutOfSampleTrades: value })}
      />
      <NumberControl
        label="Robustness"
        value={config.robustnessNeighborCount}
        min={0}
        max={20}
        onChange={(value) => onChange({ ...config, robustnessNeighborCount: value })}
      />
    </div>
  );
}

function NumberControl({
  label,
  value,
  min,
  max,
  onChange,
}: {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly onChange: (value: number) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(clampedInteger(event.currentTarget.value, min, max))}
      />
    </label>
  );
}

function StudyFacts({ preflight }: { readonly preflight: OptimizationPreflightResponse | null }) {
  return (
    <ul className="fact-list">
      {studyFacts(preflight).map((row) => (
        <li key={row.label}>
          {row.label}: {row.value}
        </li>
      ))}
    </ul>
  );
}

function StudyWindowDiagnostics({
  preflight,
  pending,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
  readonly pending: boolean;
}) {
  return (
    <details className="lab-disclosure" aria-label="Study windows and diagnostics">
      <summary className="lab-disclosure__summary">
        <h2>Windows and Diagnostics</h2>
        <span>{preflight?.walk_forward?.window_count ?? 0} windows</span>
      </summary>
      <StudyWindowTable preflight={preflight} pending={pending} />
      <ul className="fact-list">
        {(preflight?.readiness ?? []).map((item) => (
          <li key={item.name}>
            {item.name}: {item.status} - {item.message}
          </li>
        ))}
      </ul>
    </details>
  );
}

function StudyWindowTable({
  preflight,
  pending,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
  readonly pending: boolean;
}) {
  return (
    <div className="lab-table-wrap">
      <table className="lab-table">
        <thead>
          <tr>
            <th>Window</th>
            <th>Train</th>
            <th>OOS</th>
            <th>Train candles</th>
            <th>OOS candles</th>
          </tr>
        </thead>
        <tbody>
          {(preflight?.walk_forward?.windows ?? []).length ? (
            (preflight?.walk_forward?.windows ?? []).map((window) => (
              <tr key={window.index}>
                <td>{window.index}</td>
                <td>
                  {window.train_start} to {window.train_end}
                </td>
                <td>
                  {window.out_of_sample_start} to {window.out_of_sample_end}
                </td>
                <td>{window.train_candle_count}</td>
                <td>{window.out_of_sample_candle_count}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={5}>{pending ? "Loading preflight." : "No windows."}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function clampedInteger(raw: string, min: number, max: number): number {
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed)) {
    return min;
  }
  return Math.min(Math.max(parsed, min), max);
}

function studyStatusCards(preflight: OptimizationPreflightResponse | null, pending: boolean) {
  return [
    { label: "Preflight", value: preflightStatus(preflight, pending) },
    { label: "Candles", value: candleCount(preflight) },
    { label: "Session days", value: sessionDayCount(preflight) },
    { label: "Windows", value: windowCount(preflight) },
    { label: "Baseline OOS", value: baselineOosScore(preflight) },
    { label: "OOS trades", value: baselineOosTrades(preflight) },
  ];
}

function preflightStatus(preflight: OptimizationPreflightResponse | null, pending: boolean) {
  if (pending) {
    return "checking";
  }
  return preflight?.status ?? "not run";
}

function candleCount(preflight: OptimizationPreflightResponse | null) {
  return preflight?.dataset?.candle_count.toLocaleString() ?? "0";
}

function sessionDayCount(preflight: OptimizationPreflightResponse | null) {
  if (preflight?.dataset === undefined) {
    return "0";
  }
  return `${preflight.dataset.evaluable_session_day_count}/${preflight.dataset.session_day_count}`;
}

function windowCount(preflight: OptimizationPreflightResponse | null) {
  return String(preflight?.walk_forward?.window_count ?? 0);
}

function baselineOosScore(preflight: OptimizationPreflightResponse | null) {
  return preflight?.baseline?.out_of_sample.score ?? "none";
}

function baselineOosTrades(preflight: OptimizationPreflightResponse | null) {
  return statString(preflight?.baseline?.out_of_sample.stats.trade_count);
}

function statString(value: unknown) {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return "0";
}

function studyFacts(preflight: OptimizationPreflightResponse | null) {
  if (!hasStudyFacts(preflight)) {
    return [
      { label: "candidate gate", value: "positive in-sample and out-of-sample scores" },
      { label: "baseline", value: "waiting for preflight" },
    ];
  }
  return [
    { label: "candidate gate", value: preflight.candidate_gate.requires },
    {
      label: "trade floors",
      value: `${preflight.candidate_gate.min_in_sample_trades} IS / ${preflight.candidate_gate.min_out_of_sample_trades} OOS`,
    },
    { label: "baseline", value: baselineLabel(preflight.baseline?.status ?? null) },
    {
      label: "coverage",
      value: `${preflight.dataset.first_evaluable_trading_date ?? "none"} to ${preflight.dataset.last_evaluable_trading_date ?? "none"}`,
    },
    {
      label: "split",
      value: `${preflight.walk_forward.train_window_days} train / ${preflight.walk_forward.out_of_sample_window_days} OOS / ${preflight.walk_forward.step_days} step`,
    },
  ];
}

function hasStudyFacts(
  preflight: OptimizationPreflightResponse | null
): preflight is OptimizationPreflightResponse {
  const maybe = preflight as Partial<OptimizationPreflightResponse> | null;
  return Boolean(maybe?.candidate_gate && maybe.dataset && maybe.walk_forward);
}

function baselineLabel(status: string | null) {
  if (status === "candidate_gate_passed") {
    return "passes candidate gate";
  }
  if (status === "candidate_gate_failed") {
    return "does not pass candidate gate";
  }
  if (status === "no_trades") {
    return "no trades";
  }
  if (status === "below_in_sample_trade_floor") {
    return "below in-sample trade floor";
  }
  if (status === "below_out_of_sample_trade_floor") {
    return "below out-of-sample trade floor";
  }
  return "not available";
}
