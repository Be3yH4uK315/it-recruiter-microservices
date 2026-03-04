import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

@pytest.fixture(autouse=True)
def isolate_network(mocker):
    mocker.patch("app.services.auth_manager.Redis")
    mocker.patch("app.services.auth_manager.auth_manager.get_token", new_callable=AsyncMock, return_value="fake_token")

@pytest.fixture
def mock_candidate_api(mocker):
    client = AsyncMock()
    
    client.get_candidate_by_telegram_id.return_value = {
        "id": "123", "telegram_id": 123, "display_name": "Test User", "headline_role": "Tester",
        "skills": [], "experiences": [], "projects": [], "education": [], "avatars": [], "resumes": []
    }
    client.register_candidate_profile.return_value = {"id": "new_123"}
    client.update_candidate_profile.return_value = True
    client.delete_avatar.return_value = True
    client.delete_resume.return_value = True

    mocker.patch("app.services.api_client.candidate_api_client", client)
    mocker.patch("app.handlers.candidate.candidate_api_client", client, create=True)
    mocker.patch("app.handlers.employer.candidate_api_client", client, create=True)
    return client

@pytest.fixture
def mock_employer_api(mocker):
    client = AsyncMock()
    
    client.get_or_create_employer.return_value = {"id": "emp_1", "company": "Tech"}
    client.get_next_candidate.return_value = {
        "id": "cand-1", "display_name": "Pro Python", "headline_role": "Senior",
        "match_score": 0.99, "salary_min": 100, "skills": []
    }
    client.save_decision.return_value = True
    client.create_search_session.return_value = {"id": "sess-1", "filters": {}}
    client.request_contacts.return_value = {"granted": True, "contacts": {"telegram": "@test"}}

    mocker.patch("app.services.api_client.employer_api_client", client)
    mocker.patch("app.handlers.common.employer_api_client", client, create=True)
    mocker.patch("app.handlers.employer.employer_api_client", client, create=True)
    mocker.patch("app.handlers.candidate.employer_api_client", client, create=True)
    return client

@pytest.fixture
def mock_file_api(mocker):
    client = AsyncMock()
    client.get_download_url_by_file_id.return_value = "http://fake.url/cv.pdf"
    
    mocker.patch("app.services.api_client.file_api_client", client)
    mocker.patch("app.handlers.candidate.file_api_client", client, create=True)
    mocker.patch("app.handlers.employer.file_api_client", client, create=True)
    return client

@pytest.fixture
def mock_message():
    """Создает фейковое сообщение."""
    message = AsyncMock(spec=Message)
    message.from_user = User(id=123, is_bot=False, first_name="Test")
    message.chat = Chat(id=123, type="private")
    message.text = "Test text"
    message.answer = AsyncMock()
    message.delete = AsyncMock()
    message.edit_text = AsyncMock()
    message.edit_reply_markup = AsyncMock()
    return message

@pytest.fixture
def mock_callback(mock_message):
    """Создает фейковый коллбек."""
    call = AsyncMock(spec=CallbackQuery)
    call.from_user = mock_message.from_user
    call.message = mock_message
    call.data = "test_data"
    call.answer = AsyncMock()
    return call

@pytest_asyncio.fixture
async def fsm_context():
    """Правильная фикстура для FSM."""
    storage = MemoryStorage()
    key = "bot:123:123"
    ctx = FSMContext(storage=storage, key=key)
    await ctx.set_data({})
    
    original_get_data = ctx.get_data
    async def safe_get_data():
        data = await original_get_data()
        return data if data is not None else {}
    ctx.get_data = safe_get_data
    return ctx
