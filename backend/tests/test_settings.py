import pytest

from harbor_bot.settings import Settings


def test_settings_builds_async_database_url_from_compose_db_vars(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "192.168.66.3")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "harbor_app")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_NAME", "harbor")

    settings = Settings()

    assert settings.async_database_url == (
        "postgresql+asyncpg://harbor_app:secret@192.168.66.3:5432/harbor"
    )


def test_settings_normalizes_database_url_override_to_async_driver(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://override:secret@db.internal:5433/harbor_test")

    settings = Settings()

    assert settings.async_database_url == (
        "postgresql+asyncpg://override:secret@db.internal:5433/harbor_test"
    )


def test_settings_preserves_async_database_url_override(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://override:secret@db.internal:5433/harbor_test",
    )

    settings = Settings()

    assert settings.async_database_url == (
        "postgresql+asyncpg://override:secret@db.internal:5433/harbor_test"
    )


def test_oanda_settings_default_to_practice_without_credentials(monkeypatch) -> None:
    _clear_oanda_env(monkeypatch)

    settings = Settings()

    assert settings.oanda_env == "practice"
    assert settings.allow_live is False
    assert settings.oanda_api_token is None
    assert settings.oanda_account_id is None
    assert settings.oanda_rest_base_url == "https://api-fxpractice.oanda.com/v3"
    assert settings.oanda_stream_base_url == "https://stream-fxpractice.oanda.com/v3"
    assert settings.oanda_request_timeout_seconds == 10.0
    assert settings.oanda_stream_heartbeat_timeout_seconds == 20.0
    assert settings.oanda_reconnect_initial_seconds == 1.0
    assert settings.oanda_reconnect_max_seconds == 30.0
    assert settings.oanda_historical_candle_page_size == 5000
    assert settings.oanda_historical_import_count == 259_200
    assert settings.oanda_historical_request_interval_seconds == 0.1


def test_oanda_base_url_overrides_are_configuration(monkeypatch) -> None:
    _clear_oanda_env(monkeypatch)
    monkeypatch.setenv("OANDA_REST_BASE_URL", "http://oanda-rest.test/v3")
    monkeypatch.setenv("OANDA_STREAM_BASE_URL", "http://oanda-stream.test/v3")
    monkeypatch.setenv("OANDA_REQUEST_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("OANDA_STREAM_HEARTBEAT_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("OANDA_RECONNECT_INITIAL_SECONDS", "0.25")
    monkeypatch.setenv("OANDA_RECONNECT_MAX_SECONDS", "5")
    monkeypatch.setenv("OANDA_HISTORICAL_CANDLE_PAGE_SIZE", "250")
    monkeypatch.setenv("OANDA_HISTORICAL_IMPORT_COUNT", "1440")
    monkeypatch.setenv("OANDA_HISTORICAL_REQUEST_INTERVAL_SECONDS", "0.2")

    settings = Settings()

    assert settings.oanda_rest_base_url == "http://oanda-rest.test/v3"
    assert settings.oanda_stream_base_url == "http://oanda-stream.test/v3"
    assert settings.oanda_request_timeout_seconds == 2.5
    assert settings.oanda_stream_heartbeat_timeout_seconds == 7.5
    assert settings.oanda_reconnect_initial_seconds == 0.25
    assert settings.oanda_reconnect_max_seconds == 5.0
    assert settings.oanda_historical_candle_page_size == 250
    assert settings.oanda_historical_import_count == 1440
    assert settings.oanda_historical_request_interval_seconds == 0.2


def test_live_oanda_base_urls_require_allow_live(monkeypatch) -> None:
    _clear_oanda_env(monkeypatch)
    monkeypatch.setenv("OANDA_ENV", "live")

    settings = Settings()

    with pytest.raises(ValueError, match="ALLOW_LIVE=true"):
        _ = settings.oanda_rest_base_url
    with pytest.raises(ValueError, match="ALLOW_LIVE=true"):
        _ = settings.oanda_stream_base_url

    monkeypatch.setenv("ALLOW_LIVE", "true")
    allowed = Settings()

    assert allowed.oanda_rest_base_url == "https://api-fxtrade.oanda.com/v3"
    assert allowed.oanda_stream_base_url == "https://stream-fxtrade.oanda.com/v3"


def test_startup_validation_rejects_live_mode_without_allow_live(monkeypatch) -> None:
    _clear_oanda_env(monkeypatch)
    monkeypatch.setenv("OANDA_ENV", "live")

    settings = Settings()

    with pytest.raises(ValueError, match="ALLOW_LIVE=true"):
        settings.validate_startup()


def test_startup_summary_redacts_database_password(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://harbor:super-secret@db:5432/harbor")

    settings = Settings()
    summary = settings.validate_startup()

    assert summary["database_url"] == "postgresql+asyncpg://harbor:***@db:5432/harbor"
    assert "super-secret" not in str(summary)


def _clear_oanda_env(monkeypatch) -> None:
    for name in (
        "OANDA_ENV",
        "ALLOW_LIVE",
        "OANDA_API_TOKEN",
        "OANDA_ACCOUNT_ID",
        "OANDA_REST_BASE_URL",
        "OANDA_STREAM_BASE_URL",
        "OANDA_REQUEST_TIMEOUT_SECONDS",
        "OANDA_STREAM_HEARTBEAT_TIMEOUT_SECONDS",
        "OANDA_RECONNECT_INITIAL_SECONDS",
        "OANDA_RECONNECT_MAX_SECONDS",
        "OANDA_HISTORICAL_CANDLE_PAGE_SIZE",
        "OANDA_HISTORICAL_IMPORT_COUNT",
        "OANDA_HISTORICAL_REQUEST_INTERVAL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
