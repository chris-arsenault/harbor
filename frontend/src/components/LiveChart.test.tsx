import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { LiveChart } from "./LiveChart";
import type { LiveChartAdapter, LiveChartHandle } from "./chartAdapter";
import type { CandlePoint, MarkersPayload, SessionLevelSnapshot } from "../api/types";

test("LiveChart sends candles, levels, and server-authored markers to the adapter", () => {
  const handle: LiveChartHandle = {
    setCandles: vi.fn(),
    setLevels: vi.fn(),
    setMarkers: vi.fn(),
    destroy: vi.fn(),
  };
  const adapter: LiveChartAdapter = {
    mount: vi.fn(() => handle),
  };

  render(<LiveChart candles={candles} levels={levels} markers={markers} adapter={adapter} />);

  expect(screen.getByLabelText("Live chart")).toBeInTheDocument();
  expect(adapter.mount).toHaveBeenCalledTimes(1);
  expect(handle.setCandles).toHaveBeenCalledWith(candles);
  expect(handle.setLevels).toHaveBeenCalledWith(levels);
  expect(handle.setMarkers).toHaveBeenCalledWith(markers);
});

test("LiveChart uses API marker payloads directly instead of detecting strategy facts", () => {
  const handle: LiveChartHandle = {
    setCandles: vi.fn(),
    setLevels: vi.fn(),
    setMarkers: vi.fn(),
    destroy: vi.fn(),
  };
  const adapter: LiveChartAdapter = {
    mount: vi.fn(() => handle),
  };
  const serverMarkers: MarkersPayload = {
    ...markers,
    markers: [{ ...markers.markers[0], price: "9.99990000", label: "server marker" }],
  };

  render(<LiveChart candles={candles} levels={levels} markers={serverMarkers} adapter={adapter} />);

  expect(handle.setMarkers).toHaveBeenCalledWith(serverMarkers);
  expect(handle.setMarkers).not.toHaveBeenCalledWith(markers);
});

const candles: CandlePoint[] = [
  {
    instrument: "EUR_USD",
    ts: "2026-01-15T14:00:00Z",
    open: "1.10000000",
    high: "1.10500000",
    low: "1.09900000",
    close: "1.10400000",
    volume: 100,
    complete: true,
  },
];

const levels: SessionLevelSnapshot = {
  date: "2026-01-15",
  instrument: "EUR_USD",
  asia_high: "1.11000000",
  asia_low: "1.10000000",
  london_high: "1.11500000",
  london_low: "1.10500000",
  swept_levels: ["asia_low"],
  taken_levels: [],
};

const markers: MarkersPayload = {
  markers: [
    {
      kind: "sweep",
      ts: "2026-01-15T14:31:00Z",
      instrument: "EUR_USD",
      label: "asia_low swept",
      price: "1.10000000",
      direction: "bullish",
      level_name: "asia_low",
    },
  ],
  fvgs: [
    {
      id: 5,
      ts: "2026-01-15T14:31:00Z",
      instrument: "EUR_USD",
      type: "bullish",
      top: "1.10600000",
      bottom: "1.10400000",
      midpoint: "1.10500000",
      sweep_id: 3,
    },
  ],
  signals: [
    {
      id: 7,
      ts: "2026-01-15T14:31:00Z",
      instrument: "EUR_USD",
      direction: "long",
      entry: "1.10500000",
      stop: "1.10200000",
      target: "1.11100000",
      status: "filled",
    },
  ],
  trades: [
    {
      id: 11,
      signal_id: 7,
      side: "long",
      units: "1000.0000",
      entry_price: "1.10500000",
      entry_ts: "2026-01-15T14:31:00Z",
      exit_price: "1.11100000",
      exit_ts: "2026-01-15T14:45:00Z",
      pnl: "60.00000000",
      r_multiple: "2.0000",
      exit_reason: "target",
    },
  ],
};
