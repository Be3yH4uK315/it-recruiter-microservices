from __future__ import annotations

from app.application.common.contracts import SearchSessionSummary


class BotMessagesMixin:
    def _build_common_help_message(self) -> str:
        return self._build_screen_message(
            section_path="Общие команды · Помощь",
            title="Помощь",
            body_lines=[
                "Команды:",
                "  • `/start` — выбрать роль",
                "  • `/logout` — завершить сессию",
                "  • `/cancel` — отменить текущий сценарий и вернуться в меню",
                "  • `/help` — показать это сообщение",
            ],
            footer="Нажми `/start`, чтобы начать работу.",
        )

    def _build_candidate_help_message(self) -> str:
        return self._build_screen_message(
            section_path="Кабинет кандидата · Помощь",
            title="Помощь кандидату",
            body_lines=[
                "Что можно сделать:",
                "  • Заполнять и обновлять профиль",
                "  • Управлять резюме и аватаром",
                "  • Настроить видимость контактов",
                "  • Отвечать на запросы контактов работодателей",
                "",
                "Команды:",
                "  • `/cancel` — выйти из текущего шага",
                "  • `/logout` — завершить сессию",
            ],
        )

    def _build_employer_help_message(self) -> str:
        return self._build_screen_message(
            section_path="Кабинет работодателя · Помощь",
            title="Помощь работодателю",
            body_lines=[
                "Что можно сделать:",
                "  • Заполнить профиль компании",
                "  • Создавать и вести поисковые сессии",
                "  • Оценивать кандидатов и запрашивать контакты",
                "  • Просматривать избранные и открытые контакты",
                "",
                "Команды:",
                "  • `/cancel` — выйти из текущего шага",
                "  • `/logout` — завершить сессию",
            ],
        )

    def _build_searches_list_message(
        self,
        searches: list[SearchSessionSummary],
        *,
        page: int = 1,
        total_pages: int = 1,
    ) -> str:
        lines = [f"Страница: *{page}/{total_pages}*", ""]
        for index, item in enumerate(searches, start=1):
            lines.append(f"{index}. 🔎 {item.title}")
            lines.append(f"   💼 *Роль:* {item.role or '—'}")
            lines.append(f"   📊 *Статус:* {self._humanize_search_status(item.status)}")
        return self._build_screen_message(
            section_path="Кабинет работодателя · Поиск · Все поиски",
            title="Ваши поисковые сессии",
            body_lines=lines,
        )

    def _build_search_session_status_message(self, search: SearchSessionSummary) -> str:
        return self._build_status_screen(
            section_path="Кабинет работодателя · Поиск · Сессия",
            title="Состояние поиска",
            status_line="✅ Состояние поиска обновлено.",
            details=[
                f"🔎 *Название:* {search.title}",
                f"💼 *Роль:* {search.role or '—'}",
                f"📊 *Статус:* {self._humanize_search_status(search.status)}",
            ],
        )
