import type { VariantEquityCurve } from "../../api/types";

interface VariantEquityChartProps {
  readonly curve: VariantEquityCurve | null;
}

export function VariantEquityChart({ curve }: VariantEquityChartProps) {
  const points = curve?.points ?? [];
  const pointsData = points.map((point) => `${point.ts}:${point.nav}`).join("|");
  const navValues = points.map((point) => Number(point.nav));
  const minNav = Math.min(...navValues, 0);
  const maxNav = Math.max(...navValues, 1);
  const span = Math.max(maxNav - minNav, 1);
  const polyline = points
    .map((point, index) => {
      const x = 24 + (index / Math.max(points.length - 1, 1)) * 292;
      const y = 132 - ((Number(point.nav) - minNav) / span) * 104;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <section className="lab-panel" aria-label="Variant equity">
      <h2>Equity</h2>
      <svg
        className="lab-equity"
        viewBox="0 0 340 160"
        role="img"
        aria-label="Variant equity curve"
        data-points={pointsData}
      >
        <line x1="24" y1="132" x2="316" y2="132" />
        <line x1="24" y1="132" x2="24" y2="20" />
        <polyline points={polyline} />
      </svg>
    </section>
  );
}
