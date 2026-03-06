from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_e2e_search_next_candidate(async_client, mocker):
    """
    Работодатель запрашивает следующего кандидата.
    """
    from app.models.search import CandidatePreview
    from app.services.search_logic import search_engine

    mock_candidate = CandidatePreview(
        id=uuid4(),
        display_name="Found Candidate",
        headline_role="DevOps",
        experience_years=5,
        location="Remote",
        skills=["linux"],
        match_score=0.99,
    )
    mocker.patch.object(search_engine, "search", return_value=[mock_candidate])

    payload = {
        "session_id": str(uuid4()),
        "filters": {"role": "DevOps", "must_skills": ["Linux"]},
        "session_exclude_ids": [],
    }

    response = await async_client.post("/v1/search/next", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["candidate"]["display_name"] == "Found Candidate"
    assert data["candidate"]["match_score"] == 0.99


@pytest.mark.asyncio
async def test_e2e_search_no_results(async_client, mocker):
    """Кандидаты не найдены."""
    from app.services.search_logic import search_engine

    mocker.patch.object(search_engine, "search", return_value=[])

    payload = {"session_id": str(uuid4()), "filters": {"role": "Unicorn"}}

    response = await async_client.post("/v1/search/next", json=payload)

    assert response.status_code == 200
    assert response.json()["candidate"] is None
