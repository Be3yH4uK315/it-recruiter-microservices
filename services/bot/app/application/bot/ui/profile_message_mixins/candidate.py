from __future__ import annotations

from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import (
    CandidateProfileSummary,
    CandidateStatisticsView,
    ContactRequestDecisionView,
    ContactRequestDetailsView,
)


class CandidateProfileMessagesMixin(ProfileSharedMessagesMixin):
    @staticmethod
    def _build_candidate_profile_message(
        *,
        candidate: CandidateProfileSummary,
    ) -> str:
        lines = [
            "Кабинет кандидата > Профиль",
            "",
        ]
        lines.extend(
            CandidateProfileMessagesMixin._build_candidate_profile_core_lines(
                candidate,
                about_limit=600,
            )
        )

        lines.extend(
            [""]
            + CandidateProfileMessagesMixin._build_candidate_contacts_block_lines(
                contacts=candidate.contacts,
                contacts_visibility=candidate.contacts_visibility,
                can_view_contacts=True,
                contacts_title="📞 *Ваши контакты:*",
            )
        )

        return "\n".join(lines)

    @staticmethod
    def _build_candidate_dashboard_message(
        *,
        first_name: str | None,
        candidate: CandidateProfileSummary,
        statistics: CandidateStatisticsView | None,
        created_now: bool,
    ) -> str:
        header = "✅ Профиль кандидата создан." if created_now else "✅ Профиль кандидата загружен."
        display_name = (
            CandidateProfileMessagesMixin._as_clean_text(candidate.display_name) or "Имя не указано"
        )
        headline_role = (
            CandidateProfileMessagesMixin._as_clean_text(candidate.headline_role) or "Не указана"
        )
        lines = [
            "Кабинет кандидата > Главная",
            "",
            header,
            "",
            f"👤 *{CandidateProfileMessagesMixin._escape_markdown_text(display_name)}*",
            "",
            "💼 *Должность:* " + CandidateProfileMessagesMixin._escape_markdown_text(headline_role),
            "",
            "📊 *Статус:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._humanize_candidate_status(candidate.status)
            ),
            "",
            "👁 *Видимость контактов:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._humanize_contacts_visibility_for_profile(
                    candidate.contacts_visibility
                )
            ),
            "",
        ]

        lines.extend(
            [
                "Основные действия доступны в кнопках ниже.",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _build_candidate_stats_message(
        candidate: CandidateProfileSummary,
        statistics: CandidateStatisticsView | None,
    ) -> str:
        display_name = (
            CandidateProfileMessagesMixin._as_clean_text(candidate.display_name) or "Имя не указано"
        )
        headline_role = (
            CandidateProfileMessagesMixin._as_clean_text(candidate.headline_role) or "Не указана"
        )
        lines = [
            "Кабинет кандидата > Статистика",
            "",
            "📊 Статистика кандидата",
            "",
            f"👤 *{CandidateProfileMessagesMixin._escape_markdown_text(display_name)}* — "
            f"{CandidateProfileMessagesMixin._escape_markdown_text(headline_role)}",
        ]
        if statistics is None:
            lines.extend(["", "⚠️ Статистика временно недоступна."])
            return "\n".join(lines)

        lines.extend(
            [
                "",
                f"  • 👀 *Просмотры:* {statistics.total_views}",
                f"  • 👍 *Лайки:* {statistics.total_likes}",
                f"  • 🔓 *Запросы контактов:* {statistics.total_contact_requests}",
                f"  • 🛠 *Ограниченный режим:* {'да' if statistics.is_degraded else 'нет'}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _build_candidate_pending_contact_requests_message(
        requests: list,
        *,
        page: int = 1,
        total_pages: int = 1,
    ) -> str:
        lines = [
            f"Кабинет кандидата > Запросы контактов (стр. {page}/{total_pages})",
            "",
            "📨 *Ожидающие запросы на контакты:*",
            "",
        ]
        for index, item in enumerate(requests[:10], start=1):
            company = str(getattr(item, "employer_company", "") or "Компания")
            created_at = str(getattr(item, "created_at", "") or "")
            created_preview = created_at[:19].replace("T", " ") if created_at else "—"
            lines.append(
                f"{index}. 🏢 {CandidateProfileMessagesMixin._escape_markdown_text(company)}"
            )
            lines.append(
                "   🕒 *Создан:* "
                + CandidateProfileMessagesMixin._escape_markdown_text(created_preview)
            )
        return "\n".join(lines)

    @staticmethod
    def _build_candidate_contact_request_details_message(
        details: ContactRequestDetailsView,
    ) -> str:
        lines = [
            "Кабинет кандидата > Запросы контактов > Детали",
            "",
            "📨 Запрос контактов",
            "",
            (
                "🏷 *Request ID:* "
                f"{CandidateProfileMessagesMixin._escape_markdown_text(str(details.id))}"
            ),
            "👤 *Кандидат:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._as_clean_text(details.candidate_name) or "—"
            ),
            "📊 *Статус:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._as_clean_text(details.status) or "—"
            ),
            f"✅ *Одобрено:* {'да' if details.granted else 'нет'}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_candidate_contact_request_decision_message(
        result: ContactRequestDecisionView,
    ) -> str:
        status = result.status.strip().lower()
        if status == "granted":
            return (
                "Кабинет кандидата > Запросы контактов\n\n"
                "✅ Ты одобрил доступ к контактам.\n\n"
                "🏷 *Request ID:* "
                + CandidateProfileMessagesMixin._escape_markdown_text(
                    CandidateProfileMessagesMixin._as_clean_text(result.request_id) or "—"
                )
            )
        if status == "rejected":
            return (
                "Кабинет кандидата > Запросы контактов\n\n"
                "❌ Ты отклонил запрос доступа к контактам.\n\n"
                "🏷 *Request ID:* "
                + CandidateProfileMessagesMixin._escape_markdown_text(
                    CandidateProfileMessagesMixin._as_clean_text(result.request_id) or "—"
                )
            )
        return (
            "Кабинет кандидата > Запросы контактов\n\n"
            "ℹ️ Ответ по запросу контактов сохранен.\n\n"
            "📊 *Статус:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._as_clean_text(result.status) or "—"
            )
            + "\n"
            + "🏷 *Request ID:* "
            + CandidateProfileMessagesMixin._escape_markdown_text(
                CandidateProfileMessagesMixin._as_clean_text(result.request_id) or "—"
            )
        )
