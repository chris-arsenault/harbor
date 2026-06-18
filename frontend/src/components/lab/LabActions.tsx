import { useState } from "react";

interface LabActionsProps {
  readonly onCreatePaperVariant: (payload: {
    trial_id: number;
    label: string;
  }) => void | Promise<void>;
}

export function LabActions({ onCreatePaperVariant }: LabActionsProps) {
  const [trialId, setTrialId] = useState("");
  const [label, setLabel] = useState("");

  return (
    <form
      className="lab-actions"
      aria-label="Paper variant actions"
      onSubmit={(event) => {
        event.preventDefault();
        const parsedTrialId = Number(trialId);
        if (Number.isFinite(parsedTrialId) && parsedTrialId > 0) {
          void onCreatePaperVariant({ trial_id: parsedTrialId, label: label.trim() });
        }
      }}
    >
      <label>
        <span>Trial</span>
        <input
          aria-label="Trial"
          inputMode="numeric"
          value={trialId}
          onChange={(event) => setTrialId(event.currentTarget.value)}
        />
      </label>
      <label>
        <span>Label</span>
        <input
          aria-label="Label"
          value={label}
          onChange={(event) => setLabel(event.currentTarget.value)}
        />
      </label>
      <button type="submit" className="lab-button">
        Create paper variant
      </button>
    </form>
  );
}
