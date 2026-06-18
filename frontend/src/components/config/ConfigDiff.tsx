interface ConfigDiffProps {
  readonly diff: Array<{ key: string; before: unknown; after: unknown }>;
}

export function ConfigDiff({ diff }: ConfigDiffProps) {
  return (
    <section className="detail-panel" aria-label="Config diff">
      <h3>Diff Preview</h3>
      {diff.length === 0 ? (
        <p>No pending changes</p>
      ) : (
        <ul className="fact-list">
          {diff.map((item) => (
            <li key={item.key}>
              {item.key}: {String(item.before)} -&gt; {String(item.after)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
