# research

Pure, offline-capable research analysis that sits beside the strategy core but is not part of
the live trading path. Reserved home for the base-rate conditional-edge study (ADR 0005):
reuse `strategy/sweeps.py` to detect sweeps over persisted candles, then measure forward
N-minute return distributions in the reversal direction, conditioned by level type, session,
and volatility, against a chance baseline.

This package must stay pure (no network, database, clock, or broker I/O) like `strategy_core`;
data is passed in by the caller. The API layer wires it to persisted candles and the Lab UI.

Not yet implemented — see `STRATEGY-RESEARCH-PLAN.md` (milestone M1).
