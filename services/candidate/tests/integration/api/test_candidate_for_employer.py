from __future__ import annotations

from uuid import UUID


async def test_employer_view_hides_contacts_without_access(client, employer_gateway_stub) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Скрытый контакт",
            "headline_role": "Backend Engineer",
            "contacts_visibility": "on_request",
            "contacts": {"email": "hidden@example.com", "telegram": "@hidden"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    employer_gateway_stub.deny_access(
        candidate_id=UUID(candidate_id),
        employer_telegram_id=900001,
    )

    response = await client.get(
        f"/candidates/{candidate_id}/employer-view",
        params={"employer_telegram_id": 900001},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["can_view_contacts"] is False
    assert payload["contacts"] is None


async def test_employer_view_shows_contacts_with_access(client, employer_gateway_stub) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Открытый контакт",
            "headline_role": "Backend Engineer",
            "contacts_visibility": "on_request",
            "contacts": {"email": "visible@example.com", "telegram": "@visible"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    employer_gateway_stub.allow_access(
        candidate_id=UUID(candidate_id),
        employer_telegram_id=900002,
    )

    response = await client.get(
        f"/candidates/{candidate_id}/employer-view",
        params={"employer_telegram_id": 900002},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["can_view_contacts"] is True
    assert payload["contacts"]["email"] == "visible@example.com"
