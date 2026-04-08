from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.services.auth_session_service import AuthSessionService
from app.application.bot.services.dialog_message_manager import DialogAwareTelegramClient
from app.application.bot.services.dialog_render_state_service import (
    DialogRenderStateService,
)
from app.application.bot.handlers.composite import UpdateRouterHandlers
from app.application.bot.services.deduplication_service import DeduplicationService
from app.application.bot.services.rate_limit_service import RateLimitService
from app.application.candidate.services.file_flow_service import (
    CandidateFileFlowService,
)
from app.application.common.contracts import (
    CandidateGateway,
    EmployerGateway,
)
from app.application.employer.services.file_flow_service import (
    EmployerFileFlowService,
)
from app.application.state.services.conversation_state_service import (
    ConversationStateService,
)
from app.config import Settings
from app.infrastructure.db.repositories.callback_contexts import CallbackContextRepository
from app.infrastructure.db.repositories.pending_uploads import PendingUploadRepository
from app.infrastructure.db.repositories.telegram_actors import TelegramActorRepository
from app.infrastructure.observability.logger import get_logger
from app.infrastructure.observability.metrics import (
    mark_update_processed,
    mark_update_received,
)
from app.infrastructure.telegram.client import TelegramApiClient
from app.schemas.telegram import TelegramUpdate

logger = get_logger(__name__)


class UpdateRouterService(UpdateRouterHandlers):
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        telegram_client: TelegramApiClient,
        auth_session_service: AuthSessionService,
        conversation_state_service: ConversationStateService,
        candidate_gateway: CandidateGateway,
        employer_gateway: EmployerGateway,
        candidate_file_flow_service: CandidateFileFlowService,
        employer_file_flow_service: EmployerFileFlowService,
        rate_limit_service: RateLimitService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._dialog_render_state_service = DialogRenderStateService(session)
        self._telegram_client = DialogAwareTelegramClient(
            base_client=telegram_client,
            render_state_service=self._dialog_render_state_service,
        )
        self._auth_session_service = auth_session_service
        self._conversation_state_service = conversation_state_service
        self._candidate_gateway = candidate_gateway
        self._employer_gateway = employer_gateway
        self._candidate_file_flow_service = candidate_file_flow_service
        self._employer_file_flow_service = employer_file_flow_service
        self._rate_limit_service = rate_limit_service

        self._dedup = DeduplicationService(session)
        self._actor_repo = TelegramActorRepository(session)
        self._callback_repo = CallbackContextRepository(session)
        self._pending_upload_repo = PendingUploadRepository(session)

    async def route(self, update: TelegramUpdate) -> dict:
        update_type = update.detect_update_type()
        actor = update.actor()
        mark_update_received(update_type)
        self._log_flow_event(
            "update_received",
            telegram_user_id=actor.id if actor is not None else None,
            extra={"update_id": update.update_id, "update_type": update_type},
        )

        started = await self._dedup.try_start_processing(
            update_id=update.update_id,
            telegram_user_id=actor.id if actor else None,
            update_type=update_type,
        )
        if not started:
            mark_update_processed(update_type, "duplicate")
            return {"status": "duplicate", "update_id": update.update_id}

        try:
            telegram_client = getattr(self, "_telegram_client", None)
            if actor is not None:
                await self._actor_repo.upsert(
                    telegram_user_id=actor.id,
                    username=actor.username,
                    first_name=actor.first_name,
                    last_name=actor.last_name,
                    language_code=actor.language_code,
                    is_bot=actor.is_bot,
                )

            if update.message is not None:
                begin_message_update = getattr(telegram_client, "begin_message_update", None)
                if callable(begin_message_update):
                    await begin_message_update(message=update.message)
                result = await self._handle_message(update.message)
            elif update.callback_query is not None:
                begin_callback_update = getattr(telegram_client, "begin_callback_update", None)
                if callable(begin_callback_update):
                    await begin_callback_update(callback=update.callback_query)
                result = await self._handle_callback(update.callback_query)
            else:
                result = {
                    "status": "ignored",
                    "update_id": update.update_id,
                    "update_type": update_type,
                }

            finalize_update = getattr(telegram_client, "finalize_update", None)
            if callable(finalize_update):
                await finalize_update()
            await self._dedup.mark_processed(update_id=update.update_id)
            await self._session.commit()
            mark_update_processed(update_type, str(result.get("status", "processed")))

            logger.info(
                "telegram update processed",
                extra={
                    "update_id": update.update_id,
                    "telegram_user_id": actor.id if actor else None,
                    "update_type": update_type,
                },
            )
            return result
        except Exception:
            telegram_client = getattr(self, "_telegram_client", None)
            discard_update = getattr(telegram_client, "discard_update", None)
            if callable(discard_update):
                discard_update()
            await self._session.rollback()
            mark_update_processed(update_type, "failed")
            logger.exception(
                "telegram update processing failed",
                extra={
                    "update_id": update.update_id,
                    "telegram_user_id": actor.id if actor else None,
                    "update_type": update_type,
                },
            )
            raise
