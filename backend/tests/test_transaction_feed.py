from datetime import UTC, datetime

import pytest

from harbor_bot.feed.transactions import collect_transaction_stream
from harbor_bot.oanda.types import TransactionFrame, TransactionHeartbeat


@pytest.mark.asyncio
async def test_transaction_feed_collects_payloads_and_heartbeats() -> None:
    result = await collect_transaction_stream(_frames())

    assert [heartbeat.last_transaction_id for heartbeat in result.heartbeats] == ["9009"]
    assert [transaction.transaction_id for transaction in result.transactions] == ["9010"]


async def _frames():
    yield TransactionHeartbeat(
        time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        last_transaction_id="9009",
    )
    yield TransactionFrame(
        transaction_type="ORDER_FILL",
        transaction_id="9010",
        time=datetime(2026, 1, 15, 14, 30, 16, tzinfo=UTC),
        raw={
            "id": "9010",
            "time": "2026-01-15T14:30:16.000000000Z",
            "type": "ORDER_FILL",
        },
    )
