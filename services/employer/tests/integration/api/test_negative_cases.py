from __future__ import annotations

from uuid import uuid4


async def test_get_missing_employer_returns_404(client) -> None:
    response = await client.get(f"/api/v1/employers/{uuid4()}")
    assert response.status_code == 404


async def test_create_employer_forbidden_when_subject_mismatch(client, employer_payload) -> None:
    response = await client.post(
        "/api/v1/employers",
        json=employer_payload,
        headers={"X-Employer-Telegram-Id": "999999"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "telegram id mismatch"


async def test_submit_decision_for_missing_search_returns_404(client) -> None:
    response = await client.post(
        f"/api/v1/searches/{uuid4()}/decisions",
        json={
            "candidate_id": str(uuid4()),
            "decision": "like",
        },
    )
    assert response.status_code == 404
