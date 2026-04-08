from __future__ import annotations

import os

import pytest


def _run_integration_enabled() -> bool:
    return os.getenv("RUN_INTEGRATION", "").strip().lower() in {"1", "true", "yes", "on"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if _run_integration_enabled():
        return

    skip_integration = pytest.mark.skip(
        reason="integration tests are disabled by default; set RUN_INTEGRATION=1",
    )
    for item in items:
        if "/tests/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(skip_integration)
