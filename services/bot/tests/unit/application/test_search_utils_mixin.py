from __future__ import annotations

import pytest

from app.application.bot.constants import (
    EMPLOYER_SEARCH_ABOUT_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MAX_LEN,
    EMPLOYER_SEARCH_TITLE_MAX_LEN,
)
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin


class DummySearchUtils(SearchUtilsMixin):
    def __init__(self) -> None:
        self.state_calls: list[dict] = []

    async def _set_state_and_render_wizard_step(self, **kwargs) -> None:
        self.state_calls.append(kwargs)

    def _build_employer_search_filters_summary(self, payload: dict) -> str:
        return f"summary:{payload.get('title', '')}"

    async def _build_employer_search_create_confirm_markup(self, telegram_user_id: int):
        return {"uid": telegram_user_id}


def test_normalize_optional_user_input() -> None:
    assert SearchUtilsMixin._normalize_optional_user_input("  text ") == "text"
    assert SearchUtilsMixin._normalize_optional_user_input(" - ") is None
    assert SearchUtilsMixin._normalize_optional_user_input("пропустить") is None
    assert SearchUtilsMixin._normalize_optional_user_input("  ") is None


def test_get_employer_search_wizard_step_config() -> None:
    title_cfg = SearchUtilsMixin._get_employer_search_wizard_step_config("title")
    assert title_cfg is not None
    assert title_cfg["allow_skip"] is False

    assert SearchUtilsMixin._get_employer_search_wizard_step_config("unknown") is None


def test_parse_search_skill_list_valid_and_invalid() -> None:
    parsed = SearchUtilsMixin._parse_search_skill_list("Python:4, FastAPI, Docker:2")
    assert parsed == [
        {"skill": "Python", "level": 4},
        {"skill": "FastAPI"},
        {"skill": "Docker", "level": 2},
    ]

    assert SearchUtilsMixin._parse_search_skill_list("-") == []
    assert SearchUtilsMixin._parse_search_skill_list("Python:") is None
    assert SearchUtilsMixin._parse_search_skill_list(":3") is None
    assert SearchUtilsMixin._parse_search_skill_list("Python:0") is None
    assert SearchUtilsMixin._parse_search_skill_list("Python:6") is None
    assert SearchUtilsMixin._parse_search_skill_list("Python:abc") is None


def test_parse_search_experience_range() -> None:
    assert SearchUtilsMixin._parse_search_experience_range("2-5") == (2.0, 5.0)
    assert SearchUtilsMixin._parse_search_experience_range("-") == (None, None)
    assert SearchUtilsMixin._parse_search_experience_range("2") is None
    assert SearchUtilsMixin._parse_search_experience_range("5-2") is None
    assert SearchUtilsMixin._parse_search_experience_range("-1-2") is None


def test_parse_search_work_modes() -> None:
    assert SearchUtilsMixin._parse_search_work_modes("remote, onsite, remote") == [
        "remote",
        "onsite",
    ]
    assert SearchUtilsMixin._parse_search_work_modes("-") == []
    assert SearchUtilsMixin._parse_search_work_modes("invalid") is None


def test_parse_search_salary() -> None:
    assert SearchUtilsMixin._parse_search_salary("100000 200000 rub") == (100000, 200000, "RUB")
    assert SearchUtilsMixin._parse_search_salary("100000-200000 USD") == (100000, 200000, "USD")
    assert SearchUtilsMixin._parse_search_salary("-") == (None, None, None)
    assert SearchUtilsMixin._parse_search_salary("100-50") is None
    assert SearchUtilsMixin._parse_search_salary("100 aaa") is None


def test_edit_step_helpers() -> None:
    payload: dict = {}
    assert SearchUtilsMixin._get_employer_search_edit_step(payload) is None

    SearchUtilsMixin._set_employer_search_edit_step(payload, step=" Role ")
    assert SearchUtilsMixin._get_employer_search_edit_step(payload) == "role"
    assert SearchUtilsMixin._is_employer_search_edit_step(payload, step="ROLE") is True

    SearchUtilsMixin._clear_employer_search_edit_step(payload)
    assert SearchUtilsMixin._get_employer_search_edit_step(payload) is None


