import random

from jose import jwt
from locust import HttpUser, between, task

SECRET_KEY = "super-secret-key-change-me"


def generate_token():
    payload = {"tg_id": random.randint(1000, 9999)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


class FileUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.token = generate_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def upload_file(self):
        """Загрузка небольшого файла."""
        files = {
            "file": (
                "stress_test.txt",
                b"some dummy content for load testing",
                "text/plain",
            )
        }
        data = {"file_type": "resume"}

        self.client.post(
            "/v1/files/upload",
            files=files,
            data=data,
            headers=self.headers,
            name="/files/upload",
        )

    @task(1)
    def health(self):
        self.client.get("/health")
