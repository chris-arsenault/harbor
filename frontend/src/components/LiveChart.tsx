import { useEffect, useRef } from "react";

import type { CandlePoint, MarkersPayload, SessionLevelSnapshot } from "../api/types";
import {
  lightweightChartsAdapter,
  type LiveChartAdapter,
  type LiveChartHandle,
} from "./chartAdapter";

interface LiveChartProps {
  readonly candles: CandlePoint[];
  readonly levels: SessionLevelSnapshot | null;
  readonly markers: MarkersPayload;
  readonly adapter?: LiveChartAdapter;
}

export function LiveChart({
  candles,
  levels,
  markers,
  adapter = lightweightChartsAdapter,
}: LiveChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<LiveChartHandle | null>(null);

  useEffect(() => {
    if (containerRef.current === null) {
      return;
    }

    const chart = adapter.mount(containerRef.current);
    chartRef.current = chart;
    return () => {
      chart.destroy();
      chartRef.current = null;
    };
  }, [adapter]);

  useEffect(() => {
    chartRef.current?.setCandles(candles);
    chartRef.current?.setLevels(levels);
    chartRef.current?.setMarkers(markers);
  }, [candles, levels, markers]);

  return (
    <section className="chart-shell">
      <div className="live-chart" ref={containerRef} aria-label="Live chart" />
      <div className="chart-facts" aria-label="Server-authored chart facts">
        <span>{candles.length} candles</span>
        <span>{markers.markers.length} sweeps</span>
        <span>{markers.fvgs.length} FVGs</span>
        <span>{markers.signals.length} signals</span>
        <span>{markers.trades.length} trades</span>
      </div>
    </section>
  );
}
