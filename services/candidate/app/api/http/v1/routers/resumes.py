from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.http.v1.dependencies import (
    get_delete_resume_handler,
    get_replace_resume_handler,
    get_resume_upload_url_handler,
)
from app.application.candidates.commands.delete_resume import (
    DeleteResumeCommand,
    DeleteResumeHandler,
)
from app.application.candidates.commands.replace_resume import (
    ReplaceResumeCommand,
    ReplaceResumeHandler,
)
from app.application.candidates.queries.get_resume_upload_url import (
    GetResumeUploadUrlHandler,
    GetResumeUploadUrlQuery,
)
from app.infrastructure.auth.internal import CandidateSubject, require_candidate_subject
from app.schemas.candidate import ReplaceFileRequest, UploadUrlRequest, UploadUrlResponse

router = APIRouter(
    prefix="/candidates/{candidate_id}/resume",
    tags=["resumes"],
)


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_resume_upload_url(
    candidate_id: UUID,
    payload: UploadUrlRequest,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: GetResumeUploadUrlHandler = Depends(get_resume_upload_url_handler),
) -> UploadUrlResponse:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    result = await handler(
        GetResumeUploadUrlQuery(
            candidate_id=candidate_id,
            filename=payload.filename,
            content_type=payload.content_type,
        )
    )
    return UploadUrlResponse.from_result(result)


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
async def replace_resume(
    candidate_id: UUID,
    payload: ReplaceFileRequest,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: ReplaceResumeHandler = Depends(get_replace_resume_handler),
) -> Response:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    await handler(
        ReplaceResumeCommand(
            candidate_id=candidate_id,
            file_id=payload.file_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    candidate_id: UUID,
    subject: CandidateSubject = Depends(require_candidate_subject),
    handler: DeleteResumeHandler = Depends(get_delete_resume_handler),
) -> Response:
    if candidate_id != subject.candidate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="candidate access denied",
        )

    await handler(DeleteResumeCommand(candidate_id=candidate_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
