from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class TelemetryHandle:
    enabled: bool = False
    provider: Any | None = None
    exporter: str | None = None
    reason: str | None = None


def init_telemetry(
    *,
    service_name: str,
    service_version: str,
    environment: str,
) -> TelemetryHandle:
    if environment.strip().lower() == "test":
        return TelemetryHandle(enabled=False, reason="disabled_in_test_env")
    if os.getenv("OTEL_SDK_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return TelemetryHandle(enabled=False, reason="disabled_by_env")

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        return TelemetryHandle(enabled=False, reason=f"otel_import_error:{exc.__class__.__name__}")

    try:
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": environment,
            }
        )

        provider = TracerProvider(resource=resource)
        exporter_name: str | None = None

        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            exporter_name = "otlp_grpc"
        except Exception:
            exporter_name = None

        current_provider = trace.get_tracer_provider()
        if isinstance(current_provider, TracerProvider):
            return TelemetryHandle(
                enabled=True,
                provider=current_provider,
                exporter=exporter_name,
                reason="already_configured",
            )

        trace.set_tracer_provider(provider)
        return TelemetryHandle(
            enabled=True,
            provider=provider,
            exporter=exporter_name,
        )
    except Exception as exc:
        return TelemetryHandle(enabled=False, reason=f"otel_setup_error:{exc.__class__.__name__}")


def instrument_app_requests(
    app: Any,
    *,
    service_name: str,
) -> bool:
    if os.getenv("OTEL_SDK_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False

    state = getattr(app, "state", None)
    if state is not None and getattr(state, "_telemetry_request_middleware", False):
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        tracer = trace.get_tracer(service_name)

        @app.middleware("http")
        async def _otel_request_span_middleware(request, call_next):
            span_name = f"{request.method} {request.url.path}"
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("http.method", request.method)
                span.set_attribute("http.target", request.url.path)
                span.set_attribute("http.scheme", request.url.scheme)
                span.set_attribute("http.host", request.url.netloc)

                try:
                    response = await call_next(request)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    raise

                span.set_attribute("http.status_code", response.status_code)
                return response

        if state is not None:
            state._telemetry_request_middleware = True
        return True
    except Exception:
        return False


def shutdown_telemetry(handle: TelemetryHandle) -> None:
    if not handle.enabled or handle.provider is None:
        return

    shutdown = getattr(handle.provider, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            return
