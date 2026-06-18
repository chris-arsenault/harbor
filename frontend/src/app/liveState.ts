import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

import { useLiveConnection } from "../api/hooks";
import type {
  CandlePoint,
  ChartMarker,
  EventLogItem,
  FvgBox,
  LabStatusEnvelope,
  LabVariantOverview,
  MarkersPayload,
  SessionLevelSnapshot,
  SignalMarker,
  StatusSnapshot,
  TradeMarker,
  VariantEquityCurve,
  VariantEquityEnvelope,
  VariantTrade,
  WebSocketEnvelope,
} from "../api/types";

export function useLiveState() {
  const [liveStatus, setLiveStatus] = useState<StatusSnapshot | null>(null);
  const [liveLevels, setLiveLevels] = useState<SessionLevelSnapshot | null>(null);
  const [liveCandles, setLiveCandles] = useState<CandlePoint[]>([]);
  const [liveMarkers, setLiveMarkers] = useState<MarkersPayload>(emptyMarkers());
  const [liveEvents, setLiveEvents] = useState<EventLogItem[]>([]);
  const [liveEquityCurves, setLiveEquityCurves] = useState<VariantEquityCurve[]>([]);
  const [labLiveStatus, setLabLiveStatus] = useState<string | null>(null);
  const [lastWsMessageAt, setLastWsMessageAt] = useState<string | null>(null);

  const handleEnvelope = useCallback((envelope: WebSocketEnvelope) => {
    setLastWsMessageAt(envelope.sent_at);
    applyLiveEnvelope(envelope, {
      setLiveStatus,
      setLiveLevels,
      setLiveCandles,
      setLiveMarkers,
      setLiveEvents,
      setLiveEquityCurves,
      setLabLiveStatus,
    });
  }, []);

  useLiveConnection({
    onEnvelope: handleEnvelope,
    onHeartbeat: setLastWsMessageAt,
  });

  return {
    liveStatus,
    liveLevels,
    liveCandles,
    liveMarkers,
    liveEvents,
    liveEquityCurves,
    labLiveStatus,
    lastWsMessageAt,
  };
}

export type LiveState = ReturnType<typeof useLiveState>;

interface LiveSetters {
  readonly setLiveStatus: (value: StatusSnapshot) => void;
  readonly setLiveLevels: (value: SessionLevelSnapshot) => void;
  readonly setLiveCandles: Dispatch<SetStateAction<CandlePoint[]>>;
  readonly setLiveMarkers: Dispatch<SetStateAction<MarkersPayload>>;
  readonly setLiveEvents: Dispatch<SetStateAction<EventLogItem[]>>;
  readonly setLiveEquityCurves: Dispatch<SetStateAction<VariantEquityCurve[]>>;
  readonly setLabLiveStatus: Dispatch<SetStateAction<string | null>>;
}

function applyLiveEnvelope(envelope: WebSocketEnvelope, setters: LiveSetters) {
  applyDashboardEnvelope(envelope, setters);
  applyLabEnvelope(envelope, setters);
}

function applyDashboardEnvelope(envelope: WebSocketEnvelope, setters: LiveSetters) {
  const payload = envelope.payload;
  switch (envelope.type) {
    case "status":
      setters.setLiveStatus(payload as unknown as StatusSnapshot);
      break;
    case "level_update":
      setters.setLiveLevels(payload as unknown as SessionLevelSnapshot);
      break;
    case "candle":
      setters.setLiveCandles((candles) =>
        mergeCandles(candles, [payload as unknown as CandlePoint])
      );
      break;
    case "sweep":
      appendMarker(setters.setLiveMarkers, "markers", payload as unknown as ChartMarker);
      break;
    case "fvg":
      appendMarker(setters.setLiveMarkers, "fvgs", payload as unknown as FvgBox);
      break;
    case "signal":
      appendMarker(setters.setLiveMarkers, "signals", payload as unknown as SignalMarker);
      break;
    case "trade":
      appendMarker(setters.setLiveMarkers, "trades", payload as unknown as TradeMarker);
      break;
    case "log":
      setters.setLiveEvents((events) => [payload as unknown as EventLogItem, ...events]);
      break;
  }
}

