from __future__ import annotations

from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.bot.ui.search_wizard_messages import BotSearchWizardMessagesMixin


class WizardMessagesSut(BotSearchWizardMessagesMixin, ProfileSharedMessagesMixin):
    pass


def test_escape_and_format_skills_helpers() -> None:
    sut = WizardMessagesSut()

    escaped = sut._escape_markdown_text("_[`x`]\\")
    assert escaped == "\\_\\[\\`x\\`\\]\\\\"

    assert (
        sut._format_search_skills_for_summary(
            ["bad", {"skill": "Python", "level": 4}, {"skill": "Go"}]
        )
        == "Python:4, Go"
    )

    many = [{"skill": f"S{i}"} for i in range(10)]
    summarized = sut._format_search_skills_for_summary(many)
    assert summarized.endswith("(+2)")


def test_build_employer_search_filters_summary_covers_all_fields() -> None:
    sut = WizardMessagesSut()

    payload = {
        "title": "Python_[Lead]",
        "role": "Backend",
        "must_skills": [{"skill": "Python", "level": 5}],
        "nice_skills": [{"skill": "Docker"}],
        "experience_min": 2.0,
        "experience_max": 5.0,
        "location": "Moscow",
        "work_modes": ["remote", "hybrid"],
        "salary_min": 150000,
        "salary_max": 300000,
        "currency": "rub",
        "english_level": "B2",
        "about_me": "A" * 220,
    }
    text = sut._build_employer_search_filters_summary(payload)

    assert "*Название:*" in text
    assert "Python\\_\\[Lead\\]" in text
    assert "Python:5" in text
    assert "📈 *Опыт:* 2 – 5" in text
    assert "🏠 Удаленно, 📌 Гибрид" in text
    assert "150 000" in text
    assert "₽" in text
    assert "B2" in text
    assert "…" in text


def test_build_employer_search_step_current_value_for_steps() -> None:
    sut = WizardMessagesSut()
    payload = {
        "title": "Title",
        "role": "Role",
        "must_skills": [{"skill": "Python", "level": 4}],
        "nice_skills": [{"skill": "Docker"}],
        "experience_min": 1.0,
        "experience_max": 3.0,
        "location": "SPb",
        "work_modes": ["remote"],
        "salary_min": 100000,
        "salary_max": 200000,
        "currency": "RUB",
        "english_level": "C1",
        "about_me": "Details",
    }

    assert sut._build_employer_search_step_current_value(payload, "title") == "Title"
    assert sut._build_employer_search_step_current_value(payload, "role") == "Role"
    assert "Python:4" in sut._build_employer_search_step_current_value(payload, "must_skills")
    assert "Docker" in sut._build_employer_search_step_current_value(payload, "nice_skills")
    assert sut._build_employer_search_step_current_value(payload, "experience") == "1 – 3"
    assert sut._build_employer_search_step_current_value(payload, "location") == "SPb"
    assert "Удаленно" in sut._build_employer_search_step_current_value(payload, "work_modes")
    assert "₽" in sut._build_employer_search_step_current_value(payload, "salary")
    assert sut._build_employer_search_step_current_value(payload, "english") == "C1"
    assert sut._build_employer_search_step_current_value(payload, "about") == "Details"
    assert sut._build_employer_search_step_current_value(payload, "unknown") == "—"


def test_build_step_current_value_handles_empty_payload_branches() -> None:
    sut = WizardMessagesSut()
    payload = {
        "must_skills": [],
        "nice_skills": [],
        "work_modes": [],
        "salary_min": None,
        "salary_max": None,
        "currency": None,
    }

    assert sut._build_employer_search_step_current_value(payload, "must_skills") == "—"
    assert sut._build_employer_search_step_current_value(payload, "nice_skills") == "—"
    assert sut._build_employer_search_step_current_value(payload, "work_modes") == "—"
    assert sut._build_employer_search_step_current_value(payload, "salary") == "—"
    assert sut._build_employer_search_step_current_value(payload, "experience") == "—"
