# Harbor M3 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M3 - OANDA market data and closed-candle feed` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; historical candle ingestion and stream parsing persist only closed M1 candles for `EUR_USD`; OANDA calls are covered by fixtures and mocked transports, not live credentials.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M3.
- Product/feed source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 3, 4, 5, and 6.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires closed candles only at the strategy boundary.
- OANDA boundary decision: [ADR-0004](docs/adr/0004-raw-async-oanda-client.md) requires a thin raw async `httpx` client, typed adapters, bearer auth, base URL selection, timeouts, retry/backoff, streaming JSON-line parsing, request IDs, and response normalization.
- Current official OANDA docs:
  - Account summary and instruments: <https://developer.oanda.com/rest-live-v20/account-ep/>
  - Historical candles and pricing stream: <https://developer.oanda.com/rest-live-v20/pricing-ep/>
  - Transaction stream: <https://developer.oanda.com/rest-live-v20/transaction-ep/>
- Reuse from M2:
  - [backend/src/harbor_bot/settings.py](backend/src/harbor_bot/settings.py) owns runtime settings.
  - [backend/src/harbor_bot/persistence/database.py](backend/src/harbor_bot/persistence/database.py) owns async engine and transaction helpers.
  - [backend/src/harbor_bot/persistence/market_repository.py](backend/src/harbor_bot/persistence/market_repository.py) owns candle upserts and UTC-aware timestamp validation.
  - [backend/src/harbor_bot/persistence/event_repository.py](backend/src/harbor_bot/persistence/event_repository.py) owns structured event appends.
- M3 boundaries:
  - No order placement, broker execution, strategy decisions, risk gates, API endpoints, frontend UI, or deployment changes.
  - No live OANDA calls in CI. Any manual live probe must be run through `with-cred -- ...`.
  - Broker/environment knobs are configuration, not user decisions: base URLs, timeout seconds, heartbeat timeout, reconnect initial/max seconds, and historical candle page size must be settings with conservative defaults.

## Steps

1. Confirm M2 baseline before broker read-path work
   - File(s): `backend/pyproject.toml`, `backend/src/harbor_bot/persistence/*`, `backend/tests/integration/*`, `docs/adr/0004-raw-async-oanda-client.md`.
   - Reference behavior: M3 depends on M2 persistence and on ADR-0004. `httpx` already exists as the raw client dependency; no new HTTP client abstraction is needed.
   - Change: No source changes.
   - Verify: Red if M2 drifted, green when Harbor is ready for OANDA read-path work:
     ```bash
     make ci
     grep -q 'httpx' backend/pyproject.toml
     test -f docs/adr/0004-raw-async-oanda-client.md
     cd backend
     uv run --extra dev pytest tests/integration/test_migrations.py tests/integration/test_market_repository.py tests/integration/test_config_seed.py
     ```

