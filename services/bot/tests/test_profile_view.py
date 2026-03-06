from unittest.mock import ANY

import pytest
from app.core.messages import Messages
from app.handlers import candidate


@pytest.mark.asyncio
async def test_show_profile_full(mock_message, fsm_context, mock_candidate_api, mock_file_api):
    """Тест отображения полного профиля с фото."""
    mock_profile = {
        "id": "1",
        "display_name": "Test User",
        "headline_role": "Dev",
        "salary_min": 100,
        "skills": ["Python"],
        "experiences": [{"company": "A", "position": "B", "start_date": "2020-01-01"}],
        "avatars": [{"file_id": "file-1"}],
        "resumes": [{"file_id": "file-2"}],
    }
    mock_candidate_api.get_candidate_by_telegram_id.return_value = mock_profile
    mock_file_api.get_download_url_by_file_id.return_value = "http://avatar.jpg"

    mock_message.photo = None

    await candidate._show_profile(mock_message, fsm_context)

    mock_message.answer_photo.assert_called_with(
        photo="http://avatar.jpg", caption=ANY, reply_markup=ANY
    )


@pytest.mark.asyncio
async def test_show_profile_not_found(mock_message, fsm_context, mock_candidate_api):
    """Тест: профиль не найден."""
    mock_candidate_api.get_candidate_by_telegram_id.return_value = None

    await candidate._show_profile(mock_message, fsm_context)

    mock_message.answer.assert_called_with(Messages.Profile.NOT_FOUND)
