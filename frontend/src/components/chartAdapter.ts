import {
  CandlestickSeries,
  ColorType,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";

import type { CandlePoint, MarkersPayload, SessionLevelSnapshot } from "../api/types";

export interface LiveChartAdapter {
  mount: (container: HTMLElement) => LiveChartHandle;
}

export interface LiveChartHandle {
  setCandles: (candles: CandlePoint[]) => void;
  setLevels: (levels: SessionLevelSnapshot | null) => void;
  setMarkers: (markers: MarkersPayload) => void;
  destroy: () => void;
}

export const lightweightChartsAdapter: LiveChartAdapter = {
  mount: (container) => mountLightweightChart(container),
};

function mountLightweightChart(container: HTMLElement): LiveChartHandle {
  const chart: IChartApi = createChart(container, {
    height: 420,
    width: Math.max(container.clientWidth, 720),
    layout: {
      background: { type: ColorType.Solid, color: "#060c0f" },
      textColor: "#92a6ac",
    },
    grid: {
      vertLines: { color: "#13202700" },
      horzLines: { color: "#162229" },
    },
    rightPriceScale: {
      borderColor: "#22343c",
    },
    timeScale: {
      borderColor: "#22343c",
      timeVisible: true,
    },
  });
  const candles = chart.addSeries(CandlestickSeries, {
    upColor: "#34c08b",
    downColor: "#ea5a4e",
    borderVisible: false,
    wickUpColor: "#34c08b",
    wickDownColor: "#ea5a4e",
  });
  const markerPlugin: ISeriesMarkersPluginApi<Time> = createSeriesMarkers(candles, []);
  let levelLines: IPriceLine[] = [];
  let overlayLines: IPriceLine[] = [];

  return {
    setCandles: (candlePoints) => {
      candles.setData(candlePoints.map(candleData));
      chart.timeScale().fitContent();
    },
    setLevels: (levels) => {
      levelLines = removePriceLines(candles, levelLines);
      if (levels === null) {
        return;
      }
      levelLines = [
        levelLine(candles, Number(levels.asia_high), "Asia high", "#f2ab3c"),
        levelLine(candles, Number(levels.asia_low), "Asia low", "#f2ab3c"),
        levelLine(candles, Number(levels.london_high), "London high", "#54a2e2"),
        levelLine(candles, Number(levels.london_low), "London low", "#54a2e2"),
      ];
    },
    setMarkers: (markers) => {
      overlayLines = removePriceLines(candles, overlayLines);
      markerPlugin.setMarkers(markerData(markers));
      overlayLines = [
        ...markers.fvgs.flatMap((fvg) => [
          overlayLine(candles, Number(fvg.top), "FVG top", "#8a7440"),
          overlayLine(candles, Number(fvg.bottom), "FVG bottom", "#8a7440"),
        ]),
        ...markers.signals.flatMap((signal) => [
          overlayLine(candles, Number(signal.entry), "Entry", "#34c08b"),
          overlayLine(candles, Number(signal.stop), "Stop", "#ea5a4e"),
          overlayLine(candles, Number(signal.target), "Target", "#39d6cb"),
        ]),
      ];
    },
    destroy: () => chart.remove(),
  };
}

function candleData(candle: CandlePoint): CandlestickData<UTCTimestamp> {
  return {
    time: utcTimestamp(candle.ts),
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
  };
}

function markerData(markers: MarkersPayload): SeriesMarker<Time>[] {
  const sweepMarkers: SeriesMarker<Time>[] = markers.markers.map((marker) => ({
    time: utcTimestamp(marker.ts),
    position: marker.direction === "bearish" ? "aboveBar" : "belowBar",
    shape: marker.direction === "bearish" ? "arrowDown" : "arrowUp",
    color: marker.direction === "bearish" ? "#ea5a4e" : "#34c08b",
    text: marker.label,
  }));
  const tradeMarkers: SeriesMarker<Time>[] = markers.trades.map((trade) => ({
    time: utcTimestamp(trade.exit_ts ?? trade.entry_ts),
    position: "atPriceMiddle",
    shape: "square",
    color: trade.side === "short" ? "#ea5a4e" : "#34c08b",
    text: trade.exit_reason ?? "trade",
    price: Number(trade.exit_price ?? trade.entry_price),
  }));

  return [...sweepMarkers, ...tradeMarkers];
}

function levelLine(series: ISeriesApi<"Candlestick">, price: number, title: string, color: string) {
  return series.createPriceLine({
    price,
    color,
    lineWidth: 1,
    lineStyle: LineStyle.Solid,
    axisLabelVisible: true,
    title,
  });
}

function overlayLine(
  series: ISeriesApi<"Candlestick">,
  price: number,
  title: string,
  color: string
) {
  return series.createPriceLine({
    price,
    color,
    lineWidth: 1,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title,
  });
}

function removePriceLines(series: ISeriesApi<"Candlestick">, lines: IPriceLine[]) {
  for (const line of lines) {
    series.removePriceLine(line);
  }
  return [];
}

function utcTimestamp(value: string): UTCTimestamp {
  return Math.floor(Date.parse(value) / 1000) as UTCTimestamp;
}
