import type { ReactNode } from "react";

import { cx } from "./cx";

/* ---------------------------------------------------------------- View head */
export function ViewHead({
  kicker,
  title,
  sub,
  actions,
}: {
  readonly kicker: string;
  readonly title: string;
  readonly sub?: string;
  readonly actions?: ReactNode;
}) {
  return (
    <header className="view__head">
      <div className="view__titles">
        <span className="view__kicker">{kicker}</span>
        <h1 className="view__title">{title}</h1>
        {sub ? <p className="view__sub">{sub}</p> : null}
      </div>
      {actions ? <div className="view__actions">{actions}</div> : null}
    </header>
  );
}

/* ---------------------------------------------------------------- Panel */
export function Panel({
  title,
  note,
  actions,
  children,
  variant,
  flush,
  label,
}: {
  readonly title?: string;
  readonly note?: ReactNode;
  readonly actions?: ReactNode;
  readonly children: ReactNode;
  readonly variant?: "plain" | "inset" | "accent";
  readonly flush?: boolean;
  readonly label?: string;
}) {
  const className = cx("panel", variant && `panel--${variant}`, flush && "panel--flush");
  const region = label ?? title;
  return (
    <section className={className} aria-label={region}>
      {title ? (
        <div className="panel__head">
          <h2 className="panel__title">
            {title}
            {note ? <span className="panel__title-note">{note}</span> : null}
          </h2>
          {actions ? <div className="panel__actions">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

/* ---------------------------------------------------------------- Stat tile */
export function StatTile({
  label,
  value,
  tone,
  sub,
}: {
  readonly label: string;
  readonly value: ReactNode;
  readonly tone?: "up" | "down" | "beam" | "warn";
  readonly sub?: ReactNode;
}) {
  const coloredValue = tone === "up" || tone === "down";
  const tileClass = cx("tile", tone && `tile--${tone}`);
  const valueClass = cx("tile__value", coloredValue && `tile__value--${tone}`);
  return (
    <div className={tileClass}>
      <span className="tile__label">{label}</span>
      <span className={valueClass}>{value}</span>
      {sub !== undefined ? <span className="tile__sub">{sub}</span> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Tag */
export function Tag({
  children,
  tone = "muted",
  plain,
}: {
  readonly children: ReactNode;
  readonly tone?: "up" | "down" | "warn" | "info" | "beam" | "muted";
  readonly plain?: boolean;
}) {
  return <span className={cx("tag", `tag--${tone}`, plain && "tag--plain")}>{children}</span>;
}

/* ---------------------------------------------------------------- Tabs */
export interface TabItem {
  readonly id: string;
  readonly label: string;
}

export function Tabs({
  tabs,
  active,
  onSelect,
  ariaLabel,
}: {
  readonly tabs: TabItem[];
  readonly active: string;
  readonly onSelect: (id: string) => void;
  readonly ariaLabel: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === active}
          className={cx("tab", tab.id === active && "tab--active")}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- Field */
export function Field({
  label,
  children,
}: {
  readonly label: string;
  readonly children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
    </label>
  );
}

/* ---------------------------------------------------------------- Notice */
export function Notice({
  children,
  tone,
}: {
  readonly children: ReactNode;
  readonly tone?: "error" | "ok";
}) {
  return <p className={cx("notice", tone && `notice--${tone}`)}>{children}</p>;
}

/* ---------------------------------------------------------------- Empty */
export function EmptyState({
  glyph = "◷",
  title,
  hint,
}: {
  readonly glyph?: string;
  readonly title: string;
  readonly hint?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty__glyph" aria-hidden="true">
        {glyph}
      </span>
      <span className="empty__title">{title}</span>
      {hint ? <span className="empty__hint">{hint}</span> : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Meter (svg) */
export function Meter({ ratio }: { readonly ratio: number }) {
  const clamped = Math.max(0, Math.min(1, ratio));
  return (
    <svg
      className="meter"
      viewBox="0 0 100 6"
      preserveAspectRatio="none"
      aria-hidden="true"
      width="100%"
      height="6"
    >
      <rect x="0" y="0" width="100" height="6" rx="3" className="gauge__track-bg" />
      <rect
        x="0"
        y="0"
        width={(clamped * 100).toFixed(1)}
        height="6"
        rx="3"
        className="gauge__fill-bar"
      />
    </svg>
  );
}
