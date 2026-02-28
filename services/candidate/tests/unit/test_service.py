from unittest.mock import AsyncMock
import pytest
from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException
from app.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateSkillCreate
from app.models import candidate as models

def make_db_candidate(telegram_id=12345, uid=None):
    """
    Создает мок ORM модели с полным набором полей,
    чтобы Pydantic model_validate не падал.
    """
    return models.Candidate(
        id=uid or uuid4(),
        telegram_id=telegram_id,
        display_name="Test User",
        headline_role="Developer",
        status=models.Status.ACTIVE,
        contacts_visibility=models.ContactsVisibility.PUBLIC,
        contacts={},
        work_modes=["remote"],
        education=[],
        skills=[],
        projects=[],
        experiences=[],
        avatars=[],
        resumes=[],
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

@pytest.mark.asyncio
async def test_create_candidate_success(candidate_service, mock_candidate_repo, mock_outbox_repo):
    """Тест успешного создания кандидата и записи в Outbox."""
    payload = CandidateCreate(
        telegram_id=100,
        display_name="New User",
        headline_role="Dev",
        contacts={}
    )
    created_obj = make_db_candidate(telegram_id=100)
    mock_candidate_repo.create.return_value = created_obj
    result = await candidate_service.create_candidate(payload)

    assert result.telegram_id == 100
    mock_candidate_repo.create.assert_called_once_with(payload)
    mock_outbox_repo.create.assert_called_once()
    
    call_args = mock_outbox_repo.create.call_args[1]
    assert call_args['routing_key'] == "candidate.created"

@pytest.mark.asyncio
async def test_update_candidate_success(candidate_service, mock_candidate_repo, mock_outbox_repo):
    """Тест обновления профиля (скалярные поля)."""
    uid = uuid4()
    existing_cand = make_db_candidate(uid=uid)
    mock_candidate_repo.get_by_id.return_value = existing_cand
    
    update_payload = CandidateUpdate(display_name="Updated Name")
    
    result = await candidate_service.update_candidate(uid, update_payload)

    assert result.display_name == "Updated Name"
    
    mock_outbox_repo.create.assert_called()
    assert mock_outbox_repo.create.call_args[1]['routing_key'] == "candidate.updated.profile"

@pytest.mark.asyncio
async def test_update_candidate_with_skills(candidate_service, mock_candidate_repo):
    """Тест обновления вложенных списков (skills)."""
    uid = uuid4()
    existing_cand = make_db_candidate(uid=uid)
    mock_candidate_repo.get_by_id.return_value = existing_cand
    
    new_skills = [CandidateSkillCreate(skill="Python", kind="hard", level=5)]
    update_payload = CandidateUpdate(skills=new_skills)
    
    await candidate_service.update_candidate(uid, update_payload)
    
    mock_candidate_repo.sync_skills.assert_called_once_with(existing_cand, new_skills)

@pytest.mark.asyncio
async def test_update_candidate_not_found(candidate_service, mock_candidate_repo):
    """Тест ошибки 404 при обновлении."""
    mock_candidate_repo.get_by_id.return_value = None
    
    with pytest.raises(HTTPException) as exc:
        await candidate_service.update_candidate(uuid4(), CandidateUpdate(display_name="X"))
    
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_candidate_hides_contacts(candidate_service, mock_candidate_repo):
    """Тест скрытия контактов (GDPR/Privacy)."""
    cand = make_db_candidate()
    cand.contacts = {"phone": "123"}
    cand.contacts_visibility = models.ContactsVisibility.HIDDEN
    
    mock_candidate_repo.get_by_id.return_value = cand
    
    result = await candidate_service.get_candidate_by_id(cand.id, viewer_tg_id=999)
    
    assert result.contacts is None

@pytest.mark.asyncio
async def test_get_resume_upload_url(candidate_service, mock_candidate_repo):
    """Тест получения ссылки на загрузку (проксирование)."""
    from unittest.mock import MagicMock
    from app.core.resources import resources

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "upload_url": "http://s3/...", "object_key": "key", "expires_in": 3600
    }
    mock_client.post.return_value = mock_response
    resources.http_client = mock_client
    
    cand = make_db_candidate()
    mock_candidate_repo.get_by_telegram_id.return_value = cand
    
    result = await candidate_service.get_resume_upload_url(12345, "cv.pdf", "application/pdf")
    
    assert result.upload_url == "http://s3/..."
    mock_client.post.assert_called_once()
    args = mock_client.post.call_args
    assert "/files/resume/upload-url" in args[0][0]

