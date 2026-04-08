from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.v1.dependencies import get_app_settings, get_db_session
from app.config import Settings
from app.infrastructure.db.models.bot import ConversationStateModel

router = APIRouter(prefix="/internal", tags=["internal"])


def _require_internal_service(
    authorization: str | None,
    settings: Settings,
) -> None:
    if not settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service token is not configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal bearer token",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal bearer token",
        )


@router.get("/state/{telegram_user_id}")
async def get_state(
    telegram_user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    _require_internal_service(authorization, settings)

    stmt = select(ConversationStateModel).where(
        ConversationStateModel.telegram_user_id == telegram_user_id
    )
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()

    return {
        "telegram_user_id": telegram_user_id,
        "state": {
            "role_context": state.role_context if state else None,
            "state_key": state.state_key if state else None,
            "state_version": state.state_version if state else None,
            "payload": state.payload if state else None,
            "updated_at": state.updated_at.isoformat() if state else None,
        },
        "request_id": getattr(request.state, "request_id", None),
    }
