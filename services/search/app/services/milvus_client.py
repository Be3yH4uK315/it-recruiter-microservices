import asyncio
from typing import List
from pymilvus import (
    connections, utility, Collection, CollectionSchema, FieldSchema, DataType
)
import structlog

from app.core.config import settings

logger = structlog.get_logger()

DIMENSION = 768

class MilvusClientWrapper:
    def __init__(self):
        self.alias = "default"
        self.collection_name = settings.MILVUS_COLLECTION_NAME
        self.collection: Collection = None

    def connect(self):
        logger.info(f"Connecting to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        try:
            connections.connect(
                self.alias, 
                host=settings.MILVUS_HOST, 
                port=settings.MILVUS_PORT
            )
            self._ensure_collection()
        except Exception as e:
            logger.error(f"Milvus connection failed: {e}")
            raise

    def disconnect(self):
        try:
            connections.disconnect(self.alias)
        except Exception:
            pass

    def _ensure_collection(self):
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.info(f"Milvus collection '{self.collection_name}' loaded.")
        else:
            logger.info(f"Creating Milvus collection '{self.collection_name}'...")
            fields = [
                FieldSchema(name="candidate_id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION)
            ]
            schema = CollectionSchema(fields, description="Candidate embeddings")
            self.collection = Collection(self.collection_name, schema)
            
            index_params = {
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            self.collection.load()
            logger.info("Milvus collection created and loaded.")

    async def insert(self, ids: List[str], vectors: List[List[float]]):
        if not ids: return
        loop = asyncio.get_running_loop()
        
        def _sync_insert():
            self.collection.insert([ids, vectors])
            self.collection.flush() 
            
        await loop.run_in_executor(None, _sync_insert)

    async def delete(self, candidate_id: str):
        loop = asyncio.get_running_loop()
        expr = f'candidate_id == "{str(candidate_id)}"'
        await loop.run_in_executor(None, self.collection.delete, expr)

    async def search(self, query_vector: List[float], exclude_ids: List[str], top_k: int = 50) -> List[dict]:
        loop = asyncio.get_running_loop()
        
        safe_ids = exclude_ids[:1000]
        expr = ""
        if safe_ids:
            ids_list_str = ", ".join(f'"{str(uid)}"' for uid in safe_ids)
            expr = f'candidate_id not in [{ids_list_str}]'
        
        fetch_limit = top_k + len(exclude_ids)
        
        def _sync_search():
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=fetch_limit,
                expr=expr if expr else None,
                output_fields=["candidate_id"]
            )
            hits = []
            exclude_set = set(str(uid) for uid in exclude_ids)
            
            if results and len(results) > 0:
                for hit in results[0]:
                    if str(hit.id) not in exclude_set:
                        hits.append({"candidate_id": hit.id, "vector_score": hit.distance})
                        if len(hits) >= top_k:
                            break
            return hits

        try:
            return await loop.run_in_executor(None, _sync_search)
        except Exception as e:
            logger.error(f"Milvus search failed: {e}")
            return []

milvus_client = MilvusClientWrapper()
