import type { StatusSnapshot } from "../api/types";

interface StatusStripProps {
  readonly status: StatusSnapshot;
}

export function StatusStrip({ status }: StatusStripProps) {
  const facts = [
    ["Bot", status.bot_state],
    ["Session", status.session_phase],
    ["Connection", status.connection_health],
    ["Mode", status.mode],
    ["Kill switch", status.kill_switch_state],
  ];

  return (
    <section className="status-strip" aria-label="System status">
      {facts.map(([label, value]) => (
        <div className="status-strip__item" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}
