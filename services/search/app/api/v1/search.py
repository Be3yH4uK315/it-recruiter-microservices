from fastapi import APIRouter, BackgroundTasks

from app.models.search import NextCandidateRequest, NextCandidateResponse
from app.services.search_logic import search_engine
from app.services.indexer import indexer

router = APIRouter()

@router.post("/next", response_model=NextCandidateResponse)
async def get_next_candidate(request: NextCandidateRequest):
    """
    Возвращает лучшего кандидата для сессии.
    """
    combined_excludes = set(request.filters.exclude_ids)
    combined_excludes.update(request.session_exclude_ids)
    request.filters.exclude_ids = list(combined_excludes)
    
    results = await search_engine.search(request.filters)
    
    if not results:
        return {"candidate": None}
        
    best_candidate = results[0]
    return {"candidate": best_candidate}

@router.post("/index/rebuild")
async def rebuild_index(
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(indexer.run_full_reindex)
    return {"status": "accepted"}