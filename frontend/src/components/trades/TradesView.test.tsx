import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { TradeJournalItem } from "../../api/types";
import { TradesView } from "./TradesView";

test("renders broker-backed trade journal rows, filters, totals, and reconciliation ids", () => {
  render(
    <TradesView
      trades={[
        trade({
          id: 9,
          pnl: "18.00000000",
          r_multiple: "2.0000",
          broker_trade_id: "7001",
          close_transaction_id: "9201",
        }),
      ]}
      from="2026-01-15T14:00:00Z"
      to="2026-01-15T17:00:00Z"
    />
  );

  expect(screen.getByRole("heading", { name: "Trades" })).toBeInTheDocument();
  expect(screen.getByLabelText("From")).toHaveValue("2026-01-15T14:00:00Z");
  expect(screen.getByLabelText("To")).toHaveValue("2026-01-15T17:00:00Z");
  expect(screen.getByLabelText("Instrument")).toBeInTheDocument();
  expect(screen.getByLabelText("Status")).toBeInTheDocument();
  expect(screen.getByText("Total P&L")).toBeInTheDocument();
  expect(screen.getAllByText("18.00000000")).toHaveLength(2);
  expect(screen.getByRole("row", { name: /EUR_USD long 1000.0000/i })).toBeInTheDocument();
  expect(screen.getByText("7001")).toBeInTheDocument();
  expect(screen.getByText("9201")).toBeInTheDocument();
});

function trade(overrides: Partial<TradeJournalItem>): TradeJournalItem {
  return {
    id: 1,
    signal_id: 4,
    signal_key: "harbor-practice:7:2026-01-15T14:30:00Z",
    instrument: "EUR_USD",
    signal_status: "filled",
    side: "long",
    units: "1000.0000",
    entry_price: "1.09020000",
    entry_ts: "2026-01-15T14:30:00+00:00",
    exit_price: "1.09200000",
    exit_ts: "2026-01-15T16:59:00+00:00",
    pnl: "18.00000000",
    r_multiple: "2.0000",
    exit_reason: "take_profit",
    broker_order_id: "9100",
    client_order_id: "harbor-practice:7:2026-01-15T14:30:00Z",
    broker_trade_id: "7001",
    open_transaction_id: "9101",
    close_transaction_id: "9201",
    ...overrides,
  };
}
