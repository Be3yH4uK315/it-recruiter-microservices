from __future__ import annotations


async def test_update_candidate(client) -> None:
    create_response = await client.post(
        "/candidates",
        json={
            "display_name": "Петр",
            "headline_role": "Python Developer",
            "contacts": {"email": "petr@init.test", "telegram": "@petr_init"},
        },
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/candidates/{candidate_id}",
        json={
            "display_name": "Петр Иванов",
            "headline_role": "Senior Python Developer",
            "location": "Berlin",
            "salary_min": 300000,
            "salary_max": 450000,
            "currency": "EUR",
            "contacts_visibility": "public",
            "contacts": {"email": "petr@example.com", "telegram": "@petr"},
            "skills": [
                {"skill": "python", "kind": "hard", "level": 5},
                {"skill": "postgresql", "kind": "tool", "level": 4},
            ],
        },
    )
    assert update_response.status_code == 200, update_response.text

    updated = update_response.json()
    assert updated["display_name"] == "Петр Иванов"
    assert updated["headline_role"] == "Senior Python Developer"
    assert updated["location"] == "Berlin"
    assert updated["salary_min"] == 300000
    assert updated["salary_max"] == 450000
    assert updated["currency"] == "EUR"
    assert updated["contacts_visibility"] == "public"
    assert updated["contacts"]["email"] == "petr@example.com"
    assert len(updated["skills"]) == 2
