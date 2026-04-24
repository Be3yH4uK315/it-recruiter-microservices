from __future__ import annotations

from time import perf_counter
from uuid import uuid4

import requests
from locust import HttpUser, task
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from loadtests.common import (
    LoadTestConfig,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("file")


def _build_storage_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=2,
        backoff_factor=0.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "PUT"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=32,
        pool_maxsize=32,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class FileUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        self.ctx = {"owner_id": str(uuid4())}
        self.storage_session = _build_storage_session()

    def on_stop(self) -> None:
        self.storage_session.close()

    def _record_storage_request(
        self,
        *,
        method: str,
        name: str,
        started_at: float,
        response: requests.Response | None = None,
        exception: Exception | None = None,
    ) -> None:
        response_length = len(response.content) if response is not None else 0
        self.environment.events.request.fire(
            request_type=method,
            name=name,
            response_time=(perf_counter() - started_at) * 1000,
            response_length=response_length,
            exception=exception,
            context={},
        )

    def _request_storage(
        self,
        *,
        method: str,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        expected_statuses: int | tuple[int, ...] = 200,
    ) -> requests.Response | None:
        expected = (
            (expected_statuses,) if isinstance(expected_statuses, int) else expected_statuses
        )
        started_at = perf_counter()
        try:
            response = self.storage_session.request(
                method=method,
                url=url,
                headers=headers,
                data=data,
                timeout=CONFIG.request_timeout_sec,
            )
        except requests.RequestException as exc:
            self._record_storage_request(
                method=method,
                name=name,
                started_at=started_at,
                exception=exc,
            )
            return None

        if response.status_code not in expected:
            self._record_storage_request(
                method=method,
                name=name,
                started_at=started_at,
                response=response,
                exception=RuntimeError(
                    f"{name}: unexpected status={response.status_code} body={response.text[:300]}"
                ),
            )
            return None

        self._record_storage_request(
            method=method,
            name=name,
            started_at=started_at,
            response=response,
        )
        return response

    @task(1)
    def health(self) -> None:
        with self.client.get("/api/v1/health", name="health", catch_response=True) as response:
            expect_status(response, 200, "file health")

    @task(5)
    def upload_download_chain(self) -> None:
        headers = render_request_headers(CONFIG, internal=True)
        with self.client.post(
            "/api/v1/internal/files/upload-url",
            name="create_upload_url",
            headers=headers,
            json={
                "owner_service": "candidate-service",
                "owner_id": self.ctx["owner_id"],
                "filename": "resume.pdf",
                "content_type": "application/pdf",
                "category": "candidate_resume",
            },
            catch_response=True,
        ) as upload_response:
            expect_status(upload_response, 201, "file create upload-url")
            if upload_response.status_code != 201:
                return
            payload = upload_response.json()
            file_id = payload["file_id"]
            upload_url = payload["upload_url"]
            upload_headers = payload.get("headers", {})

        upload_result = self._request_storage(
            method="PUT",
            name="upload_object_to_storage",
            url=upload_url,
            headers=upload_headers,
            data=b"loadtest-file-body",
            expected_statuses=(200, 204),
        )
        if upload_result is None:
            return

        with self.client.post(
            f"/api/v1/internal/files/{file_id}/complete",
            name="complete_upload",
            headers=headers,
            json={"size_bytes": 2048},
            catch_response=True,
        ) as complete_response:
            expect_status(complete_response, 204, "file complete upload")

        with self.client.get(
            f"/api/v1/internal/files/{file_id}/download-url",
            name="create_download_url",
            headers=headers,
            params={"owner_service": "candidate-service", "owner_id": self.ctx["owner_id"]},
            catch_response=True,
        ) as download_response:
            expect_status(download_response, 200, "file create download-url")
            if download_response.status_code != 200:
                return
            download_url = download_response.json()["download_url"]

        self._request_storage(
            method="GET",
            name="download_object_from_storage",
            url=download_url,
            expected_statuses=200,
        )

    @task(2)
    def create_upload_url(self) -> None:
        with self.client.post(
            "/api/v1/internal/files/upload-url",
            name="create_upload_url_only",
            headers=render_request_headers(CONFIG, internal=True),
            json={
                "owner_service": "candidate-service",
                "owner_id": self.ctx["owner_id"],
                "filename": "avatar.jpg",
                "content_type": "image/jpeg",
                "category": "candidate_avatar",
            },
            catch_response=True,
        ) as response:
            expect_status(response, 201, "file create upload-url only")
