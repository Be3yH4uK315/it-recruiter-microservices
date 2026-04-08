from __future__ import annotations

from locust import HttpUser, task

from loadtests.common import (
    LoadTestConfig,
    ServiceContextCache,
    ensure_candidate_profile,
    ensure_employer_profile,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("candidate")
CACHE = ServiceContextCache()


def _build_context() -> dict[str, str]:
    candidate = ensure_candidate_profile(CONFIG)
    employer = ensure_employer_profile(CONFIG)
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_access_token": candidate["access_token"],
        "employer_telegram_id": str(employer["telegram_id"]),
    }


class CandidateUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        self.ctx = CACHE.get_or_create("candidate_context", _build_context)

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "candidate health")

    @task(4)
    def internal_search_documents(self) -> None:
        with self.client.get(
            "/api/v1/internal/candidates/search-documents",
            name="internal_search_documents",
            headers=render_request_headers(CONFIG, internal=True),
            params={"limit": 50, "offset": 0},
            catch_response=True,
        ) as response:
            expect_status(response, 200, "candidate internal search-documents")

    @task(3)
    def get_candidate_profile(self) -> None:
        with self.client.get(
            f"/api/v1/candidates/{self.ctx['candidate_id']}",
            name="get_candidate_profile",
            headers=render_request_headers(CONFIG, access_token=self.ctx["candidate_access_token"]),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "candidate get profile")

    @task(2)
    def get_candidate_search_document(self) -> None:
        with self.client.get(
            f"/api/v1/internal/candidates/{self.ctx['candidate_id']}/search-document",
            name="get_candidate_search_document",
            headers=render_request_headers(CONFIG, internal=True),
            catch_response=True,
        ) as response:
            expect_status(response, 200, "candidate get search document")

    @task(1)
    def employer_view(self) -> None:
        with self.client.get(
            f"/api/v1/candidates/{self.ctx['candidate_id']}/employer-view",
            name="candidate_employer_view",
            headers=render_request_headers(CONFIG, internal=True),
            params={"employer_telegram_id": self.ctx["employer_telegram_id"]},
            catch_response=True,
        ) as response:
            expect_status(response, 200, "candidate employer view")
