from __future__ import annotations

from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import (
    ContactAccessResultView,
    EmployerProfileSummary,
    EmployerStatisticsView,
)


class EmployerProfileMessagesMixin(ProfileSharedMessagesMixin):
    @staticmethod
    def _build_employer_dashboard_message(
        *,
        first_name: str | None,
        employer: EmployerProfileSummary,
        statistics: EmployerStatisticsView | None,
        created_now: bool,
    ) -> str:
        company = (
            EmployerProfileMessagesMixin._as_clean_text(employer.company) or "Компания не указана"
        )
        lines = [
            "Кабинет работодателя > Главная",
            "",
            f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*",
            "",
            f"📌 *Статус профиля:* {'✅ Создан' if created_now else '✅ Активен'}",
            "",
            f"🖼 *Аватар компании:* {'загружен' if employer.avatar_file_id else 'не загружен'}",
            "",
            f"📄 *Документ компании:* {'загружен' if employer.document_file_id else 'не загружен'}",
            "",
            "Основные действия доступны в кнопках ниже.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_employer_profile_message(
        *,
        employer: EmployerProfileSummary,
    ) -> str:
        company = (
            EmployerProfileMessagesMixin._as_clean_text(employer.company) or "Компания не указана"
        )
        lines = [
            "Кабинет работодателя > Мой профиль",
            "",
            f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*",
            "",
            "📞 *Контакты компании:*",
        ]
        contact_lines = EmployerProfileMessagesMixin._build_owner_contact_lines(employer.contacts)
        if contact_lines:
            lines.extend(contact_lines)
        else:
            lines.append("  • Не заполнены")

        lines.extend(
            [
                "",
                f"🖼 *Аватар компании:* {'загружен' if employer.avatar_file_id else 'не загружен'}",
                (
                    "📄 *Документ компании:* "
                    f"{'загружен' if employer.document_file_id else 'не загружен'}"
                ),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _build_employer_stats_message(
        employer: EmployerProfileSummary,
        statistics: EmployerStatisticsView | None,
    ) -> str:
        company = (
            EmployerProfileMessagesMixin._as_clean_text(employer.company) or "Компания не указана"
        )
        lines = [
            "Кабинет работодателя > Статистика",
            "",
            "📊 Статистика работодателя",
            "",
            f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*",
        ]
        if statistics is None:
            lines.extend(["", "⚠️ Статистика временно недоступна."])
            return "\n".join(lines)

        lines.extend(
            [
                "",
                f"  • 👀 *Просмотрено кандидатов:* {statistics.total_viewed}",
                f"  • 👍 *Лайков:* {statistics.total_liked}",
                f"  • 🔓 *Запросов контактов:* {statistics.total_contact_requests}",
                f"  • 📇 *Открытых контактов:* {statistics.total_contacts_granted}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _build_contact_access_result_message(result: ContactAccessResultView) -> str:
        status = result.status.strip().lower()

        if status == "granted":
            lines = [
                "Кабинет работодателя > Поиск > Контакты",
                "",
                "✅ Доступ к контактам открыт.",
            ]
            if result.contacts:
                lines.extend(["", "📞 *Контакты:*"])
                lines.extend(
                    EmployerProfileMessagesMixin._build_owner_contact_lines(result.contacts)
                )
            return "\n".join(lines)

        if status == "pending":
            return (
                "Кабинет работодателя > Поиск > Контакты\n\n"
                "⏳ Запрос на контакты отправлен кандидату.\n\n"
                "Когда кандидат ответит, статус можно будет увидеть в сервисе работодателя."
            )

        if status == "rejected":
            return (
                "Кабинет работодателя > Поиск > Контакты\n\n"
                "❌ Кандидат не предоставляет контакты по этому запросу."
            )

        return "Кабинет работодателя > Поиск > Контакты\n\n⚠️ Не удалось получить контакты."
