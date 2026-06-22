import type { ReactNode } from "react";

import type { StatusSnapshot } from "../api/types";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import type { ViewId } from "./nav";

export function AppShell({
  status,
  lastMessageAt,
  active,
  badges,
  onSelect,
  onArmClick,
  children,
}: {
  readonly status: StatusSnapshot;
  readonly lastMessageAt: string | null;
  readonly active: ViewId;
  readonly badges?: Partial<Record<ViewId, string>>;
  readonly onSelect: (id: ViewId) => void;
  readonly onArmClick: () => void;
  readonly children: ReactNode;
}) {
  return (
    <div className="hb-app">
      <TopBar status={status} lastMessageAt={lastMessageAt} onArmClick={onArmClick} />
      <div className="hb-body">
        <SideNav active={active} badges={badges} onSelect={onSelect} />
        <main className="hb-main">{children}</main>
      </div>
    </div>
  );
}
