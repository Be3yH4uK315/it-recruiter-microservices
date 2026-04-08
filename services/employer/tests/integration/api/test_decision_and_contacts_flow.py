from __future__ import annotations

from uuid import UUID

from app.application.common.contracts import (
    CandidateShortProfile,
    SearchCandidateResult,
    SearchCandidatesBatchResult,
)


async def test_submit_decision_and_get_statistics(
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
            "filters": {"role": "Python Developer"},
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
                    match_score=0.88,
                    explanation={"rrf": 0.77},
                ),
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

    next_response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert next_response.status_code == 200, next_response.text
    next_body = next_response.json()
    assert next_body["candidate"] is not None
    assert next_body["candidate"]["id"] == "00000000-0000-0000-0000-000000000001"

    decision_response = await client.post(
        f"/api/v1/searches/{session_id}/decisions",
        json={
            "candidate_id": "00000000-0000-0000-0000-000000000001",
            "decision": "like",
            "note": "strong backend profile",
        },
    )
    assert decision_response.status_code in (200, 201), decision_response.text

    body = decision_response.json()
    assert body["candidate_id"] == "00000000-0000-0000-0000-000000000001"
    assert body["decision"] == "like"
    assert body["note"] == "strong backend profile"

    stats_response = await client.get(f"/api/v1/employers/{employer_id}/statistics")
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()

    assert stats["total_viewed"] == 1
    assert stats["total_liked"] == 1
    assert stats["total_contact_requests"] == 0
    assert stats["total_contacts_granted"] == 0


async def test_request_contact_access_on_request_candidate(
    client,
    employer_payload,
    candidate_gateway_stub,
    candidate_short_profile,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    candidate_gateway_stub.add_profile(candidate_short_profile)

    response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(candidate_short_profile.id)},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["granted"] is False
    assert body["contacts"] is None
    assert body["notification_info"]["candidate_id"] == str(candidate_short_profile.id)


async def test_request_contact_access_public_candidate_returns_contacts(
    client,
    employer_payload,
    candidate_gateway_stub,
    candidate_short_profile,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    public_candidate = candidate_short_profile.__class__(
        id=candidate_short_profile.id,
        display_name=candidate_short_profile.display_name,
        headline_role=candidate_short_profile.headline_role,
        location=candidate_short_profile.location,
        work_modes=candidate_short_profile.work_modes,
        experience_years=candidate_short_profile.experience_years,
        skills=candidate_short_profile.skills,
        salary_min=candidate_short_profile.salary_min,
        salary_max=candidate_short_profile.salary_max,
        currency=candidate_short_profile.currency,
        english_level=candidate_short_profile.english_level,
        contacts_visibility="public",
        contacts=candidate_short_profile.contacts,
        about_me=candidate_short_profile.about_me,
        explanation=candidate_short_profile.explanation,
        match_score=candidate_short_profile.match_score,
    )
    candidate_gateway_stub.add_profile(public_candidate)

    response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(public_candidate.id)},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["granted"] is True
    assert body["contacts"]["email"] == "dmitry@example.com"
    assert body["notification_info"] is None
