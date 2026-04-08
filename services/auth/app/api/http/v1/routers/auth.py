from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.http.v1.dependencies import (
    get_current_user_id,
    get_login_via_bot_handler,
    get_login_via_telegram_handler,
    get_logout_all_handler,
    get_logout_handler,
    get_refresh_session_handler,
    get_user_by_id_handler,
)
from app.application.auth.commands.login_via_bot import LoginViaBotCommand, LoginViaBotHandler
from app.application.auth.commands.login_via_telegram import (
    LoginViaTelegramCommand,
    LoginViaTelegramHandler,
)
from app.application.auth.commands.logout import LogoutCommand, LogoutHandler
from app.application.auth.commands.logout_all import LogoutAllCommand, LogoutAllHandler
from app.application.auth.commands.refresh_session import (
    RefreshSessionCommand,
    RefreshSessionHandler,
)
from app.application.auth.dto.views import AuthSessionView, UserView
from app.application.auth.queries.get_user_by_id import GetUserByIdHandler
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.auth import (
    AuthSessionResponseSchema,
    BotLoginRequestSchema,
    LogoutRequestSchema,
    RefreshRequestSchema,
    TelegramLoginRequestSchema,
    UserResponseSchema,
    UserRolesResponseSchema,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login/bot",
    response_model=AuthSessionResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
async def login_via_bot(
    request: BotLoginRequestSchema,
    handler: LoginViaBotHandler = Depends(get_login_via_bot_handler),
) -> AuthSessionView:
    command = LoginViaBotCommand(
        telegram_id=request.telegram_id,
        role=request.role,
        username=request.username,
        first_name=request.first_name,
        last_name=request.last_name,
        photo_url=request.photo_url,
    )
    return await handler(command)


@router.post(
    "/login/telegram",
    response_model=AuthSessionResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def login_via_telegram(
    request: TelegramLoginRequestSchema,
    handler: LoginViaTelegramHandler = Depends(get_login_via_telegram_handler),
) -> AuthSessionView:
    command = LoginViaTelegramCommand(
        role=request.role,
        auth_payload=request.auth_payload.model_dump(exclude_none=True),
    )
    return await handler(command)


@router.post(
    "/refresh",
    response_model=AuthSessionResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def refresh_session(
    request: RefreshRequestSchema,
    handler: RefreshSessionHandler = Depends(get_refresh_session_handler),
) -> AuthSessionView:
    command = RefreshSessionCommand(refresh_token=request.refresh_token)
    return await handler(command)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def logout(
    request: LogoutRequestSchema,
    handler: LogoutHandler = Depends(get_logout_handler),
) -> Response:
    await handler(LogoutCommand(refresh_token=request.refresh_token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/logout/all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def logout_all(
    current_user_id: UUID = Depends(get_current_user_id),
    handler: LogoutAllHandler = Depends(get_logout_all_handler),
) -> Response:
    await handler(LogoutAllCommand(user_id=current_user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user_id: UUID = Depends(get_current_user_id),
    handler: GetUserByIdHandler = Depends(get_user_by_id_handler),
) -> UserView:
    user = await handler(current_user_id)
    return UserView.from_domain(user)


@router.get(
    "/me/roles",
    response_model=UserRolesResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def get_my_roles(
    current_user_id: UUID = Depends(get_current_user_id),
    handler: GetUserByIdHandler = Depends(get_user_by_id_handler),
) -> dict[str, object]:
    user = await handler(current_user_id)
    return UserView.from_domain(user).to_roles_dict()
