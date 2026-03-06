from uuid import uuid4

import pytest
from app.models.search import SearchFilters
from app.services.milvus_client import MilvusClientWrapper
from app.services.search_logic import search_engine


@pytest.mark.asyncio
async def test_milvus_connection_fail(mocker):
    """Тест ошибки подключения к Milvus."""
    mocker.patch("app.services.milvus_client.connections.connect", side_effect=Exception("Down"))
    client = MilvusClientWrapper()
    with pytest.raises(Exception):
        client.connect()


@pytest.mark.asyncio
async def test_milvus_search_exception(mocker):
    """Тест обработки ошибок при поиске в Milvus."""
    mocker.patch("asyncio.get_running_loop").return_value.run_in_executor.side_effect = Exception(
        "Search error"
    )
    client = MilvusClientWrapper()
    res = await client.search([], [])
    assert res == []


@pytest.mark.asyncio
async def test_search_engine_es_fail(mocker):
    """
    Тест: ES упал, но Milvus работает.
    """
    valid_uuid = str(uuid4())

    mocker.patch.object(search_engine, "_search_es_ids", return_value=[])
    mocker.patch.object(search_engine, "_search_milvus_ids", return_value=[valid_uuid])
    mocker.patch.object(search_engine, "_mget_es", return_value=[{"id": valid_uuid}])
    mocker.patch("app.services.ranker.ranker.rerank_candidates", side_effect=lambda q, c, f: c)

    filters = SearchFilters(role="Test")
    res = await search_engine.search(filters)

    assert len(res) == 1
    assert str(res[0].id) == valid_uuid


@pytest.mark.asyncio
async def test_build_es_query_logic():
    """Тест построения сложного ES запроса."""
    valid_uuid = str(uuid4())

    filters = SearchFilters(
        role="Dev",
        must_skills=["Python"],
        location="NY",
        work_modes=["remote"],
        salary_max=5000,
        exclude_ids=[valid_uuid],
    )

    query = search_engine._build_es_query(filters)
    bool_q = query["bool"]

    assert bool_q["must_not"][0]["ids"]["values"] == [valid_uuid]
    assert bool_q["must"][0]["term"]["status"] == "active"
    assert any("salary_min" in x.get("range", {}) for x in bool_q["must"])
