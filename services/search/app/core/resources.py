import httpx
from sentence_transformers import SentenceTransformer, CrossEncoder
from functools import lru_cache
import structlog
from app.core.config import settings

logger = structlog.get_logger()

class ResourceManager:
    def __init__(self):
        self.http_client: httpx.AsyncClient = None
        self.embedding_model: SentenceTransformer = None
        self.ranker_model: CrossEncoder = None

    async def startup(self):
        logger.info("Initializing Resources...")
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
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

resources = ResourceManager()
