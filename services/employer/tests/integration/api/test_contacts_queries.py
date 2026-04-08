from __future__ import annotations


async def test_get_favorites_returns_liked_candidates(
    client,
    employer_payload,
    candidate_gateway_stub,
    candidate_short_profile,
) -> None:
    create_employer = await client.post("/api/v1/employers", json=employer_payload)
    assert create_employer.status_code == 201, create_employer.text
    employer_id = create_employer.json()["id"]

    create_search = await client.post(
        f"/api/v1/employers/{employer_id}/searches",
        json={
            "title": "Favorites Search",
            "filters": {"role": "Python Developer"},
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    candidate_gateway_stub.add_profile(candidate_short_profile)

    decision_response = await client.post(
        f"/api/v1/searches/{session_id}/decisions",
        json={
            "candidate_id": str(candidate_short_profile.id),
            "decision": "like",
            "note": "top candidate",
        },
    )
    assert decision_response.status_code in (200, 201), decision_response.text

    response = await client.get(f"/api/v1/contacts/favorites/{employer_id}")
    assert response.status_code == 200, response.text

    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(candidate_short_profile.id)
    assert body[0]["display_name"] == "Дмитрий Иванов"


async def test_get_unlocked_contacts_returns_public_contact_candidate(
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

    request_response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(public_candidate.id)},
    )
    assert request_response.status_code == 200, request_response.text
    assert request_response.json()["granted"] is True

    response = await client.get(f"/api/v1/contacts/unlocked/{employer_id}")
    assert response.status_code == 200, response.text

    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(public_candidate.id)
    assert body[0]["contacts"]["email"] == "dmitry@example.com"
