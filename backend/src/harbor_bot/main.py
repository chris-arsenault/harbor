import json
import logging
import sys
from datetime import UTC, datetime

import uvicorn

from harbor_bot.settings import Settings, redact_secret_text


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secret_text(record.getMessage()),
        }
        if record.exc_info is not None:
            payload["exc_info"] = redact_secret_text(self.formatException(record.exc_info))
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)
    return root_logger


def main() -> None:
    configure_logging()
    Settings().validate_startup()
    uvicorn.run("harbor_bot.api:app", host="0.0.0.0", port=8080, log_config=None)


if __name__ == "__main__":
    main()
