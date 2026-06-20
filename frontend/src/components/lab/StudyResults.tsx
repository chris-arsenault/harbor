import type { CandidateScatterPoint, OptimizationStartResponse } from "../../api/types";
import { rankedTrialDiagnosticRows, type TrialDiagnosticRow } from "./trialDiagnosticsModel";

interface StudyResultsProps {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly optimizationResult: OptimizationStartResponse | null;
  readonly paperCandidateCount: number;
}

export function StudyResults({
  candidates,
  optimizationResult,
  paperCandidateCount,
}: StudyResultsProps) {
  const rows = rankedTrialDiagnosticRows({ candidates, optimizationResult });
  const bestOutOfSample = rows.length > 0 ? rows[0].outOfSampleScore : "none";
  const bestTrial = rows.length > 0 ? `#${rows[0].trialNo}` : "none";

  return (
    <section className="lab-panel" aria-label="Study results">
      <div className="lab-panel__header">
        <h2>Study Results</h2>
        <span>{rows.length === 1 ? "1 trial" : `${rows.length} trials`}</span>
      </div>
      <div className="lab-study-status-grid lab-study-status-grid--compact">
        <div>
          <span>Paper candidates</span>
          <strong>{paperCandidateCount}</strong>
        </div>
        <div>
          <span>Passed score gate</span>
          <strong>{rows.filter(passesScoreGate).length}</strong>
        </div>
        <div>
          <span>Best OOS</span>
          <strong>{bestOutOfSample}</strong>
        </div>
        <div>
          <span>Best trial</span>
          <strong>{bestTrial}</strong>
        </div>
      </div>
      <p className="lab-result-summary">{resultSummary(rows, paperCandidateCount)}</p>
      <div className="lab-table-wrap">
        <table className="lab-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Trial</th>
              <th>Gate</th>
              <th>IS</th>
              <th>OOS</th>
              <th>Robust</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7}>No study results yet.</td>
              </tr>
            ) : (
              rows.map((row, index) => (
                <tr key={row.id}>
                  <td>{index + 1}</td>
                  <td>{row.trialNo}</td>
                  <td>{passesScoreGate(row) ? "passes score gate" : "blocked"}</td>
                  <td>{row.inSampleScore}</td>
                  <td>{row.outOfSampleScore}</td>
                  <td>{row.robustnessScore}</td>
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

function resultSummary(rows: readonly TrialDiagnosticRow[], paperCandidateCount: number) {
  if (rows.length === 0) {
    return "Run a study to rank trials against the paper-candidate gate.";
  }
  const bestRow = rows[0];
  if (paperCandidateCount > 0) {
    return `${paperCandidateCount} paper candidate${
      paperCandidateCount === 1 ? "" : "s"
    } passed the promotion gate. Best trial #${bestRow.trialNo} has OOS ${
      bestRow.outOfSampleScore
    }.`;
  }
  if (positiveScore(bestRow.outOfSampleScore)) {
    return `No paper candidates. Best trial #${bestRow.trialNo} has positive OOS ${bestRow.outOfSampleScore}, but is blocked because ${bestRow.reason}.`;
  }
  return `No paper candidates. Best trial #${bestRow.trialNo} is blocked because ${bestRow.reason}.`;
}

function passesScoreGate(row: TrialDiagnosticRow) {
  return row.reason === "eligible for ranking";
}

function positiveScore(score: string) {
  const value = Number(score);
  return Number.isFinite(value) && value > 0;
}
