from __future__ import annotations

from uuid import UUID

from app.application.common.contracts import (
    CandidateShortProfile,
    SearchCandidateResult,
    SearchCandidatesBatchResult,
)


async def test_get_next_candidate_returns_candidate_from_remote_batch(
    client,
    employer_payload,
    search_gateway_stub,
    candidate_gateway_stub,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Python Search",
            "filters": {
                "role": "Python Developer",
                "must_skills": [{"skill": "python", "level": 5}],
            },
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    filters = {
        "role": "Python Developer",
        "must_skills": [{"skill": "python", "level": 5}],
        "nice_skills": [],
        "experience_min": None,
        "experience_max": None,
        "location": None,
        "work_modes": [],
        "salary_min": None,
        "salary_max": None,
        "currency": "RUB",
        "english_level": None,
        "exclude_ids": [],
        "about_me": None,
    }

    search_gateway_stub.set_result(
        filters=filters,
        limit=50,
        offset=0,
        result=SearchCandidatesBatchResult(
            total=1,
            items=[
                SearchCandidateResult(
                    candidate_id=UUID("00000000-0000-0000-0000-000000000001"),
                    display_name="Дмитрий Иванов",
                    headline_role="Python Developer",
                    experience_years=4.5,
                    location="Paris",
                    skills=[{"skill": "python", "level": 5}],
                    salary_min=250000,
                    salary_max=350000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Backend engineer",
                    match_score=0.93,
                    explanation={"rrf": 0.91},
                )
            ],
        ),
    )
    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            display_name="Дмитрий Иванов",
            headline_role="Python Developer",
            location="Paris",
            work_modes=["remote"],
            experience_years=4.5,
            contacts_visibility="on_request",
            contacts=None,
            skills=[{"skill": "python", "kind": "hard", "level": 5}],
            salary_min=250000,
            salary_max=350000,
            currency="RUB",
            english_level="B2",
            about_me="Backend engineer",
        )
    )

    response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["candidate"] is not None
    assert body["candidate"]["id"] == "00000000-0000-0000-0000-000000000001"
    assert body["candidate"]["display_name"] == "Дмитрий Иванов"
    assert body["candidate"]["headline_role"] == "Python Developer"
    assert body["candidate"]["match_score"] == 0.93
    assert body["message"] is None


async def test_get_next_candidate_uses_local_pool_after_first_fetch(
    client,
    employer_payload,
    search_gateway_stub,
    candidate_gateway_stub,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Python Search",
            "filters": {
                "role": "Python Developer",
            },
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    filters = {
        "role": "Python Developer",
        "must_skills": [],
        "nice_skills": [],
        "experience_min": None,
        "experience_max": None,
        "location": None,
        "work_modes": [],
        "salary_min": None,
        "salary_max": None,
        "currency": "RUB",
        "english_level": None,
        "exclude_ids": [],
        "about_me": None,
    }

    search_gateway_stub.set_result(
        filters=filters,
        limit=50,
        offset=0,
        result=SearchCandidatesBatchResult(
            total=2,
            items=[
                SearchCandidateResult(
                    candidate_id=UUID("00000000-0000-0000-0000-000000000001"),
                    display_name="Кандидат 1",
                    headline_role="Python Developer",
                    experience_years=4.0,
                    location="Paris",
                    skills=[{"skill": "python", "level": 5}],
                    salary_min=200000,
                    salary_max=300000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Candidate 1",
                    match_score=0.95,
                    explanation={"rrf": 0.95},
                ),
                SearchCandidateResult(
                    candidate_id=UUID("00000000-0000-0000-0000-000000000002"),
                    display_name="Кандидат 2",
                    headline_role="Backend Developer",
                    experience_years=5.0,
                    location="Berlin",
                    skills=[{"skill": "fastapi", "level": 4}],
                    salary_min=250000,
                    salary_max=350000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Candidate 2",
                    match_score=0.91,
                    explanation={"rrf": 0.91},
                ),
            ],
        ),
    )
    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            display_name="Кандидат 1",
            headline_role="Python Developer",
            location="Paris",
            work_modes=["remote"],
            experience_years=4.0,
            contacts_visibility="on_request",
            contacts=None,
            skills=[{"skill": "python", "kind": "hard", "level": 5}],
            salary_min=200000,
            salary_max=300000,
            currency="RUB",
            english_level="B2",
            about_me="Candidate 1",
        )
    )
    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            display_name="Кандидат 2",
            headline_role="Backend Developer",
            location="Berlin",
            work_modes=["remote"],
            experience_years=5.0,
            contacts_visibility="on_request",
            contacts=None,
            skills=[{"skill": "fastapi", "kind": "hard", "level": 4}],
            salary_min=250000,
            salary_max=350000,
            currency="RUB",
            english_level="B2",
            about_me="Candidate 2",
        )
    )

    first = await client.get(f"/api/v1/searches/{session_id}/next")
    assert first.status_code == 200, first.text
    first_candidate = first.json()["candidate"]
    assert first_candidate is not None
    assert first_candidate["display_name"] == "Кандидат 1"

    decision = await client.post(
        f"/api/v1/searches/{session_id}/decisions",
        json={
            "candidate_id": first_candidate["id"],
            "decision": "like",
        },
    )
    assert decision.status_code in (200, 201), decision.text

    second = await client.get(f"/api/v1/searches/{session_id}/next")
    assert second.status_code == 200, second.text
    second_candidate = second.json()["candidate"]
    assert second_candidate is not None
    assert second_candidate["display_name"] == "Кандидат 2"


