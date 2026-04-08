from __future__ import annotations

from app.application.common.contracts import SearchSessionSummary


class BotMessagesMixin:
    def _build_common_help_message(self) -> str:
        return (
            "🆘 Помощь\n\n"
            "Команды:\n"
            "  • /start — выбрать роль\n"
            "  • /logout — завершить сессию\n"
            "  • /cancel — отменить текущий сценарий и вернуться в меню\n"
            "  • /help — показать это сообщение\n\n"
            "Нажми /start, чтобы начать работу."
        )

    def _build_candidate_help_message(self) -> str:
        return (
            "Кабинет кандидата > Помощь\n\n"
            "🧭 Помощь кандидату\n\n"
            "Что можно сделать:\n"
            "  • Заполнять и обновлять профиль\n"
            "  • Управлять резюме и аватаром\n"
            "  • Настроить видимость контактов\n"
            "  • Отвечать на запросы контактов работодателей\n\n"
            "Команды:\n"
            "  • /cancel — выйти из текущего шага\n"
            "  • /logout — завершить сессию"
        )

    def _build_employer_help_message(self) -> str:
        return (
            "Кабинет работодателя > Помощь\n\n"
            "🧭 Помощь работодателю\n\n"
            "Что можно сделать:\n"
            "  • Заполнить профиль компании\n"
            "  • Создавать и вести поисковые сессии\n"
            "  • Оценивать кандидатов и запрашивать контакты\n"
            "  • Просматривать избранные и открытые контакты\n\n"
            "Команды:\n"
            "  • /cancel — выйти из текущего шага\n"
            "  • /logout — завершить сессию"
        )

    def _build_searches_list_message(
        self,
        searches: list[SearchSessionSummary],
        *,
        page: int = 1,
        total_pages: int = 1,
    ) -> str:
        lines = [
            f"Кабинет работодателя > Поиск > Все поиски (стр. {page}/{total_pages})",
            "",
            "🗂 Ваши поисковые сессии:",
            "",
        ]
        for index, item in enumerate(searches, start=1):
            lines.append(f"{index}. 🔎 {item.title}")
            lines.append(f"   💼 Роль: {item.role or '—'}")
            lines.append(f"   📊 Статус: {self._humanize_search_status(item.status)}")
        return "\n".join(lines)

    def _build_search_session_status_message(self, search: SearchSessionSummary) -> str:
        return (
            "Кабинет работодателя > Поиск > Сессия\n\n"
            "✅ Состояние поиска обновлено.\n\n"
            f"🔎 Название: {search.title}\n"
            f"💼 Роль: {search.role or '—'}\n"
            f"📊 Статус: {self._humanize_search_status(search.status)}"
        )
