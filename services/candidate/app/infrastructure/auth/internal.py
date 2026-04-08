from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.api.http.v1.dependencies import (
    get_auth_gateway,
    get_candidate_by_telegram_handler,
)
from app.application.candidates.queries.get_candidate_by_telegram import (
    GetCandidateByTelegramHandler,
)
from app.application.common.contracts import AuthGateway, AuthVerifiedSubject
from app.domain.candidate.enums import CandidateStatus
from app.domain.candidate.errors import CandidateNotFoundError
from app.infrastructure.integrations.auth_gateway import (
    AuthGatewayProtocolError,
    AuthServiceUnavailableError,
    InvalidAccessTokenGatewayError,
)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        return None

    return authorization[len(prefix) :].strip() or None


@dataclass(slots=True, frozen=True)
class CandidateRegistrationSubject:
    auth_user_id: UUID
    telegram_id: int


@dataclass(slots=True, frozen=True)
class CandidateSubject:
    auth_user_id: UUID
    telegram_id: int
    candidate_id: UUID


async def require_internal_service(
    authorization: str | None = Header(default=None),
) -> None:
    from app.config import get_settings

    settings = get_settings()

    if not settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service authentication is not configured.",
        )

    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal service token. Use Authorization: Bearer <token>.",
        )

    if token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token.",
        )


async def require_verified_subject(
    auth_gateway: AuthGateway = Depends(get_auth_gateway),
    authorization: str | None = Header(default=None),
) -> AuthVerifiedSubject:
    access_token = _extract_bearer_token(authorization)

    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token. Use Authorization: Bearer <access_token>.",
        )

    try:
        return await auth_gateway.verify_access_token(access_token=access_token)
    except InvalidAccessTokenGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        ) from exc
    except (AuthServiceUnavailableError, AuthGatewayProtocolError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service is temporarily unavailable.",
        ) from exc


async def require_candidate_registration_subject(
    subject: AuthVerifiedSubject = Depends(require_verified_subject),
) -> CandidateRegistrationSubject:
    if not subject.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auth subject is inactive.",
        )

    if "candidate" not in subject.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate role is required.",
        )

    if subject.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active role must be candidate.",
        )

    return CandidateRegistrationSubject(
        auth_user_id=subject.user_id,
        telegram_id=subject.telegram_id,
    )


async def require_candidate_subject(
    subject: AuthVerifiedSubject = Depends(require_verified_subject),
    get_candidate_by_telegram_handler: GetCandidateByTelegramHandler = Depends(
        get_candidate_by_telegram_handler
    ),
) -> CandidateSubject:
    if not subject.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auth subject is inactive.",
        )

    if "candidate" not in subject.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate role is required.",
        )

    if subject.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active role must be candidate.",
        )

    try:
        candidate = await get_candidate_by_telegram_handler(subject.telegram_id)
    except CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate profile is not registered.",
        ) from exc

    if candidate.status == CandidateStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate profile is blocked.",
        )

    return CandidateSubject(
        auth_user_id=subject.user_id,
        telegram_id=subject.telegram_id,
        candidate_id=candidate.id,
    )


async def require_candidate_id(
    subject: CandidateSubject = Depends(require_candidate_subject),
) -> UUID:
    return subject.candidate_id
