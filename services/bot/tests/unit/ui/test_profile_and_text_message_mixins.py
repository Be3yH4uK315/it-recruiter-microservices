from __future__ import annotations

from uuid import uuid4

from app.application.bot.ui.messages import BotMessagesMixin
from app.application.bot.ui.profile_message_mixins.candidate import CandidateProfileMessagesMixin
from app.application.bot.ui.profile_message_mixins.employer import EmployerProfileMessagesMixin
from app.application.bot.ui.profile_message_mixins.search import SearchProfileMessagesMixin
from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import (
    CandidateProfileSummary,
    CandidateStatisticsView,
    ContactAccessResultView,
    ContactRequestDecisionView,
    ContactRequestDetailsView,
    EmployerProfileSummary,
    EmployerStatisticsView,
    NextCandidateResultView,
    SearchSessionSummary,
)


class CandidateMessagesSut(CandidateProfileMessagesMixin):
    pass


class EmployerMessagesSut(EmployerProfileMessagesMixin):
    pass


class SearchMessagesSut(SearchProfileMessagesMixin):
    pass


class BotMessagesSut(BotMessagesMixin, ProfileSharedMessagesMixin):
    pass


def make_candidate(*, can_view_contacts: bool = False) -> CandidateProfileSummary:
    return CandidateProfileSummary(
        id=uuid4(),
        telegram_id=101,
        display_name="John",
        headline_role="Python Dev",
        location="Remote",
        status="active",
        avatar_file_id=None,
        avatar_download_url=None,
        resume_file_id=None,
        resume_download_url="https://example.com/resume.pdf",
        version_id=1,
        experience_years=3.2,
        work_modes=["remote", "hybrid"],
        contacts_visibility="on_request",
        contacts={"email": "john@example.com", "phone": "+100"},
        can_view_contacts=can_view_contacts,
        english_level="B2",
        about_me="About",
        salary_min=120000,
        salary_max=200000,
        currency="RUB",
        skills=[{"skill": "Python", "level": 5}],
        education=[{"level": "bachelor", "institution": "Uni", "specialization": "CS"}],
        experiences=[
            {
                "position": "Dev",
                "company": "Acme",
                "start_date": "2021-01-01",
                "end_date": "2023-01-01",
            }
        ],
        projects=[{"name": "Platform", "description": "Built", "links": ["https://example.com"]}],
    )


def make_employer() -> EmployerProfileSummary:
    return EmployerProfileSummary(
        id=uuid4(),
        telegram_id=202,
        company="Acme",
        avatar_file_id=uuid4(),
        avatar_download_url="https://example.com/a.jpg",
        document_file_id=uuid4(),
        document_download_url="https://example.com/doc.pdf",
        contacts={"email": "hr@acme.com", "website": "https://acme.com"},
    )


def test_candidate_profile_messages_cover_stats_requests_and_decisions() -> None:
    sut = CandidateMessagesSut()
    candidate = make_candidate(can_view_contacts=True)

    profile = sut._build_candidate_profile_message(candidate=candidate)
    dashboard = sut._build_candidate_dashboard_message(
        first_name="John",
        candidate=candidate,
        statistics=None,
        created_now=True,
    )
    stats_none = sut._build_candidate_stats_message(candidate, None)
    stats_ok = sut._build_candidate_stats_message(
        candidate,
        CandidateStatisticsView(
            total_views=10, total_likes=3, total_contact_requests=2, is_degraded=True
        ),
    )

    pending = sut._build_candidate_pending_contact_requests_message(
        [type("Req", (), {"employer_company": "Acme", "created_at": "2026-04-03T08:12:11Z"})()],
        page=2,
        total_pages=5,
    )
    details = sut._build_candidate_contact_request_details_message(
        ContactRequestDetailsView(
            id=uuid4(),
            employer_telegram_id=999,
            candidate_name="John",
            candidate_id=candidate.id,
            status="pending",
            granted=False,
        )
    )
    granted = sut._build_candidate_contact_request_decision_message(
        ContactRequestDecisionView(granted=True, status="granted", request_id=uuid4())
    )
    rejected = sut._build_candidate_contact_request_decision_message(
        ContactRequestDecisionView(granted=False, status="rejected", request_id=uuid4())
    )
    other = sut._build_candidate_contact_request_decision_message(
        ContactRequestDecisionView(granted=False, status="pending", request_id=uuid4())
    )

    assert "🧭 *Кабинет кандидата" in profile
    assert "*Главная*" in dashboard
    assert "✅ *Профиль кандидата создан.*" in dashboard
    assert "временно недоступна" in stats_none
    assert "Ограниченный режим" in stats_ok
    assert "Страница: *2/5*" in pending
    assert "Запрос контактов" in details
    assert "одобрил" in granted
    assert "отклонил" in rejected
    assert "Ответ по запросу контактов сохранен" in other


