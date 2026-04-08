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
            "✅ *Профиль работодателя создан.*" if created_now else "✅ *Профиль работодателя активен.*",
            "",
            f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*",
            f"📌 *Статус профиля:* {'создан' if created_now else 'активен'}",
            f"🖼 *Аватар компании:* {'загружен' if employer.avatar_file_id else 'не загружен'}",
            f"📄 *Документ компании:* {'загружен' if employer.document_file_id else 'не загружен'}",
        ]
        return EmployerProfileMessagesMixin._build_screen_message(
            section_path="Кабинет работодателя · Главная",
            title="Главная",
            body_lines=lines,
            footer="Основные действия доступны в кнопках ниже.",
        )

    @staticmethod
    def _build_employer_profile_message(
        *,
        employer: EmployerProfileSummary,
    ) -> str:
        company = (
            EmployerProfileMessagesMixin._as_clean_text(employer.company) or "Компания не указана"
        )
        lines = [f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*", "", "📞 *Контакты компании:*"]
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
        return EmployerProfileMessagesMixin._build_screen_message(
            section_path="Кабинет работодателя · Мой профиль",
            title="Профиль работодателя",
            body_lines=lines,
        )

    @staticmethod
    def _build_employer_stats_message(
        employer: EmployerProfileSummary,
        statistics: EmployerStatisticsView | None,
    ) -> str:
        company = (
            EmployerProfileMessagesMixin._as_clean_text(employer.company) or "Компания не указана"
        )
        lines = [f"🏢 *{EmployerProfileMessagesMixin._escape_markdown_text(company)}*"]
        if statistics is None:
            lines.extend(["", "⚠️ Статистика временно недоступна."])
            return EmployerProfileMessagesMixin._build_screen_message(
                section_path="Кабинет работодателя · Статистика",
                title="Статистика работодателя",
                body_lines=lines,
            )

        lines.extend(
            [
                "",
                f"  • 👀 *Просмотрено кандидатов:* {statistics.total_viewed}",
                f"  • 👍 *Лайков:* {statistics.total_liked}",
                f"  • 🔓 *Запросов контактов:* {statistics.total_contact_requests}",
                f"  • 📇 *Открытых контактов:* {statistics.total_contacts_granted}",
            ]
        )
        return EmployerProfileMessagesMixin._build_screen_message(
            section_path="Кабинет работодателя · Статистика",
            title="Статистика работодателя",
            body_lines=lines,
        )

    @staticmethod
    def _build_contact_access_result_message(result: ContactAccessResultView) -> str:
        status = result.status.strip().lower()

        if status == "granted":
            lines = ["✅ Доступ к контактам открыт."]
            if result.contacts:
                lines.extend(["", "📞 *Контакты:*"])
                lines.extend(
                    EmployerProfileMessagesMixin._build_owner_contact_lines(result.contacts)
                )
            return EmployerProfileMessagesMixin._build_screen_message(
                section_path="Кабинет работодателя · Поиск · Контакты",
                title="Доступ к контактам",
                body_lines=lines,
            )

        if status == "pending":
            return EmployerProfileMessagesMixin._build_screen_message(
                section_path="Кабинет работодателя · Поиск · Контакты",
                title="Доступ к контактам",
                body_lines=[
                    "⏳ Запрос на контакты отправлен кандидату.",
                    "",
                    "Когда кандидат ответит, статус можно будет увидеть в сервисе работодателя.",
                ],
            )

        if status == "rejected":
            return EmployerProfileMessagesMixin._build_screen_message(
                section_path="Кабинет работодателя · Поиск · Контакты",
                title="Доступ к контактам",
                body_lines=["❌ Кандидат не предоставляет контакты по этому запросу."],
            )

        return EmployerProfileMessagesMixin._build_screen_message(
            section_path="Кабинет работодателя · Поиск · Контакты",
            title="Доступ к контактам",
            body_lines=["⚠️ Не удалось получить контакты."],
        )
