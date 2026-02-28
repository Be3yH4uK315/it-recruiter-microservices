import asyncio
from typing import List, Dict
from collections import defaultdict
import structlog

from app.core.config import settings
from app.core.resources import resources
from app.services.milvus_client import milvus_client
from app.services.indexer import indexer
from app.services.ranker import ranker
from app.models.search import SearchFilters, CandidatePreview

logger = structlog.get_logger()

class SearchEngine:
    async def search(self, filters: SearchFilters) -> List[CandidatePreview]:
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
            combined_scores.keys(), 
            key=lambda x: combined_scores[x], 
            reverse=True
        )
        
        top_ids = sorted_candidates_ids[:settings.RERANK_TOP_K]
        
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
                explanation=c.get("score_explanation")
            )
            for c in ranked_results
        ]

    async def _search_milvus_ids(self, filters: SearchFilters, size: int) -> List[str]:
        """Возвращает список ID из векторного поиска."""
        if not (filters.role or filters.must_skills or filters.nice_skills):
            return []
            
        try:
            query_text = self._build_query_text(filters)
            loop = asyncio.get_running_loop()
            
            query_vector = await loop.run_in_executor(
                None, 
                resources.get_embedding_cached, 
                query_text
            )
            
            hits = await milvus_client.search(
                query_vector=query_vector.tolist(),
                exclude_ids=filters.exclude_ids,
                top_k=size
            )
            return [h["candidate_id"] for h in hits]
        except Exception as e:
            logger.error(f"Milvus search failed (circuit breaker): {e}")
            return []

    async def _search_es_ids(self, filters: SearchFilters, size: int) -> List[str]:
        """Возвращает список ID из лексического поиска."""
        query = self._build_es_query(filters)
        try:
            resp = await indexer.es_client.search(
                index=settings.CANDIDATE_INDEX_ALIAS,
                query=query,
                size=size,
                _source=False,
                stored_fields=[] 
            )
            return [hit["_id"] for hit in resp["hits"]["hits"]]
        except Exception as e:
            logger.error(f"ES search failed: {e}")
            return []

    async def _mget_es(self, ids: List[str]) -> List[Dict]:
        """Получает полные тела документов по ID."""
        if not ids: return []
        try:
            resp = await indexer.es_client.mget(
                index=settings.CANDIDATE_INDEX_ALIAS,
                body={"ids": ids}
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
        if filters.role: parts.append(filters.role)
        all_skills = filters.must_skills + filters.nice_skills
        if all_skills: parts.append(f"skills: {', '.join(all_skills)}")
        if filters.location: parts.append(f"location: {filters.location}")
        if filters.english_level: parts.append(f"English {filters.english_level}")
        return " ".join(parts)

    def _build_es_query(self, filters: SearchFilters) -> Dict:
        must = [{"term": {"status": "active"}}]
        must_not = []
        should = []

        if filters.exclude_ids:
            must_not.append({"ids": {"values": [str(uid) for uid in filters.exclude_ids]}})
        
        if filters.location: 
            must.append({"match": {"location": {"query": filters.location, "fuzziness": "AUTO"}}})
        
        if filters.work_modes: 
            must.append({"terms": {"work_modes": filters.work_modes}})

        if filters.role: 
            should.append({"match": {"headline_role": {"query": filters.role, "boost": 5}}})
            
        for skill in filters.must_skills: 
            should.append({"match": {"skills": {"query": skill, "boost": 4}}})
            
        if filters.salary_max:
             must.append({"range": {"salary_min": {"lte": filters.salary_max}}})
            
        if filters.english_level:
            should.append({"term": {"english_level": {"value": filters.english_level, "boost": 2}}})

        bool_query = {
            "bool": {
                "must": must,
                "should": should,
                "must_not": must_not,
                "minimum_should_match": 1 if should else 0
            }
        }
        
        return bool_query

search_engine = SearchEngine()
