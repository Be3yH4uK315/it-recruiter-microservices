from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.http.v1.dependencies import (
    get_jwt_service,
    get_user_by_id_handler,
    get_user_by_telegram_id_handler,
)
from app.application.auth.dto.views import UserView
from app.application.auth.queries.get_user_by_id import GetUserByIdHandler
from app.application.auth.queries.get_user_by_telegram_id import GetUserByTelegramIdHandler
from app.application.auth.services.jwt_service import JwtService
from app.domain.auth.value_objects import AccessTokenClaims
from app.infrastructure.auth.internal import require_internal_service
from app.schemas.auth import (
    InternalUserResponseSchema,
    TokenVerificationResponseSchema,
    UserRolesResponseSchema,
    VerifyAccessTokenRequestSchema,
)

router = APIRouter(
    prefix="/internal/auth",
    tags=["internal-auth"],
)


@router.get(
    "/user/{user_id}",
    response_model=InternalUserResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
async def get_user_by_id(
    user_id: UUID,
    handler: GetUserByIdHandler = Depends(get_user_by_id_handler),
) -> InternalUserResponseSchema:
    user = await handler(user_id)
    view = UserView.from_domain(user)
    return InternalUserResponseSchema(**view.to_internal_dict())


@router.get(
    "/user/{user_id}/roles",
    response_model=UserRolesResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
async def get_user_roles(
    user_id: UUID,
    handler: GetUserByIdHandler = Depends(get_user_by_id_handler),
) -> dict[str, object]:
    user = await handler(user_id)
    return UserView.from_domain(user).to_roles_dict()


@router.get(
    "/by-telegram/{telegram_id}",
    response_model=InternalUserResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
async def get_user_by_telegram_id(
    telegram_id: int,
    handler: GetUserByTelegramIdHandler = Depends(get_user_by_telegram_id_handler),
) -> InternalUserResponseSchema:
    user = await handler(telegram_id)
    view = UserView.from_domain(user)
    return InternalUserResponseSchema(**view.to_internal_dict())


@router.post(
    "/verify",
    response_model=TokenVerificationResponseSchema,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
async def verify_access_token(
    request: VerifyAccessTokenRequestSchema,
    jwt_service: JwtService = Depends(get_jwt_service),
    handler: GetUserByIdHandler = Depends(get_user_by_id_handler),
) -> TokenVerificationResponseSchema:
    claims: AccessTokenClaims = jwt_service.decode_access_token(request.access_token)

    user = await handler(UUID(claims.subject))
    view = UserView.from_domain(user)

    return TokenVerificationResponseSchema(
        user_id=view.id,
        telegram_id=view.telegram_id,
        role=view.role,
        roles=list(view.roles),
        is_active=view.is_active,
        expires_at=claims.expires_at,
    )