2. Add OANDA runtime settings boundary [depends on #1]
   - File(s): `backend/src/harbor_bot/settings.py`, `backend/tests/test_settings.py`.
   - Reference behavior: `secret-paths.yml` and `.env.example` provide `OANDA_ENV`, `ALLOW_LIVE`, `OANDA_API_TOKEN`, and `OANDA_ACCOUNT_ID`. ADR-0004 requires base URL selection, timeouts, and reconnect/backoff at the OANDA boundary. Installing packages and running unit tests must not require credentials.
   - Change: Extend `Settings` with optional OANDA token/account fields, practice/live environment selection, optional REST/stream base URL overrides, request timeout, stream heartbeat timeout, reconnect initial/max seconds, and historical candle page size. Settings construction must continue to work without credentials; the OANDA client factory validates credentials only when a real client is created. Accessing live base URLs must require `ALLOW_LIVE=true`.
   - Verify: Red before settings expose the OANDA fields/contracts, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_settings.py
     ```

3. Add typed OANDA response adapters and fixtures [depends on #2]
   - File(s): `backend/src/harbor_bot/oanda/__init__.py`, `backend/src/harbor_bot/oanda/types.py`, `backend/tests/fixtures/oanda/*.json`, `backend/tests/test_oanda_types.py`.
   - Reference behavior: Official OANDA responses encode prices and account values as strings, timestamps as RFC3339 strings, historical candles with `complete`, pricing streams as `PRICE`/heartbeat frames, and transaction streams as transaction/heartbeat frames. Harbor stores prices as `Decimal` and UTC-aware `datetime`.
   - Change: Add typed adapters for account summary, instruments, historical candles, pricing ticks, pricing heartbeats, transaction frames, and transaction heartbeats. Normalize RFC3339 timestamps to UTC-aware `datetime`, numeric strings to `Decimal`, and keep unknown transaction payload fields in a raw mapping for later execution phases. Add compact recorded-style fixtures for the response shapes M3 consumes.
   - Verify: Red before the adapter module exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_oanda_types.py
     ```

4. Implement the raw async OANDA client [depends on #3]
   - File(s): `backend/src/harbor_bot/oanda/client.py`, `backend/tests/test_oanda_client.py`.
   - Reference behavior: ADR-0004 chooses raw async `httpx`. M3 needs account summary, account instruments, historical M1 midpoint candles, pricing stream, and transaction stream framing. Official historical candles allow `count` up to 5000 and use `includeFirst` for polling continuation.
   - Change: Add an `OandaClient` with methods for account summary, instruments, historical candles, pricing stream connection, and transaction stream connection. The client owns bearer auth, `Accept-Datetime-Format: RFC3339`, REST vs stream base URLs, query parameter construction, request timeout, and typed error mapping. Use `httpx.MockTransport` in tests; do not hit the network.
   - Verify: Red before the client exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_oanda_client.py
     ```

5. Implement JSON-line stream parsing and reconnect/backoff [depends on #4]
   - File(s): `backend/src/harbor_bot/oanda/stream.py`, `backend/tests/test_oanda_stream.py`.
   - Reference behavior: Official pricing and transaction streams use chunked transfer encoding where each JSON object is serialized on one line. Pricing and transaction heartbeats are sent by OANDA and must not be treated as prices/candles/trades. ADR-0004 assigns retry/backoff and streaming JSON-line parsing to the OANDA boundary.
   - Change: Add stream utilities that parse async byte/text lines into typed pricing or transaction frames, skip blank lines, surface malformed JSON as typed errors, track heartbeat freshness, and reconnect using configurable initial/max backoff. Inject sleep/connect functions in tests so reconnect behavior is deterministic and does not wait in real time.
   - Verify: Red before stream utilities exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_oanda_stream.py
     ```

6. Build the closed M1 candle emitter [depends on #3, #5]
   - File(s): `backend/src/harbor_bot/feed/__init__.py`, `backend/src/harbor_bot/feed/candles.py`, `backend/tests/test_candle_builder.py`.
   - Reference behavior: The prime directive in the source spec is that strategy-facing feed code emits closed candles only. Historical candles use midpoint prices (`price=M`); streaming prices expose bid/ask prices, so the live M1 builder must aggregate midpoint ticks from pricing frames.
   - Change: Add a candle builder that consumes typed pricing frames, computes midpoint ticks from best bid/ask, aggregates UTC minute buckets into OHLCV-style M1 candles, and emits a candle only after a later minute has started. It must ignore heartbeats, never emit the active/current minute, and avoid synthesizing missing minutes with fabricated prices.
   - Verify: Red before the feed module exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_candle_builder.py
     ```

7. Implement historical candle ingestion into persistence [depends on #4, #6]
   - File(s): `backend/src/harbor_bot/feed/historical.py`, `backend/tests/integration/test_historical_ingestion.py`.
   - Reference behavior: M3 exit requires historical candle ingestion to produce persisted closed M1 candles for `EUR_USD`. M2 already owns candle upsert by `(instrument, ts)` and rejects non-UTC timestamps.
   - Change: Add an ingestion function that requests M1 midpoint candles from the OANDA client, filters out incomplete candles, normalizes completed candles, and upserts them through `market_repository` inside one transaction. Keep pagination bounded by the configured page size; do not compute strategy levels or decisions here.
   - Verify: Red before ingestion exists, green after against real Postgres with a fake client:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_historical_ingestion.py
     ```

8. Implement pricing stream ingestion into persistence [depends on #5, #6, #7]
   - File(s): `backend/src/harbor_bot/feed/live.py`, `backend/tests/integration/test_pricing_stream_ingestion.py`.
   - Reference behavior: M3 exit requires stream parsing to produce persisted closed M1 candles for `EUR_USD`; ADR-0003 forbids the currently forming candle from reaching the strategy boundary.
   - Change: Add a live feed ingestion function that consumes typed pricing frames from an async iterator, passes them through the closed M1 candle builder, and upserts each emitted closed candle in transactions. Append structured lifecycle events for stream connect, heartbeat timeout, and reconnect attempts. Do not call strategy code and do not persist the active minute.
   - Verify: Red before live ingestion exists, green after against real Postgres with a fake stream:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_pricing_stream_ingestion.py
     ```

9. Implement transaction stream framing without execution semantics [depends on #5]
   - File(s): `backend/src/harbor_bot/feed/transactions.py`, `backend/tests/test_transaction_stream.py`.
   - Reference behavior: M3 includes transaction stream framing, but broker execution and trade reconciliation belong to later milestones. Transaction stream heartbeats are not fills, orders, or strategy events.
   - Change: Add a small wrapper that consumes typed transaction stream frames, exposes heartbeats separately from transaction payloads, and preserves raw transaction fields for later reconciliation. Do not write trades, signals, orders, or execution state in M3.
   - Verify: Red before transaction framing exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_transaction_stream.py
     ```

10. Register feed/OANDA exports and documentation [depends on #8, #9]
    - File(s): `backend/src/harbor_bot/oanda/__init__.py`, `backend/src/harbor_bot/feed/__init__.py`, `backend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: M3 changes the backend from persistence-only to a broker read-path package with closed-candle ingestion. Docs must stay current-state and must not imply live trading or order placement exists.
    - Change: Export only stable OANDA/feed entry points needed by tests and future phases. Update docs with the M3 command shape, fixture/mock policy, credential policy, and closed-candle feed boundary. Do not add API endpoints.
    - Verify: Red before docs mention only the persistence foundation, green after:
      ```bash
      grep -q 'OANDA' backend/README.md docs/development.md docs/architecture.md
      grep -q 'closed M1' backend/README.md docs/development.md docs/architecture.md
      grep -q 'fixtures' docs/development.md
      ```

11. Run the M3 exit gate [depends on #10]
    - File(s): Harbor repo.
    - Reference behavior: M3 exit requires `make ci` green and persisted closed M1 candles from historical ingestion and stream parsing. No live OANDA credentials are required for the gate.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_oanda_client.py \
        tests/test_oanda_stream.py \
        tests/test_candle_builder.py \
        tests/test_transaction_stream.py \
        tests/integration/test_historical_ingestion.py \
        tests/integration/test_pricing_stream_ingestion.py
      ```

## M3 Decision Register

| Step | Decision you own |
| ---- | ---- |
| None | Broker timing/base URL/page-size values are runtime settings with defaults, not user-owned architecture decisions. |

## Handoff

Execute only these M3 steps next. Do not add order placement, broker execution, strategy logic, risk gates, REST/WebSocket API endpoints, frontend UI, or deployment changes during M3.
