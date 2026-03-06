from unittest.mock import ANY

import pytest
from app.core.messages import Messages
from app.handlers import common
from app.states.employer import EmployerSearch


@pytest.mark.asyncio
async def test_cmd_start(mock_message, fsm_context):
    await common.cmd_start(mock_message, fsm_context)

    mock_message.answer.assert_called_with(Messages.Common.START, reply_markup=ANY)


@pytest.mark.asyncio
async def test_select_role_candidate(mock_callback, fsm_context):
    await common.cq_select_candidate(mock_callback, fsm_context)

    data = await fsm_context.get_data()
    assert data["mode"] == "register"
    assert data["current_field"] == "display_name"

    mock_callback.message.edit_text.assert_called_with(Messages.Profile.ENTER_NAME)


@pytest.mark.asyncio
async def test_select_role_employer_new(mock_callback, fsm_context, mock_employer_api):
    mock_employer_api.get_or_create_employer.return_value = {
        "id": "uid",
        "company": None,
    }

    await common.cq_select_employer(mock_callback, fsm_context)

    state = await fsm_context.get_state()
    assert state == EmployerSearch.entering_company_name
    mock_callback.message.edit_text.assert_called_with(Messages.EmployerSearch.ENTER_COMPANY_NAME)


@pytest.mark.asyncio
async def test_select_role_employer_existing(mock_callback, fsm_context, mock_employer_api):
    mock_employer_api.get_or_create_employer.return_value = {
        "id": "uid",
        "company": "Tech Inc",
    }

    await common.cq_select_employer(mock_callback, fsm_context)

    state = await fsm_context.get_state()
    assert state == EmployerSearch.entering_filters
    mock_callback.message.edit_text.assert_called_with(Messages.EmployerSearch.STEP_1)
