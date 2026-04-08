from __future__ import annotations


async def test_create_candidate_and_get_by_id(client) -> None:
    create_payload = {
        "display_name": "Иван Смирнов",
        "headline_role": "Backend Engineer",
        "location": "Paris",
        "work_modes": ["remote"],
        "contacts_visibility": "on_request",
        "contacts": {
            "email": "ivan@example.com",
            "telegram": "@ivan",
        },
        "status": "active",
        "salary_min": 200000,
        "salary_max": 320000,
        "currency": "RUB",
        "english_level": "B2",
        "about_me": "Python backend developer",
        "skills": [
            {"skill": "python", "kind": "hard", "level": 5},
            {"skill": "fastapi", "kind": "tool", "level": 4},
        ],
        "education": [
            {"level": "bachelor", "institution": "ITMO", "year": 2021},
        ],
        "experiences": [
            {
                "company": "Acme",
                "position": "Backend Developer",
                "start_date": "2022-01-01",
                "end_date": "2024-01-01",
                "responsibilities": "Services and APIs",
            },
        ],
        "projects": [
            {
                "title": "Recruitment Platform",
                "description": "Microservice platform",
                "links": ["https://example.com/project"],
            },
        ],
    }

    create_response = await client.post("/candidates", json=create_payload)
    assert create_response.status_code == 201, create_response.text

    created = create_response.json()
    candidate_id = created["id"]

    assert created["telegram_id"] == 777001
    assert created["display_name"] == "Иван Смирнов"
    assert created["headline_role"] == "Backend Engineer"
    assert created["salary_min"] == 200000
    assert created["salary_max"] == 320000
    assert created["skills"][0]["skill"] == "python"
    assert created["avatar_file_id"] is None
    assert created["resume_file_id"] is None

    get_response = await client.get(f"/candidates/{candidate_id}")
    assert get_response.status_code == 200, get_response.text

    fetched = get_response.json()
    assert fetched["id"] == candidate_id
    assert fetched["telegram_id"] == 777001
    assert fetched["contacts"]["email"] == "ivan@example.com"
