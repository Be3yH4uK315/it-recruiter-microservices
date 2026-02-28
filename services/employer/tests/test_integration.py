from unittest.mock import MagicMock
import pytest
import respx
from httpx import Response, HTTPStatusError
from uuid import uuid4
from app.core.config import settings
from app.schemas import employer as schemas

@pytest.mark.asyncio
async def test_integration_get_next_candidate_flow(employer_service, mock_employer_repo, setup_resources):
    """
    Интеграция с Search Service и Candidate Service.
    """
    session_id = uuid4()
    candidate_id = "123e4567-e89b-12d3-a456-426614174000"
    
    mock_session = schemas.SearchSession(
        id=session_id,
        employer_id=uuid4(),
        title="Python Dev",
        status="active",
        filters={"role": "Python"}
    )
    mock_employer_repo.get_session.return_value = mock_session
    mock_employer_repo.get_viewed_candidate_ids.return_value = []

    async with respx.mock(base_url=None) as respx_mock:
        respx_mock.post(f"{settings.SEARCH_SERVICE_URL}/search/next").mock(
            return_value=Response(200, json={
                "candidate": {
                    "id": candidate_id, 
                    "match_score": 0.88
                }
            })
        )
        
        respx_mock.get(f"{settings.CANDIDATE_SERVICE_URL}/candidates/{candidate_id}").mock(
            return_value=Response(200, json={
                "id": candidate_id,
                "display_name": "Integration Candidate",
                "headline_role": "Senior Dev",
                "experience_years": 3.5, 
                "skills": [{"skill": "Python", "kind": "hard", "level": 5}],
                "contacts_visibility": "hidden"
            })
        )
        
        result = await employer_service.get_next_candidate(session_id)
        
        assert result.candidate is not None
        assert result.candidate.display_name == "Integration Candidate"
        assert result.candidate.match_score == 0.88

@pytest.mark.asyncio
async def test_integration_search_unavailable(employer_service, mock_employer_repo, setup_resources):
    """
    Сценарий: Search Service упал (500 Error).
    """
    mock_employer_repo.get_session.return_value = MagicMock(filters={})
    
    async with respx.mock(base_url=settings.SEARCH_SERVICE_URL) as respx_mock:
        respx_mock.post("/search/next").mock(return_value=Response(500))
        with pytest.raises(HTTPStatusError) as exc:
            await employer_service.get_next_candidate(uuid4())
        
        assert exc.value.response.status_code == 500
