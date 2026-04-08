from __future__ import annotations

from unittest.mock import patch

from app.worker import main


def test_worker_entrypoint_calls_asyncio_run() -> None:
    captured = {}

    def fake_run(coro):
        captured["coro"] = coro
        coro.close()
        return None

    with patch("app.worker.asyncio.run", side_effect=fake_run) as run_mock:
        main()

    run_mock.assert_called_once()
    assert "coro" in captured
