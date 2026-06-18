import httpx

from harbor_bot.notifier.models import NotificationEvent, NotificationResult


class TelegramNotifier:
    channel = "telegram"

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        client: httpx.AsyncClient,
        base_url: str = "https://api.telegram.org",
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def notify(self, event: NotificationEvent) -> NotificationResult:
        await self._client.post(
            f"{self._base_url}/bot{self._bot_token}/sendMessage",
            json={
                "chat_id": self._chat_id,
                "disable_notification": event.severity == "heartbeat",
                "text": f"{event.title}\n{event.message}",
            },
        )
        return NotificationResult(sent=True, channels=(self.channel,))
