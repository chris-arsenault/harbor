import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import type { ConfigSnapshot } from "../../api/types";
import { ConfigView } from "./ConfigView";

test("renders editable config entries with diff preview and guarded save", () => {
  const onUpdateConfig = vi.fn();

  render(<ConfigView snapshot={snapshot} pending={false} onUpdateConfig={onUpdateConfig} />);

  expect(screen.getByRole("heading", { name: "Config" })).toBeInTheDocument();
  expect(screen.getByLabelText("risk_per_trade_pct")).toHaveValue("0.5");

  fireEvent.change(screen.getByLabelText("risk_per_trade_pct"), {
    target: { value: "0.7" },
  });
  fireEvent.change(screen.getByLabelText("Confirmation"), {
    target: { value: "APPLY_CONFIG" },
  });

  expect(screen.getByText("Diff Preview")).toBeInTheDocument();
  expect(screen.getByText(/risk_per_trade_pct: 0.5 -> 0.7/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Save config" }));

  expect(onUpdateConfig).toHaveBeenCalledWith({
    updates: { risk_per_trade_pct: { value: 0.7 } },
    confirmation: "APPLY_CONFIG",
  });
});

const snapshot: ConfigSnapshot = {
  values: [
    {
      key: "instrument",
      value: { value: "EUR_USD" },
    },
    {
      key: "risk_per_trade_pct",
      value: { value: 0.5, bounds: { min: 0.1, max: 1.0 } },
    },
  ],
};
