from __future__ import annotations

from uuid import uuid4

from locust import HttpUser, task

from loadtests.common import (
    LoadTestConfig,
    ensure_candidate_profile,
    ensure_employer_profile,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
    request_json,
)

CONFIG: LoadTestConfig = load_config("employer")


class EmployerUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        candidate = ensure_candidate_profile(CONFIG)
        employer = ensure_employer_profile(CONFIG)
        session = request_json(
            "POST",
            f"{CONFIG.service_urls['employer']}/api/v1/employers/{employer['employer_id']}/searches",
            expected_statuses=201,
            headers=render_request_headers(CONFIG, access_token=employer["access_token"]),
            json_body={
                "title": f"Loadtest Search {uuid4()}",
                "filters": {
                    "role": "Python Backend Engineer",
                    "must_skills": [{"skill": "python", "level": 5}],
                    "nice_skills": [{"skill": "fastapi", "level": 4}],
                    "location": "Novosibirsk",
                    "work_modes": ["remote", "hybrid"],
                    "salary_min": 100000,
                    "salary_max": 400000,
                    "currency": "RUB",
                    "english_level": "B2",
                },
            },
            timeout=CONFIG.request_timeout_sec,
        )
        self.ctx = {
            "candidate_id": candidate["candidate_id"],
            "employer_id": employer["employer_id"],
            "employer_access_token": employer["access_token"],
            "employer_telegram_id": str(employer["telegram_id"]),
            "session_id": session["id"],
        }

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "employer health")

    @task(5)
    def internal_contact_access(self) -> None:
        with self.client.get(
            "/api/v1/internal/contact-access",
            name="internal_contact_access",
            headers=render_request_headers(CONFIG, internal=True),
            params={
                "candidate_id": self.ctx["candidate_id"],
                "employer_telegram_id": self.ctx["employer_telegram_id"],
            },
            catch_response=True,
        ) as response:
            expect_status(response, 200, "employer internal contact access")

    @task(4)
    def list_searches(self) -> None:
        with self.client.get(
            f"/api/v1/employers/{self.ctx['employer_id']}/searches",
            name="list_searches",
            headers=render_request_headers(CONFIG, access_token=self.ctx["employer_access_token"]),
            params={"limit": 20},
            catch_response=True,
        ) as response:
            expect_status(response, 200, "employer list searches")

    @task(3)
    def searches_next_candidate(self) -> None:
        with self.client.get(
            f"/api/v1/searches/{self.ctx['session_id']}/next",
            name="searches_next_candidate",
            headers=render_request_headers(CONFIG, access_token=self.ctx["employer_access_token"]),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "employer next candidate")

    @task(1)
    def create_search_session(self) -> None:
        with self.client.post(
            f"/api/v1/employers/{self.ctx['employer_id']}/searches",
            name="create_search_session",
            headers=render_request_headers(CONFIG, access_token=self.ctx["employer_access_token"]),
            json={
                "title": f"Loadtest Search {uuid4()}",
                "filters": {
                    "role": "Python Backend Engineer",
                    "must_skills": [{"skill": "python", "level": 4}],
                    "nice_skills": [{"skill": "fastapi", "level": 3}],
                    "location": "Novosibirsk",
                    "work_modes": ["remote", "hybrid"],
                    "salary_min": 120000,
                    "salary_max": 420000,
                    "currency": "RUB",
                    "english_level": "B1",
                },
            },
            catch_response=True,
        ) as response:
            expect_status(response, 201, "employer create search session")
