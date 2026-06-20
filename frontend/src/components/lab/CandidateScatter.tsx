import type { CandidateScatterPoint } from "../../api/types";

interface CandidateScatterProps {
  readonly candidates: CandidateScatterPoint[];
}

export function CandidateScatter({ candidates }: CandidateScatterProps) {
  const pointsData = candidates
    .map(
      (candidate) =>
        `${candidate.trial_no}:${candidate.in_sample_score}:${candidate.out_of_sample_score}`
    )
    .join("|");
  const maxScore = Math.max(
    1,
    ...candidates.flatMap((candidate) => [
      Number(candidate.in_sample_score),
      Number(candidate.out_of_sample_score),
    ])
  );

  return (
    <section className="lab-panel" aria-label="Trial score scatter">
      <h2>Trial Score Scatter</h2>
      <svg
        className="lab-scatter"
        viewBox="0 0 240 160"
        role="img"
        aria-label="Trial score scatter"
        data-points={pointsData}
      >
        <line x1="32" y1="128" x2="220" y2="128" />
        <line x1="32" y1="128" x2="32" y2="20" />
        {candidates.map((candidate) => {
          const x = 32 + (Number(candidate.in_sample_score) / maxScore) * 188;
          const y = 128 - (Number(candidate.out_of_sample_score) / maxScore) * 108;
          return (
            <circle key={candidate.trial_id} cx={x} cy={y} r="5" data-trial={candidate.trial_no} />
          );
        })}
      </svg>
    </section>
  );
}
