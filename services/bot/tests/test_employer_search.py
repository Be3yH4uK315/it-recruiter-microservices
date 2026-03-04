import pytest
from app.handlers import employer
from app.core.messages import Messages
from app.states.employer import EmployerSearch

@pytest.mark.asyncio
async def test_filter_role_input(mock_message, fsm_context):
    await fsm_context.set_state(EmployerSearch.entering_filters)
    await fsm_context.update_data(filter_step="role", filters={})
    mock_message.text = "Java Dev"
    
    await employer.handle_filter_input(mock_message, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["filters"]["role"] == "Java Dev"
    assert data["filter_step"] == "must_skills"
    
    mock_message.answer.assert_called_with(Messages.EmployerSearch.STEP_2, reply_markup=None)

@pytest.mark.asyncio
async def test_show_next_candidate_success(mock_callback, fsm_context, mock_employer_api):
    await fsm_context.set_data({"session_id": "sess-1"})
    
    mock_candidate = {
        "id": "cand-1",
        "display_name": "Pro Python",
        "headline_role": "Senior",
        "match_score": 0.99,
        "salary_min": 100,
        "salary_max": 200,
        "currency": "USD"
    }
    mock_employer_api.get_next_candidate.return_value = mock_candidate
    
    mock_callback.message.photo = None
    
    await employer.show_next_candidate(mock_callback, fsm_context)
    
    data = await fsm_context.get_data()
    assert data["current_candidate"] == mock_candidate
    
    assert (
        mock_callback.message.edit_text.called or 
        mock_callback.message.answer.called or
        mock_callback.message.answer_photo.called
    )

@pytest.mark.asyncio
async def test_handle_decision_like(mock_callback, fsm_context, mock_employer_api):
    await fsm_context.set_data({"session_id": "sess-1", "current_candidate": {"id": "c1"}})
    mock_employer_api.save_decision.return_value = True
    
    from app.keyboards.inline import SearchResultDecision
    cb_data = SearchResultDecision(action="like", candidate_id="c1")
    
    await employer.handle_decision(mock_callback, cb_data, fsm_context)
    
    mock_employer_api.save_decision.assert_called_once()
    mock_employer_api.save_decision.assert_called_with(
        session_id="sess-1", candidate_id="c1", decision="like"
    )
