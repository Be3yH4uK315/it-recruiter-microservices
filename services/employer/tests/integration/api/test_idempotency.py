from __future__ import annotations


async def test_idempotent_create_employer_returns_same_response(client, employer_payload) -> None:
    headers = {"Idempotency-Key": "create-employer-1"}

    first = await client.post(
        "/api/v1/employers",
        json=employer_payload,
        headers=headers,
    )
    second = await client.post(
        "/api/v1/employers",
        json=employer_payload,
        headers=headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json() == second.json()


async def test_idempotency_rejects_same_key_with_different_payload(
    client, employer_payload
) -> None:
    headers = {"Idempotency-Key": "create-employer-2"}

    first = await client.post(
        "/api/v1/employers",
        json=employer_payload,
        headers=headers,
    )
    assert first.status_code == 201, first.text

    changed_payload = {
        **employer_payload,
        "company": "Different Company",
    }

    second = await client.post(
        "/api/v1/employers",
        json=changed_payload,
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Idempotency key reuse with different payload"
