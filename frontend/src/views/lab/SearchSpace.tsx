import type { OptimizationPreflightResponse } from "../../api/optimizerTypes";
import { titleCase } from "../../ui/format";
import { EmptyState, Panel, Tag } from "../../ui/primitives";

interface SearchParam {
  readonly type: string;
  readonly min?: unknown;
  readonly max?: unknown;
  readonly step?: unknown;
  readonly choices?: unknown[];
}

function searchSpaceEntries(
  preflight: OptimizationPreflightResponse | null
): Array<[string, SearchParam]> {
  const config = preflight?.study_config as
    | { search_space?: Record<string, SearchParam> }
    | undefined;
  const space = config?.search_space;
  return space ? Object.entries(space) : [];
}

function text(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function describe(param: SearchParam): string {
  if (param.type === "categorical") {
    return (param.choices ?? []).map(text).join(", ");
  }
  const step = param.step != null ? ` (step ${text(param.step)})` : "";
  return `${text(param.min)} … ${text(param.max)}${step}`;
}

export function SearchSpacePanel({
  preflight,
}: {
  readonly preflight: OptimizationPreflightResponse | null;
}) {
  const entries = searchSpaceEntries(preflight);
  if (entries.length === 0) {
    return (
      <Panel title="Search space" label="Search space">
        <EmptyState glyph="⚙" title="Run preflight to see what the optimizer tunes" />
      </Panel>
    );
  }
  return (
    <Panel title="Search space" note={`${entries.length} dimensions`} label="Search space">
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Type</th>
              <th>Range / choices</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([name, param]) => (
              <tr key={name}>
                <td className="cell-strong">{titleCase(name)}</td>
                <td>
                  <Tag tone="muted">{param.type}</Tag>
                </td>
                <td className="mute">{describe(param)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
