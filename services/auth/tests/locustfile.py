import random

from locust import HttpUser, between, task

INTERNAL_BOT_SECRET = "super-secret-bot-password-change-me"


class AuthUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def login_bot(self):
        """
        Имитируем массовый вход пользователей через бота.
        Это создает нагрузку на БД (SELECT/INSERT) и CPU (JWT Sign + Hashing).
        """
        tg_id = random.randint(100000, 999999)
        payload = {
            "telegram_id": tg_id,
            "username": f"user_{tg_id}",
            "bot_secret": INTERNAL_BOT_SECRET,
        }

        self.client.post("/v1/auth/login/bot", json=payload, name="/auth/login/bot")

    @task(1)
    def health(self):
        self.client.get("/health")
