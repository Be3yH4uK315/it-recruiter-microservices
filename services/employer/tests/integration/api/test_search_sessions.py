from __future__ import annotations


async def test_create_search_session(client, employer_payload) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    employer_id = create_employer.json()["id"]

    payload = {
        "title": "Python Search",
        "filters": {
            "role": "Python Developer",
            "must_skills": [{"skill": "python", "level": 5}],
            "nice_skills": [{"skill": "fastapi", "level": 4}],
            "experience_min": 3,
            "work_modes": ["remote", "hybrid"],
            "salary_min": 200000,
            "salary_max": 350000,
            "currency": "RUB",
        },
    }

    response = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json=payload,
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["title"] == "Python Search"
    assert body["filters"]["role"] == "Python Developer"
    assert body["filters"]["must_skills"][0]["skill"] == "python"

    list_response = await client.get(f"/api/v1/employers/{employer_id}/searches")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == body["id"]
