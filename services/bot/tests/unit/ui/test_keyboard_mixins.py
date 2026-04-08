from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.bot.handlers.common.pagination import PaginationUtilsMixin
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin
from app.application.bot.ui.keyboard_mixins.candidate import CandidateKeyboardsMixin
from app.application.bot.ui.keyboard_mixins.common import CommonKeyboardsMixin
from app.application.bot.ui.keyboard_mixins.employer import EmployerKeyboardsMixin
from app.application.bot.ui.keyboard_mixins.search import SearchKeyboardsMixin
from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import (
    CandidateProfileSummary,
    EmployerProfileSummary,
    SearchSessionSummary,
)


class KeyboardSut(
    CommonKeyboardsMixin,
    CandidateKeyboardsMixin,
    EmployerKeyboardsMixin,
    SearchKeyboardsMixin,
    PaginationUtilsMixin,
    SearchUtilsMixin,
    ProfileSharedMessagesMixin,
):
    def __init__(self) -> None:
        self.tokens: list[tuple[int, str, dict]] = []

    async def _create_callback_context(
        self, *, telegram_user_id: int, action_type: str, payload: dict
    ):
        self.tokens.append((telegram_user_id, action_type, payload))
        return f"{action_type}:{payload}"


def make_candidate(
    *, resume_url: str | None = None, can_view_contacts: bool = False
) -> CandidateProfileSummary:
    return CandidateProfileSummary(
        id=uuid4(),
        telegram_id=101,
        display_name="John",
        headline_role="Python",
        location="Remote",
        status="active",
        avatar_file_id=None,
        avatar_download_url=None,
        resume_file_id=None,
        resume_download_url=resume_url,
        version_id=1,
        can_view_contacts=can_view_contacts,
    )


def make_employer(*, document_url: str | None = None) -> EmployerProfileSummary:
    return EmployerProfileSummary(
        id=uuid4(),
        telegram_id=201,
        company="Acme",
        avatar_file_id=None,
        avatar_download_url=None,
        document_file_id=None,
        document_download_url=document_url,
        contacts={},
    )


@pytest.mark.asyncio
async def test_common_and_candidate_markups_cover_core_branches() -> None:
    sut = KeyboardSut()

    role_markup = await sut._build_role_selection_markup(telegram_user_id=1)
    assert len(role_markup["inline_keyboard"]) == 2

    candidate_continue = await sut._build_candidate_registration_continue_markup(1)
    employer_continue = await sut._build_employer_registration_continue_markup(1)
    assert len(candidate_continue["inline_keyboard"]) == 2
    assert len(employer_continue["inline_keyboard"]) == 2

    dashboard = await sut._build_candidate_dashboard_markup(telegram_user_id=1)
    assert len(dashboard["inline_keyboard"]) == 5

    files_all = await sut._build_candidate_files_section_markup(
        telegram_user_id=1,
        has_avatar=True,
        has_resume=True,
    )
    files_upload = await sut._build_candidate_files_section_markup(
        telegram_user_id=1,
        has_avatar=False,
        has_resume=False,
    )
    assert any(
        "Скачать аватар" in btn["text"] for row in files_all["inline_keyboard"] for btn in row
    )
    assert any(
        "Загрузить резюме" in btn["text"] for row in files_upload["inline_keyboard"] for btn in row
    )

    contacts = await sut._build_candidate_contacts_section_markup(telegram_user_id=1)
    back = await sut._build_candidate_back_to_dashboard_markup(telegram_user_id=1)
    assert len(contacts["inline_keyboard"]) == 3
    assert back["inline_keyboard"][0][0]["text"] == "⬅️ В меню"


@pytest.mark.asyncio
async def test_candidate_list_and_profile_specific_markups() -> None:
    sut = KeyboardSut()

    request_items = [
        type(
            "Req", (), {"id": uuid4(), "employer_company": "Very long company name to trim display"}
        )(),
        type("Req", (), {"id": None, "employer_company": "Skip"})(),
    ]
    req_markup = await sut._build_candidate_contact_requests_list_markup(
        telegram_user_id=1,
        requests=request_items,
        page=2,
        total_pages=3,
    )
    rows = req_markup["inline_keyboard"]
    assert any("Запрос:" in row[0]["text"] for row in rows if row)
    assert any("Стр." in btn["text"] for row in rows for btn in row)

    profile_with_resume = await sut._build_candidate_profile_view_markup(
        telegram_user_id=1,
        candidate=make_candidate(resume_url="https://example.com/resume.pdf"),
    )
    profile_without_resume = await sut._build_candidate_profile_view_markup(
        telegram_user_id=1,
        candidate=make_candidate(resume_url=None),
    )
    assert len(profile_with_resume["inline_keyboard"][0]) == 2
    assert len(profile_without_resume["inline_keyboard"][0]) == 1

    edit_menu = await sut._build_candidate_profile_edit_menu_markup(telegram_user_id=1)
    assert len(edit_menu["inline_keyboard"]) == 7


