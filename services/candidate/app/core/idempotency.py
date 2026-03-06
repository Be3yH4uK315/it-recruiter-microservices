import json

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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
                logger.info("idempotency_hit", key=key)
                return JSONResponse(
                    content=existing.response_body, status_code=existing.status_code
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
                            status_code=response.status_code,
                        )
                        db.add(record)
                        try:
                            await db.commit()
                            logger.info("idempotency_key_saved", key=key)
                        except Exception as e:
                            await db.rollback()
                            logger.error(
                                "idempotency_save_failed",
                                key=key,
                                error=str(e),
                                exc_info=True,
                            )
                    else:
                        logger.info("idempotency_key_already_exists", key=key)
            except json.JSONDecodeError:
                logger.warning(
                    "idempotency_json_decode_error",
                    key=key,
                    response_length=len(response_body),
                )
            except Exception as e:
                logger.error(
                    "idempotency_unexpected_error",
                    key=key,
                    error=str(e),
                    exc_info=True,
                )

        return response
