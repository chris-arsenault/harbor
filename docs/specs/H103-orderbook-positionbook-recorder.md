# H103 — OANDA Order Book / Position Book Recorder (Build Spec)

Status: ready to build
Owner: implementation agent
Related hypothesis: `docs/research/hypotheses/H103-oanda-positioning-orderbook.md`

## 1. Objective

Record OANDA's order-book and position-book snapshots forward into PostgreSQL so
that two future hypotheses can be tested later:

- H103a: retail **position-book** extremes are contrarian (forward returns fade crowded retail).
- H103b: large **order-book** clusters act as liquidity magnets/walls (data-driven levels).

This task is **data acquisition + persistence + observability only**. Do not build
trading signals, edge algorithms, or strategy changes. Those come later once data exists.

The data is effectively **not backfillable** (OANDA only serves recent snapshots), so the
priority is getting a reliable forward recorder running.

## 2. Scope

In scope:
- OANDA async client methods for order book and position book.
- Typed parsers for both payloads.
- A migration + repository for snapshot storage (append-only, idempotent).
- A periodic recorder task wired into the app lifecycle behind a settings flag.
- A read-only status/coverage API endpoint and a small Lab panel showing recorder health + latest snapshot.
- Tests (unit + repository integration + API).

Out of scope (do NOT build):
- Any research/edge algorithm using this data.
- Any change to `strategy_core`, execution, optimizer, or paper engine.
- Backfill beyond what OANDA's `time` parameter trivially allows (see 4.3).

## 3. Conventions to follow (read these files first)

- OANDA client boundary + parsers: `backend/src/harbor_bot/oanda/client.py`, `backend/src/harbor_bot/oanda/types.py`
- Persistence patterns: `backend/src/harbor_bot/persistence/market_repository.py`, `backend/src/harbor_bot/persistence/schema.py`, `backend/db/migrations/versions/`
- Settings: `backend/src/harbor_bot/settings.py` (`OANDA_*`, `research_instruments`)
- Background task wiring + status: `backend/src/harbor_bot/api.py` (`_run_live_pricing_stream`, `_live_pricing_stream_status`, startup/shutdown handlers)
- Coverage-style status service: `backend/src/harbor_bot/feed/source_service.py`
- Lab panel pattern: `frontend/src/views/lab/*` (e.g. `CandleSource.tsx`), wired in `frontend/src/views/LabView.tsx`
- Verification: `make ci` must pass. Lint is ruff (line length 100). Frontend is prettier + eslint + tsc + vitest.

Hard rules:
- Any manual command that hits OANDA credentials must use `with-cred -- <command>`.
- Real secrets stay out of the repo; only placeholders / SSM paths.
- The recorder is practice-mode safe and read-only against the broker; it places no orders.

## 4. OANDA endpoints

Base URL is the same REST base already used by `OandaClient` (`oanda_rest_base_url`).

### 4.1 Order book

`GET /v3/instruments/{instrument}/orderBook`

Expected response shape (verify against current OANDA docs before coding):

```json
{
  "orderBook": {
    "instrument": "EUR_USD",
    "time": "2026-01-15T14:20:00Z",
    "price": "1.09000",
    "bucketWidth": "0.00050",
    "buckets": [
      {"price": "1.08500", "longCountPercent": "0.20", "shortCountPercent": "0.15"}
    ]
  }
}
```

### 4.2 Position book

`GET /v3/instruments/{instrument}/positionBook`

Same structure under `positionBook` with identical bucket fields.

### 4.3 Snapshot cadence and the `time` parameter

- OANDA publishes a new snapshot roughly every ~20 minutes; `time` in the payload is the snapshot bucket time, not “now”.
- An optional `?time=<RFC3339>` returns the snapshot at/just before that time. Limited recent history only.
- The recorder is **forward-only** by default. Do not attempt deep historical backfill.
- A bounded “fill last N snapshots on startup” using `time` is allowed but optional and must be off by default.

## 5. Data model

New Alembic migration: `0006_orderbook_positionbook.py`.

Store the snapshot header once and the buckets compactly. Prefer one row per
(`book_type`, `instrument`, `snapshot_time`) header plus a JSONB column of buckets,
to keep ingestion simple and avoid millions of bucket rows.