async def test_get_next_candidate_returns_message_when_remote_batch_empty(
    client,
    employer_payload,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Python Search",
            "filters": {
                "role": "Python Developer",
            },
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["candidate"] is None
    assert body["message"] == "No more candidates found matching criteria."


async def test_get_next_candidate_returns_degraded_message_when_search_unavailable(
    client,
    employer_payload,
    search_gateway_stub,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Python Search",
            "filters": {
                "role": "Python Developer",
            },
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    filters = {
        "role": "Python Developer",
        "must_skills": [],
        "nice_skills": [],
        "experience_min": None,
        "experience_max": None,
        "location": None,
        "work_modes": [],
        "salary_min": None,
        "salary_max": None,
        "currency": "RUB",
        "english_level": None,
        "exclude_ids": [],
        "about_me": None,
    }
    search_gateway_stub.set_result(
        filters=filters,
        limit=50,
        offset=0,
        result=SearchCandidatesBatchResult(
            total=0,
            items=[],
            is_degraded=True,
        ),
    )

    response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["candidate"] is None
    assert body["message"] == "Search service is temporarily unavailable."


async def test_get_next_candidate_skips_missing_profile_and_returns_next_available(
    client,
    employer_payload,
    search_gateway_stub,
    candidate_gateway_stub,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Python Search",
            "filters": {
                "role": "Python Developer",
            },
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    filters = {
        "role": "Python Developer",
        "must_skills": [],
        "nice_skills": [],
        "experience_min": None,
        "experience_max": None,
        "location": None,
        "work_modes": [],
        "salary_min": None,
        "salary_max": None,
        "currency": "RUB",
        "english_level": None,
        "exclude_ids": [],
        "about_me": None,
    }
    search_gateway_stub.set_result(
        filters=filters,
        limit=50,
        offset=0,
        result=SearchCandidatesBatchResult(
            total=2,
            items=[
                SearchCandidateResult(
                    candidate_id=UUID("00000000-0000-0000-0000-000000000011"),
                    display_name="Недоступный профиль",
                    headline_role="Python Developer",
                    experience_years=5.0,
                    location="Paris",
                    skills=[{"skill": "python", "level": 5}],
                    salary_min=250000,
                    salary_max=350000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Unavailable in candidate service",
                    match_score=0.94,
                    explanation={"rrf": 0.94},
                ),
                SearchCandidateResult(
                    candidate_id=UUID("00000000-0000-0000-0000-000000000012"),
                    display_name="Доступный профиль",
                    headline_role="Backend Engineer",
                    experience_years=4.2,
                    location="Berlin",
                    skills=[{"skill": "fastapi", "level": 4}],
                    salary_min=230000,
                    salary_max=320000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Available in candidate service",
                    match_score=0.91,
                    explanation={"rrf": 0.91},
                ),
            ],
        ),
    )

    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=UUID("00000000-0000-0000-0000-000000000012"),
            display_name="Доступный профиль",
            headline_role="Backend Engineer",
            location="Berlin",
            work_modes=["remote"],
            experience_years=4.2,
            contacts_visibility="on_request",
            contacts=None,
            skills=[{"skill": "fastapi", "kind": "hard", "level": 4}],
            salary_min=230000,
            salary_max=320000,
            currency="RUB",
            english_level="B2",
            about_me="Available in candidate service",
        )
    )

    response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["candidate"] is not None
    assert body["candidate"]["id"] == "00000000-0000-0000-0000-000000000012"
    assert body["candidate"]["display_name"] == "Доступный профиль"
    assert body["message"] is None
