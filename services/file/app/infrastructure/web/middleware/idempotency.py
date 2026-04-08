from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.infrastructure.db.models.file import IdempotencyKey
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        session_factory: async_sessionmaker,
        header_name: str = "Idempotency-Key",
    ) -> None:
        super().__init__(app)
        self._session_factory = session_factory
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method.upper() not in {"POST", "PATCH", "PUT", "DELETE"}:
            return await call_next(request)

        key = request.headers.get(self._header_name)
        if key is None or not key.strip():
            return await call_next(request)
        key = key.strip()

        raw_body = await request.body()
        request_hash = self._build_request_hash(
            method=request.method.upper(),
            path=request.url.path,
            query=request.url.query.encode("utf-8"),
            body=raw_body,
        )

        existing = await self._get_existing_key(key)
        if existing is not None:
            if existing.request_hash != request_hash:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "Idempotency key reuse with different payload"},
                    headers={self._header_name: key},
                )

            return self._build_stored_response(existing=existing, key=key)

        async def receive() -> dict[str, Any]:
            return {
                "type": "http.request",
                "body": raw_body,
                "more_body": False,
            }

        replayable_request = Request(request.scope, receive)
        response = await call_next(replayable_request)
        response.headers[self._header_name] = key

        if not self._should_store_response(response):
            return response

        raw_response_body = await self._read_response_body(response)
        stored_response_body = self._parse_response_body(raw_response_body)

        await self._store_response(
            key=key,
            request_hash=request_hash,
            response_body=stored_response_body,
            status_code=response.status_code,
        )

        if response.status_code == 204:
            return Response(
                status_code=204,
                headers=dict(response.headers),
            )

        return JSONResponse(
            status_code=response.status_code,
            content=stored_response_body,
            headers=dict(response.headers),
        )

    async def _get_existing_key(self, key: str) -> IdempotencyKey | None:
        async with self._session_factory() as session:
            stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _store_response(
        self,
        *,
        key: str,
        request_hash: str,
        response_body: dict[str, Any] | list[Any] | None,
        status_code: int,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                IdempotencyKey(
                    key=key,
                    request_hash=request_hash,
                    response_body=response_body,
                    status_code=status_code,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.info(
                    "idempotency key was inserted concurrently",
                    extra={"idempotency_key": key},
                )

    def _build_stored_response(
        self,
        *,
        existing: IdempotencyKey,
        key: str,
    ) -> Response:
        if existing.status_code == 204:
            return Response(
                status_code=204,
                headers={self._header_name: key},
            )

        return JSONResponse(
            status_code=existing.status_code,
            content=existing.response_body,
            headers={self._header_name: key},
        )

    @staticmethod
    async def _read_response_body(response: Response) -> bytes:
        if hasattr(response, "body") and response.body is not None:
            return response.body

        body_chunks = [chunk async for chunk in response.body_iterator]
        return b"".join(body_chunks)

    @staticmethod
    def _parse_response_body(raw_response_body: bytes) -> dict[str, Any] | list[Any] | None:
        if not raw_response_body:
            return None

        try:
            return json.loads(raw_response_body.decode("utf-8"))
        except Exception:
            return {
                "detail": raw_response_body.decode("utf-8", errors="replace"),
            }

    @staticmethod
    def _should_store_response(response: Response) -> bool:
        if response.status_code >= 500:
            return False

        if response.status_code == 204:
            return True

        content_type = response.headers.get("content-type", "")
        return "application/json" in content_type.lower()

    @staticmethod
    def _build_request_hash(
        *,
        method: str,
        path: str,
        query: bytes,
        body: bytes,
    ) -> str:
        payload = method.encode("utf-8") + b"|" + path.encode("utf-8") + b"|" + query + b"|" + body
        return hashlib.sha256(payload).hexdigest()
