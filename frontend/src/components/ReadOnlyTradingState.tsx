import type { StatusSnapshot } from "../api/types";

interface ReadOnlyTradingStateProps {
  readonly status: StatusSnapshot;
}

export function ReadOnlyTradingState({ status }: ReadOnlyTradingStateProps) {
  return (
    <section className="trading-state" aria-label="Trading state">
      <label className="trading-state__toggle">
        <input type="checkbox" checked={status.trading_enabled} disabled readOnly />
        <span>Trading enabled</span>
      </label>
      <strong>{status.trading_controls_available ? "guarded" : "display-only"}</strong>
    </section>
  );
}
