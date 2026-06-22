import type { LabSnapshot, LabVariantOverview, VariantEquityCurve } from "../../api/types";
import { fmtNum, toNumber } from "../../ui/format";
import { Panel, StatTile } from "../../ui/primitives";
import { AreaCurve, Scatter } from "../../ui/viz";
import { bestOutOfSample, candidateScatter, studyTiles } from "./labModel";
import { DiagnosticsTable, Leaderboard } from "./Leaderboard";

function pickCurve(variants: LabVariantOverview): VariantEquityCurve | null {
  if (variants.leaderboard.length > 0) {
    const topId = variants.leaderboard[0].variant.id;
    const match = variants.equity_curves.find((curve) => curve.variant_id === topId);
    if (match) {
      return match;
    }
  }
  return variants.equity_curves[0] ?? null;
}

function EquityPanel({ variants }: { readonly variants: LabVariantOverview }) {
  const curve = pickCurve(variants);
  const points = (curve?.points ?? []).map((point) => ({ v: toNumber(point.nav) ?? 0 }));
  const dataPoints = (curve?.points ?? []).map((point) => `${point.ts}:${point.nav}`).join(";");
  return (
    <Panel title="Best variant equity" label="Best variant equity">
      <AreaCurve
        points={points}
        ariaLabel="Variant equity curve"
        dataPoints={dataPoints}
        height={150}
      />
    </Panel>
  );
}

export function StudyResults({
  snapshot,
  variants,
  onPromote,
  onRetire,
}: {
  readonly snapshot: LabSnapshot;
  readonly variants: LabVariantOverview;
  readonly onPromote: (variantId: number) => void | Promise<void>;
  readonly onRetire: (variantId: number) => void | Promise<void>;
}) {
  const scatter = candidateScatter(snapshot.candidates);
  const best = bestOutOfSample(snapshot.candidates);
  return (
    <>
      <Panel title="Study progress" note={`#${snapshot.study.study_id}`} label="Study progress">
        <div className="tiles tiles--tight">
          {studyTiles(snapshot.study).map((tile) => (
            <StatTile key={tile.label} label={tile.label} value={tile.value} />
          ))}
          <StatTile label="Best OOS" value={best === null ? "—" : fmtNum(best, 3)} tone="beam" />
        </div>
      </Panel>
      <div className="duo">
        <Panel
          title="Candidate scatter"
          note="in-sample vs out-of-sample"
          label="Candidate scatter"
        >
          <Scatter
            points={scatter.points}
            ariaLabel="Trial score scatter"
            dataPoints={scatter.dataPoints}
          />
        </Panel>
        <EquityPanel variants={variants} />
      </div>
      <Panel
        title="Variant leaderboard"
        note={`${variants.leaderboard.length}`}
        label="Variant leaderboard"
      >
        <Leaderboard rows={variants.leaderboard} onPromote={onPromote} onRetire={onRetire} />
      </Panel>
      <Panel title="Trial diagnostics" label="Trial diagnostics">
        <DiagnosticsTable candidates={snapshot.candidates} />
      </Panel>
    </>
  );
}
