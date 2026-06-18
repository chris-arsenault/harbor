from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from harbor_bot.feed.transactions import collect_transaction_stream
from harbor_bot.oanda.types import TransactionFrame, TransactionHeartbeat


@pytest.mark.asyncio
async def test_transaction_stream_exposes_heartbeats_separately_from_payloads() -> None:
    result = await collect_transaction_stream(_frames())

    assert result.heartbeats == [
        TransactionHeartbeat(
            time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            last_transaction_id="9009",
        )
    ]
    assert len(result.transactions) == 1
    assert result.transactions[0].transaction_type == "ORDER_FILL"
    assert result.transactions[0].transaction_id == "9010"
    assert result.transactions[0].raw == {
        "type": "ORDER_FILL",
        "id": "9010",
        "time": "2026-01-15T14:30:16.000000000Z",
        "instrument": "EUR_USD",
        "price": "1.09020",
    }


async def _frames() -> AsyncIterator[TransactionFrame | TransactionHeartbeat]:
    yield TransactionHeartbeat(
        time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        last_transaction_id="9009",
    )
    yield TransactionFrame(
        transaction_type="ORDER_FILL",
        transaction_id="9010",
        time=datetime(2026, 1, 15, 14, 30, 16, tzinfo=UTC),
        raw={
            "type": "ORDER_FILL",
            "id": "9010",
            "time": "2026-01-15T14:30:16.000000000Z",
            "instrument": "EUR_USD",
            "price": "1.09020",
        },
    )
