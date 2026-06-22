import type { TradeJournalItem } from "../../api/types";
import { fmtNum, fmtPrice, fmtR, fmtSigned, signClass } from "../../ui/format";
import { EmptyState, Tag } from "../../ui/primitives";

export function TradeTable({
  trades,
  selectedId,
  onSelect,
}: {
  readonly trades: readonly TradeJournalItem[];
  readonly selectedId: number | null;
  readonly onSelect: (id: number) => void;
}) {
  if (trades.length === 0) {
    return (
      <EmptyState glyph="≣" title="No trades in range" hint="Closed trades will appear here." />
    );
  }
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>Instrument</th>
            <th>Side</th>
            <th className="num">Units</th>
            <th className="num">Entry</th>
            <th className="num">Exit</th>
            <th className="num">P&L</th>
            <th className="num">R</th>
            <th>Exit</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr
              key={trade.id}
              className={trade.id === selectedId ? "is-selected" : undefined}
              onClick={() => onSelect(trade.id)}
            >
              <td className="num mute">{trade.id}</td>
              <td className="cell-strong">{trade.instrument}</td>
              <td className={trade.side === "short" ? "side-short" : "side-long"}>{trade.side}</td>
              <td className="num">{fmtNum(trade.units, 0)}</td>
              <td className="num">{fmtPrice(trade.entry_price)}</td>
              <td className="num">{fmtPrice(trade.exit_price)}</td>
              <td className={`num ${signClass(trade.pnl)}`}>{fmtSigned(trade.pnl)}</td>
              <td className={`num ${signClass(trade.r_multiple)}`}>{fmtR(trade.r_multiple)}</td>
              <td className="mute">{trade.exit_reason ?? "open"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TradeDetail({ trade }: { readonly trade: TradeJournalItem | null }) {
  if (!trade) {
    return <EmptyState glyph="◌" title="No trade selected" hint="Select a row to inspect fills." />;
  }
  return (
    <div className="stack">
      <div className="row">
        <Tag tone={trade.side === "short" ? "down" : "up"}>{trade.side}</Tag>
        <Tag tone="muted">{trade.signal_status}</Tag>
      </div>
      <dl className="kv">
        <dt>Signal</dt>
        <dd>{trade.signal_key}</dd>
        <dt>Entry</dt>
        <dd>{trade.entry_ts}</dd>
        <dt>Exit</dt>
        <dd>{trade.exit_ts ?? "—"}</dd>
        <dt>Broker order</dt>
        <dd>{trade.broker_order_id ?? "—"}</dd>
        <dt>Broker trade</dt>
        <dd>{trade.broker_trade_id ?? "—"}</dd>
        <dt>Open txn</dt>
        <dd>{trade.open_transaction_id ?? "—"}</dd>
        <dt>Close txn</dt>
        <dd>{trade.close_transaction_id ?? "—"}</dd>
      </dl>
    </div>
  );
}
