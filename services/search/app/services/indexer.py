import time
from typing import Dict, Any, Optional
import httpx
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError
import structlog
from jose import jwt
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.resources import resources
from app.services.milvus_client import milvus_client

logger = structlog.get_logger()

class IndexerService:
    def __init__(self):
        self.es_client = AsyncElasticsearch(settings.ELASTICSEARCH_URL)
        self._shadow_index_name: Optional[str] = None

    def _create_system_token(self) -> str:
        payload = {
            "sub": "search-indexer",
            "role": "system",
            "tg_id": 0, 
            "exp": datetime.utcnow() + timedelta(minutes=10)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
    async def process_candidate_update(self, candidate_data: Dict[str, Any]):
        """
        Обработка события из RabbitMQ. 
        Пишет в активный индекс И (если идет реиндекс) в новый индекс.
        """
        candidate_id = candidate_data.get("id")
        if not candidate_id:
            return

        es_doc = self._prepare_es_doc(candidate_data)
        
        await self.es_client.index(
            index=settings.CANDIDATE_INDEX_ALIAS,
            id=candidate_id,
            document=es_doc
        )
        
        if self._shadow_index_name:
            try:
                await self.es_client.index(
                    index=self._shadow_index_name,
                    id=candidate_id,
                    document=es_doc
                )
            except Exception as e:
                logger.error("Failed to write to shadow index", error=str(e))

        text_for_embedding = self._prepare_text_for_embedding(candidate_data)
        vector = await resources.encode_text_async(text_for_embedding)
        
        await milvus_client.insert(ids=[candidate_id], vectors=[vector.tolist()])
        logger.info("Candidate indexed", candidate_id=candidate_id)

    async def delete_candidate(self, candidate_id: str):
        await self.es_client.delete(
            index=settings.CANDIDATE_INDEX_ALIAS, 
            id=candidate_id, 
            ignore=[404]
        )
        if self._shadow_index_name:
            await self.es_client.delete(
                index=self._shadow_index_name, 
                id=candidate_id, 
                ignore=[404]
            )
            
        await milvus_client.delete(candidate_id)
        logger.info("Candidate deleted", candidate_id=candidate_id)

    async def run_full_reindex(self):
        """
        Полная переиндексация с защитой от потери данных (Double Write).
        """
        if self._shadow_index_name:
            logger.warning("Reindex already in progress")
            return

        logger.info("Starting full re-indexation process...")
        start_time = time.time()
        new_index_name = f"candidates-{int(start_time)}"
        
        self._shadow_index_name = new_index_name
        logger.info(f"Shadow index set to: {new_index_name}")

        try:
            await self.es_client.indices.create(index=new_index_name)

            url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/"
            limit = 100
            offset = 0
            total_processed = 0
            token = self._create_system_token()
            headers = {"Authorization": f"Bearer {token}"}

            async with httpx.AsyncClient(timeout=60.0) as client:
                while True:
                    resp = await client.get(
                        url, 
                        params={"limit": limit, "offset": offset},
                        headers=headers 
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("data", [])
                    
                    if not candidates:
                        break
                    
                    texts_for_ml = []
                    ids_for_milvus = []
                    
                    for cand in candidates:
                        es_doc = self._prepare_es_doc(cand)
                        await self.es_client.index(index=new_index_name, id=cand["id"], document=es_doc)
                        
                        text = self._prepare_text_for_embedding(cand)
                        texts_for_ml.append(text)
                        ids_for_milvus.append(cand["id"])

                    if texts_for_ml:
                        vectors = await resources.encode_text_async(texts_for_ml)
                        await milvus_client.insert(ids=ids_for_milvus, vectors=vectors.tolist())

                    total_processed += len(candidates)
                    offset += limit
                    logger.info(f"Re-indexed batch: {len(candidates)}. Total: {total_processed}")

            alias_name = settings.CANDIDATE_INDEX_ALIAS
            actions = [{"add": {"index": new_index_name, "alias": alias_name}}]
            
            try:
                is_exists = await self.es_client.indices.exists(index=alias_name)
                if is_exists:
                    index_info = await self.es_client.indices.get(index=alias_name)
                    if alias_name in index_info:
                        logger.warning(f"Found physical index '{alias_name}'. Deleting it to make room for alias...")
                        await self.es_client.indices.delete(index=alias_name)
            except Exception as e:
                logger.info(f"Index check passed or index didn't exist: {e}")
            
            try:
                current_aliases = await self.es_client.indices.get_alias(name=alias_name)
                for old_index in current_aliases.keys():
                    if old_index != new_index_name:
                        actions.append({"remove": {"index": old_index, "alias": alias_name}})
            except NotFoundError:
                current_aliases = {}

            await self.es_client.indices.update_aliases(body={"actions": actions})
            logger.info("Aliases switched successfully.")

            for old_index in current_aliases.keys():
                if old_index != new_index_name:
                    await self.es_client.indices.delete(index=old_index, ignore=[404])

        except Exception as e:
            logger.error(f"Re-indexation failed: {e}")
            await self.es_client.indices.delete(index=new_index_name, ignore=[404])
        finally:
            self._shadow_index_name = None
            duration = time.time() - start_time
            logger.info(f"Full re-indexation finished in {duration:.2f}s")

    def _prepare_es_doc(self, data: Dict) -> Dict:
        skills = data.get("skills", [])
        structured_skills = []
        if skills:
            if isinstance(skills[0], dict):
                structured_skills = [{"skill": s.get("skill", "").lower(), "level": s.get("level")} for s in skills]
            else:
                structured_skills = [{"skill": str(s).lower(), "level": None} for s in skills]

        edu_list = data.get("education", [])
        edu_text = "; ".join([f"{e.get('level','')} {e.get('institution','')}" for e in edu_list]) if edu_list else ""

        return {
            "id": data["id"],
            "telegram_id": data.get("telegram_id"),
            "display_name": data.get("display_name"),
            "headline_role": data.get("headline_role"),
            "experience_years": data.get("experience_years", 0),
            "location": data.get("location"),
            "work_modes": data.get("work_modes", []),
            "skills": structured_skills,
            "status": data.get("status", "active"),
            "education_text": edu_text,
            "salary_min": data.get("salary_min"),
            "salary_max": data.get("salary_max"),
            "currency": data.get("currency", "RUB"),
            "english_level": data.get("english_level"),
            "about_me": data.get("about_me")
        }

    def _prepare_text_for_embedding(self, data: Dict) -> str:
        parts = []
        if role := data.get("headline_role"): parts.append(f"Role: {role}")
        
        skills = data.get("skills", [])
        if skills:
            if isinstance(skills[0], dict): skill_names = ", ".join([s["skill"] for s in skills])
            else: skill_names = ", ".join(skills)
            parts.append(f"Skills: {skill_names}")
            
        if exp := data.get("experience_years"): parts.append(f"Experience: {exp} years")
        
        if edu := data.get("education"):
            edu_str = ", ".join([f"{e.get('level','')} in {e.get('institution','')}" for e in edu])
            parts.append(f"Education: {edu_str}")

        if about := data.get("about_me"):
            parts.append(f"About: {about}")

        return ". ".join(parts)

indexer = IndexerService()
