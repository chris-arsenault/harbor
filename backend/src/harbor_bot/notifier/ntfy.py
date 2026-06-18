import httpx

from harbor_bot.notifier.models import NotificationEvent, NotificationResult


class NtfyNotifier:
    channel = "ntfy"

    def __init__(
        self,
        *,
        base_url: str,
        topic: str,
        client: httpx.AsyncClient,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._topic = topic.strip("/")
        self._client = client

    async def notify(self, event: NotificationEvent) -> NotificationResult:
        await self._client.post(
            f"{self._base_url}/{self._topic}",
            content=event.message.encode("utf-8"),
            headers={
                "Priority": _priority(event.severity),
                "Tags": f"harbor,{event.event_type}",
                "Title": event.title,
            },
        )
        return NotificationResult(sent=True, channels=(self.channel,))


def _priority(severity: str) -> str:
    if severity in {"error", "critical"}:
        return "high"
    if severity == "warning":
        return "default"
    return "low"
