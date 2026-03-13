import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import httpx
import structlog
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.circuit_breaker import CircuitBreakerOpenException, employer_service_breaker
from app.core.config import settings
from app.core.resources import resources
from app.repositories.employer import EmployerRepository
from app.schemas import employer as schemas

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
        updated = await self.repo.update(employer_id, update_in)
        if not updated:
            raise HTTPException(status_code=404, detail="Employer not found")
        await self.db.commit()
        await self.db.refresh(updated)
        return updated

    async def create_search_session(
        self, employer_id: UUID, session_in: schemas.SearchSessionCreate
    ):
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
            clean_filters = filters_model.model_dump(mode="json")
        except Exception as e:
            logger.error(f"Error validating filters: {e}")
            clean_filters = session.filters

        search_payload = {
            "session_id": str(session_id),
            "filters": clean_filters,
            "session_exclude_ids": [str(uid) for uid in viewed_ids],
        }

        try:
            search_url = f"{settings.SEARCH_SERVICE_URL}/search/next"

            async def _call_search():
                return await resources.http_client.post(search_url, json=search_payload)

            resp = await employer_service_breaker.call(_call_search)

            if resp.status_code == 404:
                return schemas.NextCandidateResponse(message="Search unavailable")
            if resp.status_code == 422:
                logger.error(f"Search 422: {resp.text}")
                return schemas.NextCandidateResponse(message="Invalid search criteria")

            resp.raise_for_status()
            search_data = resp.json()

            found_candidate_preview = search_data.get("candidate")

            if not found_candidate_preview:
                return schemas.NextCandidateResponse(
                    message="No more candidates found matching criteria."
                )

            candidate_id = found_candidate_preview["id"]
            match_score = found_candidate_preview.get("match_score", 0.0)

            employer = await self.repo.get_by_id(session.employer_id)

            full_profile = await employer_service_breaker.call(
                self._fetch_full_candidate_profile, candidate_id, employer.telegram_id
            )

            if not full_profile:
                logger.warning(f"Candidate {candidate_id} found in search but not in DB.")
                return schemas.NextCandidateResponse(candidate=found_candidate_preview)

            full_profile["match_score"] = match_score
            if "explanation" in found_candidate_preview:
                full_profile["explanation"] = found_candidate_preview["explanation"]

            return schemas.NextCandidateResponse(candidate=full_profile)

        except CircuitBreakerOpenException:
            logger.warning("Circuit Breaker is OPEN. Search/Candidate services are down.")
            raise HTTPException(status_code=503, detail="Services temporarily unavailable")
        except httpx.RequestError as e:
            logger.error(f"External Service request failed: {e}")
            raise HTTPException(status_code=503, detail="Service unavailable")

    async def submit_decision(self, session_id: UUID, decision_in: schemas.DecisionCreate):
        decision = await self.repo.create_decision(session_id, decision_in)
        await self.db.commit()
        return decision

    async def request_contact(self, employer_id: UUID, request_in: schemas.ContactsRequestCreate):
        employer = await self.repo.get_by_id(employer_id)
        employer_tg_id = employer.telegram_id

        existing_req = await self.repo.get_contact_request(employer_id, request_in.candidate_id)
        if existing_req and existing_req.granted:
            cand_info = await employer_service_breaker.call(
                self._fetch_full_candidate_profile, request_in.candidate_id, employer_tg_id
            )
            return schemas.ContactDetailsResponse(
                granted=True, contacts=cand_info.get("contacts") if cand_info else None
            )

        cand_info = await employer_service_breaker.call(
            self._fetch_full_candidate_profile, request_in.candidate_id, employer_tg_id
        )

        if not cand_info:
            raise HTTPException(status_code=404, detail="Candidate not found")

        visibility = cand_info.get("contacts_visibility", "on_request")
        candidate_tg_id = cand_info.get("telegram_id")
        granted = visibility == "public"

        req = await self.repo.create_contact_request(employer_id, request_in, granted)
        await self.db.commit()

        if granted:
            return schemas.ContactDetailsResponse(granted=True, contacts=cand_info.get("contacts"))

        if not granted and candidate_tg_id:
            return {
                "granted": False,
                "notification_info": {
                    "candidate_telegram_id": candidate_tg_id,
                    "employer_company": employer.company or "Неизвестная компания",
                    "request_id": str(req.id),
                },
            }

        return schemas.ContactDetailsResponse(granted=False)

    async def check_access(self, employer_tg_id: int, candidate_id: UUID) -> bool:
        employer = await self.repo.get_by_telegram_id(employer_tg_id)
        if not employer:
            return False
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

        cand_info = await employer_service_breaker.call(
            self._fetch_full_candidate_profile, req.candidate_id, employer_tg_id
        )
        cand_name = cand_info.get("display_name", "Кандидат") if cand_info else "Кандидат"

        return {
            "id": req.id,
            "employer_telegram_id": employer_tg_id,
            "candidate_name": cand_name,
            "candidate_id": req.candidate_id,
        }

    async def get_favorites(self, employer_id: UUID) -> list[dict]:
        employer = await self.repo.get_by_id(employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")

        candidate_ids = await self.repo.get_favorites(employer_id)
        if not candidate_ids:
            return []

        tasks = [
            employer_service_breaker.call(
                self._fetch_full_candidate_profile, cid, employer.telegram_id
            )
            for cid in candidate_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_profiles = [r for r in results if isinstance(r, dict)]
        return valid_profiles

    async def get_unlocked_contacts(self, employer_id: UUID) -> list[dict]:
        employer = await self.repo.get_by_id(employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")

        candidate_ids = await self.repo.get_unlocked_contacts(employer_id)
        if not candidate_ids:
            return []

        tasks = [
            employer_service_breaker.call(
                self._fetch_full_candidate_profile, cid, employer.telegram_id
            )
            for cid in candidate_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_profiles = [r for r in results if isinstance(r, dict)]
        return valid_profiles

    async def get_employer_sessions(self, employer_id: UUID) -> list[schemas.SearchSession]:
        employer = await self.repo.get_by_id(employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        return await self.repo.get_sessions_by_employer(employer_id)

    async def get_employer_statistics(
        self, employer_id: UUID
    ) -> schemas.EmployerStatisticsResponse:
        employer = await self.repo.get_by_id(employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        stats = await self.repo.get_statistics(employer_id)
        return schemas.EmployerStatisticsResponse(**stats)

    async def get_candidate_statistics(
        self, candidate_id: UUID
    ) -> schemas.CandidateStatisticsResponse:
        stats = await self.repo.get_candidate_statistics(candidate_id)
        return schemas.CandidateStatisticsResponse(**stats)

    def _create_system_token(self, employer_tg_id: int) -> str:
        payload = {
            "sub": "system-employer-service",
            "role": "employer",
            "tg_id": employer_tg_id,
            "exp": datetime.utcnow() + timedelta(minutes=5),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    async def _fetch_full_candidate_profile(
        self, candidate_id: str | UUID, employer_tg_id: int
    ) -> dict | None:
        url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/{candidate_id}"

        token = self._create_system_token(employer_tg_id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await resources.http_client.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
