# 0004 - Raw Async OANDA Client Boundary

- Status: Accepted
- Date: 2026-06-16

## Context

Harbor needs streaming prices, historical candles, order placement with bracket orders, account summary, open trades/positions, and transaction reconciliation. The official OANDA v20 API is HTTP and streaming JSON-line based, and the backend runtime is asyncio.

## Decision

Harbor implements a thin raw async OANDA client boundary over `httpx`, with typed request/response adapters and no broker calls inside strategy or risk modules.

## Alternatives considered

- **`oandapyV20` wrapper** - provides existing endpoint wrappers, but is synchronous and adds an abstraction that still needs async streaming, retry, and typed boundary work.
- **Direct `httpx` calls scattered by service** - quick to write, but spreads auth, retries, request IDs, error handling, and endpoint semantics across the codebase.
- **Broker abstraction layer** - prepares for other brokers, but the v1 scope is explicitly OANDA-only.

## Consequences

The OANDA boundary owns bearer auth, base URL selection, timeouts, retry/backoff, streaming JSON-line parsing, request IDs, and response normalization. Endpoint behavior must be verified against official OANDA docs during implementation phases.
