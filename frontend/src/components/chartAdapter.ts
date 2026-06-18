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
      background: { type: ColorType.Solid, color: "#ffffff" },
      textColor: "#26312b",
    },
    grid: {
      vertLines: { color: "#edf1ee" },
      horzLines: { color: "#edf1ee" },
    },
    rightPriceScale: {
      borderColor: "#d6ded8",
    },
    timeScale: {
      borderColor: "#d6ded8",
      timeVisible: true,
    },
  });
  const candles = chart.addSeries(CandlestickSeries, {
    upColor: "#1b8a5a",
    downColor: "#c33f32",
    borderVisible: false,
    wickUpColor: "#1b8a5a",
    wickDownColor: "#c33f32",
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
        levelLine(candles, Number(levels.asia_high), "Asia high", "#c9781d"),
        levelLine(candles, Number(levels.asia_low), "Asia low", "#c9781d"),
        levelLine(candles, Number(levels.london_high), "London high", "#2867b2"),
        levelLine(candles, Number(levels.london_low), "London low", "#2867b2"),
      ];
    },
    setMarkers: (markers) => {
      overlayLines = removePriceLines(candles, overlayLines);
      markerPlugin.setMarkers(markerData(markers));
      overlayLines = [
        ...markers.fvgs.flatMap((fvg) => [
          overlayLine(candles, Number(fvg.top), "FVG top", "#7b5f2a"),
          overlayLine(candles, Number(fvg.bottom), "FVG bottom", "#7b5f2a"),
        ]),
        ...markers.signals.flatMap((signal) => [
          overlayLine(candles, Number(signal.entry), "Entry", "#1b8a5a"),
          overlayLine(candles, Number(signal.stop), "Stop", "#c33f32"),
          overlayLine(candles, Number(signal.target), "Target", "#2867b2"),
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
    color: marker.direction === "bearish" ? "#c33f32" : "#1b8a5a",
    text: marker.label,
  }));
  const tradeMarkers: SeriesMarker<Time>[] = markers.trades.map((trade) => ({
    time: utcTimestamp(trade.exit_ts ?? trade.entry_ts),
    position: "atPriceMiddle",
    shape: "square",
    color: trade.side === "short" ? "#c33f32" : "#1b8a5a",
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
