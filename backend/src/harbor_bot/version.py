import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from harbor_bot import __version__
from harbor_bot.settings import Settings

APP_NAME = "harbor"
UNKNOWN_BUILD_VALUE = "unknown"
BUILD_TIME_FILE = Path("/app/.build_time")


@dataclass(frozen=True)
class VersionInfo:
    app: str
    version: str
    git_sha: str
    build_time: str
    started_at: datetime
    mode: str

    def to_jsonable(self) -> dict[str, str]:
        return {
            "app": self.app,
            "version": self.version,
            "git_sha": self.git_sha,
            "build_time": self.build_time,
            "started_at": _isoformat_utc(self.started_at),
            "mode": self.mode,
        }


def build_version_info(
    settings: Settings,
    *,
    started_at: datetime | None = None,
) -> VersionInfo:
    return VersionInfo(
        app=APP_NAME,
        version=__version__,
        git_sha=_build_env("HARBOR_GIT_SHA"),
        build_time=_build_time(),
        started_at=started_at or datetime.now(tz=UTC),
        mode=settings.oanda_env.lower(),
    )


def _build_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    return value or UNKNOWN_BUILD_VALUE


def _build_time() -> str:
    build_time = _build_env("HARBOR_BUILD_TIME")
    if build_time != UNKNOWN_BUILD_VALUE:
        return build_time
    try:
        value = BUILD_TIME_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return UNKNOWN_BUILD_VALUE
    return value or UNKNOWN_BUILD_VALUE


def _isoformat_utc(value: datetime) -> str:
    normalized = value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")
