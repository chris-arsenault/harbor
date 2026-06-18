import type { VariantLeaderboardRow } from "../../api/types";

interface VariantLeaderboardProps {
  readonly rows: VariantLeaderboardRow[];
  readonly onRetireVariant: (variantId: number) => void | Promise<void>;
  readonly onPromoteVariant: (variantId: number) => void | Promise<void>;
}

export function VariantLeaderboard({
  rows,
  onRetireVariant,
  onPromoteVariant,
}: VariantLeaderboardProps) {
  return (
    <section className="lab-panel" aria-label="Variant leaderboard">
      <h2>Leaderboard</h2>
      <div className="lab-table-wrap">
        <table className="lab-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Variant</th>
              <th>Trades</th>
              <th>Live score</th>
              <th>OOS</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6}>No paper variants on the leaderboard.</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.variant.id}>
                  <td>{row.rank}</td>
                  <td>{row.variant.label}</td>
                  <td>{row.stats.trade_count}</td>
                  <td>{row.stats.live_forward_score}</td>
                  <td>{row.out_of_sample_score}</td>
                  <td>
                    <button
                      type="button"
                      className="lab-button lab-button--quiet"
                      aria-label={`Promote practice variant ${row.variant.label}`}
                      onClick={() => void onPromoteVariant(row.variant.id)}
                    >
                      Promote
                    </button>
                    <button
                      type="button"
                      className="lab-button lab-button--quiet"
                      aria-label={`Retire paper variant ${row.variant.label}`}
                      onClick={() => void onRetireVariant(row.variant.id)}
                    >
                      Retire
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
