from __future__ import annotations

from uuid import uuid4


async def test_internal_contact_access_returns_false_when_no_request(
    client, employer_payload
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201

    candidate_id = uuid4()

    response = await client.get(
        "/api/v1/internal/contact-access",
        params={
            "candidate_id": str(candidate_id),
            "employer_telegram_id": 1001,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"has_access": False}


async def test_internal_candidate_statistics(client) -> None:
    candidate_id = uuid4()

    response = await client.get(f"/api/v1/internal/candidates/{candidate_id}/statistics")
    assert response.status_code == 200
    assert response.json() == {
        "total_views": 0,
        "total_likes": 0,
        "total_contact_requests": 0,
    }
