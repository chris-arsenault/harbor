export type ProductView =
  | "dashboard"
  | "trades"
  | "backtests"
  | "lab"
  | "config"
  | "events"
  | "operations";

interface ProductNavProps {
  readonly activeView: ProductView;
  readonly views: ProductView[];
  readonly onViewChange: (view: ProductView) => void;
}

const LABELS: Record<ProductView, string> = {
  dashboard: "Dashboard",
  trades: "Trades",
  backtests: "Backtests",
  lab: "Lab",
  config: "Config",
  events: "Events",
  operations: "Operations",
};

export function ProductNav({ activeView, views, onViewChange }: ProductNavProps) {
  return (
    <nav className="product-nav" aria-label="Product views">
      {views.map((view) => (
        <button
          key={view}
          type="button"
          aria-current={activeView === view ? "page" : undefined}
          className={activeView === view ? "product-nav__button--active" : ""}
          onClick={() => onViewChange(view)}
        >
          {LABELS[view]}
        </button>
      ))}
    </nav>
  );
}

export function productViewLabel(view: ProductView): string {
  return LABELS[view];
}
