from __future__ import annotations


async def test_get_contact_request_details(
    client,
    employer_payload,
    candidate_gateway_stub,
    candidate_short_profile,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    candidate_gateway_stub.add_profile(candidate_short_profile)

    request_response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(candidate_short_profile.id)},
    )
    assert request_response.status_code == 200, request_response.text
    assert request_response.json()["granted"] is False

    status_response = await client.get(
        "/api/v1/internal/contact-requests/status",
        params={
            "employer_id": employer_id,
            "candidate_id": str(candidate_short_profile.id),
        },
    )
    assert status_response.status_code == 200, status_response.text

    request_id = status_response.json()["request_id"]
    assert request_id is not None

    details_response = await client.get(f"/api/v1/contacts/requests/{request_id}")
    assert details_response.status_code == 200, details_response.text

    body = details_response.json()
    assert body["id"] == request_id
    assert body["candidate_id"] == str(candidate_short_profile.id)
    assert body["candidate_name"] == "Дмитрий Иванов"
    assert body["employer_telegram_id"] == 1001
