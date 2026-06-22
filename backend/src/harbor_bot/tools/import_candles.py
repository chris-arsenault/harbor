"""Headless candle-sourcing CLI.

Run via the credential broker so OANDA practice secrets and the database URL are
injected for this command only:

    with-cred -- uv run python -m harbor_bot.tools.import_candles --days 180

Coverage-driven and idempotent (see harbor_bot.feed.ingest): only missing ranges
are fetched, so re-running fills gaps cheaply.
"""

import argparse
import asyncio

from harbor_bot.feed.ingest import SyncReport, sync_universe
from harbor_bot.persistence.database import create_engine
from harbor_bot.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Source OANDA bid/ask candles into the database.")
    parser.add_argument("--days", type=int, default=180, help="trailing window to keep covered")
    parser.add_argument(
        "--instruments",
        nargs="*",
        default=None,
        help="instruments to source (defaults to the research universe)",
    )
    args = parser.parse_args()
    asyncio.run(_run(days=args.days, instruments=args.instruments))


async def _run(*, days: int, instruments: list[str] | None) -> None:
    settings = Settings()
    settings.validate_startup()
    selected = (
        tuple(instrument.strip().upper() for instrument in instruments) if instruments else None
    )
    engine = create_engine(settings)
    try:
        reports = await sync_universe(
            settings=settings, engine=engine, days=days, instruments=selected
        )
    finally:
        await engine.dispose()
    for report in reports:
        print(_format_report(report))


def _format_report(report: SyncReport) -> str:
    window = f"{report.coverage_from} .. {report.coverage_to}"
    return (
        f"{report.instrument}: +{report.imported} sourced, "
        f"{report.candle_count} total candles [{window}]"
    )


if __name__ == "__main__":
    main()
