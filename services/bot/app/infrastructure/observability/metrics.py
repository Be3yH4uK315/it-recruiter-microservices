from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from prometheus_client import Counter, Gauge, Histogram

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


telegram_updates_received_total = Counter(
    "telegram_updates_received_total",
    "Total received telegram updates",
    ["update_type"],
)

telegram_updates_processed_total = Counter(
    "telegram_updates_processed_total",
    "Total processed telegram updates",
    ["update_type", "status"],
)

telegram_callbacks_failed_total = Counter(
    "telegram_callbacks_failed_total",
    "Total failed telegram callback actions",
    ["reason"],
)

downstream_request_duration_seconds = Histogram(
    "downstream_request_duration_seconds",
    "Duration of downstream HTTP requests",
    ["service", "endpoint", "method", "status_code"],
)

downstream_errors_total = Counter(
    "downstream_errors_total",
    "Total downstream HTTP errors",
    ["service", "endpoint", "method", "status_code"],
)

file_upload_total = Counter(
    "file_upload_total",
    "Total file upload attempts in bot file-flow",
    ["role", "kind", "status"],
)

active_conversations_total = Gauge(
    "active_conversations_total",
    "Current number of active conversation states in bot",
)


def mark_update_received(update_type: str) -> None:
    telegram_updates_received_total.labels(update_type=update_type or "unknown").inc()


def mark_update_processed(update_type: str, status: str) -> None:
    telegram_updates_processed_total.labels(
        update_type=update_type or "unknown",
        status=status or "unknown",
    ).inc()


def mark_callback_failed(reason: str) -> None:
    telegram_callbacks_failed_total.labels(reason=(reason or "unknown")).inc()


def mark_file_upload(role: str, kind: str, status: str) -> None:
    file_upload_total.labels(
        role=role or "unknown",
        kind=kind or "unknown",
        status=status or "unknown",
    ).inc()


def set_active_conversations(value: int) -> None:
    active_conversations_total.set(max(0, int(value)))


def mark_downstream_start(request) -> None:
    request.extensions["metrics_started_at"] = time.perf_counter()


def mark_downstream_end(request, response) -> None:
    started_at = request.extensions.get("metrics_started_at")
    if not isinstance(started_at, float):
        return

    elapsed = max(0.0, time.perf_counter() - started_at)
    service = _service_from_url(str(request.url))
    endpoint = _normalize_endpoint(str(request.url))
    method = str(request.method).upper()
    status_code = str(getattr(response, "status_code", "0") or "0")

    downstream_request_duration_seconds.labels(
        service=service,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
    ).observe(elapsed)

    if status_code.startswith("4") or status_code.startswith("5"):
        downstream_errors_total.labels(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        ).inc()


def mark_downstream_exception(request) -> None:
    service = _service_from_url(str(request.url))
    endpoint = _normalize_endpoint(str(request.url))
    method = str(request.method).upper()
    downstream_errors_total.labels(
        service=service,
        endpoint=endpoint,
        method=method,
        status_code="exception",
    ).inc()


def _service_from_url(raw_url: str) -> str:
    host = (urlparse(raw_url).hostname or "").lower()
    if "candidate" in host:
        return "candidate"
    if "employer" in host:
        return "employer"
    if "auth" in host:
        return "auth"
    if "search" in host:
        return "search"
    if "telegram" in host:
        return "telegram"
    return host or "unknown"


def _normalize_endpoint(raw_url: str) -> str:
    path = urlparse(raw_url).path or "/"
    parts = [item for item in path.split("/") if item]
    normalized_parts: list[str] = []
    for part in parts[:8]:
        if part.isdigit() or _UUID_RE.match(part):
            normalized_parts.append("{id}")
            continue
        if len(part) > 48:
            normalized_parts.append("{token}")
            continue
        normalized_parts.append(part)
    return "/" + "/".join(normalized_parts)