function applyLabEnvelope(envelope: WebSocketEnvelope, setters: LiveSetters) {
  const payload = envelope.payload;
  switch (envelope.type) {
    case "variant_trade": {
      const trade = payload as unknown as VariantTrade;
      setters.setLabLiveStatus(`variant ${trade.variant_id} trade ${trade.pnl}`);
      break;
    }
    case "variant_equity": {
      const equity = payload as unknown as VariantEquityEnvelope;
      setters.setLiveEquityCurves((curves) => mergeEquityCurves(curves, equity));
      break;
    }
    case "lab_status": {
      const status = payload as unknown as LabStatusEnvelope;
      setters.setLabLiveStatus(status.message ?? status.status);
      break;
    }
  }
}

function appendMarker<TKey extends keyof MarkersPayload>(
  update: Dispatch<SetStateAction<MarkersPayload>>,
  key: TKey,
  value: MarkersPayload[TKey][number]
) {
  update((markers) => ({
    ...markers,
    [key]: [...markers[key], value],
  }));
}

export function mergeCandles(base: CandlePoint[], live: CandlePoint[]) {
  const byTimestamp = new Map<string, CandlePoint>();
  for (const candle of [...base, ...live]) {
    byTimestamp.set(candle.ts, candle);
  }
  return [...byTimestamp.values()].sort((left, right) => left.ts.localeCompare(right.ts));
}

export function mergeMarkers(base: MarkersPayload, live: MarkersPayload): MarkersPayload {
  return {
    markers: [...base.markers, ...live.markers],
    fvgs: [...base.fvgs, ...live.fvgs],
    signals: [...base.signals, ...live.signals],
    trades: [...base.trades, ...live.trades],
  };
}

export function mergeEvents(
  liveEvents: EventLogItem[],
  fetchedEvents: EventLogItem[]
): EventLogItem[] {
  const byKey = new Map<string, EventLogItem>();
  for (const event of [...liveEvents, ...fetchedEvents]) {
    byKey.set(`${event.id}-${event.ts}`, event);
  }
  return [...byKey.values()].sort((left, right) => right.ts.localeCompare(left.ts)).slice(0, 200);
}

export function mergeVariantOverview(
  base: LabVariantOverview,
  liveEquityCurves: VariantEquityCurve[]
): LabVariantOverview {
  if (liveEquityCurves.length === 0) {
    return base;
  }
  const curvesByVariant = new Map(base.equity_curves.map((curve) => [curve.variant_id, curve]));
  for (const curve of liveEquityCurves) {
    curvesByVariant.set(curve.variant_id, curve);
  }
  return {
    ...base,
    equity_curves: [...curvesByVariant.values()],
  };
}

function mergeEquityCurves(
  curves: VariantEquityCurve[],
  envelope: VariantEquityEnvelope
): VariantEquityCurve[] {
  const nextCurve = {
    variant_id: envelope.variant_id,
    points: envelope.points,
  };
  const existing = curves.filter((curve) => curve.variant_id !== envelope.variant_id);
  return [...existing, nextCurve];
}

export function emptyMarkers(): MarkersPayload {
  return { markers: [], fvgs: [], signals: [], trades: [] };
}

export function emptyVariantOverview(): LabVariantOverview {
  return { variants: [], leaderboard: [], equity_curves: [], data_separation: {} };
}

export function emptyStatus(): StatusSnapshot {
  return {
    bot_state: "IDLE",
    session_phase: "closed",
    connection_health: "unknown",
    mode: "practice",
    trading_enabled: false,
    trading_controls_available: false,
    kill_switch_state: "armed",
    day_pnl: "0",
    trades_today: 0,
    max_trades_per_day: 0,
    account_nav: null,
    open_positions: null,
    unrealized_pnl: null,
    last_heartbeat: null,
    promoted_variant: null,
    reconciliation_state: null,
    open_position: null,
    notifier_state: null,
    deployment: null,
  };
}
