from __future__ import annotations

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
    STATE_CANDIDATE_FILE_AWAIT_RESUME,
    STATE_EMPLOYER_FILE_AWAIT_AVATAR,
    STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
)
from app.application.observability.logging import get_logger

logger = get_logger(__name__)


class RecoveryHandlersMixin:
    async def _recover_pending_uploads_for_role(
        self,
        *,
        telegram_user_id: int,
        role: str,
        chat_id: int,
    ) -> None:
        hanging_uploads = await self._pending_upload_repo.list_non_terminal_for_user(
            telegram_user_id=telegram_user_id,
            role_context=role,
            limit=10,
        )

        recovered_kinds: list[str] = []
        for model in hanging_uploads:
            recovered_kinds.append(str(model.target_kind))
            await self._pending_upload_repo.set_status(
                model=model,
                status="failed",
                error_message="Загрузка была прервана. Повтори отправку файла из меню.",
            )

        state_reset = False
        state = await self._conversation_state_service.get_state(telegram_user_id=telegram_user_id)
        file_states_by_role = {
            ROLE_CANDIDATE: {STATE_CANDIDATE_FILE_AWAIT_AVATAR, STATE_CANDIDATE_FILE_AWAIT_RESUME},
            ROLE_EMPLOYER: {STATE_EMPLOYER_FILE_AWAIT_AVATAR, STATE_EMPLOYER_FILE_AWAIT_DOCUMENT},
        }
        file_states = file_states_by_role.get(role, set())
        if state is not None and state.state_key in file_states:
            await self._conversation_state_service.clear_state(telegram_user_id=telegram_user_id)
            state_reset = True

        if not recovered_kinds and not state_reset:
            return

        logger.info(
            "pending uploads recovered",
            extra={
                "telegram_user_id": telegram_user_id,
                "role": role,
                "recovered_uploads_count": len(recovered_kinds),
                "state_reset": state_reset,
            },
        )

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_pending_upload_recovery_message(
                role=role,
                recovered_kinds=recovered_kinds,
                state_reset=state_reset,
            ),
        )
