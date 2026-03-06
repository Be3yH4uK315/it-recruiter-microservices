from uuid import uuid4

import pytest
from app.models.search import SearchFilters
from app.services.ranker import ranker
from app.services.search_logic import search_engine


@pytest.mark.asyncio
async def test_rrf_logic(mocker):
    """
    Тест алгоритма RRF (слияние списков).
    Сценарий: ES нашел [A, B], Milvus нашел [B, C].
    Ожидание: B должен быть на 1 месте (так как он есть в обоих списках).
    """
    id_a = str(uuid4())
    id_b = str(uuid4())
    id_c = str(uuid4())

    mocker.patch.object(search_engine, "_search_es_ids", return_value=[id_a, id_b])
    mocker.patch.object(search_engine, "_search_milvus_ids", return_value=[id_b, id_c])
    mocker.patch.object(
        search_engine, "_mget_es", side_effect=lambda ids: [{"id": uid} for uid in ids]
    )
    mocker.patch("app.services.ranker.ranker.rerank_candidates", side_effect=lambda q, c, f: c)

    filters = SearchFilters(role="Dev")
    results = await search_engine.search(filters)
    ids = [str(res.id) for res in results]
    assert ids[0] == id_b
    assert set(ids) == {id_a, id_b, id_c}


def test_ranker_multiplicative_score():
    """
    Тест формулы скоринга: Score = ML * Skill * Exp * Loc
    """
    filters = SearchFilters(
        role="Dev",
        must_skills=["Python", "Docker"],
        experience_min=3.0,
        location="Moscow",
    )

    candidate = {
        "id": "1",
        "skills": ["Python"],
        "experience_years": 3.5,
        "location": "Moscow",
        "salary_min": 100,
    }

    ml_score = 0.8

    final_score, factors = ranker._calculate_multiplicative_score(candidate, filters, ml_score)

    assert factors["skill_factor"] == 0.65
    assert factors["loc_factor"] == 1.1
    assert factors["exp_factor"] == 1.0

    expected = 0.8 * 0.65 * 1.0 * 1.1 * 1.0
    assert final_score == round(expected, 4)


def test_indexer_prepare_es_doc():
    """Тест подготовки документа для Elastic."""
    from app.services.indexer import indexer

    data = {
        "id": "123",
        "skills": [{"skill": "Python", "level": 5}, {"skill": "Go", "level": 3}],
        "education": [{"level": "B.Sc", "institution": "MIT"}],
    }

    doc = indexer._prepare_es_doc(data)

    assert doc["id"] == "123"

    assert isinstance(doc["skills"], list)
    if isinstance(doc["skills"][0], dict):
        assert doc["skills"][0].get("skill", "").lower() == "python"
    else:
        assert "python" in [s.lower() for s in doc["skills"]]

    assert "B.Sc MIT" in doc["education_text"]
