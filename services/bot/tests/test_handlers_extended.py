from unittest.mock import ANY

import pytest
from app.core.messages import Messages
from app.handlers import candidate, employer
from app.states.candidate import CandidateFSM


@pytest.mark.asyncio
async def test_invalid_skill_input(mock_message, fsm_context):
    """Тест: Ввели невалидный навык."""
    await fsm_context.set_state(CandidateFSM.block_entry)
    await fsm_context.update_data(block_type="skill", current_step="name")
    mock_message.text = "Python"
    await candidate.handle_block_entry(mock_message, fsm_context)

    state = await fsm_context.get_state()
    assert state == CandidateFSM.selecting_options


@pytest.mark.asyncio
async def test_handle_profile_action_edit(mock_callback, fsm_context):
    """Клик по кнопке 'Редактировать'."""
    from app.keyboards.inline import ProfileAction

    cb = ProfileAction(action="edit")

    await candidate.handle_profile_action(mock_callback, cb, fsm_context)

    state = await fsm_context.get_state()
    assert state == CandidateFSM.choosing_field
    mock_callback.message.answer.assert_called_with(Messages.Profile.CHOOSE_FIELD, reply_markup=ANY)


@pytest.mark.asyncio
async def test_employer_search_no_session(mock_callback, fsm_context):
    """Тест: Сессия истекла."""
    await fsm_context.set_data({})

    await employer.show_next_candidate(mock_callback, fsm_context)

    mock_callback.message.answer.assert_called_with(Messages.EmployerSearch.SESSION_EXPIRED)
