from __future__ import annotations

from uuid import UUID

from app.application.bot.constants import (
    DECISION_LIKE,
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
from app.application.bot.handlers.common.callback_context import (
    ResolvedCallbackContext,
)
from app.application.common.contracts import NextCandidateResultView
from app.application.common.gateway_errors import EmployerGatewayError
from app.application.common.telegram_api import TelegramApiError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)


class EmployerSearchHandlersMixin:
    async def _render_employer_search_work_modes_step(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        payload: dict,
        allow_skip: bool = True,
        allow_back: bool = True,
    ) -> None:
        current = self._build_employer_search_step_current_value(payload, "work_modes")
        await self._set_state_and_render_wizard_step(
            telegram_user_id=telegram_user_id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_WORK_MODES,
            payload=payload,
            chat_id=chat_id,
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                "Выбери режимы работы кнопками ниже.\n\n"
                f"Текущий выбор: {current}"
            ),
            reply_markup=await self._build_employer_search_work_modes_selector_markup(
                telegram_user_id=telegram_user_id,
                selected_modes=(
                    payload.get("work_modes") if isinstance(payload.get("work_modes"), list) else []
                ),
                allow_skip=allow_skip,
                allow_back=allow_back,
            ),
        )

    async def _render_employer_search_english_step(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        payload: dict,
        allow_skip: bool = True,
        allow_back: bool = True,
    ) -> None:
        await self._set_state_and_render_wizard_step(
            telegram_user_id=telegram_user_id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_ENGLISH,
            payload=payload,
            chat_id=chat_id,
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                "Выбери уровень английского кнопками ниже."
            ),
            reply_markup=await self._build_employer_search_english_selector_markup(
                telegram_user_id=telegram_user_id,
                selected_level=str(payload.get("english_level") or ""),
                allow_skip=allow_skip,
                allow_back=allow_back,
            ),
        )

    async def _handle_employer_list_searches(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext | None = None,
    ) -> dict:
        requested_page = self._extract_page_number(context.payload if context is not None else None)
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            searches = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.list_searches(
                    access_token=token,
                    employer_id=employer.id,
                    limit=50,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer list searches failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_list_searches",
                retry_payload={"page": requested_page},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Список поисков",
            show_alert=False,
        )
        paged_searches, page, total_pages = self._paginate_items(
            searches,
            page=requested_page,
        )

        if not searches:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск > Все поиски\n\n"
                    "🗂 У тебя пока нет поисковых сессий.\n\n"
                    "Создай новый поиск, чтобы начать подбор кандидатов."
                ),
                reply_markup=await self._build_employer_searches_empty_markup(
                    telegram_user_id=actor.id,
                ),
            )
            return {"status": "processed", "action": "employer_list_searches_empty"}

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_searches_list_message(
                paged_searches,
                page=page,
                total_pages=total_pages,
            ),
            reply_markup=await self._build_searches_list_markup(
                actor.id,
                searches,
                page=page,
                total_pages=total_pages,
            ),
        )
        return {"status": "processed", "action": "employer_list_searches"}

    async def _handle_employer_search_create_confirm(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        confirm = bool(context.payload.get("confirm", False))
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_CONFIRM:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Мастер создания поиска устарел. Начни заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_confirm_expired"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        if not confirm:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Создание поиска отменено",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск\n\n"
                    "🛑 Создание поиска отменено.\n\n"
                    "Ты можешь запустить мастер заново в любой момент."
                ),
                reply_markup=await self._build_employer_dashboard_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_search_create_cancelled"}

        title = self._extract_payload_text(payload, "title")
        filters = self._build_employer_search_filters_payload(payload)
        invalid_payload_reason = self._validate_employer_search_draft(payload)
        if (
            not title
            or not isinstance(filters.get("role"), str)
            or invalid_payload_reason is not None
        ):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Черновик поиска неполный",
                show_alert=True,
            )
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_TITLE,
                payload=payload,
                chat_id=self._resolve_chat_id(callback, actor),
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Не удалось восстановить черновик. "
                    f"{invalid_payload_reason or 'Введи название поиска заново.'}"
                ),
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="title",
                    allow_skip=False,
                    allow_back=False,
                ),
            )
            return {"status": "processed", "action": "employer_search_confirm_invalid_payload"}

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="employer.search.create",
                resource_id=employer.id,
            )
            search = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.create_search_session(
                    access_token=token,
                    employer_id=employer.id,
                    title=title,
                    filters=filters,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer create search failed",
                extra={"telegram_user_id": actor.id, "title": title},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Поиск создан",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=(
                "Кабинет работодателя > Поиск\n\n"
                "✅ Поиск создан.\n\n"
                f"🔎 Название: {search.title}\n"
                f"💼 Роль: {search.role or '—'}\n"
                f"📊 Статус: {self._humanize_search_status(search.status)}"
            ),
            reply_markup=await self._build_open_search_markup(
                telegram_user_id=actor.id,
                session_id=search.id,
                search_status=search.status,
            ),
        )
        return {"status": "processed", "action": "employer_search_created"}

    async def _handle_employer_search_confirm_back(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_CONFIRM:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Мастер создания поиска устарел. Начни заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_confirm_back_expired"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Возвращаю к последнему шагу",
            show_alert=False,
        )
        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_ABOUT,
            payload=payload,
            chat_id=self._resolve_chat_id(callback, actor),
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                "Коротко опиши портрет кандидата/задачи команды "
                "или отправь `-`, чтобы пропустить.\n\n"
                f"Текущий выбор: {self._build_employer_search_step_current_value(payload, 'about')}"
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step="about",
                allow_skip=True,
            ),
        )
        return {"status": "processed", "action": "employer_search_confirm_back"}

    async def _handle_employer_search_confirm_edit_step(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        step = str(context.payload.get("step", "")).strip().lower()
        step_config = self._get_employer_search_wizard_step_config(step)
        if step_config is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Не удалось открыть выбранный шаг",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_confirm_edit_step_invalid"}

        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_CONFIRM:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Мастер создания поиска устарел. Начни заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_confirm_edit_step_expired"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        self._set_employer_search_edit_step(payload, step=step)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Открываю шаг для редактирования",
            show_alert=False,
        )
        if step == "work_modes":
            await self._render_employer_search_work_modes_step(
                telegram_user_id=actor.id,
                chat_id=self._resolve_chat_id(callback, actor),
                payload=payload,
                allow_skip=bool(step_config.get("allow_skip", True)),
                allow_back=bool(step_config.get("allow_back", True)),
            )
            return {"status": "processed", "action": "employer_search_confirm_edit_step"}
        if step == "english":
            await self._render_employer_search_english_step(
                telegram_user_id=actor.id,
                chat_id=self._resolve_chat_id(callback, actor),
                payload=payload,
                allow_skip=bool(step_config.get("allow_skip", True)),
                allow_back=bool(step_config.get("allow_back", True)),
            )
            return {"status": "processed", "action": "employer_search_confirm_edit_step"}
        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=str(step_config["state_key"]),
            payload=payload,
            chat_id=self._resolve_chat_id(callback, actor),
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                f"{step_config['prompt']}\n\n"
                f"Текущий выбор: {self._build_employer_search_step_current_value(payload, step)}"
            ),
            parse_mode=step_config.get("parse_mode"),
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step=step,
                allow_skip=bool(step_config.get("allow_skip", True)),
                allow_back=bool(step_config.get("allow_back", True)),
            ),
        )
        return {"status": "processed", "action": "employer_search_confirm_edit_step"}

    async def _handle_employer_search_wizard_control(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
        control: str,
    ) -> dict:
        step = str(context.payload.get("step", "")).strip().lower()
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        chat_id = self._resolve_chat_id(callback, actor)
        expected_state_by_step = {
            "title": STATE_EMPLOYER_SEARCH_TITLE,
            "role": STATE_EMPLOYER_SEARCH_ROLE,
            "must_skills": STATE_EMPLOYER_SEARCH_MUST_SKILLS,
            "nice_skills": STATE_EMPLOYER_SEARCH_NICE_SKILLS,
            "experience": STATE_EMPLOYER_SEARCH_EXPERIENCE,
            "location": STATE_EMPLOYER_SEARCH_LOCATION,
            "work_modes": STATE_EMPLOYER_SEARCH_WORK_MODES,
            "salary": STATE_EMPLOYER_SEARCH_SALARY,
            "english": STATE_EMPLOYER_SEARCH_ENGLISH,
            "about": STATE_EMPLOYER_SEARCH_ABOUT,
        }
        expected_state = expected_state_by_step.get(step)
        if expected_state is None or state is None or state.state_key != expected_state:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг мастера устарел. Начни заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_wizard_step_expired"}
        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        edit_step = self._get_employer_search_edit_step(payload)

        if control == "cancel":
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Создание поиска отменено",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск\n\n"
                    "🛑 Создание поиска отменено.\n\n"
                    "Ты можешь запустить мастер заново в любой момент."
                ),
                reply_markup=await self._build_employer_dashboard_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_search_wizard_cancelled"}

        if control == "back":
            if edit_step == step:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Возвращаю к подтверждению",
                    show_alert=False,
                )
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {"status": "processed", "action": "employer_search_wizard_back_to_confirm"}

            previous_step_by_step = {
                "role": "title",
                "must_skills": "role",
                "nice_skills": "must_skills",
                "experience": "nice_skills",
                "location": "experience",
                "work_modes": "location",
                "salary": "work_modes",
                "english": "salary",
                "about": "english",
            }
            previous_step = previous_step_by_step.get(step)
            if previous_step is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Назад недоступно на этом шаге",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_search_wizard_back_not_allowed"}

            previous_step_config = self._get_employer_search_wizard_step_config(previous_step)
            if previous_step_config is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Назад временно недоступно",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_search_wizard_back_unavailable"}

            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Возвращаю на предыдущий шаг",
                show_alert=False,
            )
            if previous_step == "work_modes":
                await self._render_employer_search_work_modes_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                    allow_skip=bool(previous_step_config.get("allow_skip", True)),
                    allow_back=bool(previous_step_config.get("allow_back", True)),
                )
                return {"status": "processed", "action": "employer_search_wizard_back"}
            if previous_step == "english":
                await self._render_employer_search_english_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                    allow_skip=bool(previous_step_config.get("allow_skip", True)),
                    allow_back=bool(previous_step_config.get("allow_back", True)),
                )
                return {"status": "processed", "action": "employer_search_wizard_back"}
            current_value = self._build_employer_search_step_current_value(
                payload,
                previous_step,
            )
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=str(previous_step_config["state_key"]),
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    f"{previous_step_config['prompt']}\n\n"
                    f"Текущий выбор: {current_value}"
                ),
                parse_mode=previous_step_config.get("parse_mode"),
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step=previous_step,
                    allow_skip=bool(previous_step_config.get("allow_skip", True)),
                    allow_back=bool(previous_step_config.get("allow_back", True)),
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_back"}

        if control != "skip":
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Неизвестная команда",
                show_alert=True,
            )
            return {"status": "ignored", "reason": "unknown_search_wizard_control"}

        if step in {"title", "role"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Этот шаг обязательный",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_wizard_skip_not_allowed"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Пропускаю шаг",
            show_alert=False,
        )

        if step == "must_skills":
            payload["must_skills"] = []
            if edit_step == "must_skills":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_must_skills_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_NICE_SKILLS,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желательные навыки через запятую.\n"
                    "Пример: `Docker:3, AWS`.\n"
                    "Отправь `-`, если шаг пропускаем."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="nice_skills",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_must_skills"}

        if step == "nice_skills":
            payload["nice_skills"] = []
            if edit_step == "nice_skills":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_nice_skills_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_EXPERIENCE,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    f"{self._build_search_experience_prompt()}"
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="experience",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_nice_skills"}

        if step == "experience":
            payload["experience_min"] = None
            payload["experience_max"] = None
            if edit_step == "experience":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_experience_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_LOCATION,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желаемую локацию (город/страна) или `-`, чтобы пропустить."
                ),
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="location",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_experience"}

        if step == "location":
            payload["location"] = None
            if edit_step == "location":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_location_from_confirm",
                }
            await self._render_employer_search_work_modes_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_location"}

        if step == "work_modes":
            payload["work_modes"] = []
            if edit_step == "work_modes":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_work_modes_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_SALARY,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    f"{self._build_search_salary_prompt()}"
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="salary",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_work_modes"}

        if step == "salary":
            payload["salary_min"] = None
            payload["salary_max"] = None
            payload["currency"] = None
            if edit_step == "salary":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_salary_from_confirm",
                }
            await self._render_employer_search_english_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_salary"}

        if step == "english":
            payload["english_level"] = None
            if edit_step == "english":
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_wizard_skipped_english_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_ABOUT,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Коротко опиши портрет кандидата/задачи команды "
                    "или отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="about",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_wizard_skipped_english"}

        payload["about_me"] = None
        await self._render_employer_search_confirm_step(
            telegram_user_id=actor.id,
            chat_id=chat_id,
            payload=payload,
        )
        return {"status": "processed", "action": "employer_search_wizard_skipped_about"}

    async def _handle_employer_search_choice_work_mode_toggle(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_WORK_MODES:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора формата устарел. Запусти мастер заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_work_modes_choice_expired"}

        mode = str(context.payload.get("mode") or "").strip().lower()
        if mode not in {"remote", "onsite", "hybrid"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Неизвестный режим работы",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_work_modes_choice_invalid"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        selected_raw = payload.get("work_modes")
        selected = []
        if isinstance(selected_raw, list):
            selected = [str(item).strip().lower() for item in selected_raw if str(item).strip()]
        if mode in selected:
            selected = [item for item in selected if item != mode]
        else:
            selected.append(mode)
        payload["work_modes"] = selected

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Выбор обновлён",
            show_alert=False,
        )
        await self._render_employer_search_work_modes_step(
            telegram_user_id=actor.id,
            chat_id=self._resolve_chat_id(callback, actor),
            payload=payload,
            allow_skip=True,
        )
        return {"status": "processed", "action": "employer_search_work_modes_choice_toggled"}

    async def _handle_employer_search_choice_work_modes_done(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_WORK_MODES:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора формата устарел. Запусти мастер заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_work_modes_done_expired"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        selected_raw = payload.get("work_modes")
        selected: list[str] = []
        if isinstance(selected_raw, list):
            selected = [
                str(item).strip().lower()
                for item in selected_raw
                if str(item).strip().lower() in {"remote", "onsite", "hybrid"}
            ]
        deduped: list[str] = []
        for item in selected:
            if item not in deduped:
                deduped.append(item)
        payload["work_modes"] = deduped
        if self._is_employer_search_edit_step(payload, step="work_modes"):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Формат работы сохранен",
                show_alert=False,
            )
            await self._render_employer_search_confirm_step(
                telegram_user_id=actor.id,
                chat_id=self._resolve_chat_id(callback, actor),
                payload=payload,
            )
            return {
                "status": "processed",
                "action": "employer_search_work_modes_saved_from_confirm",
            }

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Формат работы сохранен",
            show_alert=False,
        )
        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_SALARY,
            payload=payload,
            chat_id=self._resolve_chat_id(callback, actor),
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                f"{self._build_search_salary_prompt()}"
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step="salary",
                allow_skip=True,
            ),
        )
        return {"status": "processed", "action": "employer_search_work_modes_saved"}

    async def _handle_employer_search_choice_english(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_EMPLOYER_SEARCH_ENGLISH:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора английского устарел. Запусти мастер заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_english_choice_expired"}

        raw_value = str(context.payload.get("value") or "").strip().upper()
        english_level = raw_value or None
        if english_level is not None and english_level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Недопустимый уровень английского",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_english_choice_invalid"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        payload["english_level"] = english_level

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Английский сохранен",
            show_alert=False,
        )
        if self._is_employer_search_edit_step(payload, step="english"):
            await self._render_employer_search_confirm_step(
                telegram_user_id=actor.id,
                chat_id=self._resolve_chat_id(callback, actor),
                payload=payload,
            )
            return {"status": "processed", "action": "employer_search_english_saved_from_confirm"}

        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_ABOUT,
            payload=payload,
            chat_id=self._resolve_chat_id(callback, actor),
            text=(
                "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                "Коротко опиши портрет кандидата/задачи команды или отправь `-`, чтобы пропустить."
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step="about",
                allow_skip=True,
            ),
        )
        return {"status": "processed", "action": "employer_search_english_saved"}

    async def _handle_employer_favorites(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext | None = None,
    ) -> dict:
        requested_page = self._extract_page_number(context.payload if context is not None else None)
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            items = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_favorites(
                    access_token=token,
                    employer_id=employer.id,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer favorites failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_favorites",
                retry_payload={"page": requested_page},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Избранные контакты",
            show_alert=False,
        )
        paged_items, page, total_pages = self._paginate_items(
            items,
            page=requested_page,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_collection_message(
                title=(
                    "Кабинет работодателя > Поиск > Избранные контакты "
                    f"(стр. {page}/{total_pages})"
                ),
                items=paged_items,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_collection_markup(
                telegram_user_id=actor.id,
                items=items,
                source="favorites",
                page=page,
                total_pages=total_pages,
            ),
        )
        return {"status": "processed", "action": "employer_favorites"}

    async def _handle_employer_unlocked_contacts(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext | None = None,
    ) -> dict:
        requested_page = self._extract_page_number(context.payload if context is not None else None)
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            items = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_unlocked_contacts(
                    access_token=token,
                    employer_id=employer.id,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer unlocked contacts failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_unlocked_contacts",
                retry_payload={"page": requested_page},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Открытые контакты",
            show_alert=False,
        )
        paged_items, page, total_pages = self._paginate_items(
            items,
            page=requested_page,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_collection_message(
                title=(
                    "Кабинет работодателя > Поиск > Открытые контакты "
                    f"(стр. {page}/{total_pages})"
                ),
                items=paged_items,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_collection_markup(
                telegram_user_id=actor.id,
                items=items,
                source="unlocked",
                page=page,
                total_pages=total_pages,
            ),
        )
        return {"status": "processed", "action": "employer_unlocked_contacts"}

    async def _handle_employer_open_collection_candidate(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        source = str(context.payload.get("source", "")).strip().lower()
        candidate_id_raw = context.payload.get("candidate_id")
        try:
            candidate_id = UUID(str(candidate_id_raw))
        except (TypeError, ValueError):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Некорректный кандидат",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_collection_candidate_invalid_id"}

        if source not in {"favorites", "unlocked"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Источник списка не поддерживается",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_collection_candidate_invalid_source"}

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            items = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=(
                    (
                        lambda token: self._employer_gateway.get_favorites(
                            access_token=token,
                            employer_id=employer.id,
                        )
                    )
                    if source == "favorites"
                    else (
                        lambda token: self._employer_gateway.get_unlocked_contacts(
                            access_token=token,
                            employer_id=employer.id,
                        )
                    )
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer open collection candidate failed",
                extra={
                    "telegram_user_id": actor.id,
                    "source": source,
                    "candidate_id": str(candidate_id),
                },
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        selected = next((item for item in items if item.id == candidate_id), None)
        if selected is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Кандидат не найден в текущем списке",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_collection_candidate_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Карточка кандидата",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_next_candidate_message(
                NextCandidateResultView(
                    candidate=selected,
                    message=None,
                    is_degraded=False,
                )
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_collection_profile_markup(
                telegram_user_id=actor.id,
                source=source,
                page=int(context.payload.get("page", 1) or 1),
                total_pages=int(context.payload.get("total_pages", 1) or 1),
            ),
        )
        return {"status": "processed", "action": "employer_collection_candidate_opened"}

    async def _handle_employer_open_search(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        session_id_raw = context.payload.get("session_id")
        session_id = UUID(str(session_id_raw))
        search_status = self._normalize_search_status(context.payload.get("search_status"))

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        if self._is_search_closed(search_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск закрыт",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск > Сессия\n\n"
                    "⚫ Поиск закрыт.\n\n"
                    "Открой список поисков и выбери другую сессию."
                ),
            )
            return {"status": "processed", "action": "employer_open_search_closed"}

        if self._is_search_paused(search_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск на паузе",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск > Сессия\n\n"
                    "🟡 Поиск на паузе.\n\n"
                    "Возобнови сессию, чтобы продолжить подбор кандидатов."
                ),
                reply_markup=await self._build_next_candidate_only_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                ),
            )
            return {"status": "processed", "action": "employer_open_search_paused"}

        try:
            result = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_next_candidate(
                    access_token=token,
                    session_id=session_id,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer open search failed",
                extra={"telegram_user_id": actor.id, "session_id": str(session_id)},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_open_search",
                retry_payload={"session_id": str(session_id), "search_status": search_status},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Открываю поиск",
            show_alert=False,
        )

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_next_candidate_message(result),
            parse_mode="Markdown",
            reply_markup=(
                await self._build_candidate_decision_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    candidate=result.candidate,
                    search_status=search_status,
                )
                if result.candidate is not None
                else await self._build_no_candidate_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                    is_degraded=result.is_degraded,
                )
            ),
        )
        return {"status": "processed", "action": "employer_open_search"}

    async def _handle_employer_search_decision(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        session_id = UUID(str(context.payload["session_id"]))
        candidate_id = UUID(str(context.payload["candidate_id"]))
        decision = str(context.payload["decision"]).strip().lower()
        search_status = self._normalize_search_status(context.payload.get("search_status"))
        can_view_contacts = bool(context.payload.get("can_view_contacts", False))

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        if not self._is_search_active(search_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск не активен",
                show_alert=True,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск > Сессия\n\n"
                    "⚠️ Действие недоступно.\n\n"
                    "Поиск сейчас не активен. Возобнови его или открой другую сессию."
                ),
                reply_markup=await self._build_next_candidate_only_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                ),
            )
            return {"status": "processed", "action": "employer_search_decision_inactive"}

        try:
            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation=f"search.decision.{decision}",
                resource_id=session_id,
            )
            await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.submit_decision(
                    access_token=token,
                    session_id=session_id,
                    candidate_id=candidate_id,
                    decision=decision,
                    idempotency_key=idempotency_key,
                ),
            )

            if decision == DECISION_LIKE and not can_view_contacts:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Лайк сохранен",
                    show_alert=False,
                )
                await self._render_callback_screen(
                    callback=callback,
                    actor=actor,
                    text=(
                        "Кандидат добавлен в избранное.\n"
                        "Теперь можно запросить контакты или перейти к следующему кандидату."
                    ),
                    reply_markup=await self._build_after_like_markup(
                        telegram_user_id=actor.id,
                        session_id=session_id,
                        candidate_id=candidate_id,
                        search_status=search_status,
                    ),
                )
                return {"status": "processed", "action": "employer_search_like_saved"}

            next_result = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_next_candidate(
                    access_token=token,
                    session_id=session_id,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer search decision failed",
                extra={
                    "telegram_user_id": actor.id,
                    "session_id": str(session_id),
                    "candidate_id": str(candidate_id),
                    "decision": decision,
                },
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_search_decision",
                retry_payload={
                    "session_id": str(session_id),
                    "candidate_id": str(candidate_id),
                    "decision": decision,
                    "search_status": search_status,
                    "can_view_contacts": can_view_contacts,
                },
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text=f"Решение сохранено: {decision}",
            show_alert=False,
        )

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_next_candidate_message(next_result),
            parse_mode="Markdown",
            reply_markup=(
                await self._build_candidate_decision_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    candidate=next_result.candidate,
                    search_status=search_status,
                )
                if next_result.candidate is not None
                else await self._build_no_candidate_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                    is_degraded=next_result.is_degraded,
                )
            ),
        )
        return {"status": "processed", "action": "employer_search_decision"}

    async def _handle_employer_search_resume_download(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        resume_download_url = str(context.payload.get("resume_download_url", "")).strip()
        if not resume_download_url:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="У кандидата нет резюме",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_search_resume_missing"}

        chat_id = self._resolve_chat_id(callback, actor)
        try:
            await self._telegram_client.send_document(
                chat_id=chat_id,
                document=resume_download_url,
                caption="Резюме кандидата",
            )
            action_name = "employer_search_resume_sent"
        except TelegramApiError:
            await self._telegram_client.send_attachment_message(
                chat_id=chat_id,
                text=f"Ссылка на резюме:\n{resume_download_url}",
            )
            action_name = "employer_search_resume_link_sent"

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Резюме отправлено",
            show_alert=False,
        )
        return {"status": "processed", "action": action_name}

    async def _handle_employer_search_control(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
        operation: str,
    ) -> dict:
        session_id = UUID(str(context.payload["session_id"]))
        current_status = self._normalize_search_status(context.payload.get("search_status"))
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        if operation not in {"pause", "resume", "close"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Неизвестная операция",
                show_alert=True,
            )
            return {"status": "ignored", "reason": "unknown_search_control_operation"}

        if operation == "pause" and self._is_search_paused(current_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск уже на паузе",
                show_alert=False,
            )
            return {"status": "processed", "action": "employer_search_pause_noop"}

        if operation == "resume" and self._is_search_active(current_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск уже активен",
                show_alert=False,
            )
            return {"status": "processed", "action": "employer_search_resume_noop"}

        if operation == "close" and self._is_search_closed(current_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск уже закрыт",
                show_alert=False,
            )
            return {"status": "processed", "action": "employer_search_close_noop"}

        idempotency_key = self._build_idempotency_key(
            telegram_user_id=actor.id,
            operation=f"search.{operation}",
            resource_id=session_id,
        )

        try:
            if operation == "pause":
                search = await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.pause_search_session(
                        access_token=token,
                        session_id=session_id,
                        idempotency_key=idempotency_key,
                    ),
                )
            elif operation == "resume":
                search = await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.resume_search_session(
                        access_token=token,
                        session_id=session_id,
                        idempotency_key=idempotency_key,
                    ),
                )
            else:
                search = await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.close_search_session(
                        access_token=token,
                        session_id=session_id,
                        idempotency_key=idempotency_key,
                    ),
                )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer search control failed",
                extra={
                    "telegram_user_id": actor.id,
                    "session_id": str(session_id),
                    "operation": operation,
                },
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text=f"Поиск: {operation}",
            show_alert=False,
        )

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_search_session_status_message(search),
            reply_markup=(
                await self._build_next_candidate_only_markup(
                    telegram_user_id=actor.id,
                    session_id=search.id,
                    search_status=search.status,
                )
                if not self._is_search_closed(search.status)
                else None
            ),
        )
        return {"status": "processed", "action": f"employer_search_{operation}"}

    async def _handle_employer_request_contact_access(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        session_id_raw = context.payload.get("session_id")
        candidate_id_raw = context.payload.get("candidate_id")
        search_status = self._normalize_search_status(context.payload.get("search_status"))
        liked = bool(context.payload.get("liked", False))

        session_id = UUID(str(session_id_raw))
        candidate_id = UUID(str(candidate_id_raw))

        if not liked:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Сначала отметь кандидата как подходящего",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_request_contact_requires_like"}

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="contacts.request.create",
                resource_id=candidate_id,
            )
            result = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.request_contact_access(
                    access_token=token,
                    employer_id=employer.id,
                    candidate_id=candidate_id,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer request contact access failed",
                extra={
                    "telegram_user_id": actor.id,
                    "session_id": str(session_id),
                    "candidate_id": str(candidate_id),
                },
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_request_contact_access",
                retry_payload={
                    "session_id": str(session_id),
                    "candidate_id": str(candidate_id),
                    "search_status": search_status,
                    "liked": liked,
                },
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Запрос контактов обработан",
            show_alert=False,
        )

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_contact_access_result_message(result),
            parse_mode="Markdown",
            reply_markup=await self._build_next_candidate_only_markup(
                telegram_user_id=actor.id,
                session_id=session_id,
                search_status=search_status,
            ),
        )

        return {"status": "processed", "action": "employer_request_contact_access"}

    async def _handle_employer_next_candidate(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        session_id_raw = context.payload.get("session_id")
        session_id = UUID(str(session_id_raw))
        search_status = self._normalize_search_status(context.payload.get("search_status"))

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        if not self._is_search_active(search_status):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Поиск не активен",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Кабинет работодателя > Поиск > Сессия\n\n"
                    "⚠️ Следующий кандидат недоступен.\n\n"
                    "Поиск сейчас не активен. Возобнови сессию и попробуй снова."
                ),
                reply_markup=await self._build_next_candidate_only_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                ),
            )
            return {"status": "processed", "action": "employer_next_candidate_inactive"}

        try:
            result = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_next_candidate(
                    access_token=token,
                    session_id=session_id,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer next candidate failed",
                extra={
                    "telegram_user_id": actor.id,
                    "session_id": str(session_id),
                },
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_next_candidate",
                retry_payload={"session_id": str(session_id), "search_status": search_status},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Следующий кандидат",
            show_alert=False,
        )

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_next_candidate_message(result),
            parse_mode="Markdown",
            reply_markup=(
                await self._build_candidate_decision_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    candidate=result.candidate,
                    search_status=search_status,
                )
                if result.candidate is not None
                else await self._build_no_candidate_markup(
                    telegram_user_id=actor.id,
                    session_id=session_id,
                    search_status=search_status,
                    is_degraded=result.is_degraded,
                )
            ),
        )
        return {"status": "processed", "action": "employer_next_candidate"}
