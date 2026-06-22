export type ViewId =
  | "cockpit"
  | "journal"
  | "data"
  | "lab"
  | "validation"
  | "operations"
  | "config"
  | "events";

export interface NavItem {
  readonly id: ViewId;
  readonly label: string;
  readonly glyph: string;
}

export interface NavGroup {
  readonly label: string;
  readonly items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Monitor",
    items: [
      { id: "cockpit", label: "Cockpit", glyph: "◎" },
      { id: "journal", label: "Journal", glyph: "≣" },
    ],
  },
  {
    label: "Research",
    items: [
      { id: "data", label: "Data", glyph: "⛁" },
      { id: "lab", label: "Lab", glyph: "⚗" },
      { id: "validation", label: "Validation", glyph: "⎍" },
    ],
  },
  {
    label: "System",
    items: [
      { id: "operations", label: "Operations", glyph: "⚙" },
      { id: "config", label: "Config", glyph: "⛭" },
      { id: "events", label: "Events", glyph: "❯" },
    ],
  },
];

export const VIEW_LABELS: Record<ViewId, string> = {
  cockpit: "Cockpit",
  journal: "Journal",
  data: "Data",
  lab: "Lab",
  validation: "Validation",
  operations: "Operations",
  config: "Config",
  events: "Events",
};
