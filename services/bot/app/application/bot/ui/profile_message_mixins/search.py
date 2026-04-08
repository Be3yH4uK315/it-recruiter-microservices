from __future__ import annotations

from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import CandidateProfileSummary, NextCandidateResultView


class SearchProfileMessagesMixin(ProfileSharedMessagesMixin):
    @staticmethod
    def _build_candidate_collection_message(
        *,
        title: str,
        items: list[CandidateProfileSummary],
    ) -> str:
        if not items:
            return f"{title}\n\n🗂 Пока пусто."

        lines = [title, ""]
        for index, item in enumerate(items[:20], start=1):
            display_name = (
                SearchProfileMessagesMixin._as_clean_text(item.display_name) or "Имя не указано"
            )
            headline_role = (
                SearchProfileMessagesMixin._as_clean_text(item.headline_role) or "Не указана роль"
            )
            lines.append(
                f"{index}. 👤 *{SearchProfileMessagesMixin._escape_markdown_text(display_name)}* — "
                f"{SearchProfileMessagesMixin._escape_markdown_text(headline_role)}"
            )
            if item.location:
                lines.append(
                    "   📍 *Локация:* "
                    + SearchProfileMessagesMixin._escape_markdown_text(item.location)
                )
            if item.work_modes:
                lines.append(
                    "   💻 *Формат:* "
                    + ", ".join(
                        SearchProfileMessagesMixin._humanize_work_mode(mode)
                        for mode in item.work_modes
                    )
                )
            if item.salary_min is not None or item.salary_max is not None:
                lines.append(
                    "   💰 *Ожидания:* "
                    + SearchProfileMessagesMixin._format_candidate_salary_expectations(item)
                )
            skills_preview = SearchProfileMessagesMixin._build_skills_preview(item.skills, limit=3)
            if skills_preview:
                lines.append(
                    "   🛠 *Навыки:* "
                    + SearchProfileMessagesMixin._escape_markdown_text(skills_preview)
                )
            if item.contacts and item.can_view_contacts:
                contact_parts = SearchProfileMessagesMixin._build_owner_contact_lines(item.contacts)
                if contact_parts:
                    lines.append("   📞 *Контакты:*")
                    for part in contact_parts[:3]:
                        lines.append(f"   {part}")
            elif item.contacts_visibility:
                lines.append(
                    "   👁 *Контакты:* "
                    + SearchProfileMessagesMixin._humanize_contacts_visibility_for_profile(
                        item.contacts_visibility
                    )
                )
        return "\n".join(lines)

    @staticmethod
    def _build_next_candidate_message(result: NextCandidateResultView) -> str:
        if result.candidate is None:
            if result.is_degraded:
                return "Кабинет работодателя > Поиск > Карточка кандидата\n\n" + (
                    "⚠️ Поиск временно ограничен.\n\n"
                    + (
                        result.message
                        or (
                            "Подбор временно недоступен (degraded). "
                            "Нажми «Следующий кандидат», чтобы повторить."
                        )
                    )
                )
            return (
                "Кабинет работодателя > Поиск > Карточка кандидата\n\n"
                + "📭 Кандидаты по этому поиску закончились.\n\n"
                + (result.message or "Попробуй скорректировать фильтры или открыть другой поиск.")
            )

        candidate = result.candidate
        lines = [
            "Кабинет работодателя > Поиск > Карточка кандидата",
            "",
        ]
        lines.extend(
            SearchProfileMessagesMixin._build_candidate_profile_core_lines(
                candidate,
                about_limit=600,
            )
        )
        lines.extend(
            [""]
            + SearchProfileMessagesMixin._build_candidate_contacts_block_lines(
                contacts=candidate.contacts,
                contacts_visibility=candidate.contacts_visibility,
                can_view_contacts=bool(candidate.can_view_contacts),
                contacts_title="📞 *Контакты:*",
            )
        )

        return "\n".join(lines)