### Table `book_snapshots`

| column | type | notes |
| --- | --- | --- |
| `id` | bigint PK | identity |
| `book_type` | text | `order` or `position` |
| `instrument` | text | e.g. `EUR_USD` |
| `snapshot_time` | timestamptz | OANDA `time` (UTC) |
| `mid_price` | numeric | OANDA `price` |
| `bucket_width` | numeric | OANDA `bucketWidth` |
| `bucket_count` | int | len(buckets) |
| `buckets_json` | jsonb | list of `{price, long_pct, short_pct}` as strings |
| `recorded_ts` | timestamptz | wall-clock insert time (UTC) |

Constraints/indexes:
- UNIQUE (`book_type`, `instrument`, `snapshot_time`) — idempotency key.
- INDEX (`book_type`, `instrument`, `snapshot_time` DESC) — latest/coverage queries.

Decimals: persist prices/percentages as Decimal/numeric. Bucket inner values may
be stored as strings in JSONB to avoid float drift.

## 6. Backend implementation

### 6.1 Types + parsers (`oanda/types.py`)

Add dataclasses and pure parsers:

```python
@dataclass(frozen=True)
class BookBucket:
    price: Decimal
    long_percent: Decimal
    short_percent: Decimal

@dataclass(frozen=True)
class BookSnapshot:
    book_type: str          # "order" | "position"
    instrument: str
    time: datetime          # UTC
    price: Decimal
    bucket_width: Decimal
    buckets: tuple[BookBucket, ...]

def parse_order_book(payload: dict[str, Any]) -> BookSnapshot: ...
def parse_position_book(payload: dict[str, Any]) -> BookSnapshot: ...
```

Parse RFC3339 with the existing helper; reject missing `time`/`price`.

### 6.2 Client methods (`oanda/client.py`)

```python
async def get_order_book(self, *, instrument: str, time: datetime | None = None) -> BookSnapshot
async def get_position_book(self, *, instrument: str, time: datetime | None = None) -> BookSnapshot
```

Reuse `_request_json` + existing error handling. `time` maps to `?time=` RFC3339 when provided.

### 6.3 Repository (`persistence/book_repository.py`)

```python
async def upsert_book_snapshot(connection, *, snapshot: BookSnapshot, recorded_ts: datetime) -> bool:
    """Insert with ON CONFLICT DO NOTHING; return inserted: bool."""

async def get_book_coverage(connection, *, instruments: tuple[str, ...]) -> list[dict]:
    """Per (book_type, instrument): count, min/max snapshot_time, latest mid_price."""

async def get_latest_book_snapshot(connection, *, book_type: str, instrument: str) -> dict | None:
    """Latest snapshot row with buckets_json."""
```

Append-only; never update an existing snapshot.

### 6.4 Recorder (`feed/book_recorder.py`)

```python
async def record_books_once(*, client, engine, instruments, now) -> BookRecorderReport:
    """For each instrument fetch order + position book and upsert new snapshots."""

async def run_book_recorder(
    *,
    settings,
    engine,
    interval_seconds,
    client_factory=OandaClient.from_settings,
    sleep=asyncio.sleep,
) -> None:
    """Loop: record once, emit event, sleep interval; backoff on errors."""
```

- Emit lifecycle/error events via `persistence/event_repository.append_event` with module `feed.book_recorder`.
- Backoff on `OandaApiError` using existing reconnect settings; never crash the loop on a single failed poll.
- Default poll interval: 300s. Polling more often than snapshot cadence is OK because the unique key dedupes.

### 6.5 Settings (`settings.py`)

Add:
- `oanda_book_recorder_enabled: bool` (alias `OANDA_BOOK_RECORDER_ENABLED`, default `False`).
- `oanda_book_poll_interval_seconds: float` (alias `OANDA_BOOK_POLL_INTERVAL_SECONDS`, default `300`).

Recorder instruments reuse `settings.research_instruments`.
Update `.env.example` with placeholders. Do not add real secrets.

### 6.6 App wiring (`api.py`)

