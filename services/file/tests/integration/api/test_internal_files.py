from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_upload_url_returns_presigned_payload(client, storage_stub) -> None:
    response = await client.post(
        "/internal/files/upload-url",
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "resume.pdf",
            "content_type": "application/pdf",
            "category": "candidate_resume",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["method"] == "PUT"
    assert payload["expires_in"] == 3600
    assert payload["headers"] == {"Content-Type": "application/pdf"}
    assert len(storage_stub.upload_urls) == 1


@pytest.mark.asyncio
async def test_create_upload_url_validates_avatar_content_type(client) -> None:
    response = await client.post(
        "/internal/files/upload-url",
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "avatar.exe",
            "content_type": "application/octet-stream",
            "category": "candidate_avatar",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid content_type for avatar"


@pytest.mark.asyncio
async def test_create_upload_url_validates_resume_content_type(client) -> None:
    response = await client.post(
        "/internal/files/upload-url",
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "resume.exe",
            "content_type": "application/octet-stream",
            "category": "candidate_resume",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid content_type for document"
