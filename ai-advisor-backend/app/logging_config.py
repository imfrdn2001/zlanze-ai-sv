import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Write one machine-readable JSON object per log line."""

    _standard_fields = set(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_fields and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    level: str,
    log_file: str,
    max_bytes: int,
    backup_count: int,
) -> None:
    """Configure console logs plus rotating JSONL analytics logs."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    logger = logging.getLogger("ai_advisor")
    logger.setLevel(numeric_level)

    # Lifespan can run more than once in tests; never attach duplicate handlers.
    if any(getattr(handler, "_advisor_json_handler", False) for handler in logger.handlers):
        return

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(numeric_level)
    handler.setFormatter(JsonFormatter())
    handler._advisor_json_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
