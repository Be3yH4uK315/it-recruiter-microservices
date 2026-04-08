from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.http.v1.dependencies import (
    get_delete_employer_document_handler,
    get_employer_document_upload_url_handler,
    get_get_employer_handler,
    get_replace_employer_document_handler,
)
from app.application.employers.commands.delete_employer_document import (
    DeleteEmployerDocumentCommand,
    DeleteEmployerDocumentHandler,
)
from app.application.employers.commands.replace_employer_document import (
    ReplaceEmployerDocumentCommand,
    ReplaceEmployerDocumentHandler,
)
from app.application.employers.queries.get_employer import GetEmployerHandler
from app.application.employers.queries.get_employer_document_upload_url import (
    GetEmployerDocumentUploadUrlHandler,
    GetEmployerDocumentUploadUrlQuery,
)
from app.infrastructure.auth.internal import require_employer_subject
from app.schemas.employer import ReplaceFileRequest, UploadUrlRequest, UploadUrlResponse

router = APIRouter(
    prefix="/employers/{employer_id}/document",
    tags=["employer-document"],
)


@router.post("/upload-url", response_model=UploadUrlResponse)
async def get_employer_document_upload_url(
    employer_id: UUID,
    payload: UploadUrlRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    employer_handler: GetEmployerHandler = Depends(get_get_employer_handler),
    handler: GetEmployerDocumentUploadUrlHandler = Depends(
        get_employer_document_upload_url_handler
    ),
) -> UploadUrlResponse:
    employer = await employer_handler(employer_id)
    if employer.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    result = await handler(
        GetEmployerDocumentUploadUrlQuery(
            employer_id=employer_id,
            filename=payload.filename,
            content_type=payload.content_type,
        )
    )
    return UploadUrlResponse.from_result(result)


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
async def replace_employer_document(
    employer_id: UUID,
    payload: ReplaceFileRequest,
    subject_telegram_id: int = Depends(require_employer_subject),
    employer_handler: GetEmployerHandler = Depends(get_get_employer_handler),
    handler: ReplaceEmployerDocumentHandler = Depends(get_replace_employer_document_handler),
) -> Response:
    employer = await employer_handler(employer_id)
    if employer.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    await handler(
        ReplaceEmployerDocumentCommand(
            employer_id=employer_id,
            file_id=payload.file_id,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employer_document(
    employer_id: UUID,
    subject_telegram_id: int = Depends(require_employer_subject),
    employer_handler: GetEmployerHandler = Depends(get_get_employer_handler),
    handler: DeleteEmployerDocumentHandler = Depends(get_delete_employer_document_handler),
) -> Response:
    employer = await employer_handler(employer_id)
    if employer.telegram_id != subject_telegram_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="employer access denied",
        )

    await handler(DeleteEmployerDocumentCommand(employer_id=employer_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
