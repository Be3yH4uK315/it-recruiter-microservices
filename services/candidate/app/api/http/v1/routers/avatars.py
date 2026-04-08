from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.http.v1.dependencies import (
    get_avatar_upload_url_handler,
    get_delete_avatar_handler,
    get_replace_avatar_handler,
)
from app.application.candidates.commands.delete_avatar import (
    DeleteAvatarCommand,
    DeleteAvatarHandler,
)
from app.application.candidates.commands.replace_avatar import (
    ReplaceAvatarCommand,
    ReplaceAvatarHandler,
)
from app.application.candidates.queries.get_avatar_upload_url import (
    GetAvatarUploadUrlHandler,
    GetAvatarUploadUrlQuery,
)
from app.infrastructure.auth.internal import CandidateSubject, require_candidate_subject
from app.schemas.candidate import ReplaceFileRequest, UploadUrlRequest, UploadUrlResponse

router = APIRouter(
    prefix="/candidates/{candidate_id}/avatar",
    tags=["avatars"],
)


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_avatar_upload_url(
    candidate_id: UUID,
    payload: UploadUrlRequest,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: GetAvatarUploadUrlHandler = Depends(get_avatar_upload_url_handler),
) -> UploadUrlResponse:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(
        GetAvatarUploadUrlQuery(
            candidate_id=candidate_id,
            filename=payload.filename,
            content_type=payload.content_type,
        )
    )
    return UploadUrlResponse.from_result(result)


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
async def replace_avatar(
    candidate_id: UUID,
    payload: ReplaceFileRequest,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: ReplaceAvatarHandler = Depends(get_replace_avatar_handler),
) -> Response:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    await handler(
        ReplaceAvatarCommand(
            candidate_id=candidate_id,
            file_id=payload.file_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    candidate_id: UUID,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: DeleteAvatarHandler = Depends(get_delete_avatar_handler),
) -> Response:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    await handler(DeleteAvatarCommand(candidate_id=candidate_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
