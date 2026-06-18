import type { TradeJournalItem } from "../../api/types";

interface TradesTableProps {
  readonly trades: TradeJournalItem[];
}

export function TradesTable({ trades }: TradesTableProps) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Instrument</th>
          <th>Side</th>
          <th>Units</th>
          <th>Entry</th>
          <th>Exit</th>
          <th>P&L</th>
          <th>R</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        {trades.map((trade) => (
          <tr key={trade.id}>
            <td>{trade.instrument}</td>
            <td>{trade.side}</td>
            <td>{trade.units}</td>
            <td>{trade.entry_price}</td>
            <td>{trade.exit_price ?? "open"}</td>
            <td>{trade.pnl ?? "open"}</td>
            <td>{trade.r_multiple ?? "open"}</td>
            <td>{trade.exit_reason ?? "open"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
