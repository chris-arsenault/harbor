"""Pure, offline-capable research analysis beside the strategy core.

Holds analysis that informs strategy work but is not part of the live trading
path (ADR 0005). Like ``strategy_core``, this package must stay pure: no
network, database, clock, broker, or UI I/O — data is passed in by the caller.
"""
