import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ProductNav, type ProductView } from "./ProductNav";

const views: ProductView[] = [
  "dashboard",
  "trades",
  "backtests",
  "lab",
  "config",
  "events",
  "operations",
];

test("renders every product workflow with dashboard selected by default", () => {
  const onViewChange = vi.fn();

  render(<ProductNav activeView="dashboard" views={views} onViewChange={onViewChange} />);

  for (const label of [
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
  expect(screen.getByRole("button", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");

  fireEvent.click(screen.getByRole("button", { name: "Operations" }));

  expect(onViewChange).toHaveBeenCalledWith("operations");
});
