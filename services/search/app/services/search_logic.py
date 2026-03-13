import asyncio
from collections import defaultdict

import structlog

from app.core.config import settings
from app.core.resources import resources
from app.models.search import CandidatePreview, SearchFilters
from app.services.indexer import indexer
from app.services.milvus_client import milvus_client
from app.services.ranker import ranker
from app.utils.currency import normalize_to_rub

logger = structlog.get_logger()


class SearchEngine:
    async def search(self, filters: SearchFilters) -> list[CandidatePreview]:
        """
        Гибридный поиск:
        1. Параллельное выполнение ES (лексического) и Milvus (семантического).
        2. Взаимное ранжирование (RRF) для объединения результатов.
        3. Получение полных документов только для победителей.
        4. Повторное ранжирование L2 (перекрестное кодирование).
        """
        es_task = self._search_es_ids(filters, size=settings.RETRIEVAL_SIZE)
        milvus_task = self._search_milvus_ids(filters, size=settings.RETRIEVAL_SIZE)

        results = await asyncio.gather(es_task, milvus_task)
        es_hits = results[0]
        milvus_hits = results[1]
        combined_scores = defaultdict(float)
        k = settings.RRF_K

        for rank, doc_id in enumerate(es_hits):
            combined_scores[doc_id] += 1.0 / (k + rank + 1)

        for rank, doc_id in enumerate(milvus_hits):
            combined_scores[doc_id] += 1.0 / (k + rank + 1)

        if not combined_scores:
            return []

        sorted_candidates_ids = sorted(
            combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True
        )

        top_ids = sorted_candidates_ids[: settings.RERANK_TOP_K]
        candidates_data = await self._mget_es(top_ids)

        if not candidates_data:
            return []

        query_text = self._build_query_text(filters)
        ranked_results = await ranker.rerank_candidates(query_text, candidates_data, filters)

        return [
            CandidatePreview(
                id=c["id"],
                display_name=c.get("display_name", "Candidate"),
                headline_role=c.get("headline_role", ""),
                experience_years=c.get("experience_years", 0),
                location=c.get("location"),
                salary_min=c.get("salary_min"),
                salary_max=c.get("salary_max"),
                currency=c.get("currency", "RUB"),
                english_level=c.get("english_level"),
                about_me=c.get("about_me"),
                skills=c.get("skills", []),
                match_score=c.get("match_score", 0.0),
                explanation=c.get("score_explanation"),
            )
            for c in ranked_results
        ]

    async def _search_milvus_ids(self, filters: SearchFilters, size: int) -> list[str]:
        """Возвращает список ID из векторного поиска."""
        if not (filters.role or filters.must_skills or filters.nice_skills):
            return []

        try:
            query_text = self._build_query_text(filters)
            query_vector = await resources.encode_text_async(query_text)

            hits = await milvus_client.search(
                query_vector=query_vector.tolist(),
                exclude_ids=filters.exclude_ids,
                top_k=size,
            )
            return [h["candidate_id"] for h in hits]
        except Exception as e:
            logger.error(f"Milvus search failed (circuit breaker): {e}")
            return []

    async def _search_es_ids(self, filters: SearchFilters, size: int) -> list[str]:
        """Возвращает список ID из лексического поиска."""
        query = self._build_es_query(filters)
        try:
            resp = await indexer.es_client.search(
                index=settings.CANDIDATE_INDEX_ALIAS,
                query=query,
                size=size,
                _source=False,
                stored_fields=[],
            )
            return [hit["_id"] for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error(f"ES search failed: {e}")
            return []

    async def _mget_es(self, ids: list[str]) -> list[dict]:
        """Получает полные тела документов по ID."""
        if not ids:
            return []
        try:
            resp = await indexer.es_client.mget(
                index=settings.CANDIDATE_INDEX_ALIAS, body={"ids": ids}
            )
            results = []
            for doc in resp["docs"]:
                if doc["found"]:
                    source = doc["_source"]
                    source["id"] = doc["_id"]
                    results.append(source)
            return results
        except Exception as e:
            logger.error(f"ES Mget failed: {e}")
            return []

    def _build_query_text(self, filters: SearchFilters) -> str:
        parts = []
        if filters.role:
            parts.append(filters.role)
        all_skills = [s["skill"] for s in (filters.must_skills + (filters.nice_skills or []))]
        if all_skills:
            parts.append(f"skills: {', '.join(all_skills)}")
        if filters.location:
            parts.append(f"location: {filters.location}")
        if filters.english_level:
            parts.append(f"English {filters.english_level}")
        return " ".join(parts)

    def _build_es_query(self, filters: SearchFilters) -> dict:
        must = []
        should = []
        must_not = []
        filter_clauses = []

        if filters.role:
            must.append({"match": {"headline_role": {"query": filters.role}}})

        for skill_obj in filters.must_skills:
            filter_clauses.append({"term": {"skills.skill": skill_obj["skill"]}})
        
        for skill_obj in filters.nice_skills or []:
            should.append({"term": {"skills.skill": {"value": skill_obj["skill"], "boost": 2}}})

        if filters.location:
            if "remote" in (filters.work_modes or []):
                should.append({"match": {"location": {"query": filters.location, "boost": 2}}})
            else:
                must.append({"match": {"location": {"query": filters.location}}})

        if filters.work_modes:
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"terms": {"work_modes": filters.work_modes}},
                        {"bool": {"must_not": {"exists": {"field": "work_modes"}}}}
                    ],
                    "minimum_should_match": 1
                }
            })

        exp_range = {}
        if filters.experience_min is not None:
            exp_range["gte"] = max(0, filters.experience_min - 1)
        if filters.experience_max is not None:
            exp_range["lte"] = filters.experience_max + 2
        if exp_range:
            filter_clauses.append({"range": {"experience_years": exp_range}})

        if filters.salary_max is not None:
            max_rub = normalize_to_rub(filters.salary_max, filters.currency)
            
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"range": {"salary_min_rub": {"lte": max_rub}}},
                        {"bool": {"must_not": {"exists": {"field": "salary_min_rub"}}}}
                    ],
                    "minimum_should_match": 1
                }
            })

        if filters.english_level:
            should.append({"term": {"english_level": {"value": filters.english_level, "boost": 1}}})

        if filters.exclude_ids:
            must_not.append({"terms": {"_id": [str(uid) for uid in filters.exclude_ids]}})
        
        return {
            "bool": {
                "must": must,
                "should": should,
                "filter": filter_clauses,
                "must_not": must_not
            }
        }


search_engine = SearchEngine()
