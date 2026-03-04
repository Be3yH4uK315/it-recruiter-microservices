import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from aiogram.types import User, Chat, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from app.services.api_client import CandidateAPIClient, EmployerAPIClient, FileAPIClient


@pytest.fixture(autouse=True)
def isolate_network(mocker):
    mocker.patch("app.services.auth_manager.Redis")
    mocker.patch("app.services.auth_manager.AuthManager.get_token", new_callable=AsyncMock, return_value="fake_token")

@pytest.fixture
def mock_candidate_api(mocker):
    client = mocker.MagicMock(spec=CandidateAPIClient)
    client.get_candidate_by_telegram_id = AsyncMock()
    client.register_candidate_profile = AsyncMock()
    client.update_candidate_profile = AsyncMock()
    client.delete_avatar = AsyncMock()
    client.delete_resume = AsyncMock()

    mocker.patch("app.handlers.candidate.candidate_api_client", client, create=True)
    mocker.patch("app.handlers.employer.candidate_api_client", client, create=True)
    return client

@pytest.fixture
def mock_employer_api(mocker):
    client = mocker.MagicMock(spec=EmployerAPIClient)
    client.get_or_create_employer = AsyncMock()
    client.get_next_candidate = AsyncMock()
    client.save_decision = AsyncMock()
    client.create_search_session = AsyncMock()
    client.request_contacts = AsyncMock()

    mocker.patch("app.handlers.common.employer_api_client", client, create=True)
    mocker.patch("app.handlers.employer.employer_api_client", client, create=True)
    mocker.patch("app.handlers.candidate.employer_api_client", client, create=True)
    return client

@pytest.fixture
def mock_file_api(mocker):
    client = mocker.MagicMock(spec=FileAPIClient)
    client.get_download_url_by_file_id = AsyncMock(return_value="http://fake.url/cv.pdf")
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

@pytest.fixture
def state():
    """FSM Context в памяти."""
    storage = MemoryStorage()
    key = list(storage.storage.keys())[0] if storage.storage else "test"
    return FSMContext(storage=storage, key=key)

@pytest_asyncio.fixture
async def fsm_context():
    """Правильная фикстура для FSM."""
    storage = MemoryStorage()
    key = "bot:123:123"
    ctx = FSMContext(storage=storage, key=key)
    await ctx.set_data({})
    return ctx
