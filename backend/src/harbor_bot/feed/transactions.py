from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from harbor_bot.oanda.types import TransactionFrame, TransactionHeartbeat, TransactionStreamFrame


@dataclass(frozen=True)
class CollectedTransactionStream:
    heartbeats: list[TransactionHeartbeat] = field(default_factory=list)
    transactions: list[TransactionFrame] = field(default_factory=list)


async def collect_transaction_stream(
    frames: AsyncIterable[TransactionStreamFrame],
) -> CollectedTransactionStream:
    heartbeats: list[TransactionHeartbeat] = []
    transactions: list[TransactionFrame] = []
    async for frame in frames:
        if isinstance(frame, TransactionHeartbeat):
            heartbeats.append(frame)
        else:
            transactions.append(frame)
    return CollectedTransactionStream(heartbeats=heartbeats, transactions=transactions)
