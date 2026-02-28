from fastapi import APIRouter, Depends, status, HTTPException
from uuid import UUID

from app.api.v1 import dependencies
from app.services.employer import EmployerService
from app.schemas import employer as schemas

router = APIRouter()

@router.post("/", response_model=schemas.Employer, status_code=status.HTTP_201_CREATED)
async def create_employer(
    employer: schemas.EmployerCreate, 
    service: EmployerService = Depends(dependencies.get_service),
    user_id: int = Depends(dependencies.get_current_user_tg_id)
):
    if employer.telegram_id != user_id:
        raise HTTPException(status_code=403, detail="ID mismatch")
    return await service.register_employer(employer)

@router.patch("/{employer_id}", response_model=schemas.Employer)
async def update_employer(
    employer_id: UUID,
    employer_update: schemas.EmployerUpdate,
    service: EmployerService = Depends(dependencies.get_service)
):
    """Обновление профиля (название компании и др.)"""
    return await service.update_profile(employer_id, employer_update)

@router.post("/{employer_id}/searches", response_model=schemas.SearchSession)
async def create_search_session(
    employer_id: UUID, 
    session: schemas.SearchSessionCreate, 
    service: EmployerService = Depends(dependencies.get_service)
):
    return await service.create_search_session(employer_id, session)

@router.post("/searches/{session_id}/next", response_model=schemas.NextCandidateResponse)
async def get_next_candidate(
    session_id: UUID,
    service: EmployerService = Depends(dependencies.get_service)
):
    return await service.get_next_candidate(session_id)

@router.post("/searches/{session_id}/decisions", response_model=schemas.Decision)
async def make_decision(
    session_id: UUID,
    decision: schemas.DecisionCreate,
    service: EmployerService = Depends(dependencies.get_service)
):
    return await service.submit_decision(session_id, decision)

@router.post("/{employer_id}/contact-requests", response_model=schemas.ContactDetailsResponse)
async def request_contacts(
    employer_id: UUID,
    request: schemas.ContactsRequestCreate,
    service: EmployerService = Depends(dependencies.get_service)
):
    return await service.request_contact(employer_id, request)

@router.put("/contact-requests/{request_id}")
async def respond_to_contact_request(
    request_id: UUID,
    update: schemas.ContactUpdateRequest,
    service: EmployerService = Depends(dependencies.get_service)
):
    success = await service.respond_to_request(request_id, update.granted)
    if not success:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"status": "updated"}

@router.get("/contact-requests/{request_id}/details", response_model=schemas.ContactDetailsRequest)
async def get_contact_request_details(
    request_id: UUID,
    service: EmployerService = Depends(dependencies.get_service)
):
    details = await service.get_request_details(request_id)
    if not details:
        raise HTTPException(status_code=404, detail="Request not found")
    return details

@router.get("/internal/access-check")
async def check_access(
    candidate_id: UUID,
    employer_telegram_id: int,
    service: EmployerService = Depends(dependencies.get_service)
):
    has_access = await service.check_access(employer_telegram_id, candidate_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"granted": True}