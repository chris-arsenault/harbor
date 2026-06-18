import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { EventLogItem } from "../../api/types";
import { EventsView } from "./EventsView";

test("renders filters, daily summaries, structured detail, and live log rows", () => {
  render(<EventsView events={[liveEvent, summaryEvent, warningEvent]} loading={false} />);

  expect(screen.getByRole("heading", { name: "Events" })).toBeInTheDocument();
  expect(screen.getByLabelText("Level")).toBeInTheDocument();
  expect(screen.getByLabelText("Module")).toBeInTheDocument();
  expect(screen.getByLabelText("Type")).toBeInTheDocument();
  expect(screen.getByText("daily summary")).toBeInTheDocument();
  expect(screen.getByText("Trades Today")).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();
  expect(screen.getByText("live websocket log")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "heartbeat stale" }));
  expect(screen.getByText('"seconds": 31')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Level"), { target: { value: "warn" } });

  expect(screen.getByText("heartbeat stale")).toBeInTheDocument();
  expect(screen.queryByText("daily summary")).not.toBeInTheDocument();
});

test("renders clear empty and error states", () => {
  const { rerender } = render(
    <EventsView events={[]} loading={false} errorMessage="GET /api/events failed" />
  );

  expect(screen.getByText("GET /api/events failed")).toBeInTheDocument();

  rerender(<EventsView events={[]} loading={false} />);

  expect(screen.getByText("No events match the current filters.")).toBeInTheDocument();
});

const liveEvent: EventLogItem = {
  id: 1,
  ts: "2026-01-15T14:32:00Z",
  level: "info",
  module: "ws",
  type: "log",
  message: "live websocket log",
  data: { source: "websocket" },
};

const summaryEvent: EventLogItem = {
  id: 2,
  ts: "2026-01-15T23:59:00Z",
  level: "info",
  module: "daily",
  type: "daily_summary",
  message: "daily summary",
  data: { trades_today: 2, day_pnl: "42.00000000" },
};

const warningEvent: EventLogItem = {
  id: 3,
  ts: "2026-01-15T14:31:00Z",
  level: "warn",
  module: "feed",
  type: "heartbeat.stale",
  message: "heartbeat stale",
  data: { seconds: 31 },
};
