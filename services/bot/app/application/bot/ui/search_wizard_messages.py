from __future__ import annotations

from app.application.bot.constants import CURRENCY_SYMBOLS


class BotSearchWizardMessagesMixin:
    @staticmethod
    def _escape_markdown_text(value: object) -> str:
        normalized = str(value).strip()
        escaped = normalized.replace("\\", "\\\\")
        for char in ("_", "*", "[", "]", "`"):
            escaped = escaped.replace(char, f"\\{char}")
        return escaped or "—"

    @staticmethod
    def _format_search_experience_value(value: object | None) -> str:
        if value is None:
            return "—"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _build_employer_search_filters_summary(self, payload: dict) -> str:
        title = str(payload.get("title", "")).strip()
        role = str(payload.get("role", "")).strip()
        must_skills = (
            payload.get("must_skills") if isinstance(payload.get("must_skills"), list) else []
        )
        nice_skills = (
            payload.get("nice_skills") if isinstance(payload.get("nice_skills"), list) else []
        )
        experience_min = payload.get("experience_min")
        experience_max = payload.get("experience_max")
        location = payload.get("location")
        work_modes = (
            payload.get("work_modes") if isinstance(payload.get("work_modes"), list) else []
        )
        salary_min = payload.get("salary_min")
        salary_max = payload.get("salary_max")
        currency = payload.get("currency")
        english = payload.get("english_level")
        about_me = payload.get("about_me")
        must_skills_text = self._format_search_skills_for_summary(must_skills)
        nice_skills_text = self._format_search_skills_for_summary(nice_skills)
        salary_text = "—"
        currency_code = str(currency or "").strip().upper()
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
        if salary_min is not None or salary_max is not None:
            min_text = (
                self._format_number_with_spaces(int(salary_min))
                if isinstance(salary_min, int)
                else str(salary_min if salary_min is not None else "—")
            )
            max_text = (
                self._format_number_with_spaces(int(salary_max))
                if isinstance(salary_max, int)
                else str(salary_max if salary_max is not None else "—")
            )
            salary_text = f"{min_text} – {max_text}"
            if currency_symbol:
                salary_text = f"{salary_text} {currency_symbol}"
        about_text = str(about_me).strip() if about_me is not None else ""
        if len(about_text) > 180:
            about_text = f"{about_text[:180].rstrip()}…"
        work_modes_text = ", ".join(
            self._humanize_work_mode(str(item)) for item in work_modes if str(item).strip()
        )
        experience_min_text = self._escape_markdown_text(
            self._format_search_experience_value(experience_min)
        )
        experience_max_text = self._escape_markdown_text(
            self._format_search_experience_value(experience_max)
        )

        return (
            "🧾 Проверь параметры поиска:\n\n"
            f"🔎 *Название:* {self._escape_markdown_text(title or '—')}\n"
            f"💼 *Роль:* {self._escape_markdown_text(role or '—')}\n\n"
            f"🧠 *Обязательные навыки:* {self._escape_markdown_text(must_skills_text)}\n"
            f"🛠 *Желательные навыки:* {self._escape_markdown_text(nice_skills_text)}\n"
            f"📈 *Опыт:* {experience_min_text} – {experience_max_text}\n"
            f"📍 *Локация:* {self._escape_markdown_text(location or '—')}\n"
            f"💻 *Формат работы:* {self._escape_markdown_text(work_modes_text or '—')}\n"
            f"💰 *Зарплата:* {self._escape_markdown_text(salary_text)}\n"
            f"🇬🇧 *Английский:* {self._escape_markdown_text(english or '—')}\n"
            f"📝 *Подсказка по кандидату:* {self._escape_markdown_text(about_text or '—')}"
        )

    @staticmethod
    def _format_search_skills_for_summary(skills: list[object]) -> str:
        formatted: list[str] = []
        for item in skills:
            if not isinstance(item, dict):
                continue
            skill = str(item.get("skill") or "").strip()
            if not skill:
                continue
            level = item.get("level")
            if isinstance(level, int):
                formatted.append(f"{skill}:{level}")
            else:
                formatted.append(skill)

        if not formatted:
            return "—"
        if len(formatted) <= 8:
            return ", ".join(formatted)
        visible = ", ".join(formatted[:8])
        return f"{visible} (+{len(formatted) - 8})"

    def _build_employer_search_step_current_value(self, payload: dict, step: str) -> str:
        if step == "title":
            return self._escape_markdown_text(payload.get("title") or "—")
        if step == "role":
            return self._escape_markdown_text(payload.get("role") or "—")
        if step in {"must_skills", "nice_skills"}:
            skills = payload.get(step)
            if not isinstance(skills, list) or not skills:
                return "—"
            formatted: list[str] = []
            for item in skills:
                if not isinstance(item, dict):
                    continue
                skill = str(item.get("skill") or "").strip()
                if not skill:
                    continue
                level = item.get("level")
                if isinstance(level, int):
                    formatted.append(f"{skill}:{level}")
                else:
                    formatted.append(skill)
            return self._escape_markdown_text(", ".join(formatted) if formatted else "—")
        if step == "experience":
            min_value = payload.get("experience_min")
            max_value = payload.get("experience_max")
            if min_value is None and max_value is None:
                return "—"
            return (
                f"{self._escape_markdown_text(self._format_search_experience_value(min_value))} – "
                f"{self._escape_markdown_text(self._format_search_experience_value(max_value))}"
            )
        if step == "location":
            return self._escape_markdown_text(payload.get("location") or "—")
        if step == "work_modes":
            work_modes = payload.get("work_modes")
            if not isinstance(work_modes, list) or not work_modes:
                return "—"
            return self._escape_markdown_text(
                ", ".join(
                    self._humanize_work_mode(str(item)) for item in work_modes if str(item).strip()
                )
                or "—"
            )
        if step == "salary":
            salary_min = payload.get("salary_min")
            salary_max = payload.get("salary_max")
            currency = payload.get("currency")
            if salary_min is None and salary_max is None:
                return "—"
            currency_code = str(currency or "").strip().upper()
            currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
            min_text = (
                self._format_number_with_spaces(int(salary_min))
                if isinstance(salary_min, int)
                else str(salary_min if salary_min is not None else "—")
            )
            max_text = (
                self._format_number_with_spaces(int(salary_max))
                if isinstance(salary_max, int)
                else str(salary_max if salary_max is not None else "—")
            )
            return self._escape_markdown_text(
                (f"{min_text} – {max_text} " f"{currency_symbol}").rstrip()
            )
        if step == "english":
            return self._escape_markdown_text(payload.get("english_level") or "—")
        if step == "about":
            return self._escape_markdown_text(payload.get("about_me") or "—")
        return "—"
