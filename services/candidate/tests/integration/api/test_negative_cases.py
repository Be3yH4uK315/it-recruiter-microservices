from __future__ import annotations


async def test_get_candidate_returns_404_for_missing_candidate(client) -> None:
    response = await client.get("/candidates/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_update_candidate_returns_404_for_missing_candidate(client) -> None:
    response = await client.patch(
        "/candidates/00000000-0000-0000-0000-000000000002",
        json={"display_name": "Updated Name"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_get_candidate_statistics_returns_404_for_missing_candidate(client) -> None:
    response = await client.get(
        "/candidates/00000000-0000-0000-0000-000000000003/statistics",
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_replace_avatar_returns_404_for_missing_candidate(client) -> None:
    response = await client.put(
        "/candidates/00000000-0000-0000-0000-000000000004/avatar",
        json={"file_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_delete_avatar_returns_404_for_missing_candidate(client) -> None:
    response = await client.delete(
        "/candidates/00000000-0000-0000-0000-000000000005/avatar",
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_replace_resume_returns_404_for_missing_candidate(client) -> None:
    response = await client.put(
        "/candidates/00000000-0000-0000-0000-000000000006/resume",
        json={"file_id": "22222222-2222-2222-2222-222222222222"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_delete_resume_returns_404_for_missing_candidate(client) -> None:
    response = await client.delete(
        "/candidates/00000000-0000-0000-0000-000000000007/resume",
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_get_candidate_by_telegram_returns_404_for_missing_candidate(client) -> None:
    response = await client.get("/candidates/by-telegram/777001")
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


async def test_get_many_candidates_returns_empty_list_for_unknown_ids(client) -> None:
    response = await client.post(
        "/candidates/batch",
        json={
            "candidate_ids": [
                "00000000-0000-0000-0000-000000000008",
                "00000000-0000-0000-0000-000000000009",
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_healthcheck_returns_ok(client_without_auth) -> None:
    response = await client_without_auth.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "candidate-service"
    assert "components" in body


async def test_create_candidate_returns_409_for_duplicate_telegram_id(client) -> None:
    payload = {
        "display_name": "Duplicate User",
        "headline_role": "Python Developer",
        "contacts": {"email": "dup@example.com", "telegram": "@dup"},
    }

    first_response = await client.post("/candidates", json=payload)
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post("/candidates", json=payload)
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Candidate already exists"
