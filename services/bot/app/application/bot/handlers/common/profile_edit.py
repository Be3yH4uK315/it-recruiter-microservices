from __future__ import annotations

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_EDIT_ABOUT_ME,
    STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
    STATE_CANDIDATE_EDIT_CONTACT_PHONE,
    STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM,
    STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY,
    STATE_CANDIDATE_EDIT_DISPLAY_NAME,
    STATE_CANDIDATE_EDIT_EDUCATION,
    STATE_CANDIDATE_EDIT_ENGLISH_LEVEL,
    STATE_CANDIDATE_EDIT_EXPERIENCES,
    STATE_CANDIDATE_EDIT_HEADLINE_ROLE,
    STATE_CANDIDATE_EDIT_LOCATION,
    STATE_CANDIDATE_EDIT_PROJECTS,
    STATE_CANDIDATE_EDIT_SALARY,
    STATE_CANDIDATE_EDIT_SKILLS,
    STATE_CANDIDATE_EDIT_STATUS,
    STATE_CANDIDATE_EDIT_WORK_MODES,
    STATE_EMPLOYER_EDIT_COMPANY,
    STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
    STATE_EMPLOYER_EDIT_CONTACT_PHONE,
    STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM,
    STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
)
from app.application.common.contracts import CandidateProfileSummary, EmployerProfileSummary
from app.application.common.gateway_errors import CandidateGatewayError, EmployerGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)


