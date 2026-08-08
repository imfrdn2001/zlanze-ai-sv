import json
import logging

from app.logging_config import JsonFormatter


def test_json_formatter_includes_analytics_fields() -> None:
    record = logging.LogRecord(
        "ai_advisor.query",
        logging.INFO,
        __file__,
        1,
        "chat_turn_completed",
        (),
        None,
    )
    record.chat_id = "chat-1"
    record.intents = ["find_developer"]

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "chat_turn_completed"
    assert payload["chat_id"] == "chat-1"
    assert payload["intents"] == ["find_developer"]
    assert "timestamp" in payload
