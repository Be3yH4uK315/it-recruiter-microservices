import pytest
from unittest.mock import ANY
from app.handlers import candidate
from app.states.candidate import CandidateFSM

@pytest.mark.asyncio
async def test_experience_flow(mock_message, fsm_context):
    """Проход по всем шагам добавления опыта."""
    await fsm_context.set_state(CandidateFSM.block_entry)
    await fsm_context.update_data(block_type='experience', current_step='company')
    mock_message.text = "Google"
    await candidate.handle_block_entry(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["current_exp_company"] == "Google"
    assert data["current_step"] == "position"
    
    mock_message.text = "Dev"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "start_date"
    
    mock_message.text = "2020-01-01"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "end_date"
    
    mock_message.text = "2021-01-01"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "responsibilities"
    
    mock_message.text = "Coding"
    await candidate.handle_block_entry(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    experiences = data.get("experiences") or data.get("new_experiences")
    assert len(experiences) == 1
    assert experiences[0]["company"] == "Google"
    
    mock_message.answer.assert_called_with(ANY, reply_markup=ANY)

@pytest.mark.asyncio
async def test_education_flow(mock_message, fsm_context):
    """Проход по шагам образования."""
    await fsm_context.set_state(CandidateFSM.block_entry)
    await fsm_context.update_data(block_type='education', current_step='level')
    mock_message.text = "Master"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "institution"
    
    mock_message.text = "MIT"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "year"
    
    mock_message.text = "2023"
    await candidate.handle_block_entry(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    edu = data.get("education") or data.get("new_education")
    assert len(edu) == 1
    assert edu[0]["institution"] == "MIT"

@pytest.mark.asyncio
async def test_project_flow(mock_message, fsm_context):
    """Проход по шагам проекта."""
    await fsm_context.set_state(CandidateFSM.block_entry)
    await fsm_context.update_data(block_type='project', current_step='title')
    mock_message.text = "My Bot"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "description"
    
    mock_message.text = "Cool bot"
    await candidate.handle_block_entry(mock_message, fsm_context)
    assert (await fsm_context.get_data())["current_step"] == "links"
    
    mock_message.text = "/skip"
    await candidate.handle_block_entry(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    projects = data.get("projects") or data.get("new_projects")
    assert len(projects) == 1
    assert projects[0]["title"] == "My Bot"
