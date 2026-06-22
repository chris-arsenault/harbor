"""Headless walk-forward optimization CLI.

Runs the research-protocol optimizer over sourced persisted candles to
completion (synchronously, not queued) for one instrument, then prints the
study outcome. Run via the credential broker for the database URL:

    with-cred -- uv run python -m harbor_bot.tools.optimize --instrument EUR_USD

Source candles first with ``harbor_bot.tools.import_candles``.
"""

import argparse
import asyncio
from typing import Any

from harbor_bot.optimizer.service import OptimizerService
from harbor_bot.persistence.database import create_engine
from harbor_bot.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a walk-forward optimization study.")
    parser.add_argument(
        "--instrument",
        default=None,
        help="instrument to optimize (defaults to the configured strategy instrument)",
    )
    args = parser.parse_args()
    asyncio.run(_run(instrument=args.instrument))


async def _run(*, instrument: str | None) -> None:
    settings = Settings()
    settings.validate_startup()
    payload: dict[str, Any] = {"source": "persisted_candles"}
    if instrument:
        payload["instrument"] = instrument.strip().upper()
    engine = create_engine(settings)
    service = OptimizerService(persistence_engine=engine)
    try:
        result = await service.start_optimization(payload, background_tasks=None)
    finally:
        await engine.dispose()
    for line in _format_result(result):
        print(line)


def _format_result(result: dict[str, Any]) -> list[str]:
    lines = [
        f"study {result.get('study_id')}: {result['status']}, "
        f"{result['trial_count']} trials, {len(result.get('candidates', []))} candidates"
    ]
    for candidate in result.get("candidates", []):
        lines.append(
            f"  candidate {candidate['label']} ({candidate['status']}) "
            f"from trial #{candidate['source_trial_no']}"
        )
    return lines


if __name__ == "__main__":
    main()
