from __future__ import annotations

from locust import HttpUser, task

from loadtests.common import (
    LoadTestConfig,
    bot_login,
    expect_status,
    generate_telegram_id,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("auth")


class AuthUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        self.telegram_id = generate_telegram_id(610)
        self.username = f"auth_loadtest_{self.telegram_id}"
        self.session = bot_login(
            CONFIG,
            role="employer",
            telegram_id=self.telegram_id,
            username=self.username,
            first_name="Auth",
            last_name="User",
        )

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "auth health")

    @task(5)
    def login_via_bot(self) -> None:
        with self.client.post(
            "/api/v1/auth/login/bot",
            name="login_via_bot",
            headers=render_request_headers(CONFIG, internal=True),
            json={
                "telegram_id": self.telegram_id,
                "role": "employer",
                "username": self.username,
                "first_name": "Auth",
                "last_name": "User",
                "photo_url": "https://example.com/auth-loadtest.jpg",
            },
            catch_response=True,
        ) as response:
            expect_status(response, 200, "auth login_via_bot")
            if response.status_code == 200:
                self.session = response.json()

    @task(3)
    def refresh(self) -> None:
        with self.client.post(
            "/api/v1/auth/refresh",
            name="refresh",
            json={"refresh_token": self.session["refresh_token"]},
            headers=render_request_headers(CONFIG),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "auth refresh")
            if response.status_code == 200:
                self.session = response.json()

    @task(2)
    def verify_access_token(self) -> None:
        with self.client.post(
            "/api/v1/internal/auth/verify",
            name="internal_verify",
            json={"access_token": self.session["access_token"]},
            headers=render_request_headers(CONFIG, internal=True),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "auth internal verify")
