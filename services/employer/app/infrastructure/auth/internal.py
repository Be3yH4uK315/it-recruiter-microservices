from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.api.http.v1.dependencies import (
    get_auth_gateway,
    get_candidate_gateway,
    get_settings_dependency,
)
from app.application.common.contracts import (
    AuthGateway,
    AuthVerifiedSubject,
    CandidateGateway,
)
from app.config import Settings
from app.infrastructure.integrations.auth_gateway import (
    AuthGatewayError,
    AuthGatewayForbiddenError,
    AuthGatewayInvalidTokenError,
    AuthGatewayUnavailableError,
)


def _normalize_header_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _extract_bearer_token(authorization: str | None) -> str | None:
    authorization = _normalize_header_value(authorization)
    if not authorization:
        return None

    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        return None

    token = authorization[len(prefix) :].strip()
    return token or None


@dataclass(slots=True, frozen=True)
class CandidateSubject:
    auth_user_id: UUID
    telegram_id: int
    candidate_id: UUID


async def require_internal_service(
    settings: Settings = Depends(get_settings_dependency),
    authorization: str | None = Header(default=None),
) -> None:
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
    except AuthGatewayInvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        ) from exc
    except AuthGatewayForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden.",
        ) from exc
    except AuthGatewayUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service is unavailable.",
        ) from exc
    except AuthGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to verify access token.",
        ) from exc


async def require_employer_subject(
    subject: AuthVerifiedSubject = Depends(require_verified_subject),
) -> int:
    if not subject.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auth subject is inactive.",
        )

    if "employer" not in subject.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employer role is required.",
        )

    if subject.role != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active role must be employer.",
        )

    return subject.telegram_id


async def require_candidate_subject(
    subject: AuthVerifiedSubject = Depends(require_verified_subject),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
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

    candidate_identity = await candidate_gateway.get_candidate_identity(
        telegram_id=subject.telegram_id,
    )
    if candidate_identity is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate profile is not registered.",
        )

    if candidate_identity.status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate profile is blocked.",
        )

    return CandidateSubject(
        auth_user_id=subject.user_id,
        telegram_id=subject.telegram_id,
        candidate_id=candidate_identity.candidate_id,
    )


async def require_candidate_id(
    subject: CandidateSubject = Depends(require_candidate_subject),
) -> UUID:
    return subject.candidate_id
