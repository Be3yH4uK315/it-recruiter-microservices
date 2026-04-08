from __future__ import annotations

from uuid import uuid4


def _candidate_payload(display_name: str) -> dict:
    return {
        "display_name": display_name,
        "headline_role": "Backend Engineer",
        "location": "Paris",
        "work_modes": ["remote"],
        "contacts_visibility": "on_request",
        "contacts": {
            "email": f"{display_name.lower().replace(' ', '_')}@example.com",
            "telegram": f"@{display_name.lower().replace(' ', '_')}",
        },
        "status": "active",
        "salary_min": 200000,
        "salary_max": 300000,
        "currency": "RUB",
        "english_level": "B2",
        "about_me": "Python backend developer",
        "skills": [{"skill": "python", "kind": "hard", "level": 5}],
        "education": [{"level": "bachelor", "institution": "ITMO", "year": 2020}],
        "experiences": [
            {
                "company": "Acme",
                "position": "Backend Developer",
                "start_date": "2022-01-01",
                "end_date": "2024-01-01",
                "responsibilities": "APIs and async services",
            }
        ],
        "projects": [
            {
                "title": "Recruitment Platform",
                "description": "Microservice platform",
                "links": ["https://example.com/project"],
            }
        ],
    }


async def test_internal_search_document_contract_contains_required_fields(client) -> None:
    create_response = await client.post(
        "/candidates",
        json=_candidate_payload("Contract Candidate"),
    )
    assert create_response.status_code == 201, create_response.text
    candidate_id = create_response.json()["id"]

    response = await client.get(f"/internal/candidates/{candidate_id}/search-document")
    assert response.status_code == 200, response.text

    payload = response.json()
    required_keys = {
        "id",
        "telegram_id",
        "display_name",
        "headline_role",
        "location",
        "work_modes",
        "contacts_visibility",
        "status",
        "english_level",
        "about_me",
        "salary_min",
        "salary_max",
        "currency",
        "skills",
        "education",
        "experiences",
        "projects",
        "avatar_file_id",
        "resume_file_id",
        "created_at",
        "updated_at",
        "version_id",
    }
    assert required_keys.issubset(payload.keys())
    assert payload["id"] == candidate_id
    assert payload["telegram_id"] == 777001
    assert payload["display_name"] == "Contract Candidate"
    assert payload["work_modes"] == ["remote"]
    assert payload["contacts_visibility"] == "on_request"
    assert payload["status"] == "active"
    assert isinstance(payload["skills"], list)
    assert isinstance(payload["education"], list)
    assert isinstance(payload["experiences"], list)
    assert isinstance(payload["projects"], list)
    assert payload["version_id"] >= 1


async def test_internal_search_documents_list_contract_returns_items(client) -> None:
    first_response = await client.post(
        "/candidates",
        json=_candidate_payload("List Candidate One"),
    )
    assert first_response.status_code == 201, first_response.text
    first_candidate_id = first_response.json()["id"]

    second_response = await client.post(
        "/candidates",
        json=_candidate_payload("List Candidate Two"),
        headers={"X-Candidate-Telegram-Id": "777002"},
    )
    assert second_response.status_code == 201, second_response.text
    second_candidate_id = second_response.json()["id"]

    response = await client.get(
        "/internal/candidates/search-documents", params={"limit": 100, "offset": 0}
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)

    by_id = {item["id"]: item for item in body["items"]}
    assert first_candidate_id in by_id
    assert second_candidate_id in by_id

    for candidate_id in (first_candidate_id, second_candidate_id):
        item = by_id[candidate_id]
        assert isinstance(item["work_modes"], list)
        assert isinstance(item["skills"], list)
        assert isinstance(item["experiences"], list)
        assert isinstance(item["projects"], list)
        assert "headline_role" in item


async def test_internal_search_document_returns_404_for_missing_candidate(client) -> None:
    missing_id = uuid4()
    response = await client.get(f"/internal/candidates/{missing_id}/search-document")
    assert response.status_code == 404, response.text
