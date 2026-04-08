from __future__ import annotations

import re
from uuid import UUID, uuid4

from app.application.bot.constants import (
    EMPLOYER_SEARCH_ABOUT_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MAX_LEN,
    EMPLOYER_SEARCH_TITLE_MAX_LEN,
    ROLE_EMPLOYER,
    STATE_EMPLOYER_SEARCH_ABOUT,
    STATE_EMPLOYER_SEARCH_CONFIRM,
    STATE_EMPLOYER_SEARCH_ENGLISH,
    STATE_EMPLOYER_SEARCH_EXPERIENCE,
    STATE_EMPLOYER_SEARCH_LOCATION,
    STATE_EMPLOYER_SEARCH_MUST_SKILLS,
    STATE_EMPLOYER_SEARCH_NICE_SKILLS,
    STATE_EMPLOYER_SEARCH_ROLE,
    STATE_EMPLOYER_SEARCH_SALARY,
    STATE_EMPLOYER_SEARCH_TITLE,
    STATE_EMPLOYER_SEARCH_WORK_MODES,
)


class SearchUtilsMixin:
    _OPEN_RANGE_DASHES = ("–", "—")

    def _build_idempotency_key(
        self,
        *,
        telegram_user_id: int,
        operation: str,
        resource_id: UUID | None = None,
    ) -> str:
        resource_part = str(resource_id) if resource_id is not None else "none"
        return f"bot:{telegram_user_id}:{operation}:{resource_part}:{uuid4()}"

    @staticmethod
    def _normalize_optional_user_input(value: str) -> str | None:
        normalized = value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return None
        return normalized or None

    @staticmethod
    def _get_employer_search_wizard_step_config(step: str) -> dict[str, object] | None:
        return {
            "title": {
                "state_key": STATE_EMPLOYER_SEARCH_TITLE,
                "prompt": "Введи название поиска. Например: Python backend middle.",
                "allow_skip": False,
                "allow_back": False,
            },
            "role": {
                "state_key": STATE_EMPLOYER_SEARCH_ROLE,
                "prompt": "Введи основную роль поиска. Например: Python Backend Developer.",
                "allow_skip": False,
                "allow_back": True,
            },
            "must_skills": {
                "state_key": STATE_EMPLOYER_SEARCH_MUST_SKILLS,
                "prompt": (
                    "Введи обязательные навыки через запятую.\n"
                    "Можно указать уровень: `Python:4, FastAPI:3`.\n"
                    "Чтобы пропустить шаг, отправь `-`."
                ),
                "parse_mode": "Markdown",
                "allow_skip": True,
                "allow_back": True,
            },
            "nice_skills": {
                "state_key": STATE_EMPLOYER_SEARCH_NICE_SKILLS,
                "prompt": (
                    "Введи желательные навыки через запятую.\n"
                    "Пример: `Docker:3, AWS`.\n"
                    "Чтобы пропустить шаг, отправь `-`."
                ),
                "parse_mode": "Markdown",
                "allow_skip": True,
                "allow_back": True,
            },
            "experience": {
                "state_key": STATE_EMPLOYER_SEARCH_EXPERIENCE,
                "prompt": SearchUtilsMixin._build_search_experience_prompt(),
                "parse_mode": "Markdown",
                "allow_skip": True,
                "allow_back": True,
            },
            "location": {
                "state_key": STATE_EMPLOYER_SEARCH_LOCATION,
                "prompt": "Введи желаемую локацию (город или страна) или `-`, чтобы пропустить.",
                "allow_skip": True,
                "allow_back": True,
            },
            "work_modes": {
                "state_key": STATE_EMPLOYER_SEARCH_WORK_MODES,
                "prompt": "Выбери режимы работы кнопками ниже.",
                "allow_skip": True,
                "allow_back": True,
            },
            "salary": {
                "state_key": STATE_EMPLOYER_SEARCH_SALARY,
                "prompt": SearchUtilsMixin._build_search_salary_prompt(),
                "parse_mode": "Markdown",
                "allow_skip": True,
                "allow_back": True,
            },
            "english": {
                "state_key": STATE_EMPLOYER_SEARCH_ENGLISH,
                "prompt": "Выбери уровень английского кнопками ниже.",
                "allow_skip": True,
                "allow_back": True,
            },
            "about": {
                "state_key": STATE_EMPLOYER_SEARCH_ABOUT,
                "prompt": (
                    "Коротко опиши портрет кандидата или задачи команды.\n"
                    "Чтобы пропустить шаг, отправь `-`."
                ),
                "parse_mode": "Markdown",
                "allow_skip": True,
                "allow_back": True,
            },
        }.get(step)

    @staticmethod
    def _parse_search_skill_list(raw_value: str) -> list[dict[str, object]] | None:
        normalized = SearchUtilsMixin._normalize_optional_user_input(raw_value)
        if normalized is None:
            return []

        result: list[dict[str, object]] = []
        for part in normalized.split(","):
            item = part.strip()
            if not item:
                continue
            skill_name = item
            level: int | None = None
            if ":" in item:
                left, right = item.split(":", 1)
                skill_name = left.strip()
                level_text = right.strip()
                if not level_text:
                    return None
                try:
                    parsed_level = int(level_text)
                except ValueError:
                    return None
                if parsed_level < 1 or parsed_level > 5:
                    return None
                level = parsed_level

            if not skill_name:
                return None

            payload: dict[str, object] = {"skill": skill_name}
            if level is not None:
                payload["level"] = level
            result.append(payload)

        return result

    @staticmethod
    def _parse_search_experience_range(raw_value: str) -> tuple[float | None, float | None] | None:
        normalized = SearchUtilsMixin._normalize_optional_user_input(raw_value)
        if normalized is None:
            return (None, None)

        compact = SearchUtilsMixin._normalize_search_range_input(normalized)
        parsed = SearchUtilsMixin._parse_numeric_bounds(
            compact,
            number_pattern=r"\d+(?:[.,]\d+)?",
            from_keyword="от",
            to_keyword="до",
            cast=lambda value: float(value.replace(",", ".")),
        )
        if parsed is None:
            return None
        min_value, max_value = parsed
        if min_value is not None and min_value < 0:
            return None
        if max_value is not None and max_value < 0:
            return None
        if min_value is not None and max_value is not None and max_value < min_value:
            return None
        return (min_value, max_value)

    @staticmethod
    def _parse_search_work_modes(raw_value: str) -> list[str] | None:
        normalized = SearchUtilsMixin._normalize_optional_user_input(raw_value)
        if normalized is None:
            return []
        allowed = {"remote", "onsite", "hybrid"}
        result: list[str] = []
        for part in normalized.split(","):
            mode = part.strip().lower()
            if not mode:
                continue
            if mode not in allowed:
                return None
            if mode not in result:
                result.append(mode)
        return result

    @staticmethod
    def _parse_search_salary(raw_value: str) -> tuple[int | None, int | None, str | None] | None:
        normalized = SearchUtilsMixin._normalize_optional_user_input(raw_value)
        if normalized is None:
            return (None, None, None)

        compact = SearchUtilsMixin._normalize_search_range_input(normalized)
        currency_match = re.search(r"\s+([A-Za-z]{3,16})\s*$", compact)
        currency: str | None = None
        if currency_match is not None:
            currency = currency_match.group(1).upper()
            compact = compact[: currency_match.start()].strip()

        spaced_range_match = re.fullmatch(r"(?P<left>\d+)\s+(?P<right>\d+)", compact)
        if spaced_range_match is not None:
            min_salary = int(spaced_range_match.group("left"))
            max_salary = int(spaced_range_match.group("right"))
            if max_salary < min_salary:
                return None
            if currency is None:
                currency = "RUB"
            return (min_salary, max_salary, currency)

        parsed = SearchUtilsMixin._parse_numeric_bounds(
            compact,
            number_pattern=r"\d+",
            from_keyword="от",
            to_keyword="до",
            cast=int,
        )
        if parsed is None:
            return None

        min_salary, max_salary = parsed
        if min_salary is not None and min_salary < 0:
            return None
        if max_salary is not None and max_salary < 0:
            return None
        if min_salary is not None and max_salary is not None and max_salary < min_salary:
            return None
        if currency is None and (min_salary is not None or max_salary is not None):
            currency = "RUB"
        return (min_salary, max_salary, currency)

    @staticmethod
    def _normalize_search_range_input(value: str) -> str:
        normalized = value
        for dash in SearchUtilsMixin._OPEN_RANGE_DASHES:
            normalized = normalized.replace(dash, "-")
        return re.sub(r"\s+", " ", normalized.strip())

    @staticmethod
    def _parse_numeric_bounds(
        value: str,
        *,
        number_pattern: str,
        from_keyword: str,
        to_keyword: str,
        cast,
    ) -> tuple[object | None, object | None] | None:
        from_to_match = re.fullmatch(
            rf"{from_keyword}\s+(?P<left>{number_pattern})\s+{to_keyword}\s+(?P<right>{number_pattern})",
            value,
            flags=re.IGNORECASE,
        )
        if from_to_match is not None:
            return (
                cast(from_to_match.group("left")),
                cast(from_to_match.group("right")),
            )

        range_match = re.fullmatch(
            rf"(?P<left>{number_pattern})\s*-\s*(?P<right>{number_pattern})",
            value,
            flags=re.IGNORECASE,
        )
        if range_match is not None:
            return (
                cast(range_match.group("left")),
                cast(range_match.group("right")),
            )

        lower_only_keyword_match = re.fullmatch(
            rf"{from_keyword}\s+(?P<left>{number_pattern})",
            value,
            flags=re.IGNORECASE,
        )
        if lower_only_keyword_match is not None:
            return (cast(lower_only_keyword_match.group("left")), None)

        lower_only_dash_match = re.fullmatch(
            rf"(?P<left>{number_pattern})\s*-\s*",
            value,
            flags=re.IGNORECASE,
        )
        if lower_only_dash_match is not None:
            return (cast(lower_only_dash_match.group("left")), None)

        upper_only_keyword_match = re.fullmatch(
            rf"{to_keyword}\s+(?P<right>{number_pattern})",
            value,
            flags=re.IGNORECASE,
        )
        if upper_only_keyword_match is not None:
            return (None, cast(upper_only_keyword_match.group("right")))

        upper_only_dash_match = re.fullmatch(
            rf"-\s*(?P<right>{number_pattern})",
            value,
            flags=re.IGNORECASE,
        )
        if upper_only_dash_match is not None:
            return (None, cast(upper_only_dash_match.group("right")))

        return None

    @staticmethod
    def _build_search_experience_prompt() -> str:
        return (
            "🧭 *Мастер поиска*\n\n"
            "*Введи опыт*\n\n"
            "Можно указать диапазон, только минимум или только максимум.\n\n"
            "Примеры:\n"
            "`2-5`\n"
            "`от 2`\n"
            "`до 5`\n\n"
            "Чтобы пропустить шаг, отправь `-`."
        )

    @staticmethod
    def _build_search_experience_invalid_text() -> str:
        return (
            "⚠️ *Неверный формат опыта*\n\n"
            "Используй один из вариантов:\n"
            "`2-5`\n"
            "`от 2`\n"
            "`до 5`\n\n"
            "Или отправь `-`, чтобы пропустить шаг."
        )

    @staticmethod
    def _build_search_salary_prompt() -> str:
        return (
            "🧭 *Мастер поиска*\n\n"
            "*Введи зарплату*\n\n"
            "Можно указать диапазон, только минимум или только максимум.\n\n"
            "Примеры:\n"
            "`150000 250000 RUB`\n"
            "`от 150000 RUB`\n"
            "`до 250000 RUB`\n\n"
            "Чтобы пропустить шаг, отправь `-`."
        )

    @staticmethod
    def _build_search_salary_invalid_text() -> str:
        return (
            "⚠️ *Неверный формат зарплаты*\n\n"
            "Используй один из вариантов:\n"
            "`150000 250000 RUB`\n"
            "`от 150000 RUB`\n"
            "`до 250000 RUB`\n\n"
            "Или отправь `-`, чтобы пропустить шаг."
        )

    @staticmethod
    def _set_employer_search_edit_step(payload: dict, *, step: str) -> None:
        payload["_employer_search_edit_step"] = step.strip().lower()

    @staticmethod
    def _get_employer_search_edit_step(payload: dict) -> str | None:
        value = payload.get("_employer_search_edit_step")
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    @staticmethod
    def _is_employer_search_edit_step(payload: dict, *, step: str) -> bool:
        return SearchUtilsMixin._get_employer_search_edit_step(payload) == step.strip().lower()

    @staticmethod
    def _clear_employer_search_edit_step(payload: dict) -> None:
        payload.pop("_employer_search_edit_step", None)

    async def _render_employer_search_confirm_step(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        payload: dict,
    ) -> None:
        self._clear_employer_search_edit_step(payload)
        await self._set_state_and_render_wizard_step(
            telegram_user_id=telegram_user_id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_CONFIRM,
            payload=payload,
            chat_id=chat_id,
            text="Кабинет работодателя > Поиск > Новый поиск > Подтверждение\n\n"
            + self._build_employer_search_filters_summary(payload),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_create_confirm_markup(telegram_user_id),
        )

    @staticmethod
    def _parse_search_english_level(raw_value: str) -> str | None:
        normalized = SearchUtilsMixin._normalize_optional_user_input(raw_value)
        if normalized is None:
            return None
        level = normalized.upper()
        if level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            return None
        return level

    @staticmethod
    def _validate_employer_search_draft(payload: dict) -> str | None:
        title = str(payload.get("title", "")).strip()
        role = str(payload.get("role", "")).strip()
        if not title:
            return "Введи название поиска."
        if not role:
            return "Введи роль для поиска."
        if len(title) > EMPLOYER_SEARCH_TITLE_MAX_LEN:
            return f"Название поиска слишком длинное (максимум {EMPLOYER_SEARCH_TITLE_MAX_LEN})."
        if len(role) > EMPLOYER_SEARCH_ROLE_MAX_LEN:
            return f"Роль слишком длинная (максимум {EMPLOYER_SEARCH_ROLE_MAX_LEN})."

        for skills_key in ("must_skills", "nice_skills"):
            skills = payload.get(skills_key)
            if skills is None:
                continue
            if not isinstance(skills, list):
                return "Список навыков заполнен некорректно."
            for item in skills:
                if not isinstance(item, dict):
                    return "Список навыков заполнен некорректно."
                skill = str(item.get("skill", "")).strip()
                if not skill:
                    return "В навыках есть пустое значение."
                level = item.get("level")
                if level is not None and (not isinstance(level, int) or level < 1 or level > 5):
                    return "Уровень навыка должен быть от 1 до 5."

        experience_min = payload.get("experience_min")
        experience_max = payload.get("experience_max")
        if experience_min is not None and not isinstance(experience_min, (int, float)):
            return "Минимальный опыт заполнен некорректно."
        if experience_max is not None and not isinstance(experience_max, (int, float)):
            return "Максимальный опыт заполнен некорректно."
        if isinstance(experience_min, (int, float)) and isinstance(experience_max, (int, float)):
            if experience_min < 0 or experience_max < 0 or experience_max < experience_min:
                return "Диапазон опыта заполнен некорректно."

        work_modes = payload.get("work_modes")
        if work_modes is not None:
            if not isinstance(work_modes, list):
                return "Формат работы заполнен некорректно."
            allowed_work_modes = {"remote", "onsite", "hybrid"}
            for item in work_modes:
                if str(item).strip().lower() not in allowed_work_modes:
                    return "В формате работы есть неподдерживаемое значение."

        salary_min = payload.get("salary_min")
        salary_max = payload.get("salary_max")
        if salary_min is not None and not isinstance(salary_min, int):
            return "Минимальная зарплата заполнена некорректно."
        if salary_max is not None and not isinstance(salary_max, int):
            return "Максимальная зарплата заполнена некорректно."
        if isinstance(salary_min, int) and salary_min < 0:
            return "Минимальная зарплата не может быть отрицательной."
        if isinstance(salary_max, int) and salary_max < 0:
            return "Максимальная зарплата не может быть отрицательной."
        if isinstance(salary_min, int) and isinstance(salary_max, int) and salary_max < salary_min:
            return "Диапазон зарплаты заполнен некорректно."

        english_level = payload.get("english_level")
        if english_level is not None and str(english_level).strip().upper() not in {
            "A1",
            "A2",
            "B1",
            "B2",
            "C1",
            "C2",
        }:
            return "Уровень английского заполнен некорректно."

        about_me = payload.get("about_me")
        if about_me is not None:
            about_value = str(about_me).strip()
            if len(about_value) > EMPLOYER_SEARCH_ABOUT_MAX_LEN:
                return f"Описание слишком длинное (максимум {EMPLOYER_SEARCH_ABOUT_MAX_LEN})."

        return None

    @staticmethod
    def _build_employer_search_filters_payload(payload: dict) -> dict[str, object]:
        location_raw = payload.get("location")
        location = str(location_raw).strip() if location_raw is not None else None
        about_raw = payload.get("about_me")
        about_me = str(about_raw).strip() if about_raw is not None else None
        currency_raw = payload.get("currency")
        currency = str(currency_raw).strip().upper() if currency_raw is not None else None

        must_skills = payload.get("must_skills")
        nice_skills = payload.get("nice_skills")
        work_modes = payload.get("work_modes")
        filters: dict[str, object] = {
            "role": str(payload.get("role", "")).strip(),
            "must_skills": must_skills if isinstance(must_skills, list) else [],
            "nice_skills": nice_skills if isinstance(nice_skills, list) else [],
            "experience_min": payload.get("experience_min"),
            "experience_max": payload.get("experience_max"),
            "location": location or None,
            "work_modes": work_modes if isinstance(work_modes, list) else [],
            "exclude_ids": [],
            "salary_min": payload.get("salary_min"),
            "salary_max": payload.get("salary_max"),
            "currency": currency or None,
            "english_level": payload.get("english_level"),
            "about_me": about_me or None,
        }
        return filters

    @staticmethod
    def _normalize_search_status(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized or None

    @classmethod
    def _is_search_active(cls, status: str | None) -> bool:
        normalized = cls._normalize_search_status(status)
        if normalized is None:
            return True
        return normalized in {"active", "open", "running"}

    @classmethod
    def _is_search_paused(cls, status: str | None) -> bool:
        normalized = cls._normalize_search_status(status)
        return normalized == "paused"

    @classmethod
    def _is_search_closed(cls, status: str | None) -> bool:
        normalized = cls._normalize_search_status(status)
        return normalized in {"closed", "archived", "completed"}
