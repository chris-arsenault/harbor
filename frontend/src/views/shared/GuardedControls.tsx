import { useState } from "react";

import type { PracticeControls } from "../../api/hooks";
import type { StatusSnapshot } from "../../api/types";
import { Notice, Tag } from "../../ui/primitives";

export function GuardedControls({
  status,
  controls,
}: {
  readonly status: StatusSnapshot;
  readonly controls: PracticeControls;
}) {
  const [token, setToken] = useState("");
  const armed = status.trading_enabled;

  if (!status.trading_controls_available) {
    return (
      <div className="row">
        <Tag tone="muted">read-only</Tag>
        <span className="mute">Trading controls are disabled for this deployment.</span>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="row">
        <Tag tone={armed ? "up" : "muted"}>{armed ? "armed" : "disarmed"}</Tag>
        <Tag tone={status.kill_switch_state === "armed" ? "warn" : "down"}>
          kill: {status.kill_switch_state}
        </Tag>
      </div>
      <label className="field">
        <span className="field__label">Confirmation</span>
        <input
          className="input"
          aria-label="Confirmation"
          value={token}
          placeholder="OANDA_PRACTICE"
          onChange={(event) => setToken(event.target.value)}
        />
      </label>
      <div className="row">
        <button
          type="button"
          className={armed ? "btn btn--danger" : "btn btn--primary"}
          disabled={controls.pending || token.length === 0}
          onClick={() => controls.setTradingEnabled(!armed, token)}
        >
          {armed ? "Disable practice trading" : "Enable practice trading"}
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={controls.pending || token.length === 0}
          onClick={() => controls.flattenNow(token)}
        >
          Flatten now
        </button>
      </div>
      {controls.errorMessage ? <Notice tone="error">{controls.errorMessage}</Notice> : null}
    </div>
  );
}
