from __future__ import annotations

from uuid import uuid4

from app.application.common.contracts import CandidateDocumentPayload
from app.application.search.services.candidate_text_builder import (
    build_candidate_search_text,
)


def make_payload() -> CandidateDocumentPayload:
    return CandidateDocumentPayload(
        id=uuid4(),
        display_name="Иван Петров",
        headline_role="Python Developer",
        location="Москва",
        work_modes=["remote", "hybrid"],
        experience_years=4.5,
        skills=[
            {"skill": "Python", "level": 5, "kind": "hard"},
            {"skill": "FastAPI", "level": 4, "kind": "hard"},
            "PostgreSQL",
        ],
        salary_min=150000,
        salary_max=250000,
        currency="RUB",
        english_level="B2",
        about_me="Backend developer with microservices experience",
        experiences=[
            {
                "company": "Acme",
                "position": "Backend Engineer",
                "responsibilities": "Built APIs and async services",
            }
        ],
        projects=[
            {
                "title": "Hiring Platform",
                "description": "Search and ranking system",
                "links": ["https://example.com/project"],
            }
        ],
        education=[
            {
                "institution": "BMSTU",
                "level": "Bachelor",
            }
        ],
        status="active",
    )


def test_build_candidate_search_text_contains_main_sections() -> None:
    payload = make_payload()

    text = build_candidate_search_text(payload)

    assert "Python Developer" in text
    assert "Иван Петров" not in text
    assert "Москва" in text
    assert "Python" in text
    assert "FastAPI" in text
    assert "PostgreSQL" in text
    assert "Backend developer with microservices experience" in text
    assert "Acme" in text
    assert "Hiring Platform" in text
    assert "BMSTU" in text


def test_build_candidate_search_text_skips_empty_optional_parts() -> None:
    payload = CandidateDocumentPayload(
        id=uuid4(),
        display_name="Test User",
        headline_role="Go Developer",
        location=None,
        work_modes=[],
        experience_years=0.0,
        skills=[],
        salary_min=None,
        salary_max=None,
        currency=None,
        english_level=None,
        about_me=None,
        experiences=[],
        projects=[],
        education=[],
        status=None,
    )

    text = build_candidate_search_text(payload)

    assert "Go Developer" in text
    assert "Test User" not in text
    assert "Локация:" not in text
    assert "Навыки:" not in text
    assert "Проекты:" not in text
    assert "Образование:" not in text


def test_build_candidate_search_text_accepts_mixed_skill_formats() -> None:
    payload = make_payload()
    payload = CandidateDocumentPayload(
        id=payload.id,
        display_name=payload.display_name,
        headline_role=payload.headline_role,
        location=payload.location,
        work_modes=payload.work_modes,
        experience_years=payload.experience_years,
        skills=[
            {"skill": "Python"},
            {"name": "Docker"},
            {"title": "Kubernetes"},
            "Redis",
        ],
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        currency=payload.currency,
        english_level=payload.english_level,
        about_me=payload.about_me,
        experiences=payload.experiences,
        projects=payload.projects,
        education=payload.education,
        status=payload.status,
    )

    text = build_candidate_search_text(payload)

    assert "Python" in text
    assert "Docker" in text
    assert "Kubernetes" in text
    assert "Redis" in text
