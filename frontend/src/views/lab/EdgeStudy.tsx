import { useEdgeStudyQuery } from "../../api/hooks";
import type { ConditionalEdge, EdgeStudyResult } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Notice, Panel, StatTile, Tag } from "../../ui/primitives";

function EdgeTiles({ study }: { readonly study: EdgeStudyResult }) {
  return (
    <div className="tiles tiles--tight">
      <StatTile label="Sweeps" value={String(study.total_sweeps)} />
      <StatTile label="Forward" value={`${study.horizon}m`} />
      <StatTile label="Reversal hit-rate" value={fmtPct(study.overall.hit_rate)} />
      <StatTile
        label="Mean reversal"
        value={`${fmtNum(study.overall.mean_pips, 1)}p`}
        tone={valueTone(study.overall.mean_pips)}
      />
      <StatTile
        label="Significance (t)"
        value={fmtNum(study.overall.t_stat, 2)}
        tone={Number(study.overall.t_stat) >= 2 ? "up" : "warn"}
      />
      <StatTile label="Baseline move" value={`${fmtNum(study.baseline_mean_abs_pips, 1)}p`} />
    </div>
  );
}

function ConditionTable({ edges }: { readonly edges: ConditionalEdge[] }) {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Group</th>
            <th className="num">N</th>
            <th className="num">Hit</th>
            <th className="num">Mean p</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={`${edge.dimension}-${edge.value}`}>
              <td className="mute">{edge.dimension}</td>
              <td className="cell-strong">{edge.value}</td>
              <td className="num">{edge.summary.count}</td>
              <td className="num">{fmtPct(edge.summary.hit_rate)}</td>
              <td className={`num ${valueTone(edge.summary.mean_pips) === "down" ? "neg" : ""}`}>
                {fmtNum(edge.summary.mean_pips, 1)}
              </td>
              <td>
                <Tag tone={edge.has_edge ? "up" : "muted"}>{edge.has_edge ? "edge" : "—"}</Tag>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EdgeBody({ query }: { readonly query: ReturnType<typeof useEdgeStudyQuery> }) {
  if (query.isLoading) {
    return <p className="mute">Running edge study…</p>;
  }
  if (query.error) {
    return <Notice tone="error">{query.error.message}</Notice>;
  }
  const study = query.data;
  if (!study || !study.total_sweeps) {
    return (
      <EmptyState
        glyph="∅"
        title="No sweeps in window"
        hint="Import more history for this instrument, then re-check the edge."
      />
    );
  }
  return (
    <>
      <EdgeTiles study={study} />
      <ConditionTable edges={[...study.by_level, ...study.by_session, ...study.by_volatility]} />
    </>
  );
}

export function EdgeStudy({ instrument }: { readonly instrument: string }) {
  const query = useEdgeStudyQuery(instrument);
  const verdict = query.data?.has_edge ?? false;
  return (
    <Panel
      title="Base-rate edge"
      note={instrument}
      label="Base-rate edge"
      actions={
        query.data ? (
          <Tag tone={verdict ? "up" : "warn"}>{verdict ? "edge present" : "no edge"}</Tag>
        ) : null
      }
    >
      <EdgeBody query={query} />
    </Panel>
  );
}
