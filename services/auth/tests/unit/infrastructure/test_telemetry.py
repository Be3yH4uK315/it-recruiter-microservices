from __future__ import annotations

from app.infrastructure.observability.telemetry import TelemetryHandle, init_telemetry


def test_init_telemetry_returns_handle() -> None:
    handle = init_telemetry(
        service_name="auth-service",
        service_version="0.1.0",
        environment="test",
    )

    assert isinstance(handle, TelemetryHandle)
    assert isinstance(handle.enabled, bool)