@pytest.mark.asyncio
async def test_candidate_selectors_cover_selection_and_clear() -> None:
    sut = KeyboardSut()

    work_modes = await sut._build_candidate_work_modes_selector_markup(
        telegram_user_id=1,
        selected_modes=["remote"],
        allow_clear=True,
    )
    assert any(btn["text"].startswith("✅") for row in work_modes["inline_keyboard"] for btn in row)
    assert any(
        "Очистить выбор" in btn["text"] for row in work_modes["inline_keyboard"] for btn in row
    )

    visibility = await sut._build_candidate_contacts_visibility_selector_markup(
        telegram_user_id=1,
        selected_visibility="on_request",
    )
    assert any(btn["text"].startswith("✅") for row in visibility["inline_keyboard"] for btn in row)

    english = await sut._build_candidate_english_level_selector_markup(
        telegram_user_id=1,
        selected_level="B2",
        allow_clear=True,
    )
    assert any(
        "B2" in btn["text"] and btn["text"].startswith("✅")
        for row in english["inline_keyboard"]
        for btn in row
    )
    assert any("Очистить" in btn["text"] for row in english["inline_keyboard"] for btn in row)
    assert not any(
        "Пропустить" in btn["text"] for row in english["inline_keyboard"] for btn in row
    )

    status = await sut._build_candidate_status_selector_markup(
        telegram_user_id=1,
        selected_status="hidden",
    )
    assert status["inline_keyboard"][1][0]["text"].startswith("✅")


@pytest.mark.asyncio
async def test_employer_keyboards_cover_sections_lists_and_collection() -> None:
    sut = KeyboardSut()

    dashboard = await sut._build_employer_dashboard_markup(telegram_user_id=1)
    edit = await sut._build_employer_edit_section_markup(telegram_user_id=1)
    assert len(dashboard["inline_keyboard"]) == 6
    assert len(edit["inline_keyboard"]) == 4

    files_manage = await sut._build_employer_files_section_markup(
        telegram_user_id=1,
        has_avatar=True,
        has_document=False,
    )
    assert any(
        "Удалить аватар" in btn["text"] for row in files_manage["inline_keyboard"] for btn in row
    )
    assert any(
        "Загрузить документ" in btn["text"]
        for row in files_manage["inline_keyboard"]
        for btn in row
    )

    back = await sut._build_employer_back_to_dashboard_markup(telegram_user_id=1)
    profile_with_doc = await sut._build_employer_profile_view_markup(
        telegram_user_id=1,
        employer=make_employer(document_url="https://example.com/doc.pdf"),
    )
    profile_without_doc = await sut._build_employer_profile_view_markup(
        telegram_user_id=1,
        employer=make_employer(document_url=None),
    )
    assert back["inline_keyboard"][0][0]["text"] == "⬅️ В меню"
    assert len(profile_with_doc["inline_keyboard"][0]) == 2
    assert len(profile_without_doc["inline_keyboard"][0]) == 1

    search_section_active = await sut._build_employer_search_section_markup(
        telegram_user_id=1,
        has_active_search=True,
    )
    search_section_no_active = await sut._build_employer_search_section_markup(
        telegram_user_id=1,
        has_active_search=False,
    )
    assert len(search_section_active["inline_keyboard"][0]) == 2
    assert len(search_section_no_active["inline_keyboard"][0]) == 1

    employer_edit_prompt = await sut._build_employer_edit_prompt_markup(telegram_user_id=1)
    candidate_edit_prompt = await sut._build_candidate_edit_prompt_markup(telegram_user_id=1)
    assert employer_edit_prompt["inline_keyboard"][0][0]["text"] == "🛑 Отменить"
    assert candidate_edit_prompt["inline_keyboard"][0][0]["text"] == "🛑 Отменить"

    empty = await sut._build_employer_searches_empty_markup(telegram_user_id=1)
    assert len(empty["inline_keyboard"]) == 2

    employer_id = uuid4()
    searches = [
        SearchSessionSummary(
            id=uuid4(), employer_id=employer_id, title="S1", status="active", role="Python"
        ),
        SearchSessionSummary(
            id=uuid4(), employer_id=employer_id, title="S2", status="closed", role="Go"
        ),
    ]
    searches_markup = await sut._build_searches_list_markup(
        telegram_user_id=1,
        searches=searches,
        page=1,
        total_pages=2,
    )
    assert any("Стр." in btn["text"] for row in searches_markup["inline_keyboard"] for btn in row)
    assert any("S1" in row[0]["text"] for row in searches_markup["inline_keyboard"] if row)
    assert not any(
        "S2" in row[0]["text"] for row in searches_markup["inline_keyboard"] if row and row[0]
    )
    assert any(
        "К поиску" in btn["text"]
        for row in searches_markup["inline_keyboard"]
        for btn in row
    )

    candidates = [make_candidate(can_view_contacts=False), make_candidate(can_view_contacts=True)]
    bad_source = await sut._build_candidate_collection_markup(
        telegram_user_id=1,
        items=candidates,
        source="unknown",
        page=1,
    )
    favorites = await sut._build_candidate_collection_markup(
        telegram_user_id=1,
        items=candidates,
        source="favorites",
        page=1,
        total_pages=2,
    )
    favorites_profile = await sut._build_candidate_collection_profile_markup(
        telegram_user_id=1,
        source="favorites",
        page=1,
        total_pages=2,
    )
    unlocked = await sut._build_candidate_collection_markup(
        telegram_user_id=1,
        items=candidates,
        source="unlocked",
        page=1,
    )
    assert bad_source is None
    assert any("Стр." in btn["text"] for row in favorites["inline_keyboard"] for btn in row)
    assert any("👤" in row[0]["text"] for row in unlocked["inline_keyboard"] if row)
    assert favorites_profile["inline_keyboard"][0][0]["text"] == "⬅️ К списку"
    assert any(
        "К поиску" in btn["text"] and "В меню" not in btn["text"]
        for row in favorites["inline_keyboard"]
        for btn in row
    )
    assert any(
        "В меню" in btn["text"] for row in favorites["inline_keyboard"] for btn in row
    )


