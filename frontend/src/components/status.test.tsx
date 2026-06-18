import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { HealthCards } from "./HealthCards";
import { GuardedTradingControls } from "./GuardedTradingControls";
import { HeartbeatIndicator } from "./HeartbeatIndicator";
import { ReadOnlyTradingState } from "./ReadOnlyTradingState";
import { StatusStrip } from "./StatusStrip";
import type { StatusSnapshot } from "../api/types";

test("StatusStrip renders operational status facts", () => {
  render(<StatusStrip status={status} />);

  expect(screen.getByText("WAIT_SWEEP")).toBeInTheDocument();
  expect(screen.getByText("ny_trade")).toBeInTheDocument();
  expect(screen.getByText("unknown")).toBeInTheDocument();
  expect(screen.getByText("practice")).toBeInTheDocument();
  expect(screen.getByText("armed")).toBeInTheDocument();
});

test("HealthCards renders pnl, account, open position, and trade count facts", () => {
  render(<HealthCards status={status} />);

  expect(screen.getByText("60.00000000")).toBeInTheDocument();
  expect(screen.getByText("10060.00000000")).toBeInTheDocument();
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.getByText("1 / 2")).toBeInTheDocument();
});

test("HeartbeatIndicator reports fresh and stale websocket heartbeats", () => {
  const { rerender } = render(
    <HeartbeatIndicator lastMessageAt="2026-01-15T14:31:00Z" now="2026-01-15T14:31:20Z" />
  );

  expect(screen.getByText("fresh")).toBeInTheDocument();

  rerender(<HeartbeatIndicator lastMessageAt="2026-01-15T14:31:00Z" now="2026-01-15T14:32:00Z" />);

  expect(screen.getByText("stale")).toBeInTheDocument();
});

test("ReadOnlyTradingState renders disabled trading controls until execution exists", () => {
  render(<ReadOnlyTradingState status={status} />);

  const control = screen.getByRole("checkbox", { name: "Trading enabled" });
  expect(control).toBeDisabled();
  expect(control).not.toBeChecked();
  expect(screen.getByText("display-only")).toBeInTheDocument();
});

test("GuardedTradingControls requires confirmation before practice mutations", () => {
  const onSetTradingEnabled = vi.fn();
  const onFlattenNow = vi.fn();

  render(
    <GuardedTradingControls
      status={{
        ...status,
        trading_controls_available: true,
        promoted_variant: { id: 7, label: "promoted", status: "promoted" },
        reconciliation_state: { drift_detected: false },
        open_position: { instrument: "EUR_USD" },
      }}
      pending={false}
      errorMessage={null}
      onSetTradingEnabled={onSetTradingEnabled}
      onFlattenNow={onFlattenNow}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "Enable practice trading" }));
  expect(onSetTradingEnabled).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Confirmation"), {
    target: { value: "OANDA_PRACTICE" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enable practice trading" }));
  fireEvent.click(screen.getByRole("button", { name: "Flatten now" }));

  expect(onSetTradingEnabled).toHaveBeenCalledWith(true, "OANDA_PRACTICE");
  expect(onFlattenNow).toHaveBeenCalledWith("OANDA_PRACTICE");
});

const status: StatusSnapshot = {
  bot_state: "WAIT_SWEEP",
  session_phase: "ny_trade",
  connection_health: "unknown",
  mode: "practice",
  trading_enabled: false,
  trading_controls_available: false,
  kill_switch_state: "armed",
  day_pnl: "60.00000000",
  trades_today: 1,
  max_trades_per_day: 2,
  account_nav: "10060.00000000",
  open_positions: 0,
  unrealized_pnl: "0E-8",
  last_heartbeat: "2026-01-15T14:31:00Z",
};