@pytest.mark.asyncio
async def test_update_resume_success(candidate_service, mock_candidate_repo, mock_outbox_repo):
    """Тест привязки резюме к профилю."""
    cand = make_db_candidate()
    mock_candidate_repo.get_by_telegram_id.return_value = cand
    mock_candidate_repo.replace_resume.return_value = uuid4()
    
    async def side_effect_refresh(obj, attribute_names=None):
        from app.models.candidate import Resume
        from datetime import datetime
        
        obj.resumes = [
            Resume(
                id=uuid4(), 
                file_id=uuid4(), 
                candidate_id=obj.id,
                created_at=datetime.now()
            )
        ]
    
    candidate_service.db.refresh.side_effect = side_effect_refresh

    from app.schemas.candidate import ResumeCreate
    payload = ResumeCreate(file_id=uuid4())
    
    result = await candidate_service.update_resume(12345, payload)
    
    assert result is not None
    mock_outbox_repo.create.assert_called()

@pytest.mark.asyncio
async def test_delete_resume_success(candidate_service, mock_candidate_repo, mock_outbox_repo):
    """Тест удаления резюме (БД + S3)."""
    from unittest.mock import MagicMock
    from app.core.resources import resources
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_client.delete.return_value = mock_response
    resources.http_client = mock_client

    cand = make_db_candidate()
    mock_candidate_repo.get_by_telegram_id.return_value = cand
    mock_candidate_repo.delete_resume.return_value = uuid4()

    await candidate_service.delete_resume(12345)

    mock_candidate_repo.delete_resume.assert_called_once()
    mock_client.delete.assert_called_once()
    mock_outbox_repo.create.assert_called()

@pytest.mark.asyncio
async def test_update_avatar_success(candidate_service, mock_candidate_repo):
    """Тест обновления аватара."""
    from unittest.mock import MagicMock
    from app.core.resources import resources
    mock_client = AsyncMock()
    mock_client.delete.return_value = MagicMock(status_code=204)
    resources.http_client = mock_client

    cand = make_db_candidate()
    avatar_mock = MagicMock()
    avatar_mock.file_id = uuid4()
    cand.avatars = [avatar_mock]
    
    mock_candidate_repo.get_by_telegram_id.return_value = cand
    
    candidate_service._emit_updated_event = AsyncMock()
    
    candidate_service.db.refresh = AsyncMock()

    from app.schemas.candidate import AvatarCreate
    payload = AvatarCreate(file_id=uuid4())

    await candidate_service.update_avatar(12345, payload)

    mock_client.delete.assert_called_once()
    mock_candidate_repo.replace_avatar.assert_called_once()
    candidate_service._emit_updated_event.assert_called_once()

@pytest.mark.asyncio
async def test_delete_avatar_success(candidate_service, mock_candidate_repo):
    """Тест удаления аватара."""
    from unittest.mock import MagicMock
    from app.core.resources import resources
    mock_client = AsyncMock()
    mock_client.delete.return_value = MagicMock(status_code=204)
    resources.http_client = mock_client

    cand = make_db_candidate()
    mock_candidate_repo.get_by_telegram_id.return_value = cand
    mock_candidate_repo.delete_avatar.return_value = uuid4()

    await candidate_service.delete_avatar(12345)

    mock_candidate_repo.delete_avatar.assert_called_once()
    mock_client.delete.assert_called_once()