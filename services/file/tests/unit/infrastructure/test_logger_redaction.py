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


def test_json_formatter_redacts_tokens_and_s3_keys() -> None:
    record = _make_record(
        msg="POST https://api.telegram.org/bot123456:ABCDEF/sendMessage",
        extra={
            "telegram_bot_token": "123456:ABCDEF",
            "internal_service_token": "internal-secret",
            "s3_access_key": "minio",
            "s3_secret_key": "minio123",
            "aws_access_key_id": "AKIA_TEST",
            "aws_secret_access_key": "aws-secret",
            "webhook_url": "https://api.telegram.org/file/bot123456:ABCDEF/photos/file.jpg",
        },
    )

    rendered = JsonFormatter().format(record)

    for raw in (
        "123456:ABCDEF",
        "internal-secret",
        "minio123",
        "AKIA_TEST",
        "aws-secret",
    ):
        assert raw not in rendered
    assert "/bot***/sendMessage" in rendered
    assert "/file/bot***/photos/file.jpg" in rendered
    assert '"telegram_bot_token": "***"' in rendered
    assert '"internal_service_token": "***"' in rendered
    assert '"s3_secret_key": "***"' in rendered


def test_plain_formatter_redacts_assignment_style_secrets() -> None:
    record = _make_record(
        msg=(
            "Loaded BOT_TOKEN=123456:ABCDEF "
            "internal_service_token=internal-secret "
            "s3_secret_key=minio123"
        )
    )

    rendered = PlainFormatter().format(record)

    assert "123456:ABCDEF" not in rendered
    assert "internal-secret" not in rendered
    assert "minio123" not in rendered
    assert "BOT_TOKEN=***" in rendered
    assert "internal_service_token=***" in rendered
    assert "s3_secret_key=***" in rendered
