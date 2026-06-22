import type { CandidateScatterPoint, OptimizationStartResponse } from "../../api/types";
import { trialDiagnosticRows } from "./trialDiagnosticsModel";

interface TrialDiagnosticsProps {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly optimizationResult: OptimizationStartResponse | null;
}

export function TrialDiagnostics({ candidates, optimizationResult }: TrialDiagnosticsProps) {
  const rows = trialDiagnosticRows({ candidates, optimizationResult });

  return (
    <details className="lab-panel lab-disclosure" aria-label="Trial diagnostics">
      <summary className="lab-disclosure__summary">
        <h2>Trial Diagnostics</h2>
        <span>{rows.length === 1 ? "1 trial" : `${rows.length} trials`}</span>
      </summary>
      <div className="lab-table-wrap">
        <table className="lab-table">
          <thead>
            <tr>
              <th>Trial</th>
              <th>Status</th>
              <th>IS</th>
              <th>OOS</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5}>No trial diagnostics yet.</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.trialNo}</td>
                  <td>{row.status}</td>
                  <td>{row.inSampleScore}</td>
                  <td>{row.outOfSampleScore}</td>
                  <td>{row.reason}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}
