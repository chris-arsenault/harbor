import type { BacktestRunDetail } from "../../api/types";
import { fmtNum, fmtPct, fmtPrice, fmtR, fmtSigned, signClass, valueTone } from "../../ui/format";
import { EmptyState, Panel, StatTile } from "../../ui/primitives";
import { AreaCurve } from "../../ui/viz";
import { cumulativePnl, readTradeRow } from "./runModel";

function SummaryTiles({ stats }: { readonly stats: Record<string, unknown> }) {
  return (
    <div className="tiles">
      <StatTile label="Trades" value={fmtNum(stats.trade_count, 0)} />
      <StatTile label="Net P&L" value={fmtSigned(stats.net_pnl)} tone={valueTone(stats.net_pnl)} />
      <StatTile label="Win rate" value={fmtPct(stats.win_rate)} tone="beam" />
      <StatTile
        label="Expectancy"
        value={fmtSigned(stats.expectancy)}
        tone={valueTone(stats.expectancy)}
      />
      <StatTile label="Avg R" value={fmtR(stats.average_r)} tone={valueTone(stats.average_r)} />
      <StatTile label="Max drawdown" value={fmtNum(stats.max_drawdown, 2)} tone="warn" />
    </div>
  );
}

function BacktestTrades({ trades }: { readonly trades: readonly Record<string, unknown>[] }) {
  if (trades.length === 0) {
    return <p className="mute">No simulated trades for this run.</p>;
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Side</th>
            <th>Level</th>
            <th className="num">Units</th>
            <th className="num">Entry</th>
            <th className="num">Exit</th>
            <th className="num">P&L</th>
            <th className="num">R</th>
            <th>Exit</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((row, index) => {
            const trade = readTradeRow(row);
            return (
              <tr key={index}>
                <td className={trade.side === "short" ? "side-short" : "side-long"}>
                  {trade.side}
                </td>
                <td className="mute">{trade.level}</td>
                <td className="num">{fmtNum(trade.units, 0)}</td>
                <td className="num">{fmtPrice(trade.entry)}</td>
                <td className="num">{fmtPrice(trade.exit)}</td>
                <td className={`num ${signClass(trade.pnl)}`}>{fmtSigned(trade.pnl)}</td>
                <td className={`num ${signClass(trade.r)}`}>{fmtR(trade.r)}</td>
                <td className="mute">{trade.reason}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function BacktestSummary({
  run,
  pending,
}: {
  readonly run: BacktestRunDetail | null;
  readonly pending: boolean;
}) {
  if (!run) {
    return (
      <Panel title="Result" label="Result">
        <EmptyState
          glyph="⎍"
          title={pending ? "Running backtest…" : "No backtest selected"}
          hint="Run a backtest or pick a row from history."
        />
      </Panel>
    );
  }
  const equity = cumulativePnl(run.trades).map((v) => ({ v }));
  const net = equity.length > 0 ? equity[equity.length - 1].v : 0;
  return (
    <Panel
      title="Result"
      note={run.run_id === null ? "latest" : `run #${run.run_id}`}
      label="Result"
    >
      <SummaryTiles stats={run.stats} />
      <AreaCurve
        points={equity}
        ariaLabel="Backtest cumulative P&L"
        tone={net >= 0 ? "up" : "down"}
        height={150}
      />
      <BacktestTrades trades={run.trades} />
    </Panel>
  );
}
