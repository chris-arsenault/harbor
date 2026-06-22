import type { CandidateScatterPoint, VariantLeaderboardRow } from "../../api/types";
import { fmtNum, signClass } from "../../ui/format";
import { EmptyState, Tag } from "../../ui/primitives";

function statusTone(status: string): "beam" | "up" | "muted" {
  if (status === "promoted") {
    return "beam";
  }
  return status === "paper" ? "up" : "muted";
}

export function Leaderboard({
  rows,
  onPromote,
  onRetire,
}: {
  readonly rows: readonly VariantLeaderboardRow[];
  readonly onPromote: (variantId: number) => void | Promise<void>;
  readonly onRetire: (variantId: number) => void | Promise<void>;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        glyph="⚗"
        title="No paper variants"
        hint="Promote candidates from a completed study to forward-test them."
      />
    );
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>Variant</th>
            <th>Status</th>
            <th className="num">Trades</th>
            <th className="num">Fwd score</th>
            <th className="num">OOS</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.variant.id}>
              <td className="num mute">{row.rank}</td>
              <td className="cell-strong">{row.variant.label}</td>
              <td>
                <Tag tone={statusTone(row.variant.status)}>{row.variant.status}</Tag>
              </td>
              <td className="num">{row.stats.trade_count}</td>
              <td className={`num ${signClass(row.stats.live_forward_score)}`}>
                {fmtNum(row.stats.live_forward_score, 2)}
              </td>
              <td className="num">{fmtNum(row.out_of_sample_score, 2)}</td>
              <td>
                <div className="row">
                  <button
                    type="button"
                    className="btn btn--sm btn--primary"
                    disabled={row.variant.status !== "paper" || row.stats.trade_count === 0}
                    onClick={() => void onPromote(row.variant.id)}
                  >
                    Promote
                  </button>
                  <button
                    type="button"
                    className="btn btn--sm btn--ghost"
                    disabled={row.variant.status === "retired"}
                    onClick={() => void onRetire(row.variant.id)}
                  >
                    Retire
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DiagnosticsTable({
  candidates,
}: {
  readonly candidates: readonly CandidateScatterPoint[];
}) {
  if (candidates.length === 0) {
    return <p className="mute">No trial candidates recorded for this study.</p>;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Trial</th>
            <th>Status</th>
            <th className="num">In-sample</th>
            <th className="num">Out-of-sample</th>
            <th className="num">Robustness</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.trial_id}>
              <td className="num mute">#{candidate.trial_no}</td>
              <td>{candidate.pruned ? "pruned" : candidate.status}</td>
              <td className="num">{fmtNum(candidate.in_sample_score, 3)}</td>
              <td className="num">{fmtNum(candidate.out_of_sample_score, 3)}</td>
              <td className="num">{fmtNum(candidate.robustness_score, 3)}</td>
              <td className="mute">
                {candidate.candidate_rejection_reason ?? candidate.failure_reason ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
