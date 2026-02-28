import pytest
from unittest.mock import ANY
from app.handlers import candidate
from app.core.messages import Messages
from app.states.candidate import CandidateFSM

@pytest.mark.asyncio
async def test_input_basic_info_name(mock_message, fsm_context):
    await fsm_context.set_data({"mode": "register", "current_field": "display_name"})
    mock_message.text = "Ivan Ivanov"
    
    await candidate.handle_basic_input(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["display_name"] == "Ivan Ivanov"
    assert data["current_field"] == "headline_role"
    
    mock_message.answer.assert_called_with(Messages.Profile.ENTER_ROLE)

@pytest.mark.asyncio
async def test_input_salary_parsing(mock_message, fsm_context):
    await fsm_context.set_data({"mode": "register", "current_field": "salary"})
    mock_message.text = "100000"
    
    await candidate.handle_basic_input(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["salary_min"] == 100000
    
    state = await fsm_context.get_state()
    assert state == CandidateFSM.selecting_options

@pytest.mark.asyncio
async def test_add_skill_flow(mock_message, fsm_context):
    await fsm_context.set_state(CandidateFSM.block_entry)
    await fsm_context.update_data(block_type='skill', current_step='name')
    mock_message.text = "Python"
    
    await candidate.handle_block_entry(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["current_skill_name"] == "Python"
    
    state = await fsm_context.get_state()
    assert state == CandidateFSM.selecting_options
    mock_message.answer.assert_called_with(Messages.Profile.ENTER_SKILL_KIND, reply_markup=ANY)

@pytest.mark.asyncio
async def test_finish_registration(mock_message, fsm_context, mock_candidate_api):
    await fsm_context.set_data({"mode": "register", "file_type": "avatar"})
    mock_message.text = "/skip"
    mock_message.photo = None
    
    mock_profile = {
        "id": "123",
        "telegram_id": 123,
        "display_name": "Test User",
        "headline_role": "Tester",
        "status": "active",
        "contacts_visibility": "hidden"
    }
    mock_candidate_api.get_candidate_by_telegram_id.return_value = mock_profile
    
    await candidate.handle_skip_uploading(mock_message, fsm_context)
    
    mock_message.answer.assert_any_call(Messages.Profile.FINISH_OK)
    mock_candidate_api.get_candidate_by_telegram_id.assert_called()