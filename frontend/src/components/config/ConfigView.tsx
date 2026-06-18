import { useMemo, useState } from "react";

import type { ConfigSnapshot, ConfigUpdateRequest } from "../../api/types";
import { ConfigDiff } from "./ConfigDiff";
import { ConfigEditor } from "./ConfigEditor";

interface ConfigViewProps {
  readonly snapshot: ConfigSnapshot;
  readonly pending: boolean;
  readonly onUpdateConfig: (payload: ConfigUpdateRequest) => void | Promise<void>;
}

export function ConfigView({ snapshot, pending, onUpdateConfig }: ConfigViewProps) {
  const [editedValues, setEditedValues] = useState<Record<string, unknown>>({});
  const [confirmation, setConfirmation] = useState("");
  const diff = useMemo(() => buildDiff(snapshot, editedValues), [snapshot, editedValues]);

  return (
    <section className="product-view config-view" aria-label="Config page">
      <div className="product-view__header">
        <h2>Config</h2>
      </div>
      <ConfigEditor
        values={snapshot.values}
        editedValues={editedValues}
        onChange={(key, value) =>
          setEditedValues((current) => ({
            ...current,
            [key]: parseEditedValue(snapshot, key, value),
          }))
        }
      />
      <ConfigDiff diff={diff} />
      <form
        className="run-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onUpdateConfig({
            updates: Object.fromEntries(diff.map((item) => [item.key, { value: item.after }])),
            confirmation,
          });
        }}
      >
        <label>
          Confirmation
          <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
        </label>
        <button type="submit" disabled={pending || diff.length === 0}>
          Save config
        </button>
      </form>
    </section>
  );
}

function buildDiff(snapshot: ConfigSnapshot, editedValues: Record<string, unknown>) {
  return snapshot.values
    .filter((entry) => Object.prototype.hasOwnProperty.call(editedValues, entry.key))
    .filter((entry) => editedValues[entry.key] !== entry.value.value)
    .map((entry) => ({
      key: entry.key,
      before: entry.value.value,
      after: editedValues[entry.key],
    }));
}

function parseEditedValue(snapshot: ConfigSnapshot, key: string, raw: string): unknown {
  const entry = snapshot.values.find((value) => value.key === key);
  const original = entry?.value.value;
  if (typeof original === "number") {
    return Number(raw);
  }
  if (typeof original === "boolean") {
    return raw === "true";
  }
  return raw;
}
