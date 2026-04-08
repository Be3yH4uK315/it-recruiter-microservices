from __future__ import annotations

import logging

from app.infrastructure.observability.logger import JsonFormatter, PlainFormatter


def _make_record(*, msg: str, extra: dict | None = None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if extra:
        for key, value in extra.items():
            setattr(record, key, value)
    return record


def test_json_formatter_redacts_telegram_token_in_message_and_extra() -> None:
    record = _make_record(
        msg="POST https://api.telegram.org/bot123456:ABCDEF/sendMessage",
        extra={
            "webhook_url": "https://api.telegram.org/file/bot123456:ABCDEF/photos/file.jpg",
            "telegram_bot_token": "123456:ABCDEF",
        },
    )

    rendered = JsonFormatter().format(record)

    assert "123456:ABCDEF" not in rendered
    assert "/bot***/sendMessage" in rendered
    assert "/file/bot***/photos/file.jpg" in rendered
    assert '"telegram_bot_token": "***"' in rendered


def test_plain_formatter_redacts_assignment_style_token() -> None:
    record = _make_record(msg="Loaded BOT_TOKEN=123456:ABCDEF")

    rendered = PlainFormatter().format(record)

    assert "123456:ABCDEF" not in rendered
    assert "BOT_TOKEN=***" in rendered
