import type { CandidateScatterPoint, LabStudyProgress } from "../../api/types";
import type { ScatterPoint } from "../../ui/viz";
import { toNumber } from "../../ui/format";

export function candidateScatter(candidates: readonly CandidateScatterPoint[]): {
  points: ScatterPoint[];
  dataPoints: string;
} {
  const points: ScatterPoint[] = candidates.map((candidate) => ({
    x: toNumber(candidate.in_sample_score) ?? 0,
    y: toNumber(candidate.out_of_sample_score) ?? 0,
    kind: candidate.pruned ? "pruned" : "default",
  }));
  const dataPoints = candidates
    .map(
      (candidate) =>
        `${candidate.trial_no}:${candidate.in_sample_score}:${candidate.out_of_sample_score}`
    )
    .join(";");
  return { points, dataPoints };
}

export interface StudyTile {
  readonly label: string;
  readonly value: string;
}

export function studyTiles(study: LabStudyProgress): StudyTile[] {
  return [
    { label: "Status", value: study.status },
    { label: "Trials", value: String(study.trial_count) },
    { label: "Candidates", value: String(study.candidate_count) },
    { label: "Paper variants", value: String(study.paper_variant_count) },
  ];
}

export function bestOutOfSample(candidates: readonly CandidateScatterPoint[]): number | null {
  const scores = candidates
    .map((candidate) => toNumber(candidate.out_of_sample_score))
    .filter((score): score is number => score !== null);
  return scores.length > 0 ? Math.max(...scores) : null;
}
