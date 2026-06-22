import { NAV_GROUPS, type ViewId } from "./nav";

export function SideNav({
  active,
  badges,
  onSelect,
}: {
  readonly active: ViewId;
  readonly badges?: Partial<Record<ViewId, string>>;
  readonly onSelect: (id: ViewId) => void;
}) {
  return (
    <nav className="hb-nav" aria-label="Primary">
      {NAV_GROUPS.map((group) => (
        <div className="hb-nav__group" key={group.label}>
          <span className="hb-nav__group-label">{group.label}</span>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-current={active === item.id ? "page" : undefined}
              className={`hb-nav__item${active === item.id ? " hb-nav__item--active" : ""}`}
              onClick={() => onSelect(item.id)}
            >
              <span className="hb-nav__glyph" aria-hidden="true">
                {item.glyph}
              </span>
              {item.label}
              {badges?.[item.id] ? <span className="hb-nav__badge">{badges[item.id]}</span> : null}
            </button>
          ))}
        </div>
      ))}
      <div className="hb-nav__foot">
        harbor · oanda practice
        <br />
        closed-candle research
      </div>
    </nav>
  );
}
