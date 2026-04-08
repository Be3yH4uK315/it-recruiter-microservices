from __future__ import annotations

from app.application.common.gateway_errors import EmployerGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramUser

logger = get_logger(__name__)


class EmployerProfileSubmitHandlersMixin:
    def _build_employer_submit_status_message(
        self,
        *,
        title: str,
        status_line: str,
        details: list[str] | None = None,
        footer: str | None = None,
    ) -> str:
        return self._build_status_screen(
            section_path="Кабинет работодателя · Редактирование профиля",
            title=title,
            status_line=status_line,
            details=details,
            footer=footer,
        )

    async def _clear_employer_submit_state_and_send_message(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        text: str,
        action: str,
        parse_mode: str | None = None,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=telegram_user_id)
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        return {"status": "processed", "action": action}

    async def _clear_employer_submit_state_and_handle_gateway_error(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        exc: EmployerGatewayError,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=telegram_user_id)
        await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
        return {"status": "processed", "action": "employer_gateway_error"}

    async def _finish_employer_submit_success(
        self,
        *,
        telegram_user_id: int,
        actor: TelegramUser,
        chat_id: int,
        access_token: str,
        employer,
        action: str,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=telegram_user_id)
        await self._render_employer_dashboard_after_submit(
            actor=actor,
            chat_id=chat_id,
            access_token=access_token,
            employer=employer,
        )
        return {"status": "processed", "action": action}

    async def _render_employer_dashboard_after_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        access_token: str,
        employer,
    ) -> None:
        stats = await self._safe_get_employer_statistics(
            access_token=access_token,
            employer_id=employer.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=(
                "✅ *Изменения сохранены.*\n\n"
                + self._build_employer_dashboard_message(
                    first_name=actor.first_name,
                    employer=employer,
                    statistics=stats,
                    created_now=False,
                )
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_dashboard_markup(actor.id),
        )

    async def _handle_employer_edit_company_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        company: str | None,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            return await self._clear_employer_submit_state_and_send_message(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                text=self._build_employer_submit_status_message(
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                action="session_expired",
                parse_mode="Markdown",
            )

        normalized_company = company.strip() if isinstance(company, str) else company
        if isinstance(normalized_company, str) and not normalized_company:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_employer_submit_status_message(
                    title="Нужно значение",
                    status_line="⚠️ Пустое значение сохранить нельзя.",
                    details=["Введи название компании или отправь `-`, чтобы очистить поле."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "employer_edit_company_empty"}
        normalized_company, error_text = self._normalize_profile_name_value(
            raw_value=normalized_company if isinstance(normalized_company, str) else None,
            field_label="Название компании",
        )
        if error_text is not None:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=error_text,
            )
            return {"status": "processed", "action": "employer_edit_company_invalid"}

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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=self._build_employer_submit_status_message(
                        title="Профиль не найден",
                        status_line="⚠️ Профиль работодателя не найден.",
                        details=["Нажми `/start`, чтобы начать заново."],
                    ),
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_not_found"}

            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="employer.profile.update",
                resource_id=employer.id,
            )
            updated = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.update_employer(
                    access_token=token,
                    employer_id=employer.id,
                    company=normalized_company,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer edit company failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            return await self._clear_employer_submit_state_and_handle_gateway_error(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                exc=exc,
            )

        return await self._finish_employer_submit_success(
            telegram_user_id=actor.id,
            actor=actor,
            chat_id=chat_id,
            access_token=access_token,
            employer=updated,
            action="employer_edit_company_saved",
        )

    async def _handle_employer_contact_submit(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        contact_key: str,
        raw_value: str | None,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            return await self._clear_employer_submit_state_and_send_message(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                text=self._build_employer_submit_status_message(
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                action="session_expired",
                parse_mode="Markdown",
            )

        if contact_key not in {"telegram", "email", "phone", "website"}:
            return await self._clear_employer_submit_state_and_send_message(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                text=self._build_employer_submit_status_message(
                    title="Неизвестное поле",
                    status_line="⚠️ Неизвестное поле контакта.",
                    details=["Нажми `/start`, чтобы открыть меню заново."],
                ),
                action="employer_contact_invalid_key",
                parse_mode="Markdown",
            )

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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=self._build_employer_submit_status_message(
                        title="Профиль не найден",
                        status_line="⚠️ Профиль работодателя не найден.",
                        details=["Нажми `/start`, чтобы начать заново."],
                    ),
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_not_found"}
        except EmployerGatewayError as exc:
            logger.warning(
                "employer contact edit load failed",
                extra={"telegram_user_id": actor.id, "contact_key": contact_key},
                exc_info=exc,
            )
            return await self._clear_employer_submit_state_and_handle_gateway_error(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                exc=exc,
            )

        existing_contacts = dict(employer.contacts or {})
        if raw_value is None:
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
                return {"status": "processed", "action": "employer_contact_invalid"}
            existing_contacts[contact_key] = normalized

        has_any_contact = any(
            isinstance(value, str) and value.strip() for value in existing_contacts.values()
        )
        contacts_payload: dict[str, str | None] | None = (
            existing_contacts if has_any_contact else None
        )

        try:
            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation=f"employer.contact.update.{contact_key}",
                resource_id=employer.id,
            )
            updated = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.update_employer(
                    access_token=token,
                    employer_id=employer.id,
                    contacts=contacts_payload,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer contact edit update failed",
                extra={"telegram_user_id": actor.id, "contact_key": contact_key},
                exc_info=exc,
            )
            return await self._clear_employer_submit_state_and_handle_gateway_error(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                exc=exc,
            )

        return await self._finish_employer_submit_success(
            telegram_user_id=actor.id,
            actor=actor,
            chat_id=chat_id,
            access_token=access_token,
            employer=updated,
            action=f"employer_edit_contact_{contact_key}_saved",
        )
