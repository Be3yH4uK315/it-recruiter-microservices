from __future__ import annotations

import logging

from app.config import Settings
from app.infrastructure.observability.logger import (
    JsonFormatter,
    PlainFormatter,
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)


def test_request_id_context_roundtrip() -> None:
    set_request_id("req-123")
    assert get_request_id() == "req-123"

    set_request_id(None)
    assert get_request_id() is None


def test_json_formatter_includes_request_id() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"

    output = formatter.format(record)

    assert '"message": "hello"' in output
    assert '"request_id": "req-123"' in output


def test_plain_formatter_includes_request_id() -> None:
    formatter = PlainFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"

    output = formatter.format(record)

    assert "INFO test.logger:" in output
    assert "[request_id=req-123]" in output
    assert "hello" in output


def test_configure_logging_sets_root_logger() -> None:
    settings = Settings(
        log_level="INFO",
        log_json=False,
    )

    configure_logging(settings)

    logger = get_logger("test.logger")
    logger.info("configured")

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) >= 1
