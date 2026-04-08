from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.file import IdempotencyKey


async def _count_idempotency_keys(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(IdempotencyKey))
    return len(result.scalars().all())


@pytest.mark.asyncio
async def test_same_idempotency_key_and_same_payload_returns_cached_response(
    client,
    storage_stub,
    db_session: AsyncSession,
) -> None:
    headers = {
        "Idempotency-Key": "upload-url-same-payload",
    }
    payload = {
        "owner_service": "candidate-service",
        "owner_id": "11111111-1111-1111-1111-111111111111",
        "filename": "resume.pdf",
        "content_type": "application/pdf",
        "category": "candidate_resume",
    }

    response1 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json=payload,
    )
    response2 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json=payload,
    )

    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json() == response2.json()

    assert len(storage_stub.upload_urls) == 1

    result = await db_session.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == "upload-url-same-payload")
    )
    record = result.scalars().one_or_none()

    assert record is not None
    assert record.status_code == 201
    assert record.response_body is not None
    assert record.response_body["file_id"] == response1.json()["file_id"]


@pytest.mark.asyncio
async def test_same_idempotency_key_with_different_payload_returns_409(
    client,
    storage_stub,
) -> None:
    headers = {
        "Idempotency-Key": "upload-url-different-payload",
    }

    response1 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "resume.pdf",
            "content_type": "application/pdf",
            "category": "candidate_resume",
        },
    )
    response2 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "avatar.png",
            "content_type": "image/png",
            "category": "candidate_avatar",
        },
    )

    assert response1.status_code == 201
    assert response2.status_code == 409
    assert response2.json()["detail"] == "Idempotency key reuse with different payload"

    assert len(storage_stub.upload_urls) == 1


@pytest.mark.asyncio
async def test_without_idempotency_key_request_is_executed_each_time(
    client,
    storage_stub,
) -> None:
    headers = {}

    response1 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "resume-v1.pdf",
            "content_type": "application/pdf",
            "category": "candidate_resume",
        },
    )
    response2 = await client.post(
        "/internal/files/upload-url",
        headers=headers,
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "resume-v2.pdf",
            "content_type": "application/pdf",
            "category": "candidate_resume",
        },
    )

    assert response1.status_code == 201
    assert response2.status_code == 201

    body1 = response1.json()
    body2 = response2.json()

    assert body1["file_id"] != body2["file_id"]
    assert len(storage_stub.upload_urls) == 2


@pytest.mark.asyncio
async def test_get_request_ignores_idempotency_key(
    client,
) -> None:
    response = await client.get(
        "/health",
        headers={"Idempotency-Key": "health-key"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_request_is_cached_by_idempotency_key(
    client,
    db_session: AsyncSession,
    storage_stub,
) -> None:
    create_response = await client.post(
        "/internal/files/upload-url",
        headers={
            "Idempotency-Key": "seed-file-create",
        },
        json={
            "owner_service": "candidate-service",
            "owner_id": "11111111-1111-1111-1111-111111111111",
            "filename": "avatar.png",
            "content_type": "image/png",
            "category": "candidate_avatar",
        },
    )
    assert create_response.status_code == 201

    file_id = create_response.json()["file_id"]
    object_key = storage_stub.upload_urls[-1]["object_key"]
    storage_stub.existing_keys.add(object_key)

    complete_response = await client.post(
        f"/internal/files/{file_id}/complete",
        json={"size_bytes": 128},
    )
    assert complete_response.status_code == 204

    headers = {"Idempotency-Key": "delete-same-file"}
    payload = {
        "reason": "candidate_avatar_replaced",
        "requested_by_service": "candidate-service",
    }

    response1 = await client.post(
        f"/internal/files/{file_id}/cleanup", headers=headers, json=payload
    )
    response2 = await client.post(
        f"/internal/files/{file_id}/cleanup", headers=headers, json=payload
    )

    assert response1.status_code == 204
    assert response2.status_code == 204

    assert storage_stub.deleted_keys.count(object_key) == 1


@pytest.mark.asyncio
async def test_idempotency_record_is_created_only_once_for_same_key(
    client,
    db_session: AsyncSession,
) -> None:
    before = await _count_idempotency_keys(db_session)

    headers = {
        "Idempotency-Key": "single-record-key",
    }
    payload = {
        "owner_service": "candidate-service",
        "owner_id": "11111111-1111-1111-1111-111111111111",
        "filename": "resume.pdf",
        "content_type": "application/pdf",
        "category": "candidate_resume",
    }

    response1 = await client.post("/internal/files/upload-url", headers=headers, json=payload)
    response2 = await client.post("/internal/files/upload-url", headers=headers, json=payload)

    assert response1.status_code == 201
    assert response2.status_code == 201

    after = await _count_idempotency_keys(db_session)
    assert after == before + 1
