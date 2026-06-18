import type { TradeJournalItem } from "../../api/types";

interface TradeDetailProps {
  readonly trade: TradeJournalItem | null;
}

export function TradeDetail({ trade }: TradeDetailProps) {
  if (trade === null) {
    return (
      <section className="detail-panel" aria-label="Trade detail">
        <h3>Trade Detail</h3>
        <p>No trade selected</p>
      </section>
    );
  }

  return (
    <section className="detail-panel" aria-label="Trade detail">
      <h3>Trade Detail</h3>
      <dl>
        <dt>Signal</dt>
        <dd>{trade.signal_key}</dd>
        <dt>Broker order</dt>
        <dd>{trade.broker_order_id ?? "none"}</dd>
        <dt>Broker trade</dt>
        <dd>{trade.broker_trade_id ?? "none"}</dd>
        <dt>Open transaction</dt>
        <dd>{trade.open_transaction_id ?? "none"}</dd>
        <dt>Close transaction</dt>
        <dd>{trade.close_transaction_id ?? "none"}</dd>
      </dl>
    </section>
  );
}
