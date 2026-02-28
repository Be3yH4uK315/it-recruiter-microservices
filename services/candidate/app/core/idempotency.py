import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog

from app.core.db import AsyncSessionLocal
from app.models.candidate import IdempotencyKey

logger = structlog.get_logger()

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        async with AsyncSessionLocal() as db:
            existing = await db.get(IdempotencyKey, key)
            if existing:
                logger.info("Idempotency hit", key=key)
                return JSONResponse(
                    content=existing.response_body, 
                    status_code=existing.status_code
                )

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            async def new_iterator():
                yield response_body
            
            response.body_iterator = new_iterator()

            try:
                json_body = json.loads(response_body) if response_body else None
                async with AsyncSessionLocal() as db:
                    existing = await db.get(IdempotencyKey, key)
                    if not existing:
                        record = IdempotencyKey(
                            key=key, 
                            response_body=json_body, 
                            status_code=response.status_code
                        )
                        db.add(record)
                        await db.commit()
            except Exception as e:
                logger.error("Failed to save idempotency key", error=str(e))

        return response