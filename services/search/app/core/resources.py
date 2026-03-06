import asyncio
from functools import lru_cache

import httpx
import structlog
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.core.config import settings

logger = structlog.get_logger()


class ResourceManager:
    def __init__(self):
        self.http_client: httpx.AsyncClient = None
        self.embedding_model: SentenceTransformer = None
        self.ranker_model: CrossEncoder = None
        self.ml_semaphore: asyncio.Semaphore = None

    async def startup(self):
        logger.info("Initializing Resources...")
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

        self.ml_semaphore = asyncio.Semaphore(1)

        logger.info(f"Loading Embedding Model: {settings.SENTENCE_MODEL_NAME}")
        self.embedding_model = SentenceTransformer(settings.SENTENCE_MODEL_NAME)
        self.get_embedding_cached("warm up query")

        logger.info(f"Loading Ranker Model: {settings.RANKER_MODEL_NAME}")
        self.ranker_model = CrossEncoder(settings.RANKER_MODEL_NAME)
        self.ranker_model.predict([("query", "document")])

        logger.info("ML models loaded.")

    async def shutdown(self):
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Resources released.")

    @lru_cache(maxsize=1024)
    def get_embedding_cached(self, text: str):
        return self.embedding_model.encode(text)

    async def encode_text_async(self, text: str | list[str]):
        """Безопасная асинхронная обертка для энкодера"""
        loop = asyncio.get_running_loop()
        async with self.ml_semaphore:
            if isinstance(text, str):
                return await loop.run_in_executor(None, self.get_embedding_cached, text)
            return await loop.run_in_executor(None, self.embedding_model.encode, text)

    async def predict_ranker_async(self, pairs: list[list[str]]):
        """Безопасная асинхронная обертка для реранкера"""
        loop = asyncio.get_running_loop()
        async with self.ml_semaphore:
            return await loop.run_in_executor(None, self.ranker_model.predict, pairs)


resources = ResourceManager()