def test_employer_profile_messages_cover_stats_and_contact_access_statuses() -> None:
    sut = EmployerMessagesSut()
    employer = make_employer()

    dashboard = sut._build_employer_dashboard_message(
        first_name="HR",
        employer=employer,
        statistics=None,
        created_now=False,
    )
    profile = sut._build_employer_profile_message(employer=employer)
    stats_none = sut._build_employer_stats_message(employer, None)
    stats_ok = sut._build_employer_stats_message(
        employer,
        EmployerStatisticsView(
            total_viewed=30,
            total_liked=7,
            total_contact_requests=4,
            total_contacts_granted=2,
        ),
    )

    granted = sut._build_contact_access_result_message(
        ContactAccessResultView(
            granted=True, status="granted", contacts={"email": "candidate@example.com"}
        )
    )
    pending = sut._build_contact_access_result_message(
        ContactAccessResultView(granted=False, status="pending")
    )
    rejected = sut._build_contact_access_result_message(
        ContactAccessResultView(granted=False, status="rejected")
    )
    fallback = sut._build_contact_access_result_message(
        ContactAccessResultView(granted=False, status="unknown")
    )

    assert "🧭 *Кабинет работодателя" in dashboard
    assert "*Главная*" in dashboard
    assert "Контакты компании" in profile
    assert "временно недоступна" in stats_none
    assert "Открытых контактов" in stats_ok
    assert "Доступ к контактам открыт" in granted
    assert "Запрос на контакты отправлен" in pending
    assert "не предоставляет контакты" in rejected
    assert "Не удалось получить контакты" in fallback


def test_search_profile_messages_cover_empty_collection_and_next_candidate_paths() -> None:
    sut = SearchMessagesSut()
    candidate_hidden_contacts = make_candidate(can_view_contacts=False)
    candidate_open_contacts = make_candidate(can_view_contacts=True)

    empty = sut._build_candidate_collection_message(title="Favorites", items=[])
    collection = sut._build_candidate_collection_message(
        title="Favorites",
        items=[candidate_hidden_contacts, candidate_open_contacts],
    )

    none_degraded = sut._build_next_candidate_message(
        NextCandidateResultView(candidate=None, message=None, is_degraded=True)
    )
    none_regular = sut._build_next_candidate_message(
        NextCandidateResultView(candidate=None, message="No more", is_degraded=False)
    )
    with_candidate = sut._build_next_candidate_message(
        NextCandidateResultView(candidate=candidate_open_contacts, message=None, is_degraded=False)
    )

    assert "Пока пусто" in empty
    assert "Контакты" in collection
    assert "Поиск временно ограничен" in none_degraded
    assert "Кандидаты по этому поиску закончились" in none_regular
    assert "🧭 *Кабинет работодателя" in with_candidate
    assert "Карточка кандидата" in with_candidate


def test_bot_messages_cover_help_list_and_status_builders() -> None:
    sut = BotMessagesSut()

    help_common = sut._build_common_help_message()
    help_candidate = sut._build_candidate_help_message()
    help_employer = sut._build_employer_help_message()

    searches = [
        SearchSessionSummary(
            id=uuid4(), employer_id=uuid4(), title="Python", status="active", role="Backend"
        ),
        SearchSessionSummary(
            id=uuid4(), employer_id=uuid4(), title="Data", status="closed", role="ML"
        ),
    ]
    list_message = sut._build_searches_list_message(searches, page=1, total_pages=2)
    status_message = sut._build_search_session_status_message(searches[0])

    assert "/start" in help_common and "/logout" in help_common
    assert "🧭 *Общие команды" in help_common
    assert "Кабинет кандидата" in help_candidate
    assert "Кабинет работодателя" in help_employer
    assert "Страница: *1/2*" in list_message
    assert "Статус" in list_message
    assert "Состояние поиска обновлено" in status_message
