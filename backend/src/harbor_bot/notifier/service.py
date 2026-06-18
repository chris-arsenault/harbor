from typing import Protocol

from harbor_bot.notifier.models import NotificationConfig, NotificationEvent, NotificationResult


class Notifier(Protocol):
    channel: str

    async def notify(self, event: NotificationEvent) -> NotificationResult:
        raise NotImplementedError


class NotifierService:
    def __init__(
        self,
        *,
        config: NotificationConfig,
        ntfy: Notifier | None = None,
        telegram: Notifier | None = None,
    ) -> None:
        self._config = config
        self._ntfy = ntfy
        self._telegram = telegram

    async def notify(self, event: NotificationEvent) -> NotificationResult:
        enabled: list[Notifier] = []
        if self._config.ntfy_enabled and self._ntfy is not None:
            enabled.append(self._ntfy)
        if self._config.telegram_enabled and self._telegram is not None:
            enabled.append(self._telegram)
        if not enabled:
            return NotificationResult(
                sent=False,
                channels=(),
                skipped_reason="all notifier channels disabled",
            )

        channels: list[str] = []
        for notifier in enabled:
            result = await notifier.notify(event)
            channels.extend(result.channels)
        return NotificationResult(sent=True, channels=tuple(channels))


class RecordingNotifier:
    def __init__(self, *, channel: str) -> None:
        self.channel = channel
        self.events: list[NotificationEvent] = []

    async def notify(self, event: NotificationEvent) -> NotificationResult:
        self.events.append(event)
        return NotificationResult(sent=True, channels=(self.channel,))
