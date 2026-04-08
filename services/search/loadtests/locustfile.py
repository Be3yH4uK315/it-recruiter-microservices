from __future__ import annotations

from locust import HttpUser, events, task

from loadtests.common import (
    LoadTestConfig,
    ServiceContextCache,
    ensure_candidate_profile,
    ensure_search_index_document,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("search")
CACHE = ServiceContextCache()


def _build_context() -> dict[str, str]:
    candidate = ensure_candidate_profile(CONFIG)
    ensure_search_index_document(CONFIG, candidate["candidate_id"])
    return {
        "candidate_id": candidate["candidate_id"],
    }


@events.test_start.add_listener
def _prepare_context(environment, **_kwargs) -> None:
    _ = environment
    CACHE.get_or_create("search_context", _build_context)


class SearchUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        self.ctx = CACHE.get_or_create("search_context", _build_context)

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "search health")

    @task(5)
    def search_candidates(self) -> None:
        with self.client.post(
            "/api/v1/search/candidates",
            name="search_candidates",
            headers=render_request_headers(CONFIG, internal=True),
            json={
                "filters": {
                    "role": "Python Backend Engineer",
                    "must_skills": [{"skill": "python", "level": 5}],
                    "location": "Novosibirsk",
                    "salary_min": 100000,
                    "salary_max": 400000,
                    "currency": "RUB",
                },
                "limit": 10,
            },
            catch_response=True,
        ) as response:
            expect_status(response, 200, "search candidates")

    @task(2)
    def get_candidate_document(self) -> None:
        with self.client.get(
            f"/api/v1/internal/index/candidates/{self.ctx['candidate_id']}",
            name="get_candidate_document",
            headers=render_request_headers(CONFIG, internal=True),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "search get candidate document")
