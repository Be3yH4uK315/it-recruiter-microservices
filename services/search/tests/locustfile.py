import random
import uuid

from locust import HttpUser, between, task


class SearchUser(HttpUser):
    wait_time = between(0.5, 2)

    @task
    def search_candidate(self):
        """
        Имитируем запрос от Employer Service.
        """
        payload = {
            "session_id": str(uuid.uuid4()),
            "filters": {
                "role": "Python Developer",
                "must_skills": ["Python", "FastAPI", "PostgreSQL"],
                "experience_min": random.randint(1, 5),
                "location": "Moscow",
            },
            "session_exclude_ids": [str(uuid.uuid4()) for _ in range(5)],
        }

        self.client.post("/v1/search/next", json=payload, name="/search/next")

    @task(1)
    def health(self):
        self.client.get("/health")
