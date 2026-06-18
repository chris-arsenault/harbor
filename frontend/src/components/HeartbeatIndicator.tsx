export const HEARTBEAT_STALE_AFTER_SECONDS = 30;

interface HeartbeatIndicatorProps {
  readonly lastMessageAt: string | null;
  readonly now?: string;
  readonly staleAfterSeconds?: number;
}

export function HeartbeatIndicator({
  lastMessageAt,
  now,
  staleAfterSeconds = HEARTBEAT_STALE_AFTER_SECONDS,
}: HeartbeatIndicatorProps) {
  const state = heartbeatState(lastMessageAt, now, staleAfterSeconds);

  return (
    <div className={`heartbeat heartbeat--${state}`} aria-label="WebSocket heartbeat">
      <span className="heartbeat__dot" aria-hidden="true" />
      <span>{state}</span>
    </div>
  );
}

function heartbeatState(
  lastMessageAt: string | null,
  now: string | undefined,
  staleAfterSeconds: number
) {
  if (lastMessageAt === null) {
    return "missing";
  }
  const current = now ? Date.parse(now) : Date.now();
  const last = Date.parse(lastMessageAt);
  if (!Number.isFinite(last)) {
    return "missing";
  }
  return current - last > staleAfterSeconds * 1000 ? "stale" : "fresh";
}