class ProfileEditUtilsMixin:
    def _build_candidate_choice_prompt(
        self,
        *,
        title: str,
        instruction: str,
        current_value: str,
    ) -> str:
        return self._build_structured_prompt(
            section_path="Кабинет кандидата · Редактирование",
            title=title,
            instruction=instruction,
            current_value=current_value,
        )

    async def _handle_candidate_edit_work_modes_choice_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        candidate = await self._try_get_candidate_profile_for_prompt(telegram_user_id=actor.id)
        selected = candidate.work_modes if candidate is not None and candidate.work_modes else []
        payload = {"selected_work_modes": selected}
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_EDIT_WORK_MODES,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        current_text = (
            ", ".join(self._humanize_work_mode(item) for item in selected) if selected else "—"
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_choice_prompt(
                title="Выбери форматы работы",
                instruction="Используй кнопки ниже, чтобы отметить подходящие варианты.",
                current_value=current_text,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_work_modes_selector_markup(
                telegram_user_id=actor.id,
                selected_modes=selected,
                allow_clear=True,
            ),
        )
        return {"status": "processed", "action": "candidate_edit_work_modes_start"}

    async def _handle_candidate_edit_contacts_visibility_choice_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        candidate = await self._try_get_candidate_profile_for_prompt(telegram_user_id=actor.id)
        selected = candidate.contacts_visibility if candidate is not None else None
        payload = {"selected_contacts_visibility": selected}
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        current_text = self._humanize_contacts_visibility_for_profile(selected)
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_choice_prompt(
                title="Выбери видимость контактов",
                instruction="Используй кнопки ниже, чтобы задать режим приватности.",
                current_value=current_text,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_contacts_visibility_selector_markup(
                telegram_user_id=actor.id,
                selected_visibility=selected,
            ),
        )
        return {"status": "processed", "action": "candidate_edit_contacts_visibility_start"}

    async def _handle_candidate_edit_english_choice_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        candidate = await self._try_get_candidate_profile_for_prompt(telegram_user_id=actor.id)
        selected = candidate.english_level if candidate is not None else None
        payload = {"selected_english_level": selected}
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_EDIT_ENGLISH_LEVEL,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_choice_prompt(
                title="Выбери уровень английского",
                instruction="Используй кнопки ниже, чтобы указать актуальный уровень.",
                current_value=selected or "—",
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_english_level_selector_markup(
                telegram_user_id=actor.id,
                selected_level=selected,
                allow_clear=True,
            ),
        )
        return {"status": "processed", "action": "candidate_edit_english_level_start"}

    async def _handle_candidate_edit_status_choice_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        candidate = await self._try_get_candidate_profile_for_prompt(telegram_user_id=actor.id)
        selected = candidate.status if candidate is not None else None
        payload = {"selected_status": selected}
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_EDIT_STATUS,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_choice_prompt(
                title="Выбери статус профиля",
                instruction="Используй кнопки ниже, чтобы обновить статус профиля.",
                current_value=self._humanize_candidate_status(selected),
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_status_selector_markup(
                telegram_user_id=actor.id,
                selected_status=selected,
            ),
        )
        return {"status": "processed", "action": "candidate_edit_status_start"}

    async def _handle_candidate_edit_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        state_key: str,
        prompt: str,
        action_name: str,
        parse_mode: str | None = None,
    ) -> dict:
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=state_key,
            payload=None,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        current_value = await self._resolve_candidate_current_edit_value(
            telegram_user_id=actor.id,
            state_key=state_key,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_edit_prompt_message(
                cabinet_prefix="Кабинет кандидата > Редактирование",
                prompt=prompt,
                current_value=current_value,
                parse_mode=parse_mode,
            ),
            parse_mode=parse_mode,
            reply_markup=await self._build_candidate_edit_prompt_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": action_name}

    async def _handle_employer_edit_start(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        state_key: str,
        prompt: str,
        action_name: str,
        parse_mode: str | None = None,
    ) -> dict:
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=state_key,
            payload=None,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        current_value = await self._resolve_employer_current_edit_value(
            telegram_user_id=actor.id,
            state_key=state_key,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_edit_prompt_message(
                cabinet_prefix="Кабинет работодателя > Редактирование",
                prompt=prompt,
                current_value=current_value,
                parse_mode=parse_mode,
            ),
            parse_mode=parse_mode,
            reply_markup=await self._build_employer_edit_prompt_markup(telegram_user_id=actor.id),
        )
        return {"status": "processed", "action": action_name}

    async def _resolve_candidate_current_edit_value(
        self,
        *,
        telegram_user_id: int,
        state_key: str,
    ) -> str | None:
        candidate = await self._try_get_candidate_profile_for_prompt(
            telegram_user_id=telegram_user_id
        )
        if candidate is None:
            return None
        return self._build_candidate_edit_current_value(
            state_key=state_key,
            candidate=candidate,
        )

    async def _resolve_employer_current_edit_value(
        self,
        *,
        telegram_user_id: int,
        state_key: str,
    ) -> str | None:
        employer = await self._try_get_employer_profile_for_prompt(
            telegram_user_id=telegram_user_id
        )
        if employer is None:
            return None
        return self._build_employer_edit_current_value(
            state_key=state_key,
            employer=employer,
        )

    async def _try_get_candidate_profile_for_prompt(
        self,
        *,
        telegram_user_id: int,
    ) -> CandidateProfileSummary | None:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=telegram_user_id
        )
        if access_token is None:
            return None

        try:
            return await self._run_candidate_gateway_call(
                telegram_user_id=telegram_user_id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=telegram_user_id,
                ),
            )
        except CandidateGatewayError:
            logger.warning(
                "candidate current value load failed",
                extra={"telegram_user_id": telegram_user_id},
            )
            return None

    async def _try_get_employer_profile_for_prompt(
        self,
        *,
        telegram_user_id: int,
    ) -> EmployerProfileSummary | None:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=telegram_user_id
        )
        if access_token is None:
            return None

        try:
            return await self._run_employer_gateway_call(
                telegram_user_id=telegram_user_id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=telegram_user_id,
                ),
            )
        except EmployerGatewayError:
            logger.warning(
                "employer current value load failed",
                extra={"telegram_user_id": telegram_user_id},
            )
            return None

    def _build_candidate_edit_current_value(
        self,
        *,
        state_key: str,
        candidate: CandidateProfileSummary,
    ) -> str:
        if state_key == STATE_CANDIDATE_EDIT_DISPLAY_NAME:
            return candidate.display_name or "—"
        if state_key == STATE_CANDIDATE_EDIT_HEADLINE_ROLE:
            return candidate.headline_role or "—"
        if state_key == STATE_CANDIDATE_EDIT_LOCATION:
            return candidate.location or "—"
        if state_key == STATE_CANDIDATE_EDIT_ABOUT_ME:
            return candidate.about_me or "—"
        if state_key == STATE_CANDIDATE_EDIT_WORK_MODES:
            if not candidate.work_modes:
                return "—"
            return ", ".join(candidate.work_modes)
        if state_key == STATE_CANDIDATE_EDIT_ENGLISH_LEVEL:
            return candidate.english_level or "—"
        if state_key == STATE_CANDIDATE_EDIT_STATUS:
            return candidate.status or "—"
        if state_key == STATE_CANDIDATE_EDIT_SALARY:
            if candidate.salary_min is None and candidate.salary_max is None:
                return "—"
            return (
                f"{candidate.salary_min if candidate.salary_min is not None else '—'} "
                f"{candidate.salary_max if candidate.salary_max is not None else '—'} "
                f"{candidate.currency or ''}"
            ).strip()
        if state_key == STATE_CANDIDATE_EDIT_SKILLS:
            preview = self._build_skills_preview(
                candidate.skills,
                limit=8,
            )
            return preview or "—"
        if state_key == STATE_CANDIDATE_EDIT_EDUCATION:
            return self._build_collection_size_preview(candidate.education)
        if state_key == STATE_CANDIDATE_EDIT_EXPERIENCES:
            return self._build_collection_size_preview(candidate.experiences)
        if state_key == STATE_CANDIDATE_EDIT_PROJECTS:
            return self._build_collection_size_preview(candidate.projects)
        if state_key == STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY:
            if not candidate.contacts_visibility:
                return "—"
            return self._humanize_contacts_visibility(candidate.contacts_visibility)
        if state_key == STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM:
            return self._extract_contact_value(candidate.contacts, "telegram")
        if state_key == STATE_CANDIDATE_EDIT_CONTACT_EMAIL:
            return self._extract_contact_value(candidate.contacts, "email")
        if state_key == STATE_CANDIDATE_EDIT_CONTACT_PHONE:
            phone = self._extract_contact_value(candidate.contacts, "phone")
            if phone == "—":
                return phone
            return self._format_phone_for_profile(phone)
        return "—"

    def _build_employer_edit_current_value(
        self,
        *,
        state_key: str,
        employer: EmployerProfileSummary,
    ) -> str:
        if state_key == STATE_EMPLOYER_EDIT_COMPANY:
            return employer.company or "—"
        if state_key == STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM:
            return self._extract_contact_value(employer.contacts, "telegram")
        if state_key == STATE_EMPLOYER_EDIT_CONTACT_EMAIL:
            return self._extract_contact_value(employer.contacts, "email")
        if state_key == STATE_EMPLOYER_EDIT_CONTACT_PHONE:
            phone = self._extract_contact_value(employer.contacts, "phone")
            if phone == "—":
                return phone
            return self._format_phone_for_profile(phone)
        if state_key == STATE_EMPLOYER_EDIT_CONTACT_WEBSITE:
            return self._extract_contact_value(employer.contacts, "website")
        return "—"

    @staticmethod
    def _extract_contact_value(
        contacts: dict[str, str | None] | None,
        key: str,
    ) -> str:
        if not isinstance(contacts, dict):
            return "—"
        value = contacts.get(key)
        if value is None:
            return "—"
        normalized = str(value).strip()
        return normalized or "—"

    @staticmethod
    def _build_collection_size_preview(items: list[dict] | None) -> str:
        if not items:
            return "—"
        count = len(items)
        if count == 1:
            return "1 запись"
        return f"{count} записей"

    @staticmethod
    def _build_edit_prompt_message(
        *,
        cabinet_prefix: str,
        prompt: str,
        current_value: str | None,
        parse_mode: str | None,
    ) -> str:
        if parse_mode == "Markdown":
            return ProfileEditUtilsMixin._build_structured_prompt(
                section_path=cabinet_prefix,
                title="Редактирование",
                instruction=prompt,
                current_value=current_value,
            )

        lines = [cabinet_prefix, "", "Редактирование", "", prompt]
        if current_value is not None:
            preview = current_value.strip() or "—"
            if len(preview) > 240:
                preview = f"{preview[:240].rstrip()}…"
            lines.extend(["", f"Текущий выбор: {preview}"])
        return "\n".join(lines)
