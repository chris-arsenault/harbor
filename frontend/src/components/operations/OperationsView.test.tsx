import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { PracticeControls } from "../../api/hooks";
import type { StatusSnapshot } from "../../api/types";
import { lanEndpoint } from "../../utils/format";
import { OperationsView } from "./OperationsView";

test("renders practice controls, broker state, alerts, and LAN deployment facts", () => {
  const controls: PracticeControls = {
    pending: false,
    errorMessage: null,
    setTradingEnabled: vi.fn(),
    flattenNow: vi.fn(),
  };

  render(<OperationsView status={status} controls={controls} />);

  expect(screen.getByRole("heading", { name: "Operations" })).toBeInTheDocument();
  expect(screen.getByText("practice-only")).toBeInTheDocument();
  expect(screen.getAllByText("promoted").length).toBeGreaterThan(0);
  expect(screen.getAllByText("EUR_USD").length).toBeGreaterThan(0);
  expect(screen.getAllByText("reconciled").length).toBeGreaterThan(0);
  expect(screen.getByText("clear")).toBeInTheDocument();
  expect(screen.getByText("18.00000000")).toBeInTheDocument();
  expect(screen.getByText("ntfy disabled")).toBeInTheDocument();
  expect(screen.getByText("telegram disabled")).toBeInTheDocument();
  expect(screen.getByText(lanEndpoint())).toBeInTheDocument();
  expect(screen.getByText("public route disabled")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Confirmation"), {
    target: { value: "OANDA_PRACTICE" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Flatten now" }));

  expect(controls.flattenNow).toHaveBeenCalledWith("OANDA_PRACTICE");
});

const status: StatusSnapshot = {
  bot_state: "IDLE",
  session_phase: "ny_trade",
  connection_health: "ok",
  mode: "practice",
  trading_enabled: true,
  trading_controls_available: true,
  kill_switch_state: "clear",
  day_pnl: "18.00000000",
  trades_today: 1,
  max_trades_per_day: 2,
  account_nav: "10018.00000000",
  open_positions: 1,
  unrealized_pnl: "0",
  last_heartbeat: "2026-01-15T14:30:00Z",
  promoted_variant: { id: 7, label: "promoted", status: "promoted" },
  reconciliation_state: { drift_detected: false },
  open_position: { instrument: "EUR_USD", broker_trade_id: "7001" },
  notifier_state: { ntfy_enabled: false, telegram_enabled: false },
  deployment: {
    access: "LAN",
    frontend_url: lanEndpoint(),
    public_route: false,
  },
};
