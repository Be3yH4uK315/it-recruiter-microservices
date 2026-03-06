import httpx
import structlog

logger = structlog.get_logger()


class ResourceManager:
    def __init__(self):
        self.http_client: httpx.AsyncClient = None

    async def startup(self):
        logger.info("Initializing Employer Service resources...")
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    async def shutdown(self):
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Resources released.")


resources = ResourceManager()
