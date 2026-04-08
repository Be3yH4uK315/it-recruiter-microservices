from __future__ import annotations


async def test_create_candidate_is_idempotent_for_same_key_and_same_payload(client) -> None:
    headers = {"Idempotency-Key": "create-candidate-same-key-1"}
    payload = {
        "display_name": "Idempotent User",
        "headline_role": "Backend Engineer",
        "contacts": {"email": "idempotent@example.com", "telegram": "@idempotent"},
        "location": "Paris",
        "salary_min": 200000,
        "salary_max": 300000,
        "currency": "RUB",
    }

    first_response = await client.post("/candidates", json=payload, headers=headers)
    assert first_response.status_code == 201, first_response.text
    first_body = first_response.json()

    second_response = await client.post("/candidates", json=payload, headers=headers)
    assert second_response.status_code == 201, second_response.text
    second_body = second_response.json()

    assert second_body == first_body


async def test_create_candidate_returns_409_for_same_key_with_different_payload(client) -> None:
    headers = {"Idempotency-Key": "create-candidate-same-key-2"}

    first_response = await client.post(
        "/candidates",
        json={
            "display_name": "First Payload",
            "headline_role": "Backend Engineer",
            "contacts": {"email": "first@example.com", "telegram": "@first"},
        },
        headers=headers,
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/candidates",
        json={
            "display_name": "Different Payload",
            "headline_role": "Backend Engineer",
            "contacts": {"email": "second@example.com", "telegram": "@second"},
        },
        headers=headers,
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Idempotency key reuse with different payload"


async def test_replace_avatar_is_idempotent_for_same_key_and_same_payload(client) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Avatar Idempotency",
            "headline_role": "Engineer",
            "contacts": {
                "email": "avatar-idempotency@example.com",
                "telegram": "@avatar_idempotency",
            },
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    upload_url_response = await client.post(
        f"/candidates/{candidate_id}/avatar/upload-url",
        json={"filename": "avatar.png", "content_type": "image/png"},
    )
    assert upload_url_response.status_code == 200, upload_url_response.text

    headers = {"Idempotency-Key": "replace-avatar-same-key-1"}
    payload = {"file_id": "11111111-1111-1111-1111-111111111111"}

    first_response = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json=payload,
        headers=headers,
    )
    assert first_response.status_code == 204, first_response.text

    second_response = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json=payload,
        headers=headers,
    )
    assert second_response.status_code == 204, second_response.text

    get_response = await client.get(f"/candidates/{candidate_id}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["avatar_file_id"] == "11111111-1111-1111-1111-111111111111"


async def test_replace_avatar_returns_409_for_same_key_with_different_payload(client) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Avatar Conflict",
            "headline_role": "Engineer",
            "contacts": {"email": "avatar-conflict@example.com", "telegram": "@avatar_conflict"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    upload_url_response = await client.post(
        f"/candidates/{candidate_id}/avatar/upload-url",
        json={"filename": "avatar.png", "content_type": "image/png"},
    )
    assert upload_url_response.status_code == 200, upload_url_response.text

    headers = {"Idempotency-Key": "replace-avatar-same-key-2"}

    first_response = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json={"file_id": "11111111-1111-1111-1111-111111111111"},
        headers=headers,
    )
    assert first_response.status_code == 204, first_response.text

    second_response = await client.put(
        f"/candidates/{candidate_id}/avatar",
        json={"file_id": "33333333-3333-3333-3333-333333333333"},
        headers=headers,
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Idempotency key reuse with different payload"


async def test_requests_without_idempotency_key_use_normal_behavior(client) -> None:
    payload = {
        "display_name": "Normal Request",
        "headline_role": "Engineer",
        "contacts": {"email": "normal@example.com", "telegram": "@normal"},
    }

    first_response = await client.post("/candidates", json=payload)
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post("/candidates", json=payload)
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Candidate already exists"
