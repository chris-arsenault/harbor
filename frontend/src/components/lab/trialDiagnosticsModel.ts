import type {
  CandidateScatterPoint,
  OptimizationStartResponse,
  OptimizationTrialResult,
} from "../../api/types";

interface TrialDiagnosticRow {
  readonly id: string;
  readonly trialNo: number;
  readonly status: string;
  readonly inSampleScore: string;
  readonly outOfSampleScore: string;
  readonly reason: string;
}

export function trialDiagnosticRows({
  candidates,
  optimizationResult,
}: {
  readonly candidates: readonly CandidateScatterPoint[];
  readonly optimizationResult: OptimizationStartResponse | null;
}): TrialDiagnosticRow[] {
  if (optimizationResult !== null && optimizationResult.trials.length > 0) {
    return optimizationResult.trials.map((trial) => trialDiagnosticRowFromTrial(trial));
  }
  return candidates.map((candidate) => trialDiagnosticRowFromCandidate(candidate));
}

function trialDiagnosticRowFromTrial(trial: OptimizationTrialResult): TrialDiagnosticRow {
  return {
    id: `result-${trial.trial_no}`,
    trialNo: trial.trial_no,
    status: trial.status,
    inSampleScore: trial.is_score,
    outOfSampleScore: trial.oos_score,
    reason:
      candidateRejectionReason({
        status: trial.status,
        pruned: trial.pruned,
        failureReason: trial.failure_reason,
        inSampleScore: trial.is_score,
        outOfSampleScore: trial.oos_score,
      }) ?? "eligible for ranking",
  };
}

function trialDiagnosticRowFromCandidate(candidate: CandidateScatterPoint): TrialDiagnosticRow {
  return {
    id: `candidate-${candidate.trial_id}`,
    trialNo: candidate.trial_no,
    status: candidate.status,
    inSampleScore: candidate.in_sample_score,
    outOfSampleScore: candidate.out_of_sample_score,
    reason:
      candidate.candidate_rejection_reason ??
      candidateRejectionReason({
        status: candidate.status,
        pruned: candidate.pruned,
        failureReason: candidate.failure_reason,
        inSampleScore: candidate.in_sample_score,
        outOfSampleScore: candidate.out_of_sample_score,
      }) ??
      "eligible for ranking",
  };
}

function candidateRejectionReason({
  status,
  pruned,
  failureReason,
  inSampleScore,
  outOfSampleScore,
}: {
  readonly status: string;
  readonly pruned: boolean;
  readonly failureReason: string | null;
  readonly inSampleScore: string;
  readonly outOfSampleScore: string;
}): string | null {
  if (failureReason !== null && failureReason.trim().length > 0) {
    return failureReason;
  }
  if (status === "failed") {
    return "trial failed during evaluation";
  }
  if (status === "pruned" || pruned) {
    return "trial was pruned";
  }
  const inSampleNonPositive = isNonPositiveScore(inSampleScore);
  const outOfSampleNonPositive = isNonPositiveScore(outOfSampleScore);
  if (inSampleNonPositive && outOfSampleNonPositive) {
    return "in-sample and out-of-sample scores are not positive";
  }
  if (inSampleNonPositive) {
    return "in-sample score is not positive";
  }
  if (outOfSampleNonPositive) {
    return "out-of-sample score is not positive";
  }
  return null;
}

function isNonPositiveScore(score: string): boolean {
  const numericScore = Number(score);
  return Number.isFinite(numericScore) && numericScore <= 0;
}

export function noCandidateExplanation(rows: readonly TrialDiagnosticRow[]): string {
  const reasons = rows
    .map((row) => row.reason)
    .filter((reason) => reason !== "eligible for ranking");
  if (reasons.length === 0) {
    return "No leaderboard row was created because no candidate passed the scoring gates.";
  }
  const counts = new Map<string, number>();
  for (const reason of reasons) {
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  }
  const [dominantReason, count] = [...counts.entries()].sort(
    (left, right) => right[1] - left[1]
  )[0];
  const prefix =
    count === rows.length ? `All ${rows.length} trials` : `${count} of ${rows.length} trials`;
  return `${prefix} ${reasonClause(dominantReason)}; see Trial diagnostics.`;
}

function reasonClause(reason: string): string {
  if (reason === "in-sample and out-of-sample scores are not positive") {
    return "had non-positive in-sample and out-of-sample scores";
  }
  if (reason === "in-sample score is not positive") {
    return "had non-positive in-sample scores";
  }
  if (reason === "out-of-sample score is not positive") {
    return "had non-positive out-of-sample scores";
  }
  if (reason === "trial was pruned") {
    return "were pruned";
  }
  if (reason === "trial failed during evaluation") {
    return "failed during evaluation";
  }
  return `were rejected: ${reason}`;
}
