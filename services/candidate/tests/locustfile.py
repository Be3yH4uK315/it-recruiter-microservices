import random
import uuid
from datetime import datetime, timedelta

from jose import jwt
from locust import HttpUser, between, task

SECRET_KEY = "super-secret-key-change-me"
ALGORITHM = "HS256"


def generate_token(telegram_id: int) -> str:
    """Генерирует валидный JWT токен для теста."""
    payload = {"tg_id": telegram_id, "exp": datetime.utcnow() + timedelta(minutes=60)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class CandidateUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """
        Запускается при старте каждого 'виртуального пользователя'.
        Здесь мы генерируем ему ID и Токен.
        """
        self.telegram_id = random.randint(10000, 99999)
        self.token = generate_token(self.telegram_id)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        with self.client.post(
            "/v1/candidates/",
            json={
                "telegram_id": self.telegram_id,
                "display_name": f"LoadUser_{self.telegram_id}",
                "headline_role": "Load Tester",
                "contacts": {"email": "load@test.com"},
                "work_modes": ["remote"],
            },
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 409:
                response.success()

    @task(3)
    def view_my_profile(self):
        """
        Сценарий 1: Просмотр своего профиля.
        Вес 3 (выполняется часто).
        """
        self.client.get(
            f"/v1/candidates/by-telegram/{self.telegram_id}",
            headers=self.headers,
            name="/v1/candidates/by-telegram/{id}",
        )

    @task(1)
    def update_status(self):
        """
        Сценарий 2: Обновление статуса (запись в БД + отправка события).
        Вес 1 (выполняется реже).
        """
        headers = self.headers.copy()
        headers["Idempotency-Key"] = str(uuid.uuid4())

        new_status = random.choice(["active", "hidden"])

        self.client.patch(
            f"/v1/candidates/by-telegram/{self.telegram_id}",
            json={"status": new_status},
            headers=headers,
            name="/v1/candidates/update",
        )

    @task(1)
    def health_check(self):
        """
        Сценарий 3: Проверка здоровья (легкий запрос).
        """
        self.client.get("/health", name="/health")
