from __future__ import annotations


async def test_get_candidate_statistics(client, employer_gateway_stub) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Статистика",
            "headline_role": "Developer",
            "contacts": {"email": "stats@example.com", "telegram": "@stats"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    employer_gateway_stub.set_statistics(
        candidate_id=__import__("uuid").UUID(candidate_id),
        profile_views=11,
        contact_requests=3,
        unlocked_contacts=2,
        is_degraded=False,
    )

    response = await client.get(f"/candidates/{candidate_id}/statistics")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload == {
        "total_views": 11,
        "total_likes": 2,
        "total_contact_requests": 3,
        "is_degraded": False,
    }
