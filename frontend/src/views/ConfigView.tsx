import { useMemo, useState } from "react";

import type { ConfigEntry, ConfigSnapshot, ConfigUpdateRequest } from "../api/types";
import { displayValue } from "../utils/format";
import { EmptyState, Panel, ViewHead } from "../ui/primitives";

interface DiffItem {
  readonly key: string;
  readonly before: unknown;
  readonly after: unknown;
}

function currentValue(entry: ConfigEntry): unknown {
  return entry.value.value;
}

function parseLike(original: unknown, raw: string): unknown {
  if (typeof original === "number") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : original;
  }
  if (typeof original === "boolean") {
    return raw === "true";
  }
  return raw;
}

function computeDiff(values: ConfigEntry[], edits: Record<string, string | undefined>): DiffItem[] {
  const diff: DiffItem[] = [];
  for (const entry of values) {
    const raw = edits[entry.key];
    if (raw === undefined) {
      continue;
    }
    const before = currentValue(entry);
    const after = parseLike(before, raw);
    if (String(before) !== String(after)) {
      diff.push({ key: entry.key, before, after });
    }
  }
  return diff;
}

function Editor({
  values,
  edits,
  onChange,
}: {
  readonly values: ConfigEntry[];
  readonly edits: Record<string, string | undefined>;
  readonly onChange: (key: string, raw: string) => void;
}) {
  return (
    <div className="fieldset">
      {values.map((entry) => (
        <label className="field" key={entry.key}>
          <span className="field__label">{entry.key}</span>
          <input
            className="input"
            value={edits[entry.key] ?? String(currentValue(entry))}
            onChange={(event) => onChange(entry.key, event.target.value)}
          />
        </label>
      ))}
    </div>
  );
}

function DiffList({ diff }: { readonly diff: DiffItem[] }) {
  if (diff.length === 0) {
    return <p className="mute">No pending changes.</p>;
  }
  return (
    <dl className="kv">
      {diff.map((item) => (
        <div key={item.key} className="row">
          <dt>{item.key}</dt>
          <dd>
            {displayValue(item.before)} →{" "}
            <span className="beam-text">{displayValue(item.after)}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ConfigView({
  snapshot,
  pending,
  onUpdateConfig,
}: {
  readonly snapshot: ConfigSnapshot;
  readonly pending: boolean;
  readonly onUpdateConfig: (payload: ConfigUpdateRequest) => void | Promise<void>;
}) {
  const [edits, setEdits] = useState<Record<string, string | undefined>>({});
  const [confirmation, setConfirmation] = useState("");
  const diff = useMemo(() => computeDiff(snapshot.values, edits), [snapshot.values, edits]);

  function save() {
    const updates: Record<string, Record<string, unknown>> = {};
    for (const item of diff) {
      updates[item.key] = { value: item.after };
    }
    void onUpdateConfig({ updates, confirmation });
  }

  return (
    <section className="view" aria-label="Config">
      <ViewHead kicker="System" title="Config" sub="Edit runtime strategy configuration." />
      {snapshot.values.length === 0 ? (
        <Panel title="Configuration" label="Configuration">
          <EmptyState glyph="⛭" title="No configuration values" />
        </Panel>
      ) : (
        <>
          <Panel title="Values" label="Values">
            <Editor
              values={snapshot.values}
              edits={edits}
              onChange={(key, raw) => setEdits((prev) => ({ ...prev, [key]: raw }))}
            />
          </Panel>
          <Panel
            title="Pending changes"
            note={`${diff.length}`}
            label="Pending changes"
            actions={
              <div className="row">
                <input
                  className="input"
                  aria-label="Confirmation"
                  placeholder="confirmation"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                />
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={pending || diff.length === 0 || confirmation.length === 0}
                  onClick={save}
                >
                  Save config
                </button>
              </div>
            }
          >
            <DiffList diff={diff} />
          </Panel>
        </>
      )}
    </section>
  );
}
