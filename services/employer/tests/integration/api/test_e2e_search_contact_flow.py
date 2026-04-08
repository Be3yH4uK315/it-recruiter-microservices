from __future__ import annotations

from uuid import UUID

from app.application.common.contracts import (
    CandidateShortProfile,
    SearchCandidateResult,
    SearchCandidatesBatchResult,
)


async def test_e2e_search_to_contact_unlock_flow(
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
            "title": "E2E Search",
            "filters": {"role": "Python Developer"},
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    candidate_id = UUID("00000000-0000-0000-0000-0000000000aa")
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
                    candidate_id=candidate_id,
                    display_name="Иван Петров",
                    headline_role="Python Developer",
                    experience_years=4.5,
                    location="Paris",
                    skills=[{"skill": "python", "level": 5}],
                    salary_min=240000,
                    salary_max=340000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Backend engineer",
                    match_score=0.93,
                    explanation={"rrf": 0.9},
                )
            ],
        ),
    )
    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=candidate_id,
            display_name="Иван Петров",
            headline_role="Python Developer",
            location="Paris",
            work_modes=["remote"],
            experience_years=4.5,
            contacts_visibility="on_request",
            contacts={"email": "ivan.petrov@example.com", "telegram": "@ivan_petrov"},
            skills=[{"skill": "python", "kind": "hard", "level": 5}],
            salary_min=240000,
            salary_max=340000,
            currency="RUB",
            english_level="B2",
            about_me="Backend engineer",
        )
    )

    next_response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert next_response.status_code == 200, next_response.text
    next_body = next_response.json()
    assert next_body["candidate"] is not None
    assert next_body["candidate"]["id"] == str(candidate_id)
    assert next_body["candidate"]["match_score"] == 0.93

    decision_response = await client.post(
        f"/api/v1/searches/{session_id}/decisions",
        json={"candidate_id": str(candidate_id), "decision": "like"},
    )
    assert decision_response.status_code in (200, 201), decision_response.text

    request_response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(candidate_id)},
    )
    assert request_response.status_code == 200, request_response.text
    request_body = request_response.json()
    assert request_body["granted"] is False
    assert request_body["status"] == "pending"
    request_id = request_body["request_id"]
    assert request_id is not None

    pending_response = await client.get("/api/v1/contacts/requests/candidate/pending")
    assert pending_response.status_code == 200, pending_response.text
    pending_items = pending_response.json()
    assert any(item["id"] == request_id for item in pending_items)

    details_response = await client.get(f"/api/v1/contacts/requests/{request_id}")
    assert details_response.status_code == 200, details_response.text
    details_body = details_response.json()
    assert details_body["candidate_id"] == str(candidate_id)
    assert details_body["status"] == "pending"

    candidate_approve_response = await client.patch(
        f"/api/v1/contacts/requests/{request_id}/candidate-response",
        json={"granted": True},
    )
    assert candidate_approve_response.status_code == 200, candidate_approve_response.text
    approve_body = candidate_approve_response.json()
    assert approve_body["granted"] is True
    assert approve_body["status"] == "granted"

    status_response = await client.get(
        "/api/v1/internal/contact-requests/status",
        params={"employer_id": employer_id, "candidate_id": str(candidate_id)},
    )
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["exists"] is True
    assert status_body["granted"] is True
    assert status_body["status"] == "granted"

    unlocked_response = await client.get(f"/api/v1/contacts/unlocked/{employer_id}")
    assert unlocked_response.status_code == 200, unlocked_response.text
    unlocked_items = unlocked_response.json()
    assert len(unlocked_items) == 1
    assert unlocked_items[0]["id"] == str(candidate_id)
    assert unlocked_items[0]["contacts"]["email"] == "ivan.petrov@example.com"


async def test_e2e_search_to_contact_reject_flow(
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
            "title": "E2E Reject Search",
            "filters": {"role": "Python Developer"},
        },
    )
    assert create_search.status_code in (200, 201), create_search.text
    session_id = create_search.json()["id"]

    candidate_id = UUID("00000000-0000-0000-0000-0000000000ab")
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
                    candidate_id=candidate_id,
                    display_name="Петр Сидоров",
                    headline_role="Python Developer",
                    experience_years=3.8,
                    location="Berlin",
                    skills=[{"skill": "python", "level": 4}],
                    salary_min=220000,
                    salary_max=310000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Backend developer",
                    match_score=0.89,
                    explanation={"rrf": 0.82},
                )
            ],
        ),
    )
    candidate_gateway_stub.add_profile(
        CandidateShortProfile(
            id=candidate_id,
            display_name="Петр Сидоров",
            headline_role="Python Developer",
            location="Berlin",
            work_modes=["remote"],
            experience_years=3.8,
            contacts_visibility="on_request",
            contacts={"email": "petr.sidorov@example.com", "telegram": "@petr_sidorov"},
            skills=[{"skill": "python", "kind": "hard", "level": 4}],
            salary_min=220000,
            salary_max=310000,
            currency="RUB",
            english_level="B2",
            about_me="Backend developer",
        )
    )

    next_response = await client.get(f"/api/v1/searches/{session_id}/next")
    assert next_response.status_code == 200, next_response.text
    next_body = next_response.json()
    assert next_body["candidate"] is not None
    assert next_body["candidate"]["id"] == str(candidate_id)

    decision_response = await client.post(
        f"/api/v1/searches/{session_id}/decisions",
        json={"candidate_id": str(candidate_id), "decision": "like"},
    )
    assert decision_response.status_code in (200, 201), decision_response.text

    request_response = await client.post(
        f"/api/v1/contacts/requests/{employer_id}",
        json={"candidate_id": str(candidate_id)},
    )
    assert request_response.status_code == 200, request_response.text
    request_body = request_response.json()
    assert request_body["granted"] is False
    assert request_body["status"] == "pending"
    request_id = request_body["request_id"]
    assert request_id is not None

    candidate_reject_response = await client.patch(
        f"/api/v1/contacts/requests/{request_id}/candidate-response",
        json={"granted": False},
    )
    assert candidate_reject_response.status_code == 200, candidate_reject_response.text
    reject_body = candidate_reject_response.json()
    assert reject_body["granted"] is False
    assert reject_body["status"] == "rejected"

    status_response = await client.get(
        "/api/v1/internal/contact-requests/status",
        params={"employer_id": employer_id, "candidate_id": str(candidate_id)},
    )
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["exists"] is True
    assert status_body["granted"] is False
    assert status_body["status"] == "rejected"

    unlocked_response = await client.get(f"/api/v1/contacts/unlocked/{employer_id}")
    assert unlocked_response.status_code == 200, unlocked_response.text
    unlocked_items = unlocked_response.json()
    assert unlocked_items == []