@pytest.mark.asyncio
async def test_render_confirm_step_calls_state_render() -> None:
    sut = DummySearchUtils()
    payload = {"title": "Senior Python"}

    await sut._render_employer_search_confirm_step(
        telegram_user_id=111,
        chat_id=222,
        payload=payload,
    )

    assert len(sut.state_calls) == 1
    call = sut.state_calls[0]
    assert call["telegram_user_id"] == 111
    assert call["chat_id"] == 222
    assert "summary:Senior Python" in call["text"]


def test_parse_search_english_level() -> None:
    assert SearchUtilsMixin._parse_search_english_level("b2") == "B2"
    assert SearchUtilsMixin._parse_search_english_level("-") is None
    assert SearchUtilsMixin._parse_search_english_level("native") is None


@pytest.mark.parametrize(
    ("payload", "expected_substring"),
    [
        ({"title": "", "role": "Python"}, "Заполни название поиска"),
        ({"title": "A", "role": ""}, "Заполни роль"),
        ({"title": "x" * (EMPLOYER_SEARCH_TITLE_MAX_LEN + 1), "role": "R"}, "слишком длинное"),
        ({"title": "T", "role": "x" * (EMPLOYER_SEARCH_ROLE_MAX_LEN + 1)}, "слишком длинная"),
        ({"title": "T", "role": "R", "must_skills": "bad"}, "Список навыков"),
        (
            {"title": "T", "role": "R", "must_skills": [{"skill": "", "level": 1}]},
            "пустое значение",
        ),
        ({"title": "T", "role": "R", "must_skills": [{"skill": "Py", "level": 7}]}, "от 1 до 5"),
        ({"title": "T", "role": "R", "experience_min": "bad"}, "Минимальный опыт"),
        ({"title": "T", "role": "R", "experience_min": 5, "experience_max": 3}, "Диапазон опыта"),
        ({"title": "T", "role": "R", "work_modes": ["mars"]}, "неподдерживаемое"),
        ({"title": "T", "role": "R", "salary_min": "bad"}, "Минимальная зарплата"),
        ({"title": "T", "role": "R", "salary_min": -1}, "не может быть отрицательной"),
        ({"title": "T", "role": "R", "salary_min": 200, "salary_max": 100}, "Диапазон зарплаты"),
        ({"title": "T", "role": "R", "english_level": "zzz"}, "английского"),
        (
            {"title": "T", "role": "R", "about_me": "x" * (EMPLOYER_SEARCH_ABOUT_MAX_LEN + 1)},
            "Описание слишком длинное",
        ),
    ],
)
def test_validate_employer_search_draft_errors(payload: dict, expected_substring: str) -> None:
    error = SearchUtilsMixin._validate_employer_search_draft(payload)
    assert error is not None
    assert expected_substring in error


def test_validate_employer_search_draft_ok_and_payload_building() -> None:
    payload = {
        "title": "Data Search",
        "role": "Data Engineer",
        "must_skills": [{"skill": "Python", "level": 4}],
        "nice_skills": [{"skill": "Airflow"}],
        "experience_min": 2,
        "experience_max": 5,
        "location": "  Moscow ",
        "work_modes": ["remote"],
        "salary_min": 120000,
        "salary_max": 250000,
        "currency": " rub ",
        "english_level": "B2",
        "about_me": " strong backend ",
    }

    assert SearchUtilsMixin._validate_employer_search_draft(payload) is None

    filters = SearchUtilsMixin._build_employer_search_filters_payload(payload)
    assert filters["role"] == "Data Engineer"
    assert filters["location"] == "Moscow"
    assert filters["currency"] == "RUB"
    assert filters["about_me"] == "strong backend"


def test_search_status_helpers() -> None:
    assert SearchUtilsMixin._normalize_search_status(" Active ") == "active"
    assert SearchUtilsMixin._normalize_search_status(None) is None

    assert SearchUtilsMixin._is_search_active(None) is True
    assert SearchUtilsMixin._is_search_active("open") is True
    assert SearchUtilsMixin._is_search_active("closed") is False

    assert SearchUtilsMixin._is_search_paused("paused") is True
    assert SearchUtilsMixin._is_search_closed("archived") is True
