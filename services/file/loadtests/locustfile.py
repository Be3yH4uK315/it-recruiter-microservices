from __future__ import annotations

from uuid import uuid4

import requests
from locust import HttpUser, task

from loadtests.common import (
    LoadTestConfig,
    ServiceContextCache,
    expect_status,
    load_config,
    profile_wait_time,
    render_request_headers,
)

CONFIG: LoadTestConfig = load_config("file")
CACHE = ServiceContextCache()


def _build_context() -> dict[str, str]:
    owner_id = str(uuid4())
    return {"owner_id": owner_id}


class FileUser(HttpUser):
    wait_time = profile_wait_time(CONFIG)

    def on_start(self) -> None:
        self.ctx = CACHE.get_or_create("file_context", _build_context)

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

        upload_result = requests.put(
            upload_url,
            headers=upload_headers,
            data=b"loadtest-file-body",
            timeout=CONFIG.request_timeout_sec,
        )
        if upload_result.status_code >= 400:
            self.environment.events.request.fire(
                request_type="PUT",
                name="upload_object_to_storage",
                response_time=0,
                response_length=0,
                exception=RuntimeError(
                    f"storage upload failed status={upload_result.status_code} body={upload_result.text[:300]}"
                ),
            )
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
