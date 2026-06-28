import re
from typing import Any

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

PRACTICE_REST_BASE_URL = "https://api-fxpractice.oanda.com/v3"
PRACTICE_STREAM_BASE_URL = "https://stream-fxpractice.oanda.com/v3"
LIVE_REST_BASE_URL = "https://api-fxtrade.oanda.com/v3"
LIVE_STREAM_BASE_URL = "https://stream-fxtrade.oanda.com/v3"
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|api[_-]?key|password|secret)=([^\s,;]+)",
    re.IGNORECASE,
)
URL_PASSWORD_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:\s/@]+):([^@\s]+)@")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_user: str = Field(default="harbor_app", validation_alias="DB_USER")
    db_password: str = Field(default="", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="harbor", validation_alias="DB_NAME")

    oanda_env: str = Field(default="practice", validation_alias="OANDA_ENV")
    allow_live: bool = Field(default=False, validation_alias="ALLOW_LIVE")
    oanda_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OANDA_API_TOKEN", "OANDA_API_KEY"),
    )
    oanda_account_id: str | None = Field(default=None, validation_alias="OANDA_ACCOUNT_ID")
    oanda_rest_base_url_override: str | None = Field(
        default=None,
        validation_alias="OANDA_REST_BASE_URL",
    )
    oanda_stream_base_url_override: str | None = Field(
        default=None,
        validation_alias="OANDA_STREAM_BASE_URL",
    )
    oanda_request_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="OANDA_REQUEST_TIMEOUT_SECONDS",
    )
    oanda_stream_heartbeat_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="OANDA_STREAM_HEARTBEAT_TIMEOUT_SECONDS",
    )
    oanda_reconnect_initial_seconds: float = Field(
        default=1.0,
        validation_alias="OANDA_RECONNECT_INITIAL_SECONDS",
    )
    oanda_reconnect_max_seconds: float = Field(
        default=30.0,
        validation_alias="OANDA_RECONNECT_MAX_SECONDS",
    )
    oanda_historical_candle_page_size: int = Field(
        default=5000,
        validation_alias="OANDA_HISTORICAL_CANDLE_PAGE_SIZE",
    )
    oanda_historical_import_count: int = Field(
        default=259_200,
        validation_alias="OANDA_HISTORICAL_IMPORT_COUNT",
    )
    oanda_historical_request_interval_seconds: float = Field(
        default=0.1,
        validation_alias="OANDA_HISTORICAL_REQUEST_INTERVAL_SECONDS",
    )
    oanda_pricing_stream_enabled: bool = Field(
        default=False,
        validation_alias="HARBOR_LIVE_INGEST_ENABLED",
    )
    oanda_book_recorder_enabled: bool = Field(
        default=True,
        validation_alias="OANDA_BOOK_RECORDER_ENABLED",
    )
    oanda_book_poll_interval_seconds: float = Field(
        default=300.0,
        validation_alias="OANDA_BOOK_POLL_INTERVAL_SECONDS",
    )
    research_instruments_csv: str = Field(
        default="GBP_USD,EUR_USD,USD_JPY,EUR_JPY,GBP_JPY,AUD_JPY,AUD_USD,EUR_GBP",
        validation_alias="HARBOR_RESEARCH_INSTRUMENTS",
    )

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return _normalize_async_postgres_url(self.database_url)

        return URL.create(
            "postgresql+asyncpg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    @property
    def oanda_rest_base_url(self) -> str:
        if self.oanda_rest_base_url_override:
            return self.oanda_rest_base_url_override
        return _oanda_base_url(
            env=self.oanda_env,
            allow_live=self.allow_live,
            practice_url=PRACTICE_REST_BASE_URL,
            live_url=LIVE_REST_BASE_URL,
        )

    @property
    def oanda_stream_base_url(self) -> str:
        if self.oanda_stream_base_url_override:
            return self.oanda_stream_base_url_override
        return _oanda_base_url(
            env=self.oanda_env,
            allow_live=self.allow_live,
            practice_url=PRACTICE_STREAM_BASE_URL,
            live_url=LIVE_STREAM_BASE_URL,
        )

    def validate_startup(self) -> dict[str, Any]:
        normalized_env = self.oanda_env.lower()
        if normalized_env not in {"practice", "live"}:
            msg = "OANDA_ENV must be 'practice' or 'live'"
            raise ValueError(msg)
        if normalized_env == "live" and not self.allow_live:
            msg = "OANDA live mode requires ALLOW_LIVE=true"
            raise ValueError(msg)

        database_url = self.async_database_url
        _ = self.oanda_rest_base_url
        _ = self.oanda_stream_base_url
        return {
            "database_url": redact_secret_text(database_url),
            "oanda_env": normalized_env,
            "allow_live": self.allow_live,
            "practice_only": normalized_env == "practice",
        }

    @property
    def research_instruments(self) -> tuple[str, ...]:
        return tuple(
            item.strip().upper()
            for item in self.research_instruments_csv.split(",")
            if item.strip()
        )


def redact_secret_text(value: object) -> str:
    text = str(value)
    text = URL_PASSWORD_PATTERN.sub(r"\1:***@", text)
    return SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=***", text)


def _normalize_async_postgres_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        msg = "DATABASE_URL must use a PostgreSQL driver"
        raise ValueError(msg)
    return url.render_as_string(hide_password=False)


def _oanda_base_url(*, env: str, allow_live: bool, practice_url: str, live_url: str) -> str:
    normalized = env.lower()
    if normalized == "practice":
        return practice_url
    if normalized == "live":
        if not allow_live:
            msg = "OANDA live base URLs require ALLOW_LIVE=true"
            raise ValueError(msg)
        return live_url
    msg = "OANDA_ENV must be 'practice' or 'live'"
    raise ValueError(msg)