Mirror the live pricing stream:
- `_should_start_book_recorder(app)` gate: enabled flag + token + account + engine present.
- Start `asyncio.create_task(_run_book_recorder(app))` in startup; cancel in shutdown.
- Track `app.state.book_recorder_state` like `live_pricing_stream_state`:
  - `state`
  - `running`
  - `last_started_at`
  - `last_stopped_at`
  - `last_error` redacted via `redact_secret_text`

### 6.7 API endpoint

`GET /api/research/books/status`

Response shape:

```json
{
  "recorder": {
    "running": true,
    "state": "running",
    "last_started_at": "...",
    "last_error": null
  },
  "coverage": [
    {
      "book_type": "order",
      "instrument": "EUR_USD",
      "snapshot_count": 12,
      "from": "...",
      "to": "...",
      "latest_mid_price": "1.09000"
    }
  ],
  "latest": {
    "EUR_USD": {
      "order": {"snapshot_time": "...", "bucket_count": 401},
      "position": {"snapshot_time": "...", "bucket_count": 401}
    }
  }
}
```

Read-only. Reuse a small service method; extending `ResearchService` is acceptable.

## 7. Frontend (Lab)

Add one read-only panel, separate from Edge/Capture/Cross panels:

- File: `frontend/src/views/lab/BookRecorder.tsx`
- Wire into `frontend/src/views/LabView.tsx`
- Add API types/client in `frontend/src/api/research.ts`
- Add hook in `frontend/src/api/hooks.ts`, refetch about every 30s

Panel content:
- recorder running/state
- latest started/stopped/error
- per-instrument order/position snapshot counts
- earliest/latest snapshot time
- latest snapshot age
- note: “Book data is forward-recorded only; history begins when the recorder is enabled.”

No controls besides optional manual refresh.

## 8. Testing requirements

Backend:
- Parser unit tests with fixtures:
  - `backend/tests/fixtures/oanda/order_book.json`
  - `backend/tests/fixtures/oanda/position_book.json`
- OANDA client tests using existing fake httpx transport pattern.
- Repository integration test:
  - insert idempotency on unique key
  - coverage query
  - latest query
- Recorder unit test:
  - fake client returns order+position snapshots
  - first run inserts
  - second run skips duplicates
  - one instrument failure does not stop all instruments
- API test:
  - `GET /api/research/books/status` routes through injected fake service

Frontend:
- `BookRecorder.test.tsx` renders coverage + recorder state from mocked fetch.

Full gate:
- `make ci` green.

## 9. Acceptance criteria

1. With `OANDA_BOOK_RECORDER_ENABLED=true` and valid practice credentials, Harbor records order+position book snapshots for all `research_instruments` on interval.
2. Re-polling the same snapshot does not duplicate rows.
3. `GET /api/research/books/status` reports recorder state and per-instrument coverage.
4. Lab shows recorder health and latest snapshot age.
5. No broker writes, no strategy/execution changes, recorder disabled by default.
6. All new code is covered by tests and `make ci` passes.

## 10. File checklist

Backend:
- `backend/src/harbor_bot/oanda/types.py`
- `backend/src/harbor_bot/oanda/client.py`
- `backend/db/migrations/versions/0006_orderbook_positionbook.py`
- `backend/src/harbor_bot/persistence/schema.py`
- `backend/src/harbor_bot/persistence/book_repository.py`
- `backend/src/harbor_bot/feed/book_recorder.py`
- `backend/src/harbor_bot/settings.py`
- `.env.example`
- `backend/src/harbor_bot/api.py`
- tests listed above

Frontend:
- `frontend/src/api/research.ts`
- `frontend/src/api/hooks.ts`
- `frontend/src/views/lab/BookRecorder.tsx`
- `frontend/src/views/LabView.tsx`
- `frontend/src/views/lab/BookRecorder.test.tsx`

Docs:
- Flip `docs/research/hypotheses/H103-oanda-positioning-orderbook.md` to “recorder built; awaiting forward data” when done.

## 11. Gotchas

- Verify exact OANDA field names against current v20 docs before coding.
- Store buckets as JSONB for now; normalize later only if analysis needs bucket-level SQL.
- Polling more often than snapshot cadence is safe if idempotent.
- One instrument failing must not stop all instruments.
- This unlocks H103 later; do not build H103 signals in this task.
