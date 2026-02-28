from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from jose import jwt
import httpx
import logging

from app.models import candidate as models
from app.schemas import candidate as schemas
from app.repositories.candidate import CandidateRepository
from app.repositories.outbox import OutboxRepository
from app.core.circuit_breaker import employer_service_breaker
from app.core.resources import resources
from app.core.config import settings

logger = logging.getLogger(__name__)

class CandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CandidateRepository(db)
        self.outbox = OutboxRepository(db)
    
    def _create_system_token(self, owner_id: int) -> str:
        """Генерирует токен от имени пользователя для технического вызова."""
        payload = {
            "tg_id": owner_id,
            "role": "system",
            "exp": datetime.utcnow() + timedelta(minutes=1)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    async def _emit_updated_event(
        self,
        candidate: models.Candidate,
        update_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Отправка события изменения в Outbox.
        Это событие слушает Search Service для переиндексации.
        """
        await self.db.refresh(candidate)

        pydantic_candidate = schemas.Candidate.model_validate(candidate)
        routing_key = "candidate.updated.profile"
        
        self.outbox.create(
            routing_key=routing_key,
            message_body=pydantic_candidate.model_dump(mode="json"),
        )

    async def _sanitize_candidate(
        self,
        candidate: models.Candidate,
        viewer_tg_id: Optional[int],
    ) -> models.Candidate:
        """
        Скрывает контакты в зависимости от настроек видимости.
        """
        if viewer_tg_id and candidate.telegram_id == viewer_tg_id:
            return candidate

        self.db.expunge(candidate)

        should_hide = False

        if candidate.contacts_visibility == models.ContactsVisibility.HIDDEN:
            should_hide = True
        elif candidate.contacts_visibility == models.ContactsVisibility.ON_REQUEST:
            if not viewer_tg_id:
                should_hide = True
            else:
                has_access = await self._check_employer_access(
                    candidate.id, viewer_tg_id
                )
                if not has_access:
                    should_hide = True

        if should_hide:
            candidate.contacts = None

        return candidate

    async def _check_employer_access(
        self,
        candidate_id: UUID,
        employer_tg_id: int,
    ) -> bool:
        """
        Межсервисный запрос в Employer Service.
        Использует Circuit Breaker.
        """
        url = f"{settings.EMPLOYER_SERVICE_URL}/internal/access-check"

        async def _call():
            resp = await resources.http_client.get(
                url,
                params={
                    "candidate_id": str(candidate_id),
                    "employer_telegram_id": employer_tg_id,
                },
            )
            if resp.status_code in (403, 404):
                return False
            resp.raise_for_status()
            data = resp.json()
            return data.get("granted", False)

        try:
            return await employer_service_breaker.call(_call)
        except Exception:
            return False

    async def _ensure_owner(self, candidate_id: UUID, user_tg_id: Optional[int]):
        """Проверка прав на редактирование."""
        if user_tg_id is None:
            raise HTTPException(status_code=401, detail="Authentication required")

        candidate = await self.repo.get_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        if candidate.telegram_id != user_tg_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        return candidate

    async def create_candidate(self, candidate_in: schemas.CandidateCreate) -> models.Candidate:
        try:
            new_candidate = await self.repo.create(candidate_in)
            await self.db.flush()

            self.outbox.create(
                routing_key="candidate.created",
                message_body={
                    "id": str(new_candidate.id),
                    "telegram_id": new_candidate.telegram_id,
                    "payload": candidate_in.model_dump(mode="json")
                },
            )

            await self.db.commit()
            await self.db.refresh(new_candidate)
            return new_candidate
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail="Candidate already exists")

    async def get_candidate_by_id(self, candidate_id: UUID, viewer_tg_id: Optional[int] = None) -> models.Candidate:
        candidate = await self.repo.get_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        if candidate.status == models.Status.BLOCKED:
            if not viewer_tg_id or candidate.telegram_id != viewer_tg_id:
                raise HTTPException(status_code=404, detail="Candidate not found")

        return await self._sanitize_candidate(candidate, viewer_tg_id)

    async def get_candidate_by_telegram(self, telegram_id: int) -> models.Candidate:
        candidate = await self.repo.get_by_telegram_id(telegram_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return candidate

    async def update_candidate(
        self, candidate_id: UUID, candidate_in: schemas.CandidateUpdate
    ) -> models.Candidate:
        candidate = await self.repo.get_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        update_data = candidate_in.model_dump(exclude_unset=True)

        if "status" in update_data and candidate.status == models.Status.BLOCKED:
             if update_data["status"] == models.Status.ACTIVE:
                 raise HTTPException(status_code=403, detail="Cannot unblock yourself")

        scalar_fields = [
            "display_name", "headline_role", "location", "work_modes", 
            "contacts_visibility", "contacts", "status", 
            "salary_min", "salary_max", "currency",
            "english_level", "about_me"
        ]
        for field in scalar_fields:
            if field in update_data:
                setattr(candidate, field, update_data[field])

        if "skills" in update_data:
            await self.repo.sync_skills(candidate, candidate_in.skills)
        if "projects" in update_data:
            await self.repo.replace_projects(candidate, candidate_in.projects)
        if "experiences" in update_data:
            await self.repo.replace_experiences(candidate, candidate_in.experiences)
        if "education" in update_data:
            await self.repo.replace_education(candidate, candidate_in.education)

        await self.db.flush()

        await self._emit_updated_event(candidate, update_data)
        
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate

    async def get_resume_upload_url(self, telegram_id: int, filename: str, content_type: str):
        candidate = await self.get_candidate_by_telegram(telegram_id)
        
        url = f"{settings.FILE_SERVICE_URL}/files/resume/upload-url"
        payload = {"owner_id": str(candidate.id), "filename": filename, "content_type": content_type}
        
        try:
            resp = await resources.http_client.post(url, json=payload)
            resp.raise_for_status()
            return schemas.ResumeUploadResponse(**resp.json())
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"File service error: {e}")

    async def update_resume(self, telegram_id: int, resume_in: schemas.ResumeCreate):
        candidate = await self.get_candidate_by_telegram(telegram_id)
        old_id = await self.repo.replace_resume(candidate, resume_in.file_id)
        
        await self.db.flush()
        await self._emit_updated_event(candidate, {"resumes": True})
        
        if old_id:
            self.outbox.create(routing_key="file.resume.deleted", message_body={"file_id": str(old_id)})
            
        await self.db.commit()
        await self.db.refresh(candidate, attribute_names=["resumes"])
        return candidate.resumes[0]
    
    async def delete_resume(self, telegram_id: int):
        candidate = await self.get_candidate_by_telegram(telegram_id)
        
        deleted_file_id = await self.repo.delete_resume(candidate)
        if not deleted_file_id:
            raise HTTPException(status_code=404, detail="Resume not found")

        await self._delete_file_from_storage(deleted_file_id, telegram_id)

        await self.db.flush()
        await self._emit_updated_event(candidate, {"resumes": True})
        
        self.outbox.create(routing_key="file.resume.deleted", message_body={"file_id": str(deleted_file_id)})
        
        await self.db.commit()

    async def update_avatar(self, telegram_id: int, avatar_in: schemas.AvatarCreate):
        logger.info(f"Updating avatar for tg_id={telegram_id}")
        candidate = await self.get_candidate_by_telegram(telegram_id)
        
        if candidate.avatars:
            await self._delete_file_from_storage(candidate.avatars[0].file_id, telegram_id)

        await self.repo.replace_avatar(candidate, avatar_in.file_id)
        
        await self.db.flush()
        await self.db.refresh(candidate, attribute_names=["avatars"])
        
        await self._emit_updated_event(candidate, {"avatars": True})
        
        await self.db.commit()
        
        logger.info(f"Avatar updated. New ID: {candidate.avatars[0].id}")
        return candidate.avatars[0]

    async def delete_avatar(self, telegram_id: int):
        candidate = await self.get_candidate_by_telegram(telegram_id)
        deleted_file_id = await self.repo.delete_avatar(candidate)
        
        if not deleted_file_id:
            raise HTTPException(status_code=404, detail="Avatar not found")

        await self._delete_file_from_storage(deleted_file_id, telegram_id)

        await self.db.flush()
        await self._emit_updated_event(candidate, {"avatars": True})
        self.outbox.create(routing_key="file.avatar.deleted", message_body={"file_id": str(deleted_file_id)})
        await self.db.commit()

    async def _delete_file_from_storage(self, file_id: UUID, owner_telegram_id: int):
        """
        Прямой вызов File Service для удаления.
        """
        url = f"{settings.FILE_SERVICE_URL}/files/{file_id}"
        token = self._create_system_token(owner_telegram_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = await resources.http_client.delete(url, headers=headers)
            
            if resp.status_code != 404:
                resp.raise_for_status()
                
        except Exception as e:
            logger.error(f"Failed to delete file {file_id} from storage: {e}")