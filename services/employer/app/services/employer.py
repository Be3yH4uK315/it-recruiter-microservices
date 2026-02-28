from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional, Dict
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from jose import jwt
import structlog

from app.repositories.employer import EmployerRepository
from app.schemas import employer as schemas
from app.core.resources import resources
from app.core.config import settings

logger = structlog.get_logger()

class EmployerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EmployerRepository(db)

    async def register_employer(self, employer_in: schemas.EmployerCreate):
        existing = await self.repo.get_by_telegram_id(employer_in.telegram_id)
        if existing:
            return existing
        
        employer = await self.repo.create(employer_in)
        await self.db.commit()
        await self.db.refresh(employer)
        return employer

    async def update_profile(self, employer_id: UUID, update_in: schemas.EmployerUpdate):
        """Обновление данных профиля (например, название компании)."""
        updated = await self.repo.update(employer_id, update_in)
        if not updated:
            raise HTTPException(status_code=404, detail="Employer not found")
        await self.db.commit()
        await self.db.refresh(updated)
        return updated

    async def create_search_session(self, employer_id: UUID, session_in: schemas.SearchSessionCreate):
        session = await self.repo.create_session(employer_id, session_in)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_next_candidate(self, session_id: UUID) -> schemas.NextCandidateResponse:
        session = await self.repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        viewed_ids = await self.repo.get_viewed_candidate_ids(session_id)
        
        try:
            filters_model = schemas.SearchFilters(**session.filters)
            clean_filters = filters_model.model_dump(mode='json')
        except Exception as e:
            logger.error(f"Error validating filters: {e}")
            clean_filters = session.filters
        
        search_payload = {
            "session_id": str(session_id),
            "filters": clean_filters,
            "session_exclude_ids": [str(uid) for uid in viewed_ids]
        }
        
        try:
            search_url = f"{settings.SEARCH_SERVICE_URL}/search/next"
            resp = await resources.http_client.post(search_url, json=search_payload)
            
            if resp.status_code == 404:
                return schemas.NextCandidateResponse(message="Search unavailable")
            if resp.status_code == 422:
                logger.error(f"Search 422: {resp.text}")
                return schemas.NextCandidateResponse(message="Invalid search criteria")
                
            resp.raise_for_status()
            search_data = resp.json()
            
            found_candidate_preview = search_data.get("candidate")
            
            if not found_candidate_preview:
                return schemas.NextCandidateResponse(message="No more candidates found matching criteria.")
                
            candidate_id = found_candidate_preview["id"]
            match_score = found_candidate_preview.get("match_score", 0.0)

            employer = await self.repo.get_by_id(session.employer_id)
            full_profile = await self._fetch_full_candidate_profile(candidate_id, employer.telegram_id)
            
            if not full_profile:
                logger.warning(f"Candidate {candidate_id} found in search but not in DB.")
                return schemas.NextCandidateResponse(candidate=found_candidate_preview)

            full_profile["match_score"] = match_score
            if "explanation" in found_candidate_preview:
                full_profile["explanation"] = found_candidate_preview["explanation"]
            
            return schemas.NextCandidateResponse(candidate=full_profile)
            
        except httpx.RequestError as e:
            logger.error(f"Search Service unavailable: {e}")
            raise HTTPException(status_code=503, detail="Search Service unavailable")

    async def submit_decision(self, session_id: UUID, decision_in: schemas.DecisionCreate):
        decision = await self.repo.create_decision(session_id, decision_in)
        await self.db.commit()
        return decision

    async def request_contact(self, employer_id: UUID, request_in: schemas.ContactsRequestCreate):
        employer = await self.repo.get_by_id(employer_id)
        employer_tg_id = employer.telegram_id

        existing_req = await self.repo.get_contact_request(employer_id, request_in.candidate_id)
        if existing_req and existing_req.granted:
            contacts_resp = await self._fetch_contacts(request_in.candidate_id, employer_tg_id)
            return contacts_resp

        cand_info = await self._fetch_full_candidate_profile(request_in.candidate_id, employer_tg_id)
        visibility = "on_request"
        if cand_info:
            visibility = cand_info.get("contacts_visibility", "on_request")
        
        candidate_tg_id = cand_info.get("telegram_id")
        employer = await self.repo.get_by_id(employer_id)
        
        granted = (visibility == "public")
        
        req = await self.repo.create_contact_request(employer_id, request_in, granted)
        await self.db.commit()

        if granted:
            contacts_resp = await self._fetch_contacts(request_in.candidate_id, employer_tg_id)
            return contacts_resp
        
        if not granted and candidate_tg_id:
            return {
                "granted": False,
                "notification_info": {
                    "candidate_telegram_id": candidate_tg_id,
                    "employer_company": employer.company or "Неизвестная компания",
                    "request_id": str(req.id)
                }
            }
            
        return schemas.ContactDetailsResponse(granted=False)

    async def check_access(self, employer_tg_id: int, candidate_id: UUID) -> bool:
        employer = await self.repo.get_by_telegram_id(employer_tg_id)
        if not employer: return False
        req = await self.repo.get_contact_request(employer.id, candidate_id)
        return bool(req and req.granted)
    
    async def respond_to_request(self, request_id: UUID, granted: bool):
        success = await self.repo.update_contact_request_status(request_id, granted)
        await self.db.commit()
        return success
    
    async def get_request_details(self, request_id: UUID):
        res = await self.repo.get_request_with_employer_tg(request_id)
        if not res:
            return None
        
        req, employer_tg_id = res
        
        cand_info = await self._fetch_full_candidate_profile(req.candidate_id, employer_tg_id)
        cand_name = cand_info.get("display_name", "Кандидат") if cand_info else "Кандидат"
        
        return {
            "id": req.id,
            "employer_telegram_id": employer_tg_id,
            "candidate_name": cand_name,
            "candidate_id": req.candidate_id
        }
    
    def _create_system_token(self, employer_tg_id: int) -> str:
        """Генерирует токен для межсервисного общения."""
        payload = {
            "sub": "system-employer-service",
            "role": "employer",
            "tg_id": employer_tg_id, 
            "exp": datetime.utcnow() + timedelta(minutes=5)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        
    async def _fetch_full_candidate_profile(self, candidate_id: str | UUID, employer_tg_id: int) -> Optional[Dict]:
        url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/{candidate_id}"

        token = self._create_system_token(employer_tg_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = await resources.http_client.get(url, headers=headers)
            if resp.status_code == 404: 
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch candidate profile {candidate_id}: {e}")
            return None

    async def _fetch_contacts(self, candidate_id: UUID, employer_tg_id: int) -> schemas.ContactDetailsResponse:
        profile = await self._fetch_full_candidate_profile(str(candidate_id), employer_tg_id)
        contacts = profile.get("contacts") if profile else None
        return schemas.ContactDetailsResponse(granted=True, contacts=contacts)
