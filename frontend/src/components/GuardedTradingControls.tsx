import { useState } from "react";

import type { StatusSnapshot } from "../api/types";

const CONFIRMATION_TOKEN = "OANDA_PRACTICE";

interface GuardedTradingControlsProps {
  readonly status: StatusSnapshot;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly onSetTradingEnabled: (enabled: boolean, confirmationToken: string) => void;
  readonly onFlattenNow: (confirmationToken: string) => void;
}

export function GuardedTradingControls({
  status,
  pending,
  errorMessage,
  onSetTradingEnabled,
  onFlattenNow,
}: GuardedTradingControlsProps) {
  const [confirmation, setConfirmation] = useState("");
  const confirmed = confirmation === CONFIRMATION_TOKEN;
  const facts = controlFacts(status);

  return (
    <section className="trading-controls" aria-label="Practice trading controls">
      <div className="trading-controls__facts">
        {facts.map((fact) => (
          <span key={fact}>{fact}</span>
        ))}
      </div>
      <label className="trading-controls__confirm">
        <span>Confirmation</span>
        <input
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          autoComplete="off"
        />
      </label>
      <div className="trading-controls__actions">
        <button
          type="button"
          disabled={!confirmed || pending}
          onClick={() => onSetTradingEnabled(!status.trading_enabled, confirmation)}
        >
          {tradingActionLabel(status)}
        </button>
        <button
          type="button"
          disabled={!confirmed || pending}
          onClick={() => onFlattenNow(confirmation)}
        >
          Flatten now
        </button>
      </div>
      {errorMessage === null ? null : (
        <strong className="trading-controls__error">{errorMessage}</strong>
      )}
    </section>
  );
}

function controlFacts(status: StatusSnapshot): string[] {
  return [
    status.trading_enabled ? "enabled" : "disabled",
    status.promoted_variant?.label ?? "none",
    status.reconciliation_state?.drift_detected ? "drift" : "reconciled",
    openPositionLabel(status),
  ];
}

function openPositionLabel(status: StatusSnapshot): string {
  const instrument = status.open_position?.instrument;
  return typeof instrument === "string" ? instrument : "flat";
}

function tradingActionLabel(status: StatusSnapshot): string {
  return status.trading_enabled ? "Disable practice trading" : "Enable practice trading";
}
