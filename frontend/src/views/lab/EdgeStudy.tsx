import { useState } from "react";

import { useEdgeStudyQuery } from "../../api/hooks";
import type { ConditionalEdge, EdgeStudyResult } from "../../api/research";
import { fmtNum, fmtPct, valueTone } from "../../ui/format";
import { EmptyState, Notice, Panel, StatTile, Tag } from "../../ui/primitives";

function EdgeTiles({ study }: { readonly study: EdgeStudyResult }) {
  return (
    <div className="tiles tiles--tight">
      <StatTile label="Sweeps" value={String(study.total_sweeps)} />
      <StatTile label="Hypothesis" value={study.hypothesis_id} />
      <StatTile label="Forward" value={`${study.horizon}m`} />
      <StatTile label="Reversal hit-rate" value={fmtPct(study.overall.hit_rate)} />
      <StatTile
        label="Mean reversal"
        value={`${fmtNum(study.overall.mean_pips, 1)}p`}
        tone={valueTone(study.overall.mean_pips)}
      />
      <StatTile
        label="Corrected t"
        value={fmtNum(study.overall.t_stat, 2)}
        tone={Number(study.overall.t_stat) >= 2 ? "up" : "warn"}
      />
      <StatTile label="Naive t" value={fmtNum(study.overall.naive_t_stat, 2)} />
      <StatTile label="Effective N" value={String(study.overall.effective_sample_size)} />
      <StatTile label="Bonferroni p" value={fmtNum(study.overall.bonferroni_p_value, 4)} />
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
            <th className="num">Eff N</th>
            <th className="num">t</th>
            <th className="num">p adj</th>
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
              <td className="num">{edge.summary.effective_sample_size}</td>
              <td className="num">{fmtNum(edge.summary.t_stat, 2)}</td>
              <td className="num">{fmtNum(edge.summary.bonferroni_p_value, 4)}</td>
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
      <p className="mute">
        Algorithm: {study.algorithm_label}. t-stat uses{" "}
        {study.statistical_notes.standard_error_correction}; effective N is{" "}
        {study.statistical_notes.effective_sample_unit}; conditional p-values use{" "}
        {study.statistical_notes.conditional_multiple_test_method} across{" "}
        {study.statistical_notes.conditional_test_count} slices.
      </p>
      <ConditionTable edges={[...study.by_level, ...study.by_session, ...study.by_volatility]} />
    </>
  );
}

function IdlePrompt({ onRun }: { readonly onRun: () => void }) {
  return (
    <div className="stack">
      <p className="mute">
        Runs a statistical edge study against persisted candles to check whether sweep-based entries
        have a measurable base-rate advantage.
      </p>
      <button type="button" className="btn btn--primary" onClick={onRun}>
        Run edge study
      </button>
    </div>
  );
}

export function EdgeStudy({ instrument }: { readonly instrument: string }) {
  const [enabled, setEnabled] = useState(false);
  const query = useEdgeStudyQuery(instrument, enabled);
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
      {enabled ? <EdgeBody query={query} /> : <IdlePrompt onRun={() => setEnabled(true)} />}
    </Panel>
  );
}
