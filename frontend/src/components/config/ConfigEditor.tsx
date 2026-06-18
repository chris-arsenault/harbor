import type { ConfigEntry } from "../../api/types";
import { displayValue } from "../../utils/format";

interface ConfigEditorProps {
  readonly values: ConfigEntry[];
  readonly editedValues: Record<string, unknown>;
  readonly onChange: (key: string, value: string) => void;
}

export function ConfigEditor({ values, editedValues, onChange }: ConfigEditorProps) {
  return (
    <section className="table-panel" aria-label="Config editor">
      <h3>Strategy Parameters</h3>
      <div className="config-grid">
        {values.map((entry) => (
          <label key={entry.key}>
            {entry.key}
            <input
              aria-label={entry.key}
              value={displayValue(editedValues[entry.key] ?? entry.value.value, "")}
              onChange={(event) => onChange(entry.key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </section>
  );
}
