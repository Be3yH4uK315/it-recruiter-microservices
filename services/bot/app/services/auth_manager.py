import logging
import httpx
from typing import Optional
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.redis = Redis(
            host=settings.REDIS_HOST, 
            port=settings.REDIS_PORT, 
            decode_responses=True
        )
        self.auth_url = settings.AUTH_SERVICE_URL.rstrip("/")
        self.secret = settings.INTERNAL_BOT_SECRET

    async def get_token(self, telegram_id: int, username: Optional[str] = None) -> Optional[str]:
        """
        Возвращает валидный Access Token.
        1. Ищет в Redis.
        2. Если нет -> идет в Auth Service -> сохраняет в Redis -> возвращает.
        """
        redis_key = f"token_access:{telegram_id}"
        
        token = await self.redis.get(redis_key)
        if token:
            return token

        logger.info(f"Token missing/expired for {telegram_id}. Logging in via Auth Service...")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                payload = {
                    "telegram_id": telegram_id,
                    "username": username,
                    "bot_secret": self.secret
                }
                response = await client.post(f"{self.auth_url}/v1/auth/login/bot", json=payload)
                response.raise_for_status()
                data = response.json()
                
                access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                ttl = max(60, expires_in - 60)
                await self.redis.setex(redis_key, ttl, access_token)
                
                return access_token
                
        except Exception as e:
            logger.error(f"Failed to authenticate user {telegram_id}: {e}")
            return None

    async def close(self):
        await self.redis.aclose()

auth_manager = AuthManager()
