import type { LabStudyProgress } from "../../api/types";

interface StudyProgressProps {
  readonly study: LabStudyProgress;
}

export function StudyProgress({ study }: StudyProgressProps) {
  return (
    <section className="lab-progress" aria-label="Study progress">
      <div>
        <span>Study</span>
        <strong>{study.status}</strong>
      </div>
      <div>
        <span>Trials</span>
        <strong>{study.trial_count} trials</strong>
      </div>
      <div>
        <span>Candidates</span>
        <strong>{study.candidate_count}</strong>
      </div>
      <div>
        <span>Paper</span>
        <strong>{study.paper_variant_count}</strong>
      </div>
    </section>
  );
}
