import type { CandidateScatterPoint, OptimizationStartResponse } from "../../api/types";
import { trialDiagnosticRows } from "./trialDiagnosticsModel";

interface TrialDiagnosticsProps {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly optimizationResult: OptimizationStartResponse | null;
}

export function TrialDiagnostics({ candidates, optimizationResult }: TrialDiagnosticsProps) {
  const rows = trialDiagnosticRows({ candidates, optimizationResult });

  return (
    <section className="lab-panel" aria-label="Trial diagnostics">
      <h2>Trial Diagnostics</h2>
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
    </section>
  );
}
