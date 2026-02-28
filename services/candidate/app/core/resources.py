import httpx
from typing import Optional

class ResourceManager:
    """
    Управляет глобальными ресурсами приложения, такими как HTTP-клиенты.
    Позволяет переиспользовать TCP-соединения (Connection Pooling).
    """
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None

    async def startup(self):
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )

    async def shutdown(self):
        if self.http_client:
            await self.http_client.aclose()

resources = ResourceManager()
