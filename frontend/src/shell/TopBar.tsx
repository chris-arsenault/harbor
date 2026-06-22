import type { StatusSnapshot } from "../api/types";
import { cx } from "../ui/cx";
import { fmtInt, fmtNum, fmtSigned, valueTone } from "../ui/format";
import { LiveValue } from "../ui/LiveValue";

interface BeatState {
  readonly state: "fresh" | "stale" | "missing";
  readonly label: string;
}

function beatState(lastMessageAt: string | null, staleAfter = 30): BeatState {
  if (!lastMessageAt) {
    return { state: "missing", label: "no signal" };
  }
  const seconds = (Date.now() - Date.parse(lastMessageAt)) / 1000;
  if (Number.isNaN(seconds)) {
    return { state: "missing", label: "no signal" };
  }
  return seconds <= staleAfter
    ? { state: "fresh", label: "live" }
    : { state: "stale", label: "stale" };
}

function Vital({
  label,
  value,
  raw,
  tone,
}: {
  readonly label: string;
  readonly value: string;
  readonly raw?: unknown;
  readonly tone?: "up" | "down";
}) {
  const valueClass = cx("hb-vital__value", tone === "up" && "pos", tone === "down" && "neg");
  return (
    <div className="hb-vital">
      <span className="hb-vital__label">{label}</span>
      <LiveValue value={raw} className={valueClass}>
        {value}
      </LiveValue>
    </div>
  );
}

export function TopBar({
  status,
  lastMessageAt,
  onArmClick,
}: {
  readonly status: StatusSnapshot;
  readonly lastMessageAt: string | null;
  readonly onArmClick: () => void;
}) {
  const beat = beatState(lastMessageAt);
  const armed = status.trading_enabled;
  const live = status.mode === "live";
  return (
    <header className="hb-topbar">
      <div className="hb-brand">
        <span className="hb-brand__beacon" aria-hidden="true" />
        Harbor
      </div>
      <span className={`hb-mode hb-mode--${live ? "live" : "practice"}`}>{status.mode}</span>

      <div className="hb-vitals" aria-label="Account vitals">
        <Vital
          label="Day P&L"
          value={fmtSigned(status.day_pnl)}
          raw={status.day_pnl}
          tone={valueTone(status.day_pnl)}
        />
        <Vital label="NAV" value={fmtNum(status.account_nav)} raw={status.account_nav} />
        <Vital
          label="Unreal"
          value={fmtSigned(status.unrealized_pnl)}
          raw={status.unrealized_pnl}
          tone={valueTone(status.unrealized_pnl)}
        />
        <Vital label="Open" value={fmtInt(status.open_positions ?? 0)} />
        <Vital label="Trades" value={`${status.trades_today}/${status.max_trades_per_day}`} />
      </div>

      <span className={`hb-beat hb-beat--${beat.state}`} aria-label="Feed heartbeat">
        <span className="hb-beat__dot" aria-hidden="true" />
        {beat.label}
      </span>

      <button
        type="button"
        className={`hb-arm${armed ? " hb-arm--on" : ""}`}
        onClick={onArmClick}
        aria-label="Trading state"
      >
        <span className="hb-arm__led" aria-hidden="true" />
        {armed ? "Armed" : "Disarmed"}
      </button>
    </header>
  );
}
