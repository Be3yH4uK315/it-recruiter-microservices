from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import CandidateProfileSummary


def make_candidate(**overrides) -> CandidateProfileSummary:
    base = CandidateProfileSummary(
        id=uuid4(),
        telegram_id=1,
        display_name="John_Doe",
        headline_role="Python Backend",
        location="Moscow",
        status="actively_looking",
        avatar_file_id=None,
        avatar_download_url=None,
        resume_file_id=None,
        resume_download_url=None,
        version_id=1,
        experience_years=4.5,
        work_modes=["remote", "hybrid"],
        contacts_visibility="on_request",
        contacts={"email": "john@example.com", "phone": "+7 900 123-45-67"},
        can_view_contacts=True,
        english_level="B2",
        about_me="About [me]",
        salary_min=150000,
        salary_max=250000,
        currency="RUB",
        skills=[
            {"skill": "Python", "level": 5, "kind": "hard"},
            {"skill": "Docker", "kind": "tool"},
        ],
        education=[{"level": "Bachelor", "institution": "MSU", "year": "2018"}],
        experiences=[
            {
                "position": "Backend",
                "company": "Acme",
                "start_date": "2021-01-01",
                "end_date": None,
                "responsibilities": "Build APIs",
            }
        ],
        projects=[
            {"title": "Recruiter", "links": ["https://example.com"], "description": "Search app"}
        ],
        explanation=None,
        match_score=0.0,
    )
    return replace(base, **overrides)


def test_build_candidate_profile_core_lines_contains_expected_sections() -> None:
    candidate = make_candidate()
    lines = ProfileSharedMessagesMixin._build_candidate_profile_core_lines(candidate)
    text = "\n".join(lines)

    assert "*John\\_Doe*" in text
    assert "*Должность:*" in text
    assert "*Статус:*" in text
    assert "*Навыки:*" in text
    assert "*Проекты:*" in text


def test_contacts_block_lines_for_viewable_and_hidden_contacts() -> None:
    viewable = ProfileSharedMessagesMixin._build_candidate_contacts_block_lines(
        contacts={"email": "a@b.c"},
        contacts_visibility="public",
        can_view_contacts=True,
        contacts_title="📞 *Контакты:*",
    )
    assert any("email" in line.lower() for line in viewable)

    hidden = ProfileSharedMessagesMixin._build_candidate_contacts_block_lines(
        contacts={"email": "a@b.c"},
        contacts_visibility="hidden",
        can_view_contacts=False,
        contacts_title="📞 *Контакты:*",
    )
    assert any("Недоступны" in line for line in hidden)


def test_pending_upload_recovery_message_variants() -> None:
    candidate_message = ProfileSharedMessagesMixin._build_pending_upload_recovery_message(
        role="candidate",
        recovered_kinds=["candidate_avatar", "candidate_avatar", "candidate_resume"],
        state_reset=True,
    )
    assert "аватар кандидата" in candidate_message
    assert "резюме кандидата" in candidate_message

    fallback_message = ProfileSharedMessagesMixin._build_pending_upload_recovery_message(
        role="unknown",
        recovered_kinds=[],
        state_reset=False,
    )
    assert "Повтори отправку файла" in fallback_message


def test_small_helpers_humanization_and_formatting() -> None:
    assert (
        ProfileSharedMessagesMixin._humanize_pending_upload_target_kind(" employer_document ")
        == "документ компании"
    )
    assert (
        ProfileSharedMessagesMixin._build_skills_preview(
            [{"skill": "Python"}, {"skill": "Go"}], limit=1
        )
        == "Python +1"
    )
    assert (
        ProfileSharedMessagesMixin._build_last_experience_preview(
            [{"position": "Dev", "company": "Acme"}]
        )
        == "Dev @ Acme"
    )
    assert ProfileSharedMessagesMixin._humanize_contacts_visibility("public") == "открыты"
    assert ProfileSharedMessagesMixin._humanize_search_status("paused") != "—"
    assert ProfileSharedMessagesMixin._as_clean_text("  a  ") == "a"
    assert ProfileSharedMessagesMixin._escape_markdown_text("a_b*") == "a\\_b\\*"
    assert ProfileSharedMessagesMixin._humanize_candidate_status("active") != "active"
    assert ProfileSharedMessagesMixin._humanize_work_mode("remote") != "remote"
    assert (
        ProfileSharedMessagesMixin._humanize_contacts_visibility_for_profile("on_request")
        != "on_request"
    )


def test_salary_and_dates_and_grouping_and_links_and_contacts() -> None:
    candidate = make_candidate(salary_min=100000, salary_max=200000, currency="RUB")
    assert "100 000" in ProfileSharedMessagesMixin._format_candidate_salary_expectations(candidate)
    assert ProfileSharedMessagesMixin._format_number_with_spaces(1234567) == "1 234 567"
    assert ProfileSharedMessagesMixin._format_experience_period(
        start_date="2021-01-01", end_date=None
    ).endswith("н.в.")
    assert ProfileSharedMessagesMixin._format_profile_date("2020-02-20T12:00:00") == "2020.02.20"

    grouped = ProfileSharedMessagesMixin._build_grouped_skills_preview(
        [
            {"skill": "Python", "kind": "hard", "level": 5},
            {"skill": "Docker", "kind": "tool"},
            {"skill": "English", "kind": "language"},
            {"skill": "Teamwork", "kind": "soft"},
        ]
    )
    assert len(grouped) == 4

    assert ProfileSharedMessagesMixin._join_limited(["a", "b", "c"], limit=2) == "a, b +1"
    assert (
        ProfileSharedMessagesMixin._extract_project_primary_link({"repo": "https://x"})
        == "https://x"
    )
    assert (
        ProfileSharedMessagesMixin._extract_project_primary_link(["", "https://y"]) == "https://y"
    )

    md_link = ProfileSharedMessagesMixin._format_project_title_link(
        title="Proj", link="https://example.com"
    )
    assert md_link.startswith("[")
    plain_link = ProfileSharedMessagesMixin._format_project_title_link(
        title="Proj", link="not-a-url"
    )
    assert "(" in plain_link and ")" in plain_link

    contact_lines = ProfileSharedMessagesMixin._build_owner_contact_lines(
        {"email": "a@b.c", "phone": "8 (900) 123-45-67", "telegram": "@john", "website": "site"}
    )
    assert len(contact_lines) == 4
    assert "+7 (900) 123-45-67" in "\n".join(contact_lines)

    assert ProfileSharedMessagesMixin._format_phone_for_profile("123") == "123"
