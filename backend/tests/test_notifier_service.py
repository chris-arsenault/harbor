from datetime import UTC, datetime

import httpx
import pytest

from harbor_bot.notifier.models import NotificationConfig, NotificationEvent
from harbor_bot.notifier.ntfy import NtfyNotifier
from harbor_bot.notifier.service import NotifierService, RecordingNotifier
from harbor_bot.notifier.telegram import TelegramNotifier


@pytest.mark.asyncio
async def test_notifier_service_routes_enabled_events_to_ntfy_only() -> None:
    ntfy = RecordingNotifier(channel="ntfy")
    telegram = RecordingNotifier(channel="telegram")
    service = NotifierService(
        config=NotificationConfig(ntfy_enabled=True, telegram_enabled=False),
        ntfy=ntfy,
        telegram=telegram,
    )
    event = _event(event_type="fill")

    result = await service.notify(event)

    assert result.sent is True
    assert result.channels == ("ntfy",)
    assert ntfy.events == [event]
    assert telegram.events == []


@pytest.mark.asyncio
async def test_notifier_service_is_noop_when_channels_are_disabled() -> None:
    service = NotifierService(config=NotificationConfig())

    result = await service.notify(_event(event_type="heartbeat"))

    assert result.sent is False
    assert result.channels == ()
    assert result.skipped_reason == "all notifier channels disabled"


@pytest.mark.asyncio
async def test_ntfy_notifier_posts_to_configured_topic_with_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = NtfyNotifier(
            base_url="https://ntfy.local",
            topic="harbor",
            client=client,
        )
        result = await notifier.notify(_event(event_type="kill_switch"))

    assert result.sent is True
    assert result.channels == ("ntfy",)
    assert len(requests) == 1
    assert str(requests[0].url) == "https://ntfy.local/harbor"
    assert requests[0].headers["title"] == "Harbor kill_switch"
    assert requests[0].headers["tags"] == "harbor,kill_switch"
    assert requests[0].content == b"Daily loss guard tripped"


@pytest.mark.asyncio
async def test_telegram_notifier_uses_injected_http_client() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(
            bot_token="token",
            chat_id="chat",
            client=client,
        )
        result = await notifier.notify(_event(event_type="error"))

    assert result.sent is True
    assert result.channels == ("telegram",)
    assert requests[0].url.path == "/bottoken/sendMessage"
    assert requests[0].headers["content-type"] == "application/json"
    assert requests[0].read().decode()


def _event(*, event_type: str) -> NotificationEvent:
    return NotificationEvent(
        event_type=event_type,
        title=f"Harbor {event_type}",
        message="Daily loss guard tripped",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        severity="warning",
        data={"broker_trade_id": "7001"},
    )
