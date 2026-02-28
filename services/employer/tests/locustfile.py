import random
import uuid
from locust import HttpUser, task, between
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "super-secret-key-change-me"
ALGORITHM = "HS256"

def generate_token(tg_id: int):
    payload = {
        "tg_id": tg_id,
        "role": "employer",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

class EmployerUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Инициализация:
        1. Генерируем токен.
        2. Регистрируем работодателя.
        3. Создаем реальную сессию поиска.
        """
        self.telegram_id = random.randint(100000, 999999)
        self.token = generate_token(self.telegram_id)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        reg_payload = {
            "telegram_id": self.telegram_id,
            "company": f"LoadTest Corp {self.telegram_id}",
            "contacts": {"email": f"hr{self.telegram_id}@test.com"}
        }
        with self.client.post("/v1/employers/", json=reg_payload, headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 201 or resp.status_code == 200:
                self.employer_id = resp.json()["id"]
            else:
                resp.failure(f"Registration failed: {resp.text}")
                return

        search_payload = {
            "title": "Python Dev",
            "filters": {
                "role": "Python Developer",
                "experience_min": 1,
                "must_skills": ["Python", "FastAPI"]
            }
        }
        with self.client.post(f"/v1/employers/{self.employer_id}/searches", json=search_payload, headers=self.headers, catch_response=True) as resp:
            if resp.status_code == 200:
                self.session_id = resp.json()["id"]
            else:
                resp.failure(f"Search session creation failed: {resp.text}")
                self.session_id = None

    @task(5)
    def get_next_candidate(self):
        """Сценарий: Получение следующего кандидата (Свайп)."""
        if not self.session_id: return
        self.client.post(
            f"/v1/employers/searches/{self.session_id}/next",
            headers=self.headers,
            name="/v1/employers/searches/next"
        )

    @task(2)
    def make_decision(self):
        """Сценарий: Принятие решения."""
        if not self.session_id: return
        
        payload = {
            "candidate_id": str(uuid.uuid4()),
            "decision": random.choice(["like", "skip"]),
            "note": "Load test decision"
        }
        
        self.client.post(
            f"/v1/employers/searches/{self.session_id}/decisions",
            json=payload,
            headers=self.headers,
            name="/v1/employers/searches/decisions"
        )

    @task(1)
    def health_check(self):
        self.client.get("/health")
