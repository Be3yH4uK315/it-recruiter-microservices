from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from app.application.common.contracts import UNSET
from app.application.common.gateway_errors import CandidateGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramUser

logger = get_logger(__name__)


class CandidateProfileSubmitHandlersMixin:
    async def _handle_candidate_edit_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        field_name: str,
        raw_value: object | None,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate edit load profile failed",
                extra={"telegram_user_id": actor.id, "field_name": field_name},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
            )
            return {"status": "processed", "action": "candidate_not_found"}

        normalized_value = raw_value.strip() if isinstance(raw_value, str) else raw_value
        if (
            field_name in {"display_name", "headline_role"}
            and isinstance(normalized_value, str)
            and not normalized_value
        ):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Пустое значение сохранить нельзя. "
                    "Введи текст или отправь `-`, чтобы очистить поле."
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_edit_empty_value"}
        if field_name == "display_name":
            normalized_value, error_text = self._normalize_profile_name_value(
                raw_value=normalized_value if isinstance(normalized_value, str) else None,
                field_label="Отображаемое имя",
            )
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                )
                return {"status": "processed", "action": "candidate_edit_display_name_invalid"}

        update_kwargs: dict[str, object] = {
            "display_name": UNSET,
            "headline_role": UNSET,
            "location": UNSET,
            "work_modes": UNSET,
            "about_me": UNSET,
            "contacts_visibility": UNSET,
            "contacts": UNSET,
            "status": UNSET,
            "salary_min": UNSET,
            "salary_max": UNSET,
            "currency": UNSET,
            "english_level": UNSET,
            "skills": UNSET,
        }
        if field_name not in update_kwargs:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Неизвестное поле редактирования. Нажми /start, чтобы открыть меню заново.",
            )
            return {"status": "processed", "action": "candidate_edit_invalid_field"}

        update_kwargs[field_name] = normalized_value
        idempotency_key = self._build_idempotency_key(
            telegram_user_id=actor.id,
            operation="candidate.profile.update",
            resource_id=candidate.id,
        )

        try:
            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.update_candidate_profile(
                    access_token=token,
                    candidate_id=candidate.id,
                    display_name=update_kwargs["display_name"],
                    headline_role=update_kwargs["headline_role"],
                    location=update_kwargs["location"],
                    work_modes=update_kwargs["work_modes"],
                    about_me=update_kwargs["about_me"],
                    contacts_visibility=update_kwargs["contacts_visibility"],
                    contacts=update_kwargs["contacts"],
                    status=update_kwargs["status"],
                    salary_min=update_kwargs["salary_min"],
                    salary_max=update_kwargs["salary_max"],
                    currency=update_kwargs["currency"],
                    english_level=update_kwargs["english_level"],
                    skills=update_kwargs["skills"],
                    idempotency_key=idempotency_key,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate edit update failed",
                extra={
                    "telegram_user_id": actor.id,
                    "candidate_id": str(candidate.id),
                    "field_name": field_name,
                },
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=updated.id,
        )

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": f"candidate_edit_{field_name}_saved"}

    async def _handle_candidate_salary_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_value: str,
    ) -> dict:
        normalized = raw_value.strip()

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate salary edit load profile failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
            )
            return {"status": "processed", "action": "candidate_not_found"}

        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            salary_min = None
            salary_max = None
            currency = None
        else:
            parsed_salary = self._parse_search_salary(normalized)
            if parsed_salary is None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Введи зарплату в формате `min max currency`, например `250000 350000 RUB`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_salary_invalid"}
            salary_min, salary_max, currency = parsed_salary
            if salary_min < 0 or salary_max < 0 or salary_max < salary_min:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Проверь значения: `min` и `max` не могут быть отрицательными, а `max` должен быть не меньше `min`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_salary_invalid"}
            if currency is not None and (len(currency) < 3 or len(currency) > 5):
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Валюта должна быть кодом вроде `RUB`, `USD` или `EUR`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_salary_invalid"}

        idempotency_key = self._build_idempotency_key(
            telegram_user_id=actor.id,
            operation="candidate.salary.update",
            resource_id=candidate.id,
        )
        try:
            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.update_candidate_profile(
                    access_token=token,
                    candidate_id=candidate.id,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    idempotency_key=idempotency_key,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate salary edit update failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=updated.id,
        )

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": "candidate_edit_salary_saved"}

    async def _handle_candidate_skills_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_value: str,
    ) -> dict:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return await self._update_candidate_section_payload(
                actor=actor,
                chat_id=chat_id,
                operation="candidate.skills.update",
                update_kwargs={"skills": []},
                action_name="candidate_edit_skills_saved",
            )

        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Добавь хотя бы одну строку навыка или отправь `-`, чтобы очистить список.",
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_edit_skills_invalid"}

        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            if len(parts) < 2:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: используй формат `skill; kind; level`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_skills_invalid"}

            skill = parts[0]
            kind = parts[1].lower()
            level_raw = parts[2] if len(parts) == 3 else ""

            if not skill:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: skill не может быть пустым.",
                )
                return {"status": "processed", "action": "candidate_edit_skills_invalid"}
            if kind not in {"hard", "soft", "tool", "language"}:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: kind должен быть `hard`, `soft`, `tool` или `language`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_skills_invalid"}

            level: int | None = None
            if level_raw:
                try:
                    level = int(level_raw)
                except ValueError:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=f"Строка {index}: level должен быть числом от 1 до 5 или пустым.",
                    )
                    return {"status": "processed", "action": "candidate_edit_skills_invalid"}
                if level < 1 or level > 5:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=f"Строка {index}: level должен быть в диапазоне от 1 до 5.",
                    )
                    return {"status": "processed", "action": "candidate_edit_skills_invalid"}

            parsed.append({"skill": skill, "kind": kind, "level": level})

        return await self._update_candidate_section_payload(
            actor=actor,
            chat_id=chat_id,
            operation="candidate.skills.update",
            update_kwargs={"skills": parsed},
            action_name="candidate_edit_skills_saved",
        )

    async def _handle_candidate_education_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_value: str,
    ) -> dict:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return await self._update_candidate_section_payload(
                actor=actor,
                chat_id=chat_id,
                operation="candidate.education.update",
                update_kwargs={"education": []},
                action_name="candidate_edit_education_saved",
            )

        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Добавь хотя бы одну строку образования или отправь `-`, чтобы очистить список.",
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_edit_education_invalid"}

        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            if len(parts) != 3:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: используй формат `level; institution; year`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_education_invalid"}

            level, institution, year_raw = parts
            if not level or not institution:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: `level` и `institution` обязательны.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_education_invalid"}

            try:
                year = int(year_raw)
            except ValueError:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: `year` должен быть числом.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_education_invalid"}
            if year < 1950 or year > 2100:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: `year` должен быть в диапазоне от 1950 до 2100.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_education_invalid"}

            parsed.append({"level": level, "institution": institution, "year": year})

        return await self._update_candidate_section_payload(
            actor=actor,
            chat_id=chat_id,
            operation="candidate.education.update",
            update_kwargs={"education": parsed},
            action_name="candidate_edit_education_saved",
        )

    async def _handle_candidate_experiences_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_value: str,
    ) -> dict:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return await self._update_candidate_section_payload(
                actor=actor,
                chat_id=chat_id,
                operation="candidate.experiences.update",
                update_kwargs={"experiences": []},
                action_name="candidate_edit_experiences_saved",
            )

        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Добавь хотя бы одну строку опыта или отправь `-`, чтобы очистить список.",
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_edit_experiences_invalid"}

        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=5)
            if len(parts) != 5:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        f"Строка {index}: используй формат "
                        "`company; position; start_date; end_date; responsibilities`."
                    ),
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_experiences_invalid"}

            company, position, start_raw, end_raw, responsibilities_raw = parts
            if not company or not position or not start_raw:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: `company`, `position` и `start_date` обязательны.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_experiences_invalid"}

            try:
                start_date = date.fromisoformat(start_raw)
            except ValueError:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: `start_date` должен быть в формате `YYYY-MM-DD`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_experiences_invalid"}

            end_date: str | None = None
            if end_raw:
                try:
                    parsed_end = date.fromisoformat(end_raw)
                except ValueError:
                    await self._telegram_client.send_message(
                    chat_id=chat_id,
                        text=f"Строка {index}: `end_date` должен быть в формате `YYYY-MM-DD` или пустым.",
                        parse_mode="Markdown",
                    )
                    return {"status": "processed", "action": "candidate_edit_experiences_invalid"}
                end_date = parsed_end.isoformat()

            parsed.append(
                {
                    "company": company,
                    "position": position,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date,
                    "responsibilities": responsibilities_raw or None,
                }
            )

        return await self._update_candidate_section_payload(
            actor=actor,
            chat_id=chat_id,
            operation="candidate.experiences.update",
            update_kwargs={"experiences": parsed},
            action_name="candidate_edit_experiences_saved",
        )

    async def _handle_candidate_projects_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_value: str,
    ) -> dict:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return await self._update_candidate_section_payload(
                actor=actor,
                chat_id=chat_id,
                operation="candidate.projects.update",
                update_kwargs={"projects": []},
                action_name="candidate_edit_projects_saved",
            )

        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Добавь хотя бы одну строку проекта или отправь `-` для очистки.",
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_edit_projects_invalid"}

        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            if len(parts) != 3:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: формат `title; description; link1,link2`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_edit_projects_invalid"}

            title, description, links_raw = parts
            if not title:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Строка {index}: title обязателен.",
                )
                return {"status": "processed", "action": "candidate_edit_projects_invalid"}

            links: list[str] = []
            if links_raw:
                for link in [item.strip() for item in links_raw.split(",") if item.strip()]:
                    parsed_url = urlparse(link)
                    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                        await self._telegram_client.send_message(
                            chat_id=chat_id,
                            text=f"Строка {index}: ссылка `{link}` должна быть http/https URL.",
                            parse_mode="Markdown",
                        )
                        return {"status": "processed", "action": "candidate_edit_projects_invalid"}
                    links.append(link)

            parsed.append(
                {
                    "title": title,
                    "description": description or None,
                    "links": links,
                }
            )

        return await self._update_candidate_section_payload(
            actor=actor,
            chat_id=chat_id,
            operation="candidate.projects.update",
            update_kwargs={"projects": parsed},
            action_name="candidate_edit_projects_saved",
        )

    async def _update_candidate_section_payload(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        operation: str,
        update_kwargs: dict[str, object],
        action_name: str,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate section edit load profile failed",
                extra={"telegram_user_id": actor.id, "operation": operation},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
            )
            return {"status": "processed", "action": "candidate_not_found"}

        idempotency_key = self._build_idempotency_key(
            telegram_user_id=actor.id,
            operation=operation,
            resource_id=candidate.id,
        )
        try:
            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.update_candidate_profile(
                    access_token=token,
                    candidate_id=candidate.id,
                    idempotency_key=idempotency_key,
                    **update_kwargs,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate section edit update failed",
                extra={"telegram_user_id": actor.id, "operation": operation},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=updated.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": action_name}

    @staticmethod
    def _split_candidate_structured_line(line: str, *, expected_parts: int) -> list[str]:
        normalized = line.strip()
        if "|" in normalized:
            separator = "|"
        elif ";" in normalized:
            separator = ";"
        else:
            return [normalized]

        parts = [part.strip() for part in normalized.split(separator, expected_parts - 1)]
        while len(parts) < expected_parts:
            parts.append("")
        return parts

    async def _handle_candidate_contact_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        contact_key: str,
        raw_value: str | None,
        allow_clear: bool,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate contact edit load profile failed",
                extra={"telegram_user_id": actor.id, "contact_key": contact_key},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
            )
            return {"status": "processed", "action": "candidate_not_found"}

        existing_contacts = dict(candidate.contacts or {})

        if raw_value is None:
            if not allow_clear:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Это поле нельзя очищать. Укажи значение.",
                )
                return {"status": "processed", "action": "candidate_contact_clear_forbidden"}
            existing_contacts[contact_key] = None
        else:
            normalized, error_text = self._normalize_contact_value(
                contact_key=contact_key,
                raw_value=raw_value,
            )
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_contact_invalid"}
            existing_contacts[contact_key] = normalized

        telegram_contact = existing_contacts.get("telegram")
        if not telegram_contact:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Поле telegram обязательно и не может быть пустым.",
            )
            return {"status": "processed", "action": "candidate_contact_missing_telegram"}
        idempotency_key = self._build_idempotency_key(
            telegram_user_id=actor.id,
            operation="candidate.contacts.update",
            resource_id=candidate.id,
        )

        try:
            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.update_candidate_profile(
                    access_token=token,
                    candidate_id=candidate.id,
                    contacts=existing_contacts,
                    idempotency_key=idempotency_key,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate contact edit update failed",
                extra={
                    "telegram_user_id": actor.id,
                    "candidate_id": str(candidate.id),
                    "contact_key": contact_key,
                },
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=updated.id,
        )

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": f"candidate_edit_contact_{contact_key}_saved"}
