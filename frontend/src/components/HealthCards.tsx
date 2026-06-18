import type { StatusSnapshot } from "../api/types";

interface HealthCardsProps {
  readonly status: StatusSnapshot;
}

export function HealthCards({ status }: HealthCardsProps) {
  const cards = [
    ["Day P&L", status.day_pnl],
    ["Account NAV", status.account_nav ?? "n/a"],
    ["Open positions", String(status.open_positions ?? "n/a")],
    ["Trades today", `${status.trades_today} / ${status.max_trades_per_day}`],
  ];

  return (
    <section className="health-grid" aria-label="Health summary">
      {cards.map(([label, value]) => (
        <article className="health-card" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </article>
      ))}
    </section>
  );
}
