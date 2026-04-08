from __future__ import annotations

from locust import HttpUser, task

from loadtests.common import (
    LoadTestConfig,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("bot")


class BotUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "bot health")

    @task(4)
    def internal_state(self) -> None:
        with self.client.get(
            "/api/v1/internal/state/1001",
            name="internal_state",
            headers=render_request_headers(CONFIG, internal=True),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "bot internal state")

    @task(3)
    def webhook(self) -> None:
        with self.client.post(
            "/api/v1/telegram/webhook",
            name="telegram_webhook",
            headers=render_request_headers(
                CONFIG,
                extra={"X-Telegram-Bot-Api-Secret-Token": CONFIG.webhook_secret or ""},
            ),
            json={
                "update_id": 1,
                "message": {
                    "message_id": 10,
                    "from": {"id": 123, "is_bot": False, "first_name": "Load"},
                    "chat": {"id": 123, "type": "private"},
                    "text": "/start",
                },
            },
            catch_response=True,
        ) as response:
            expect_status(response, 200, "bot telegram webhook")
