import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ProductNav, type ProductView } from "./ProductNav";

const views: ProductView[] = [
  "workflow",
  "dashboard",
  "trades",
  "backtests",
  "lab",
  "config",
  "events",
  "operations",
];

test("renders every product workflow with workflow selected by default", () => {
  const onViewChange = vi.fn();

  render(<ProductNav activeView="workflow" views={views} onViewChange={onViewChange} />);

  for (const label of [
    "Workflow",
    "Dashboard",
    "Trades",
    "Backtests",
    "Lab",
    "Config",
    "Events",
    "Operations",
  ]) {
    expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
  }
  expect(screen.getByRole("button", { name: "Workflow" })).toHaveAttribute("aria-current", "page");

  fireEvent.click(screen.getByRole("button", { name: "Operations" }));

  expect(onViewChange).toHaveBeenCalledWith("operations");
});