@pytest.mark.asyncio
async def test_search_keyboards_cover_closed_active_and_decision_paths() -> None:
    sut = KeyboardSut()
    session_id = uuid4()
    candidate = make_candidate(resume_url="https://example.com/resume.pdf", can_view_contacts=True)

    confirm = await sut._build_employer_search_create_confirm_markup(telegram_user_id=1)
    assert len(confirm["inline_keyboard"]) == 8

    controls = await sut._build_employer_search_wizard_controls_markup(
        telegram_user_id=1,
        step="title",
        allow_skip=True,
        allow_back=True,
    )
    controls_min = await sut._build_employer_search_wizard_controls_markup(
        telegram_user_id=1,
        step="title",
        allow_skip=False,
        allow_back=False,
    )
    assert len(controls["inline_keyboard"]) == 2
    assert len(controls_min["inline_keyboard"]) == 1

    work_modes = await sut._build_employer_search_work_modes_selector_markup(
        telegram_user_id=1,
        selected_modes=["remote"],
        allow_skip=True,
    )
    english = await sut._build_employer_search_english_selector_markup(
        telegram_user_id=1,
        selected_level="C1",
        allow_skip=True,
    )
    assert any(btn["text"].startswith("✅") for row in work_modes["inline_keyboard"] for btn in row)
    assert any("Очистить" in btn["text"] for row in english["inline_keyboard"] for btn in row)
    assert any("Пропустить" in btn["text"] for row in english["inline_keyboard"] for btn in row)

    open_active = await sut._build_open_search_markup(1, session_id, "active")
    open_closed = await sut._build_open_search_markup(1, session_id, "closed")
    assert any(
        "Открыть поиск" in btn["text"] for row in open_active["inline_keyboard"] for btn in row
    )
    assert not any(
        "Открыть поиск" in btn["text"] for row in open_closed["inline_keyboard"] for btn in row
    )

    next_active = await sut._build_next_candidate_only_markup(
        telegram_user_id=1,
        session_id=session_id,
        search_status="active",
    )
    next_closed = await sut._build_next_candidate_only_markup(
        telegram_user_id=1,
        session_id=session_id,
        search_status="closed",
    )
    assert any(
        "Следующий кандидат" in btn["text"] for row in next_active["inline_keyboard"] for btn in row
    )
    assert not any(
        "Следующий кандидат" in btn["text"] for row in next_closed["inline_keyboard"] for btn in row
    )

    no_candidate = await sut._build_no_candidate_markup(
        telegram_user_id=1,
        session_id=session_id,
        search_status="active",
        is_degraded=True,
    )
    assert any("Повторить" in btn["text"] for row in no_candidate["inline_keyboard"] for btn in row)

    after_like_active = await sut._build_after_like_markup(
        telegram_user_id=1,
        session_id=session_id,
        candidate_id=candidate.id,
        search_status="active",
    )
    after_like_closed = await sut._build_after_like_markup(
        telegram_user_id=1,
        session_id=session_id,
        candidate_id=candidate.id,
        search_status="closed",
    )
    assert any(
        "Запросить контакты" in btn["text"]
        for row in after_like_active["inline_keyboard"]
        for btn in row
    )
    assert any(
        "Следующий кандидат" in btn["text"]
        for row in after_like_active["inline_keyboard"]
        for btn in row
    )
    assert not any(
        "Следующий кандидат" in btn["text"]
        for row in after_like_closed["inline_keyboard"]
        for btn in row
    )

    decision_none = await sut._build_candidate_decision_markup(
        telegram_user_id=1,
        session_id=session_id,
        candidate=None,
        search_status="active",
    )
    decision_closed = await sut._build_candidate_decision_markup(
        telegram_user_id=1,
        session_id=session_id,
        candidate=candidate,
        search_status="closed",
    )
    decision_active = await sut._build_candidate_decision_markup(
        telegram_user_id=1,
        session_id=session_id,
        candidate=candidate,
        search_status="active",
    )
    assert decision_none["inline_keyboard"] == []
    assert any(
        "К списку поисков" in row[0]["text"] for row in decision_closed["inline_keyboard"] if row
    )
    assert any(
        "Открыть резюме" in row[0]["text"] for row in decision_active["inline_keyboard"] if row
    )
