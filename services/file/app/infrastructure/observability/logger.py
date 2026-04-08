from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.config import Settings

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_REDACTED = "***"

_TELEGRAM_URL_TOKEN_RE = re.compile(r"(/(?:file/)?bot)([^/\s]+)")
_SENSITIVE_FIELD_NAMES = {
    "bot_token",
    "telegram_bot_token",
    "internal_service_token",
    "s3_access_key",
    "s3_secret_key",
    "aws_access_key_id",
    "aws_secret_access_key",
}
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r'(?P<prefix>\b(?:BOT_TOKEN|TELEGRAM_BOT_TOKEN|bot_token|telegram_bot_token|internal_service_token|s3_access_key|s3_secret_key|aws_access_key_id|aws_secret_access_key)\b\s*[=:]\s*[\'"]?)(?P<value>[^\'"\s,}]+)',
    re.IGNORECASE,
)
_SENSITIVE_JSON_FIELD_RE = re.compile(
    r'(?P<prefix>"(?:BOT_TOKEN|TELEGRAM_BOT_TOKEN|bot_token|telegram_bot_token|internal_service_token|s3_access_key|s3_secret_key|aws_access_key_id|aws_secret_access_key)"\s*:\s*")(?P<value>[^"]+)',
    re.IGNORECASE,
)

_RESERVED_LOG_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "request_id",
}


def set_request_id(request_id: str | None) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def _redact_sensitive_text(value: str) -> str:
    redacted = _TELEGRAM_URL_TOKEN_RE.sub(rf"\1{_REDACTED}", value)
    redacted = _SENSITIVE_ASSIGNMENT_RE.sub(rf"\g<prefix>{_REDACTED}", redacted)
    redacted = _SENSITIVE_JSON_FIELD_RE.sub(rf"\g<prefix>{_REDACTED}", redacted)
    return redacted


def _sanitize_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_sensitive_text(value)
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in _SENSITIVE_FIELD_NAMES:
                sanitized[key] = _REDACTED
            else:
                sanitized[key] = _sanitize_log_value(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_log_value(item) for item in value)
    return value


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_sensitive_text(record.getMessage()),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        extra_fields = self._extract_extra_fields(record)
        if extra_fields:
            payload["extra"] = extra_fields

        if record.exc_info:
            payload["exc_info"] = _redact_sensitive_text(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            if key.strip().lower() in _SENSITIVE_FIELD_NAMES:
                extracted[key] = _REDACTED
            else:
                extracted[key] = _sanitize_log_value(value)
        return extracted


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None)
        prefix = f"[request_id={request_id}] " if request_id else ""
        message = (
            f"{record.levelname} {record.name}: "
            f"{prefix}{_redact_sensitive_text(record.getMessage())}"
        )

        extra_fields = JsonFormatter._extract_extra_fields(record)
        if extra_fields:
            message = f"{message} | extra={json.dumps(extra_fields, ensure_ascii=False)}"

        if record.exc_info:
            return f"{message}\n{_redact_sensitive_text(self.formatException(record.exc_info))}"
        return message


def configure_logging(settings: Settings) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.log_level)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter() if settings.log_json else PlainFormatter())
    root_logger.addHandler(handler)

    logging.captureWarnings(True)

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.engine",
        "aio_pika",
        "aioboto3",
        "botocore",
        "boto3",
    ):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    if not settings.sql_echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
